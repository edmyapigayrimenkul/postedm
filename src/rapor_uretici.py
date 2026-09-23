"""
src/rapor_uretici.py — Detaylı Sistem, GitHub Actions ve Yapay Zeka Kota Raporu

Kullanıcının Telegram'dan /kota veya butonla talep ettiği durumlarda:
  1. KATEGORİ 1: Bulut, Yapay Zeka & API Altyapısı (GitHub Actions, Gemini AI, Cloudflare, GitHub API)
  2. KATEGORİ 2: Sosyal Medya, Yayın & Depolama (Instagram 24s sınırı, YouTube 10k birim, Jetonlar, DB)
  3. KATEGORİ 3: Kapsamlı Özet Tablo
bilgilerini ve her kotanın tam sıfırlanma anını 35 karakter genişliğinde monospaced kartla sunar.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from . import config, db, konu_bankasi

log = logging.getLogger(__name__)

KOK = Path(__file__).resolve().parent.parent


def cizgi_bar(yuzde: float, uzunluk: int = 10) -> str:
    """Yüzdeye göre [■■□□□□□□□□] ilerleme çubuğu üretir."""
    oran = max(0.0, min(100.0, float(yuzde)))
    dolu = min(uzunluk, max(0, int(round((oran / 100.0) * uzunluk))))
    return "■" * dolu + "□" * (uzunluk - dolu)


def format_kompakt_kutu(
    baslik: str,
    tarih_str: str,
    bolumler: List[Tuple[str, List[Tuple[str, str]]]],
    w_k: int = 15,
    w_v: int = 14,
) -> str:
    """Telegram monospace bloğu (<pre>) için tek parça, kenarlıklı, kompakt kart üretir."""
    w_inner = w_k + 2 + w_v  # 15 + 2 + 14 = 31 (toplam genişlik: 35 karakter)
    cizgi_ust = "┌" + "─" * (w_inner + 2) + "┐"
    cizgi_orta = "├" + "─" * (w_inner + 2) + "┤"
    cizgi_alt = "└" + "─" * (w_inner + 2) + "┘"

    satirlar = [
        "<pre>",
        cizgi_ust,
        f"│ {baslik[:w_inner]:<{w_inner}} │",
        f"│ {tarih_str[:w_inner]:<{w_inner}} │",
    ]

    for bolum_baslik, veriler in bolumler:
        satirlar.append(cizgi_orta)
        satirlar.append(f"│ {bolum_baslik[:w_inner]:<{w_inner}} │")
        satirlar.append(cizgi_orta)
        for k, v in veriler:
            k_kirp = str(k)[:w_k]
            v_kirp = str(v)[:w_v]
            satirlar.append(f"│ {k_kirp:<{w_k}}: {v_kirp:>{w_v}} │")

    satirlar.append(cizgi_alt)
    satirlar.append("</pre>")
    return "\n".join(satirlar)


# -----------------------------------------------------------------------------
# Sıfırlanma ve Bitiş Süresi Hesaplayıcıları
# -----------------------------------------------------------------------------

def sifirlanma_ay_basi() -> str:
    """Gelecek ayın 1'ine kalan gün sayısını döner (Örn: '01.10 (13 gun)')."""
    now = datetime.now(timezone.utc)
    if now.month == 12:
        next_month = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_month = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)
    kalan_gun = max(1, (next_month - now).days)
    return f"{next_month.strftime('%d.%m')} ({kalan_gun} gun)"


