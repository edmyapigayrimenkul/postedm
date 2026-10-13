"""
src/telegram/akislar/finans.py — Finans bülteni: konu bankasından (F serisi) içerik üretir, kapıdan geçerse otomatik yayınlar.

Katman 4 (akış). Otomatik yayın insan onayını atladığı için en ufak denetim uyarısında durur; kapı kapalı başarısız olur.
"""

from __future__ import annotations

import html
import json
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from ... import db, generate_text, konu_bankasi, upload_image
from .. import album, istemci
from . import kapi, onay

log = logging.getLogger(__name__)

KOK = Path(__file__).resolve().parents[3]


def finans_icerigi_hazirla_ve_yayinla(oto_yayin: bool = True) -> bool:
    """Finans, bankacılık, faiz, konut kredisi veya yakın sektörleri ele alan bülteni hazırlar.
    
    Kullanıcı Kuralı:
      - oto_yayin=True ise Telegram onayına takılmadan doğrudan canlı yayınlanır.
      - YouTube: Her zaman Shorts (Sesli dikey video).
      - YouTube dışındaki tüm kanallar (IG, FB, Threads, Story, TT): Standart gönderi!
    """
    konu = konu_bankasi.sonraki_finans_konusu(format_turu="finans")
    if not konu:
        istemci.mesaj_gonder("⚠️ Konu bankasında uygun finans / bankacılık konusu bulunamadı.")
        return False

    bilgi_baslik = "🚀 <b>GÜNLÜK FİNANS & EMLAK BÜLTENİ (OTOMATİK YAYIN)</b>" if oto_yayin else "⏳ <b>GÜNLÜK FİNANS & EMLAK BÜLTENİ</b>"
    istemci.mesaj_gonder(
        f"{bilgi_baslik}\n\n"
        f"📌 <b>{konu['kod']}</b> · {konu['sutun']} · {konu['bicim']}\n"
        f"<i>{konu['baslik']}</i>\n\n"
        f"İçerik, görseller ve video hazırlanıyor..."
    )

    veri = generate_text.konudan_uret(konu)
    if not veri:
        istemci.mesaj_gonder("❌ Finans içeriği üretilemedi. Gemini API yanıt vermedi.")
        return False

    orijinal_url = f"edm://finans/{konu['kod']}/{int(time.time())}"
    simdi = datetime.now(timezone.utc).isoformat()
    with db._baglanti_al() as conn:
        cur = conn.execute(
            """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, orijinal_ozet,
                                     eklenme_tarihi, onem_puani, kategori, manset, detay_metni,
                                     ig_caption, threads_metin, durum)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'yeni')""",
            (
                f"EDM Finans // {konu['kod']}",
                konu["baslik"],
                orijinal_url,
                veri.get("spot", ""),
                simdi,
                veri.get("onem_puani", 9),
                "FINANS_VE_BANKACILIK",
                generate_text.manset_birlestir(veri) or konu["baslik"],
                json.dumps(veri, ensure_ascii=False),
                veri.get("caption_instagram", ""),
                veri.get("caption_threads", ""),
            ),
        )
        haber_id = cur.lastrowid
        conn.commit()

    konu_bankasi.kullanildi_isaretle(konu["kod"], haber_id=haber_id, format_turu="finans")

    # 1. 4:5 Slaytları Üret (Instagram, Facebook, Threads, TikTok için)
    from ... import make_image, ses, video
    try:
        slayt_yollari = make_image.otorite_gonderi_slaytlari_uret(veri, cikti_onek=f"haber_{haber_id}")
    except make_image.EksikIcerik as e:
        # Otomatik yayın yolu da yarım/taşan görseli yayınlamaz
        log.warning("Finans #%d görseli üretilemedi: %s", haber_id, e)
        kapi._eksik_icerik_bildir(haber_id, e)
        return False
    slayt_str_yollari = [str(p) for p in slayt_yollari]

    # CDN yükleme
    slayt_urlleri = []
    try:
        slayt_urlleri = upload_image.coklu_gorsel_yukle(slayt_yollari)
    except Exception as ue:
        log.warning("Finans slaytları CDN'e yüklenemedi: %s", ue)

    # 2. YouTube Shorts için dikey 9:16 video ve fon müziği hazırla
    v_yolu = None
    try:
        v_yolu = video.slaytlardan_reels_uret(slayt_str_yollari)
        if v_yolu and v_yolu.exists():
            sesli_v = ses.sesli_video_hazirla(v_yolu, ses_seviyesi=0.20)
            if sesli_v and sesli_v.exists():
                v_yolu = sesli_v
    except Exception as ve:
        log.warning("YouTube Shorts dikey videosu üretilemedi: %s", ve)

    db.haber_guncelle(
        haber_id,
        slayt_yollari=json.dumps(slayt_str_yollari, ensure_ascii=False),
        slayt_urlleri=json.dumps(slayt_urlleri) if slayt_urlleri else None,
        video_yolu=str(v_yolu) if v_yolu else None,
    )

    # DOĞRULAMA KAPISI: otomatik yayın insan onayını atlıyor; bu yüzden en ufak
    # denetim uyarısında (doğrulanmamış madde numarası, kaynaksız faiz/oran,
    # abartı) yayın DURUR ve içerik onaya düşer. Finansta "dayanaksız rakam"
    # da kritiktir: faiz ve kredi koşulları okuyanın parasını etkiler.
    # Model yazdığı için kapı iki ayaklıdır (dogrula.otomatik_yayina_uygun_mu): hiç uyarı olmamalı VE anlam
    # hakemi (ikinci model) gerçekten çalışıp temiz demiş olmalı. Hakem kota/kaynak yüzünden çalışamadıysa
    # "temiz" varsayılmaz; içerik onaya düşer.
    from ... import dogrula
    if oto_yayin:
        uygun, uyarilar = dogrula.otomatik_yayina_uygun_mu(veri)
        if not uygun:
            log.warning("Finans #%d otomatik yayını durduruldu: %s", haber_id, "; ".join(uyarilar))
            istemci.mesaj_gonder(
                f"🛑 <b>Otomatik yayın durduruldu (#{haber_id})</b> — {len(uyarilar)} denetim bulgusu.\n"
                + "\n".join(html.escape(u) for u in uyarilar[:3])
                + "\n<i>İçerik onayına sunuluyor; uyarıları kontrol edip elle yayınla.</i>"
            )
            oto_yayin = False

    if not oto_yayin:
        return onay.haber_onayina_sun(haber_id)

    # Önce slayt görsellerini Telegram grubuna ilet
    try:
        album.medya_grubu_gonder(
            slayt_yollari,
            caption=f"📊 <b>GÜNLÜK FİNANS & BANKACILIK POSTU</b>\n📌 {veri.get('manset') or konu['baslik']}"
        )
    except Exception as me:
        log.warning("Finans albümü Telegram'a iletilemedi: %s", me)

    # Otomatik Yayın Akışı (Bana sormadan paylaşılsın)
    # Hedefler: ig,threads,story,tiktok,facebook,youtube
    # reels_modu = False olduğu için YouTube video alır, Facebook dahil diğer tüm kanallar standart post alır.
    komut = [
        sys.executable,
        str(KOK / "scripts/yayinla.py"),
        "--tur", "haber",
        "--id", str(haber_id),
        "--hedef", "ig,threads,story,tiktok,facebook,youtube",
    ]
    log.info("Finans bülteni otomatik yayınlanıyor: %s", komut)
    calisma = subprocess.run(komut, cwd=KOK, capture_output=True, text=True, timeout=15 * 60)
    
    # yayinla.py kendi içinde rapor gönderir ve DB'yi günceller
    if calisma.returncode == 0 or "POSTEDM_SONUC=" in calisma.stdout:
        log.info("Finans bülteni otomatik yayını tamamlandı.")
        return True
    else:
        log.error("Finans bülteni otomatik yayınlanamadı: %s\n%s", calisma.stdout, calisma.stderr)
        istemci.mesaj_gonder(
            f"⚠️ <b>Finans bülteni otomatik yayınlanırken hata oluştu:</b>\n"
            f"<pre>{html.escape(calisma.stderr[-1000:])}</pre>"
        )
        return False