def sifirlanma_gece_yarisi() -> str:
    """Gece yarısı 00:00 UTC'ye kalan saati döner (Örn: '00:00 (4 saat)')."""
    now = datetime.now(timezone.utc)
    yarin = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=1)
    fark = yarin - now
    kalan_saat = max(1, int(fark.total_seconds() // 3600))
    return f"00:00 ({kalan_saat} saat)"


def sifirlanma_youtube() -> str:
    """YouTube kotalarının sıfırlandığı Pasifik Gece Yarısına (10:00 TSI) kalan süreyi döner."""
    now = datetime.now(timezone.utc)
    # Midnight PT = 07:00 UTC (10:00 TSI)
    hedef_bugun = datetime(now.year, now.month, now.day, 7, 0, tzinfo=timezone.utc)
    hedef = hedef_bugun if now < hedef_bugun else hedef_bugun + timedelta(days=1)
    kalan_saat = max(1, int((hedef - now).total_seconds() // 3600))
    return f"10:00 TSI ({kalan_saat}s)"


def sifirlanma_saatlik() -> str:
    """Saatlik kota sıfırlanmasına kalan dakikayı döner (Örn: 'Saatlik (38d)')."""
    now = datetime.now(timezone.utc)
    kalan_dk = max(1, 60 - now.minute)
    return f"Saatlik ({kalan_dk}d)"


# -----------------------------------------------------------------------------
# Veri Toplayıcı Fonksiyonlar
# -----------------------------------------------------------------------------

def _github_token_al(token: Optional[str] = None) -> Optional[str]:
    """Sistem ortamından veya gh CLI üzerinden geçerli GitHub PAT tokenını alır."""
    sec_token = token or config.env_al("GITHUB_TOKEN") or config.env_al("GH_TOKEN") or config.env_al("GITHUB_PAT")
    # Test modunda makinedeki gh oturumuna uzanılmaz: testler canlı API'ye gitmesin.
    if not sec_token and not config.test_modu():
        try:
            p = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=3)
            if p.returncode == 0 and p.stdout.strip():
                sec_token = p.stdout.strip()
        except Exception:
            pass
    return sec_token


def github_actions_kullanimi(
    token: Optional[str] = None,
    repo: str = "edmyapigayrimenkul/postedm"
) -> Dict[str, Any]:
    """Bu ayın TÜM Actions çalıştırmalarından tahmini faturalanan dakika.

    Önceki sürüm yalnızca ilk 100 çalıştırmayı sayıyordu (ayda ~500 var) ve
    API hatasında "125 dk harcandı / 1.875 kaldı" gibi UYDURMA sayılar dönüyordu;
    iş akışının actions:read izni olmadığı için pratikte hep uydurma sayı
    görünüyordu. Ölçülemeyen değer None döner, rapor "alınamadı" yazar.
    """
    now = datetime.now(timezone.utc)
    bu_ay_basi = datetime(now.year, now.month, 1, tzinfo=timezone.utc).strftime("%Y-%m-%d")
    sec_token = _github_token_al(token)
    kota_toplam = 2000

    def olculemedi(neden: str) -> Dict[str, Any]:
        return {"toplam_kosu": None, "harcanan_dk": None, "kalan_dk": None, "yuzde": None,
                "is_akislari": {}, "kaynak": neden}

    if not sec_token:
        return olculemedi("jeton yok")

    headers = {
        "Authorization": f"Bearer {sec_token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "postedm-reporter",
    }
    kosular: List[Dict[str, Any]] = []
    try:
        for sayfa in range(1, 21):
            r = requests.get(
                f"https://api.github.com/repos/{repo}/actions/runs",
                params={"created": f">={bu_ay_basi}", "per_page": 100, "page": sayfa},
                headers=headers, timeout=12,
            )
            if r.status_code != 200:
                log.warning("GitHub Actions kullanımı okunamadı [%d]: %s", r.status_code, r.text[:120])
                return olculemedi(f"HTTP {r.status_code}")
            parti = r.json().get("workflow_runs", [])
            kosular.extend(parti)
            if len(parti) < 100:
                break
    except Exception as e:
        log.warning("GitHub Actions kullanım verisi alınamadı: %s", e)
        return olculemedi(type(e).__name__)

    by_wf: Dict[str, int] = {}
    for run in kosular:
        st = run.get("run_started_at") or run.get("created_at")
        up = run.get("updated_at")
        if not (st and up and run.get("status") == "completed"):
            continue
        try:
            sure = (datetime.fromisoformat(up.replace("Z", "+00:00")) - datetime.fromisoformat(st.replace("Z", "+00:00"))).total_seconds()
        except ValueError:
            continue
        # Faturalama iş başına dakikaya yuvarlar; iş akışları tek işli → yaklaşık.
        ad = run.get("name", "Diğer")
        by_wf[ad] = by_wf.get(ad, 0) + max(1, int((max(0.0, sure) + 59) // 60))

    harcanan = sum(by_wf.values())
    return {
        "toplam_kosu": len(kosular),
        "harcanan_dk": harcanan,
        "kalan_dk": max(0, kota_toplam - harcanan),
        "yuzde": harcanan / kota_toplam * 100.0,
        "is_akislari": by_wf,
        "kaynak": "canli_api",
    }


def yapay_zeka_kullanimi() -> Dict[str, Any]:
    """Gemini API üzerinden bu ayki içerik üretimi ve token tüketimini analiz eder."""
    now = datetime.now(timezone.utc)
    bu_ay_basi = datetime(now.year, now.month, 1, tzinfo=timezone.utc).isoformat()
    bugun_basi = datetime(now.year, now.month, now.day, tzinfo=timezone.utc).isoformat()

    try:
        with db._baglanti_al() as conn:
            bu_ay_haber = conn.execute(
                "SELECT COUNT(*) FROM haberler WHERE eklenme_tarihi >= ?",
                (bu_ay_basi,)
            ).fetchone()[0]

            bugun_haber = conn.execute(
                "SELECT COUNT(*) FROM haberler WHERE eklenme_tarihi >= ?",
                (bugun_basi,)
            ).fetchone()[0]

            rows = conn.execute(
                "SELECT detay_metni FROM haberler WHERE eklenme_tarihi >= ? AND detay_metni IS NOT NULL",
                (bu_ay_basi,)
            ).fetchall()

            toplam_karakter = sum(len(r[0]) for r in rows if r[0])
            tahmini_token = (len(rows) * 2500) + int(toplam_karakter / 3.5)
    except Exception as e:
        log.warning("AI kullanım verisi db'den okunamadı: %s", e)
        bu_ay_haber = 0
        bugun_haber = 0
        tahmini_token = 0

    ai_gunluk_cagri = max(2, bugun_haber * 2) if bugun_haber > 0 else 2
    ai_yuzde = (ai_gunluk_cagri / 1500.0) * 100.0
    kalan_cagri = max(0, 1500 - ai_gunluk_cagri)

    return {
        "bu_ay_haber": bu_ay_haber,
        "bugun_haber": bugun_haber,
        "tahmini_token": tahmini_token,
        "gunluk_cagri": ai_gunluk_cagri,
        "kalan_cagri": kalan_cagri,
        "gunluk_yuzde": ai_yuzde,
        "model_katmani": "3.x Flash",
    }


def cloudflare_kullanimi() -> Dict[str, Any]:
    """Cloudflare kullanımı bu raporda ÖLÇÜLMÜYOR.

    Önceki sürüm sabit "1.240 / 100.000 istek", "120 MB / 10 GB" basıyordu —
    hiçbir ölçüme dayanmayan sayılar. Ölçmek için Actions'a Cloudflare API
    jetonu (Account Analytics okuma) verilmesi gerekir.
    """
    return {
        "worker_istek": "ölçülmüyor",
        "kv_yazma": "kullanılmıyor",
        "r2_depolama": "ölçülmüyor",
        "sifirlanma": sifirlanma_gece_yarisi(),
    }


def github_rest_api_kullanimi() -> Dict[str, Any]:
    """GitHub REST API saatlik 5.000 istek limitini ve sıfırlanma süresini döner."""
    sec_token = _github_token_al()
    if sec_token:
        try:
            r = requests.get(
                "https://api.github.com/rate_limit",
                headers={"Authorization": f"Bearer {sec_token}", "User-Agent": "postedm-reporter"},
                timeout=4,
            )
            if r.status_code == 200:
                core = r.json().get("resources", {}).get("core", {})
                kalan = core.get("remaining", 0)
                limit = core.get("limit", 0)
                reset_ts = core.get("reset", 0)
                if reset_ts:
                    kalan_dk = max(1, int((datetime.fromtimestamp(reset_ts, timezone.utc) - datetime.now(timezone.utc)).total_seconds() // 60))
                    sifirlanma = f"Saatlik ({kalan_dk}d)"
                else:
                    sifirlanma = sifirlanma_saatlik()
                return {"istek": f"{kalan:,} / {limit:,}", "sifirlanma": sifirlanma}
        except Exception:
            pass
    return {
        "istek": "alınamadı",
        "sifirlanma": sifirlanma_saatlik(),
    }


def sosyal_medya_ve_yayin_kotalari() -> Dict[str, Any]:
    """Instagram 24s kayan sınırı, YouTube 10.000 birim sınırı ve depolama metrikleri."""
    now = datetime.now(timezone.utc)
    son_24s = (now - timedelta(hours=24)).isoformat()
    bugun_basi = datetime(now.year, now.month, now.day, tzinfo=timezone.utc).isoformat()

    # Önceki sürüm IG'yi eklenme tarihinden sayıyordu ve YouTube sorgusu var olmayan
    # youtube_shorts_url sütununa bakıp HER ZAMAN hataya düşüp 0 dönüyordu.
    try:
        with db._baglanti_al() as conn:
            ig_24s = conn.execute(
                "SELECT COUNT(*) FROM haberler WHERE yayin_zamani >= ? AND instagram_post_id IS NOT NULL",
                (son_24s,)
            ).fetchone()[0]

            yt_bugun = conn.execute(
                "SELECT COUNT(*) FROM haberler WHERE yayin_zamani >= ? AND youtube_video_id IS NOT NULL",
                (bugun_basi,)
            ).fetchone()[0]
    except Exception as e:
        log.warning("Yayın sayaçları okunamadı: %s", e)
        ig_24s = 0
        yt_bugun = 0

    ig_kalan = max(0, 25 - ig_24s)
    yt_birim = yt_bugun * 1600
    yt_kalan_shorts = max(0, int((10000 - yt_birim) // 1600))

    # Depolama / Boyut — önceki sürümde git boyutu sabit "84.2 MB", ölçülemeyen
    # değerler için de uydurma varsayılanlar (3.5 MB, 5.0 GB) vardı.
    db_yolu = KOK / "data" / "edm.db"
    db_mb = f"{db_yolu.stat().st_size / (1024 * 1024):.1f} MB" if db_yolu.exists() else "yok"
    git_mb = "ölçülemedi"
    try:
        s = subprocess.run(["git", "count-objects", "-v"], cwd=KOK, capture_output=True, text=True, timeout=10)
        alan = dict(satir.split(": ", 1) for satir in s.stdout.splitlines() if ": " in satir)
        kb = int(alan.get("size", 0)) + int(alan.get("size-pack", 0))
        git_mb = f"{kb / 1024:.1f} MB"
    except Exception as e:
        log.warning("Git boyutu ölçülemedi: %s", e)
    try:
        _, _, free = shutil.disk_usage(KOK)
        disk_gb = f"{free / (1024 ** 3):.1f} GB"
    except Exception:
        disk_gb = "ölçülemedi"

    return {
        "ig_kullanilan": ig_24s,
        "ig_kalan": ig_kalan,
        "yt_birim": yt_birim,
        "yt_kalan_shorts": yt_kalan_shorts,
        "yt_sifirlanma": sifirlanma_youtube(),
        "db_mb": db_mb,
        "git_mb": git_mb,
        "disk_gb": disk_gb,
    }


def jeton_durumlari() -> List[Tuple[str, str]]:
    """Jetonları GERÇEKTEN dener. Önceki sürüm sabit "Meta Graph Aktif (54 gün)",
    "TikTok Aktif ✓" basıyordu — insights izni yokken ve ölçüm körken bile."""
    satirlar: List[Tuple[str, str]] = []

    def dene(url: str, params: Dict[str, Any]) -> str:
        try:
            r = requests.get(url, params=params, timeout=8)
            if r.ok:
                return "geçerli ✓"
            kod = (r.json().get("error") or {}).get("code", r.status_code)
            return f"HATA ({kod}) ✗"
        except Exception as e:
            return f"denenemedi ({type(e).__name__})"

    try:
        from . import instagram
        hid, tok = instagram._hesap_bilgileri()
        satirlar.append(("Instagram", dene(f"{instagram.GRAPH_TABAN}/{hid}", {"fields": "username", "access_token": tok}) if tok else "tanımsız ✗"))
        # En kritik izin: olmadan erişim/kayıt/paylaşım ölçülemez
        with db._baglanti_al() as conn:
            son = conn.execute("SELECT instagram_post_id FROM haberler WHERE instagram_post_id IS NOT NULL "
                               "ORDER BY yayin_zamani DESC LIMIT 1").fetchone()
        if tok and son:
            m = instagram.medya_metrikleri_al(son[0]) or {}
            hata = m.get("insights_hata")
            satirlar.append(("IG Insights", "İZİN YOK ✗" if hata == "izin_yok" else (f"HATA ({hata}) ✗" if hata else "ölçülüyor ✓")))
    except Exception as e:
        satirlar.append(("Instagram", f"denenemedi ({type(e).__name__})"))

    try:
        from . import threads
        uid, ttok = threads._hesap_bilgileri()
        satirlar.append(("Threads", dene(f"{threads.THREADS_TABAN}/me", {"fields": "id", "access_token": ttok}) if ttok else "tanımsız ✗"))
    except Exception as e:
        satirlar.append(("Threads", f"denenemedi ({type(e).__name__})"))

    # TikTok erişim jetonu 24 saatlik ve her yayında yenileniyor; burada yalnızca
    # yenileme kimliklerinin tanımlı olduğuna bakılır.
    tt = all(config.env_al(k) for k in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN"))
    satirlar.append(("TikTok", "kimlik var" if tt else "tanımsız ✗"))
    r2 = all(config.env_al(k) for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"))
    satirlar.append(("Cloudflare R2", "tanımlı" if r2 else "tanımsız"))
    return satirlar


def icerik_ve_rezerv_durumu() -> Dict[str, Any]:
    """Yayın havuzu ve konu bankası rezerv durumunu derler."""
    now = datetime.now(timezone.utc)
    bu_ay_basi = datetime(now.year, now.month, 1, tzinfo=timezone.utc).isoformat()

    try:
        with db._baglanti_al() as conn:
            yayinlanan_ay = conn.execute(
                "SELECT COUNT(*) FROM haberler WHERE eklenme_tarihi >= ? AND durum IN ('yayinlandi', 'yayinda')",
                (bu_ay_basi,)
            ).fetchone()[0]
            bekleyen = conn.execute(
                "SELECT COUNT(*) FROM haberler WHERE durum = 'onay_bekliyor'"
            ).fetchone()[0]
            havuz = conn.execute(
                "SELECT COUNT(*) FROM haberler WHERE durum = 'yeni'"
            ).fetchone()[0]
    except Exception as e:
        log.warning("İçerik havuzu okunamadı: %s", e)
        yayinlanan_ay = 0
        bekleyen = 0
        havuz = 0

    ozet = konu_bankasi.durum_ozeti()
    return {
        "yayinlanan_ay": yayinlanan_ay,
        "bekleyen": bekleyen,
        "havuz": havuz,
        "bakir": ozet.get("bakir", 0),
        "kalan_hafta": ozet.get("kalan_hafta", 0.0),
    }


# -----------------------------------------------------------------------------
# Rapor Kartı Üreticileri (Kategori 1 & Kategori 2)
# -----------------------------------------------------------------------------

def kota_metni_uret(kategori: int | str = 1) -> str:
    """Kullanıcıya gönderilecek kompakt, sıfırlanma süreli kota kartını üretir."""
    now = datetime.now(timezone.utc)
    tarih_str = now.strftime("%d.%m.%Y %H:%M UTC")
    kat_int = 2 if str(kategori) in ("2", "sosyal", "yayin") else (3 if str(kategori) in ("3", "tumu") else 1)

    # =========================================================================
    # KATEGORİ 1: BULUT, YAPAY ZEKA & API ALTYAPISI
    # =========================================================================
    if kat_int == 1:
        gh = github_actions_kullanimi()
        if gh["harcanan_dk"] is None:
            gh_satirlar: List[Tuple[str, str]] = [
                ("Durum", f"alınamadı ({gh['kaynak']})"),
                ("Sifirlanma", sifirlanma_ay_basi()),
            ]
        else:
            gh_satirlar = [
                ("Harcanan ~", f"{gh['harcanan_dk']:,} dk (%{gh['yuzde']:.1f})"),
                ("Kalan", f"{gh['kalan_dk']:,} dk"),
                ("Calistirma", f"{gh['toplam_kosu']}"),
                ("Sifirlanma", sifirlanma_ay_basi()),
                ("Ilerleme", f"[{cizgi_bar(gh['yuzde'])}]"),
            ]
        if gh.get("is_akislari"):
            sirali_wf = sorted(gh["is_akislari"].items(), key=lambda x: x[1], reverse=True)[:3]
            for adi, dk in sirali_wf:
                temiz_ad = adi.replace(" (EDM)", "").replace("Site İlan Paylaşım Kuyruğu", "Site Ilan")[:12]
                gh_satirlar.append((f"• {temiz_ad}", f"{dk} dk"))

        # Gemini çağrı sayısı ve kota ölçülmüyor; önceki sürüm "bugünkü içerik × 2"
        # ile uydurulmuş bir çağrı sayısını 1.500'lük varsayılan kotayla oranlıyordu.
        ai = yapay_zeka_kullanimi()
        ai_satirlar: List[Tuple[str, str]] = [
            ("Bugun Uretim", f"{ai['bugun_haber']} icerik"),
            ("Bu Ay Uretim", f"{ai['bu_ay_haber']} icerik"),
            ("Token (tahmini)", f"~{ai['tahmini_token']:,}"),
            ("Cagri / Kota", "ölçülmüyor"),
            ("Model Katmani", "3.x Flash"),
        ]

        cf = cloudflare_kullanimi()
        cf_satirlar: List[Tuple[str, str]] = [
            ("Worker Cagri", cf["worker_istek"]),
            ("KV Yazma", cf["kv_yazma"]),
            ("R2 Depolama", cf["r2_depolama"]),
            ("Sifirlanma", cf["sifirlanma"]),
        ]

        gh_api = github_rest_api_kullanimi()
        api_satirlar: List[Tuple[str, str]] = [
            ("Kalan Istek", gh_api["istek"]),
            ("Sifirlanma", gh_api["sifirlanma"]),
        ]

        bolumler = [
            ("GH ACTIONS (varsayım 2.000 dk)", gh_satirlar),
            ("YAPAY ZEKA (Gemini AI)", ai_satirlar),
            ("CLOUDFLARE (Worker & KV)", cf_satirlar),
            ("GITHUB REST API", api_satirlar),
        ]

        kutu_metni = format_kompakt_kutu(
            baslik="BULUT & API KOTA RAPORU",
            tarih_str=tarih_str,
            bolumler=bolumler,
        )

        return (
            "📊 <b>EDM BULUT, AI & API KOTALARI</b>\n\n"
            f"{kutu_metni}\n\n"
            "💡 <i>Aylık kotalar ayın 1'inde, günlük API çağrıları her gece 00:00 UTC'de sıfırlanır.</i>"
        )

    # =========================================================================
    # KATEGORİ 2: SOSYAL MEDYA, YAYIN & DEPOLAMA
    # =========================================================================
    sm_k = sosyal_medya_ve_yayin_kotalari()

    ig_satirlar: List[Tuple[str, str]] = [
        ("24s Yayin Hakki", f"{sm_k['ig_kullanilan']} / 25 post"),
        ("Kalan Yayin", f"{sm_k['ig_kalan']} post"),
        ("Sifirlanma", "Kayan 24 Saat"),
    ]

    yt_satirlar: List[Tuple[str, str]] = [
        ("Harcanan Birim", f"{sm_k['yt_birim']} / 10.000"),
        ("Kalan Shorts", f"{sm_k['yt_kalan_shorts']} video"),
        ("Sifirlanma", sm_k["yt_sifirlanma"]),
    ]

    token_satirlar: List[Tuple[str, str]] = jeton_durumlari()

    depo_satirlar: List[Tuple[str, str]] = [
        ("DB Boyutu", sm_k["db_mb"]),
        ("Git Repo", sm_k["git_mb"]),
        ("Disk Bos Alan", sm_k["disk_gb"]),
    ]

    ic = icerik_ve_rezerv_durumu()
    ic_satirlar: List[Tuple[str, str]] = [
        ("Bu Ay Yayin", f"{ic['yayinlanan_ay']} post"),
        ("Onay Bekleyen", f"{ic['bekleyen']} post"),
        ("Havuz & Bakir", f"{ic['bakir']} konu"),
        ("Rezerv Omru", f"~{ic['kalan_hafta']} hafta" if ic.get("kalan_hafta") else "ölçülemedi"),
    ]

    bolumler = [
        ("INSTAGRAM GRAPH API", ig_satirlar),
        ("YOUTUBE DATA API", yt_satirlar),
        ("TOKEN & SERVIS GUVENCESI", token_satirlar),
        ("DEPOLAMA & VERITABANI", depo_satirlar),
        ("YAYIN HAVUZU & REZERV", ic_satirlar),
    ]

    kutu_metni = format_kompakt_kutu(
        baslik="SOSYAL MEDYA & YAYIN KOTASI",
        tarih_str=tarih_str,
        bolumler=bolumler,
    )

    return (
        "📱 <b>EDM SOSYAL MEDYA & YAYIN KOTALARI</b>\n\n"
        f"{kutu_metni}\n\n"
        "✨ <i>Instagram 24 saatlik pencerede, YouTube ise her gün 10:00 TSİ'de yenilenir.</i>"
    )


def kota_secenek_menusu() -> Tuple[str, Dict[str, Any]]:
    """Kullanıcı sadece /kota yazdığında sunulacak 2 seçenekli interaktif menü."""
    metin = (
        "📊 <b>EDM SİSTEM & KOTA İZLEME MERKEZİ</b>\n\n"
        "Lütfen incelemek istediğiniz kota kategorisini seçin:\n\n"
        "☁️ <b>1. Bulut, Yapay Zeka & API Kotaları</b>\n"
        "<i>GitHub Actions dakikaları, Gemini AI token/istekleri, Cloudflare Worker/KV/R2 ve GitHub REST API sınırları.</i>\n\n"
        "📱 <b>2. Sosyal Medya, Yayın & Depolama Kotaları</b>\n"
        "<i>Instagram 24 saatlik 25 post sınırı, YouTube 10.000 birim kotası, token geçerlilik günleri, DB ve havuz durumu.</i>"
    )
    butonlar = {
        "inline_keyboard": [
            [
                {"text": "☁️ 1. Bulut, AI & API Altyapısı", "callback_data": "kota_kat:1"},
            ],
            [
                {"text": "📱 2. Sosyal Medya & Yayın Kotaları", "callback_data": "kota_kat:2"},
            ],
            [
                {"text": "🎛 Kontrol Paneli", "callback_data": "panel"},
            ]
        ]
    }
    return metin, butonlar


def kota_gonder(
    mesaj_id: Optional[int] = None,
    kategori: int | str = "menu"
) -> Optional[Dict[str, Any]]:
    """Kullanıcının tercihine göre 2 seçenekli menüyü veya ilgili kategori kartını gönderir/günceller."""
    from . import telegram_bot

    kat_str = str(kategori).lower().strip()

    if kat_str in ("menu", "secim", "0"):
        metin, butonlar = kota_secenek_menusu()
        if mesaj_id:
            return telegram_bot.mesaji_guncelle(mesaj_id, metin, reply_markup=butonlar)
        return telegram_bot.mesaj_gonder(metin, reply_markup=butonlar)

    # Belirli bir kategori istendi (1 veya 2)
    kat_no = 2 if kat_str in ("2", "sosyal", "yayin") else 1
    metin = kota_metni_uret(kategori=kat_no)

    diger_kat = 2 if kat_no == 1 else 1
    diger_ad = "📱 2. Sosyal Medya" if kat_no == 1 else "☁️ 1. Bulut & API"

    butonlar = {
        "inline_keyboard": [
            [
                {"text": f"🔄 Kotayı Yenile ({kat_no})", "callback_data": f"kota_kat:{kat_no}"},
                {"text": diger_ad, "callback_data": f"kota_kat:{diger_kat}"},
            ],
            [
                {"text": "📋 Kota Menüsü", "callback_data": "kota_menu"},
                {"text": "🎛 Kontrol Paneli", "callback_data": "panel"},
            ]
        ]
    }

    if mesaj_id:
        return telegram_bot.mesaji_guncelle(mesaj_id, metin, reply_markup=butonlar)
    return telegram_bot.mesaj_gonder(metin, reply_markup=butonlar)


# Fonksiyon adı "rapor" yerine "kota" olsun kuralı ve geriye dönük takma adlar (aliases)
kota = kota_gonder
kota_metni = kota_metni_uret
detayli_rapor_gonder = kota_gonder
detayli_rapor_metni_uret = kota_metni_uret
