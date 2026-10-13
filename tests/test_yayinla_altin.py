"""
tests/test_yayinla_altin.py — scripts/yayinla.py "ALTIN ÇIKTI" (golden master) güvencesi (2026-10-13)

NİYE: yayinla.py 1339 satırlık tek bir main() idi ve bölünüyor (src/yayin/). Bölme davranışı DEĞİŞTİRMEMELİ: bu dosya
yayının dış dünyaya yaptığı HER şeyi — kanal API çağrıları (hangi argümanla), Telegram mesaj metinleri ve düğmeleri,
veritabanındaki son durum, stdout sonucu, fırlatılan hata — 40 senaryoda kaydeder ve kaydedilenle karşılaştırır.

Çalışma:
  python -m unittest tests.test_yayinla_altin                       # karşılaştır
  YAYIN_ALTIN_KAYDET=1 python -m unittest tests.test_yayinla_altin  # YENİDEN KAYDET (yalnız bilerek, davranış değiştiğinde)

Belirlenimcilik: ThreadPoolExecutor sıralı bir yürütücüyle değiştirilir (kanallar gönderim sırasıyla çalışır); zaman, geçici dizin
ve Path'ler normalleştirilir; dış modüllerin işlevleri (instagram, threads, ... telegram_bot) yama ile değiştirilir, yani ağ yok.
Yamalar MODÜL NESNELERİNİN öznitelikleri üzerindedir: kod nereye taşınırsa taşınsın (scripts/yayinla.py ya da src/yayin/…)
dış modülleri `modul.islev()` biçiminde çağırdığı sürece aynı kayıt çıkar.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import concurrent.futures
import contextlib
import copy
import difflib
import io
import json
import re
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from PIL import Image

from scripts import yayinla
from src import (db, db_senkron, facebook, generate_text, hata_bildir, instagram, konu_bankasi, linkedin, make_image,
                 ses, telegram_bot, threads, tiktok, twitter, upload_image, video, yeni_formatlar, youtube)

ALTIN_YOLU = KOK / "tests" / "altin" / "yayinla.json"
KAYDET = os.environ.get("YAYIN_ALTIN_KAYDET") == "1"


class SiraliYurutucu:
    """ThreadPoolExecutor yerine: görevler gönderim sırasıyla, aynı iş parçacığında çalışır."""

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def submit(self, fn, *a, **k):
        f = concurrent.futures.Future()
        try:
            f.set_result(fn(*a, **k))
        except BaseException as e:  # noqa: BLE001 — gerçek yürütücü de istisnayı future'a yazar
            f.set_exception(e)
        return f


class Kayitci:
    """Sahte işlevlerin çağrılarını normalleştirip toplar."""

    def __init__(self, tmp: Path):
        self.tmp = str(tmp)
        self.cagrilar: list[str] = []
        self.telegram: list[dict] = []
        self.kilit = threading.Lock()

    def norm(self, v):
        if isinstance(v, Path):
            return "P:" + v.name
        if isinstance(v, str):
            s = v.replace(self.tmp, "<TMP>").replace(str(KOK), "<KOK>")
            return re.sub(r"Dağıtım Süresi:</b> [0-9.]+ sn", "Dağıtım Süresi:</b> <SURE> sn", s)
        if isinstance(v, bytes):
            return f"<bytes {len(v)}>"
        if v is None or isinstance(v, (bool, int, float)):
            return v
        if isinstance(v, dict):
            return {str(k): self.norm(x) for k, x in sorted(v.items(), key=lambda kv: str(kv[0]))}
        if isinstance(v, (set, frozenset)):
            return sorted((self.norm(x) for x in v), key=repr)
        if isinstance(v, (list, tuple)):
            return [self.norm(x) for x in v]
        return f"<{type(v).__name__}>"

    # Saf sorgular: kaç kez sorulduğu davranış değil (sonucun yol açtığı davranış zaten kayıtlı)
    GURULTU = frozenset({"linkedin.kullanilabilir_mi", "twitter.kullanilabilir_mi"})

    def kaydet(self, ad: str, args, kwargs, telegram: bool = False):
        if ad in self.GURULTU:
            return
        girdi = {"islev": ad, "args": self.norm(list(args)), "kwargs": self.norm(dict(kwargs))}
        with self.kilit:
            self.cagrilar.append(json.dumps(girdi, ensure_ascii=False, sort_keys=True))
            if telegram:
                self.telegram.append(girdi)


def _jpeg_bayt(boyut=(1080, 1350)) -> bytes:
    tampon = io.BytesIO()
    Image.new("RGB", boyut, (30, 60, 90)).save(tampon, "JPEG")
    return tampon.getvalue()


def _jpeg(yol: Path, boyut=(1080, 1350)) -> Path:
    yol.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", boyut, (30, 60, 90)).save(yol, "JPEG")
    return yol


class Ortam:
    """Bir senaryonun geçici dünyası: veritabanı, dosyalar, sahte modüller, kayıtçı."""

    VARSAYILAN = {
        "instagram.carousel_yayinla": "IGC1",
        "instagram.tekil_gorsel_yayinla": "IGT1",
        "instagram.story_yayinla": "IGS1",
        "instagram.gorselleri_4_5_yap": lambda ortam, yollar, *a, **k: [f"https://cdn.example.com/k45_{i}.jpg" for i, _ in enumerate(yollar)],
        "facebook.paylas": "FB1",
        "facebook.video_yayinla": "FBV1",
        "facebook.story_yayinla": "FBS1",
        "facebook.post_baglantisi": lambda ortam, i: f"https://facebook.example/{i}",
        "threads.paylas": "TH1",
        "threads.zincir_paylas_sonuc": {"kok_id": "THZ", "yayinlanan": 2, "toplam": 2, "eksik": []},
        "threads.metinleri_slaytlara_dagit": lambda ortam, haber, urller: ["parca1", "parca2"] if len(urller or []) > 1 else ["parca1"],
        "threads.post_baglantisi": lambda ortam, i: f"https://threads.example/{i}",
        "tiktok.foto_yayinla": {"durum": True, "publish_id": "TT1"},
        "tiktok.video_yukle": {"durum": True, "publish_id": "TTV1"},
        "youtube.shorts_yukle": {"durum": True, "video_id": "YT1", "url": "https://youtu.be/YT1"},
        "linkedin.kullanilabilir_mi": False,
        "linkedin.linkedin_metni_hazirla": "LI METNİ",
        "linkedin.paylas": "LI1",
        "twitter.kullanilabilir_mi": False,
        "twitter.tekil_yayinla": "TW1",
        "twitter.zincir_yayinla": ("TWZ", 3),
        "twitter.post_baglantisi": lambda ortam, i: f"https://x.example/{i}",
        "upload_image.gorsel_yukle": lambda ortam, p, *a, **k: f"https://cdn.example.com/{Path(str(p)).name}",
        "upload_image.coklu_gorsel_yukle": lambda ortam, ps, *a, **k: [f"https://cdn.example.com/{Path(str(p)).name}" for p in ps],
        "video.slaytlardan_reels_uret": lambda ortam, slaytlar, haber=None, **k: ortam.dosya("video", "uretilen.mp4"),
        "ses.sesli_video_hazirla": lambda ortam, v, **k: v,
        "ses.anlatimli_video_uret": lambda ortam, slaytlar, veri=None, muzik=True, sonuc=None, **k: (
            sonuc.update({"anlatim": True}) if isinstance(sonuc, dict) else None) or ortam.dosya("video", "anlatimli.mp4"),
        "generate_text.caption_zenginlestir": lambda ortam, c, **k: f"[{k.get('platform')}] {c}",
        "generate_text.haber_metinleri_uret": True,
        "telegram_bot.mesaj_gonder": {"message_id": 9001},
        "telegram_bot.sonucu_yaz": None,
        "telegram_bot.video_gonder": 9002,
        "telegram_bot.icerik_onceki_mesajlarini_temizle": 0,
        "telegram_bot.yayindan_kaldir": None,
        "telegram_bot.slaytlari_gonder": True,
        "telegram_bot.yayin_kapisi": (True, []),
        "telegram_bot.haber_onayina_sun": True,
        "telegram_bot.reels_hazirla_ve_sun": True,
        "telegram_bot.konu_bankasindan_hazirla": True,
        "telegram_bot.ilan_postunu_hazirla_ve_sor": True,
        "db_senkron.uzaktan_tazele": None,
        "hata_bildir.son_ham_hata_kaydet": None,
    }
    MODULLER = {
        "instagram": instagram, "facebook": facebook, "threads": threads, "tiktok": tiktok, "youtube": youtube,
        "linkedin": linkedin, "twitter": twitter, "upload_image": upload_image, "video": video, "ses": ses,
        "generate_text": generate_text, "telegram_bot": telegram_bot, "db_senkron": db_senkron, "hata_bildir": hata_bildir,
    }
    TELEGRAM_KAYITLI = {"mesaj_gonder", "sonucu_yaz", "video_gonder", "yayindan_kaldir", "slaytlari_gonder",
                        "icerik_onceki_mesajlarini_temizle"}

    def __init__(self, donusler: dict | None = None):
        self.tmp = Path(tempfile.mkdtemp(prefix="yayin_altin_"))
        self.kayitci = Kayitci(self.tmp)
        self.donusler = {**self.VARSAYILAN, **(donusler or {})}
        self.ilan_cagri = 0
        self.temizlenecek: list[Path] = []
        self.yamalar: list = []

    # --- dosyalar ----------------------------------------------------------------------------------------------
    def dosya(self, alt: str, ad: str) -> Path:
        yol = self.tmp / alt / ad
        yol.parent.mkdir(parents=True, exist_ok=True)
        if not yol.exists():
            yol.write_bytes(b"sahte-icerik")
        return yol

    def slaytlar(self, adet: int, boyut=(1080, 1350), onek="slayt") -> list[Path]:
        return [_jpeg(self.tmp / "slaytlar" / f"{onek}_{i + 1}.jpg", boyut) for i in range(adet)]

    # --- sahte işlevler ------------------------------------------------------------------------------------------
    def _sahte(self, tam_ad: str):
        modul_ad, islev = tam_ad.split(".", 1)
        modul = self.MODULLER[modul_ad]
        donus = self.donusler[tam_ad]
        telegram = modul_ad == "telegram_bot" and islev in self.TELEGRAM_KAYITLI

        def f(*a, **k):
            self.kayitci.kaydet(tam_ad, a, k, telegram=telegram)
            d = donus
            if isinstance(d, BaseException):
                raise d
            if callable(d):
                return d(self, *a, **k)
            return copy.deepcopy(d)

        return patch.object(modul, islev, side_effect=f)

    def _canli_durum(self):
        def f(*a, **k):
            # Zamanlama bağımlı ara güncellemeler kaydedilmez; yalnız TAMAMLANMIŞ durum (adim == toplam_adim) deterministiktir
            if k.get("adim") == k.get("toplam_adim"):
                self.kayitci.kaydet("telegram_bot.canli_yayin_durumu_guncelle", a, {x: y for x, y in k.items() if x != "baslangic_ts"})
        return patch.object(telegram_bot, "canli_yayin_durumu_guncelle", side_effect=f)

    def _resim_ureticiler(self):
        ortam = self

        def slaytlari_uret(veri, format_turu=None, cikti_onek="x", olcu="besleme", **k):
            ortam.kayitci.kaydet("yeni_formatlar.slaytlari_uret", (veri,), {"format_turu": format_turu, "cikti_onek": cikti_onek, "olcu": olcu})
            if ortam.donusler.get("resim.hata") and olcu == "story":
                raise RuntimeError("çizim hatası")
            boyut = (1080, 1920) if olcu == "story" else (1080, 1350)
            return [_jpeg(ortam.tmp / "cizim" / f"{cikti_onek}_{olcu}_{i}.jpg", boyut) for i in (1, 2, 3, 4)]

        def otorite(veri, cikti_onek="x", olcu="besleme", **k):
            ortam.kayitci.kaydet("make_image.otorite_gonderi_slaytlari_uret", (veri,), {"cikti_onek": cikti_onek, "olcu": olcu})
            if ortam.donusler.get("resim.hata") and olcu == "story":
                raise RuntimeError("çizim hatası")
            boyut = (1080, 1920) if olcu == "story" else (1080, 1350)
            return [_jpeg(ortam.tmp / "cizim" / f"{cikti_onek}_{olcu}_{i}.jpg", boyut) for i in (1, 2, 3, 4)]

        def dailybrief(haber, cikti_yolu=None, sayfa_no="1/1", **k):
            ortam.kayitci.kaydet("make_image.haber_dailybrief_slayti_ciz", (), {"cikti_yolu": cikti_yolu, "sayfa_no": sayfa_no,
                                                                              "foto_kaynak": haber.get("foto_kaynak"), "saf_editoryal": haber.get("saf_editoryal")})
            if ortam.donusler.get("resim.aday_yok"):
                return None
            _jpeg(Path(cikti_yolu))
            return cikti_yolu

        def ilan_slayti(ad):
            def f(ilan, *a, **k):
                ortam.kayitci.kaydet(f"make_image.{ad}", (ilan.get("id"),), {})
                ortam.ilan_cagri += 1
                if ortam.donusler.get("resim.ilan_hata") and ortam.ilan_cagri > 3:  # ilk 3 çağrı yayın slaytları; sonrası video yolu
                    raise RuntimeError("ilan çizim hatası")
                return _jpeg(ortam.tmp / "ilan" / f"{ad}_{ilan.get('id')}.jpg")
            return f

        def kapak(veri, cikti_kapak, *a, **k):
            ortam.kayitci.kaydet("make_image.otorite_slayt_1_kapak", (), {"cikti_kapak": cikti_kapak})
            return _jpeg(Path(cikti_kapak), (1080, 1920))

        return [
            patch.object(yeni_formatlar, "slaytlari_uret", side_effect=slaytlari_uret),
            patch.object(make_image, "otorite_gonderi_slaytlari_uret", side_effect=otorite),
            patch.object(make_image, "haber_dailybrief_slayti_ciz", side_effect=dailybrief),
            patch.object(make_image, "ilan_kapak_slayti_ciz", side_effect=ilan_slayti("ilan_kapak_slayti_ciz")),
            patch.object(make_image, "ilan_detay_slayti_ciz", side_effect=ilan_slayti("ilan_detay_slayti_ciz")),
            patch.object(make_image, "ilan_kapanis_slayti_ciz", side_effect=ilan_slayti("ilan_kapanis_slayti_ciz")),
            patch.object(make_image, "otorite_slayt_1_kapak", side_effect=kapak),
        ]

    def baslat(self):
        db_yolu = self.tmp / "altin.db"
        self.yamalar = [
            patch("src.db.DB_YOLU", db_yolu),
            patch("concurrent.futures.ThreadPoolExecutor", SiraliYurutucu),
            patch("requests.head", return_value=MagicMock(status_code=200)),
            patch("requests.get", return_value=MagicMock(status_code=200, content=_jpeg_bayt())),
            patch.object(sys, "argv", ["yayinla.py"]),
            *[self._sahte(ad) for ad in self.donusler if ad in self.VARSAYILAN or ad.split(".")[0] in self.MODULLER],
            self._canli_durum(),
            *self._resim_ureticiler(),
        ]
        for y in self.yamalar:
            y.start()
        db.tablolari_olustur()
        konu_bankasi.tabloyu_kur()

    def bitir(self):
        for y in reversed(self.yamalar):
            try:
                y.stop()
            except RuntimeError:
                pass
        for yol in (KOK / "data/output").glob("story_[0-9]*.jpg"):
            yol.unlink(missing_ok=True)
        shutil.rmtree(KOK / "data/output/adaylar", ignore_errors=True)
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- veritabanı ---------------------------------------------------------------------------------------------
    def haber_ekle(self, id: int, **kolon):
        varsayilan = {
            "kaynak": "EDM Konu Bankası // S1-001", "orijinal_baslik": f"Orijinal başlık {id}", "orijinal_url": f"edm://altin/{id}",
            "eklenme_tarihi": "2026-10-01T10:00:00+00:00", "onem_puani": 8, "kategori": "TAPU_VE_HUKUK", "manset": f"Manşet {id}",
            "ig_caption": f"Açıklama {id}", "threads_metin": f"Threads metni {id}", "durum": "onay_bekliyor", "detay_metni": None,
        }
        veri = {**varsayilan, **kolon, "id": id}
        sutunlar = ", ".join(veri)
        with db._baglanti_al() as conn:
            conn.execute(f"INSERT INTO haberler ({sutunlar}) VALUES ({', '.join('?' for _ in veri)})", tuple(veri.values()))
            conn.commit()

    def ilan_ekle(self, id: str, **kolon):
        varsayilan = {"baslik": f"Satılık Daire {id}", "fiyat": 5_250_000.0, "ilce": "Silivri", "mahalle": "Merkez", "durum": "onay_bekliyor",
                      "kaynak_url": "https://edmyapigayrimenkul.com/ilan/1", "gorseller_json": "[]"}
        veri = {**varsayilan, **kolon, "id": id}
        with db._baglanti_al() as conn:
            conn.execute(f"INSERT INTO ilanlar ({', '.join(veri)}) VALUES ({', '.join('?' for _ in veri)})", tuple(veri.values()))
            conn.commit()

    def konu_kaydi(self, haber_id: int, sonuc: str = "uretildi"):
        with db._baglanti_al() as conn:
            conn.execute("INSERT INTO konu_gecmisi (konu_kodu, kullanim_tarihi, haber_id, sonuc) VALUES (?, ?, ?, ?)",
                         (f"S1-{haber_id}", "2026-10-01", haber_id, sonuc))
            conn.commit()

    def onay_ekle(self, tur: str, ref: str, mesaj_id: int):
        db.onay_istegi_kaydet(tur, str(ref), mesaj_id, -100123)

    def haber_slaytlariyla(self, id: int, adet: int, url_var: bool = True, **kolon):
        yollar = self.slaytlar(adet, onek=f"h{id}")
        ek = {"slayt_yollari": json.dumps([str(p) for p in yollar])}
        if url_var:
            ek["slayt_urlleri"] = json.dumps([f"https://cdn.example.com/h{id}_{i + 1}.jpg" for i in range(adet)])
        self.haber_ekle(id, **{**ek, **kolon})
        return yollar

    # --- sonuç -----------------------------------------------------------------------------------------------------
    def db_ozeti(self) -> dict:
        n = self.kayitci.norm
        sonuc: dict = {}
        with db._baglanti_al() as conn:
            haberler = []
            for r in conn.execute("SELECT * FROM haberler ORDER BY id"):
                d = dict(r)
                satir = {k: d.get(k) for k in (
                    "id", "durum", "instagram_post_id", "threads_post_id", "facebook_post_id", "youtube_video_id", "tiktok_publish_id",
                    "twitter_tweet_id", "linkedin_post_id", "video_yolu", "slayt_yollari", "slayt_urlleri", "planlanan_yayin",
                    "yayin_zamani", "detay_metni") if k in d}
                if satir.get("yayin_zamani"):
                    satir["yayin_zamani"] = "<ZAMAN>"
                haberler.append(n(satir))
            sonuc["haberler"] = haberler
            sonuc["ilanlar"] = [n({k: dict(r).get(k) for k in ("id", "durum", "paylasim_sayisi")} | {"son_paylasim": bool(dict(r).get("son_paylasim_tarihi"))})
                                for r in conn.execute("SELECT * FROM ilanlar ORDER BY id")]
            sonuc["onay_istekleri"] = [n({k: dict(r).get(k) for k in ("tur", "referans_id", "telegram_mesaj_id", "durum")})
                                       for r in conn.execute("SELECT * FROM onay_istekleri ORDER BY id")]
            sonuc["konu_gecmisi"] = [n({k: dict(r).get(k) for k in ("haber_id", "sonuc")}) for r in conn.execute("SELECT * FROM konu_gecmisi ORDER BY id")]
        return sonuc


# ---------------------------------------------------------------------------------------------------------------------
# SENARYOLAR
# ---------------------------------------------------------------------------------------------------------------------

DETAY_HABER = json.dumps({"format_turu": "dailybrief", "manset": "Detay manşeti", "spot": "Spot"}, ensure_ascii=False)
DETAY_SOZLUK = json.dumps({"format_turu": "sozluk", "terim": "İPOTEK", "tanim_metni": "Tanım"}, ensure_ascii=False)
DETAY_OTORITE = json.dumps({"bicim": "B1", "manset": "Otorite", "slayt_4x5_urlleri": ["https://cdn.example.com/a45_1.jpg", "https://cdn.example.com/a45_2.jpg"]},
                           ensure_ascii=False)

SENARYOLAR: list[dict] = []


def senaryo(ad: str, argv: list[str], kur=None, donusler: dict | None = None, env: dict | None = None):
    SENARYOLAR.append({"ad": ad, "argv": argv, "kur": kur, "donusler": donusler or {}, "env": env or {}})


# --- yayın akışı --------------------------------------------------------------------------------------------------
senaryo("haber_hepsi_cok_slayt", ["--tur", "haber", "--id", "701", "--hedef", "hepsi"],
        lambda o: o.haber_slaytlariyla(701, 3, detay_metni=DETAY_HABER))
senaryo("haber_hepsi_tek_slayt", ["--tur", "haber", "--id", "702", "--hedef", "hepsi"],
        lambda o: o.haber_slaytlariyla(702, 1, detay_metni=DETAY_SOZLUK))
senaryo("haber_hepsi_urlsiz_yukleme_gerekir", ["--tur", "haber", "--id", "703", "--hedef", "ig,threads,fb"],
        lambda o: o.haber_slaytlariyla(703, 3, url_var=False, detay_metni=DETAY_HABER))
senaryo("haber_kanallarin_hepsi_basarisiz", ["--tur", "haber", "--id", "704", "--hedef", "hepsi"],
        lambda o: o.haber_slaytlariyla(704, 3, detay_metni=DETAY_HABER),
        donusler={"instagram.carousel_yayinla": None, "threads.zincir_paylas_sonuc": RuntimeError("threads kotası"),
                  "facebook.paylas": None, "youtube.shorts_yukle": {"durum": False, "hata": "kota doldu"},
                  "tiktok.foto_yayinla": RuntimeError("tiktok yok"), "instagram.story_yayinla": None, "facebook.story_yayinla": RuntimeError("fb story")})
senaryo("haber_kismi_basari", ["--tur", "haber", "--id", "705", "--hedef", "ig,threads,fb,yt"],
        lambda o: o.haber_slaytlariyla(705, 3, detay_metni=DETAY_HABER),
        donusler={"threads.zincir_paylas_sonuc": {"kok_id": "THZ", "yayinlanan": 1, "toplam": 3, "eksik": [2, 3]},
                  "facebook.paylas": RuntimeError("fb 500")})
senaryo("haber_threads_tekil_ve_cok_parca_yok", ["--tur", "haber", "--id", "706", "--hedef", "threads"],
        lambda o: o.haber_slaytlariyla(706, 2, detay_metni=DETAY_HABER),
        donusler={"threads.metinleri_slaytlara_dagit": lambda o, h, u: ["tek parca"]})
senaryo("haber_ig_tek_ve_carousel_tiktok_taslak", ["--tur", "haber", "--id", "707", "--hedef", "ig,tiktok"],
        lambda o: o.haber_slaytlariyla(707, 3, detay_metni=DETAY_HABER),
        donusler={"tiktok.foto_yayinla": {"durum": True, "taslak_mi": True, "publish_id": "TTD"}})
senaryo("haber_story_sadece", ["--tur", "haber", "--id", "708", "--hedef", "story"],
        lambda o: o.haber_slaytlariyla(708, 3, detay_metni=DETAY_HABER))
senaryo("haber_story_otorite_bicimi", ["--tur", "haber", "--id", "709", "--hedef", "story"],
        lambda o: o.haber_slaytlariyla(709, 3, detay_metni=DETAY_OTORITE))
senaryo("haber_story_detaysiz_yedek_yol", ["--tur", "haber", "--id", "710", "--hedef", "story"],
        lambda o: o.haber_slaytlariyla(710, 3))
senaryo("haber_reels_modu_tum_kanallar", ["--tur", "haber", "--id", "711", "--hedef", "reels,tiktok,fb,yt,threads,story"],
        lambda o: o.haber_slaytlariyla(711, 3, detay_metni=DETAY_HABER))
senaryo("reels_turu_hepsi", ["--tur", "reels", "--id", "712", "--hedef", "hepsi"],
        lambda o: o.haber_slaytlariyla(712, 3, kategori="REELS", detay_metni=DETAY_OTORITE))
senaryo("reels_video_uretilemez", ["--tur", "reels", "--id", "713", "--hedef", "reels,yt,tiktok,fb"],
        lambda o: o.haber_slaytlariyla(713, 3, kategori="REELS", detay_metni=DETAY_HABER),
        donusler={"video.slaytlardan_reels_uret": RuntimeError("ffmpeg yok")})
senaryo("reels_kayitli_video_taze", ["--tur", "reels", "--id", "714", "--hedef", "reels,yt"],
        lambda o: o.haber_slaytlariyla(714, 3, kategori="REELS", detay_metni=DETAY_HABER, video_yolu=str(o.dosya("kayitli", "onayli.mp4"))))
senaryo("sesli_yayin_muzikli", ["--tur", "haber", "--id", "715", "--hedef", "yt,fb,tiktok,ses_muzikli"],
        lambda o: o.haber_slaytlariyla(715, 3, detay_metni=DETAY_HABER))
senaryo("sesli_yayin_muziksiz_anlatim_uretilemedi", ["--tur", "haber", "--id", "716", "--hedef", "yt,ses_muziksiz"],
        lambda o: o.haber_slaytlariyla(716, 3, detay_metni=DETAY_HABER),
        donusler={"ses.anlatimli_video_uret": lambda o, slaytlar, veri=None, muzik=True, sonuc=None, **k: o.dosya("video", "sessiz.mp4")})
senaryo("linkedin_ve_twitter_cok_slayt", ["--tur", "haber", "--id", "717", "--hedef", "li,x"],
        lambda o: o.haber_slaytlariyla(717, 3, detay_metni=DETAY_HABER),
        donusler={"linkedin.kullanilabilir_mi": True, "twitter.kullanilabilir_mi": True})
senaryo("linkedin_ve_twitter_tek_slayt", ["--tur", "haber", "--id", "718", "--hedef", "linkedin,twitter"],
        lambda o: o.haber_slaytlariyla(718, 1, detay_metni=DETAY_HABER),
        donusler={"linkedin.kullanilabilir_mi": True, "twitter.kullanilabilir_mi": True})
senaryo("linkedin_ve_twitter_yapilandirilmamis", ["--tur", "haber", "--id", "719", "--hedef", "li,x"],
        lambda o: o.haber_slaytlariyla(719, 3, detay_metni=DETAY_HABER))
senaryo("linkedin_hepsi_icinde_acik", ["--tur", "haber", "--id", "720", "--hedef", "hepsi"],
        lambda o: o.haber_slaytlariyla(720, 3, detay_metni=DETAY_HABER),
        donusler={"linkedin.kullanilabilir_mi": True, "linkedin.paylas": RuntimeError("li 403"), "twitter.kullanilabilir_mi": True})
senaryo("ilan_ig_fb_story_threads", ["--tur", "ilan", "--id", "ilan-7", "--hedef", "ig,facebook,story,threads"],
        lambda o: o.ilan_ekle("ilan-7"))
senaryo("ilan_hepsi_yeniden_ciz", ["--tur", "ilan", "--id", "ilan-8", "--hedef", "hepsi", "--yeniden-ciz"],
        lambda o: o.ilan_ekle("ilan-8"))
senaryo("ilan_video_kanallari", ["--tur", "ilan", "--id", "ilan-9", "--hedef", "yt,tiktok,reels"],
        lambda o: o.ilan_ekle("ilan-9"))
senaryo("canli_durum_mesaj_id", ["--tur", "haber", "--id", "721", "--hedef", "ig,threads,fb", "--mesaj-id", "55"],
        lambda o: o.haber_slaytlariyla(721, 3, detay_metni=DETAY_HABER))
senaryo("mesajdan_icerik_bulunur", ["--hedef", "ig", "--mesaj-id", "77"],
        lambda o: (o.haber_slaytlariyla(722, 3, detay_metni=DETAY_HABER), o.onay_ekle("haber", "722", 77)))
senaryo("id_yok_cikis", ["--hedef", "ig"], lambda o: None)
senaryo("site_taslagi_aktarilir", ["--tur", "haber", "--id", "723", "--hedef", "ig"],
        lambda o: o.haber_slaytlariyla(723, 3, detay_metni=DETAY_HABER), env={"EDM_SITE_ICERIK_AKTARIMI": "1"})
senaryo("yayin_kapisi_durdurur", ["--tur", "haber", "--id", "724", "--hedef", "ig"],
        lambda o: o.haber_slaytlariyla(724, 3, detay_metni=DETAY_HABER),
        donusler={"telegram_bot.yayin_kapisi": (False, ["⛔ ABARTI"])})
senaryo("durum_korumasi_kapali_icerik", ["--tur", "haber", "--id", "725", "--hedef", "ig"],
        lambda o: o.haber_slaytlariyla(725, 3, durum="iptal"))
senaryo("zaten_yayinda_kanallar_atlanir", ["--tur", "haber", "--id", "726", "--hedef", "ig,threads"],
        lambda o: o.haber_slaytlariyla(726, 3, detay_metni=DETAY_HABER, durum="yayinlandi", instagram_post_id="IGOLD"))
senaryo("hepsi_zaten_yayinda_cikis", ["--tur", "haber", "--id", "727", "--hedef", "ig"],
        lambda o: o.haber_slaytlariyla(727, 3, detay_metni=DETAY_HABER, durum="yayinlandi", instagram_post_id="IGOLD"))
senaryo("slayt_yok_hata", ["--tur", "haber", "--id", "728", "--hedef", "ig"],
        lambda o: o.haber_ekle(728, detay_metni=None),
        donusler={"upload_image.coklu_gorsel_yukle": lambda o, ps, *a, **k: []})
senaryo("haber_bulunamadi_hata", ["--tur", "haber", "--id", "999", "--hedef", "ig"], lambda o: None)
senaryo("url_olmus_yerelden_onarilir", ["--tur", "haber", "--id", "729", "--hedef", "ig"],
        lambda o: o.haber_slaytlariyla(729, 3, detay_metni=DETAY_HABER, slayt_urlleri=json.dumps(["https://uguu.se/eski1.jpg", "https://cdn.example.com/ok.jpg"])))

# --- aksiyonlar ---------------------------------------------------------------------------------------------------
senaryo("plan_ayarla", ["--tur", "haber", "--id", "730", "--hedef", "planla", "--plan-an", "2026-10-14T09:00:00Z"],
        lambda o: o.haber_ekle(730))
senaryo("plan_gecersiz_zaman", ["--tur", "haber", "--id", "731", "--hedef", "planla", "--plan-an", "yarin"], lambda o: o.haber_ekle(731))
senaryo("plan_iptal", ["--tur", "haber", "--id", "732", "--hedef", "plan_iptal"],
        lambda o: o.haber_ekle(732, planlanan_yayin="2026-10-14T09:00:00+00:00"))
senaryo("plan_ilan_dokunmaz", ["--tur", "ilan", "--id", "ilan-1", "--hedef", "planla", "--plan-an", "2026-10-14T09:00:00Z"],
        lambda o: o.ilan_ekle("ilan-1"))
senaryo("reddet_konu_bankasi_yenisi_uretilir", ["--tur", "haber", "--id", "733", "--hedef", "reddet"], lambda o: (o.haber_ekle(733), o.konu_kaydi(733)))
senaryo("reddet_sozluk_yenisi_uretilmez", ["--tur", "haber", "--id", "734", "--hedef", "iptal"],
        lambda o: (o.haber_ekle(734, kaynak="EDM Sözlük Kartı // SZ-001"), o.konu_kaydi(734)))
senaryo("reddet_reels", ["--tur", "reels", "--id", "735", "--hedef", "reddet"], lambda o: o.haber_ekle(735, kategori="REELS"))
senaryo("reddet_ilan", ["--tur", "ilan", "--id", "ilan-2", "--hedef", "reddet"], lambda o: o.ilan_ekle("ilan-2"))
senaryo("cope_at_haber", ["--tur", "haber", "--id", "736", "--hedef", "cope_at"], lambda o: (o.haber_ekle(736), o.konu_kaydi(736)))
senaryo("cope_at_ilan", ["--tur", "ilan", "--id", "ilan-3", "--hedef", "cope_at"], lambda o: o.ilan_ekle("ilan-3"))
senaryo("ertele_haber", ["--tur", "haber", "--id", "737", "--hedef", "ertele"], lambda o: (o.haber_ekle(737), o.onay_ekle("haber", "737", 31)))
senaryo("ertele_ilan", ["--tur", "ilan", "--id", "ilan-4", "--hedef", "ertele"], lambda o: (o.ilan_ekle("ilan-4"), o.onay_ekle("ilan", "ilan-4", 32)))
senaryo("kaldir", ["--tur", "haber", "--id", "738", "--hedef", "kaldir", "--mesaj-id", "40"], lambda o: o.haber_ekle(738, durum="yayinlandi"))
senaryo("manuel_paket_haber", ["--tur", "haber", "--id", "739", "--hedef", "manuel_paket"], lambda o: o.haber_ekle(739))
senaryo("manuel_paket_ilan", ["--tur", "ilan", "--id", "ilan-5", "--hedef", "manuel_paket"], lambda o: o.ilan_ekle("ilan-5"))
senaryo("manuel_paket_haber_yok", ["--tur", "haber", "--id", "998", "--hedef", "manuel_paket"], lambda o: None)
senaryo("tamamla_haber", ["--tur", "haber", "--id", "740", "--hedef", "tamamla"], lambda o: o.haber_ekle(740))
senaryo("tamamla_haber_site", ["--tur", "haber", "--id", "741", "--hedef", "manuel_tamam"], lambda o: o.haber_ekle(741),
        env={"EDM_SITE_ICERIK_AKTARIMI": "1"})
senaryo("tamamla_reels", ["--tur", "reels", "--id", "742", "--hedef", "tamamla"], lambda o: o.haber_ekle(742, kategori="REELS"))
senaryo("tamamla_ilan", ["--tur", "ilan", "--id", "ilan-6", "--hedef", "tamamla"], lambda o: o.ilan_ekle("ilan-6"))
senaryo("yenile_haber", ["--tur", "haber", "--id", "743", "--hedef", "yenile"],
        lambda o: (o.haber_slaytlariyla(743, 2), o.onay_ekle("haber", "743", 41)))
senaryo("yenile_reels", ["--tur", "reels", "--id", "744", "--hedef", "yenile"], lambda o: o.haber_ekle(744, kategori="REELS"))
senaryo("yenile_ilan", ["--tur", "ilan", "--id", "ilan-10", "--hedef", "yenile"], lambda o: o.ilan_ekle("ilan-10"))
senaryo("yenile_haber_yok", ["--tur", "haber", "--id", "997", "--hedef", "yenile"], lambda o: None)
senaryo("metin_ozetle_haber", ["--tur", "haber", "--id", "745", "--hedef", "metin_ozetle"], lambda o: o.haber_slaytlariyla(745, 2))
senaryo("metin_detaylandir_reels", ["--tur", "reels", "--id", "746", "--hedef", "metin_detaylandir"],
        lambda o: o.haber_slaytlariyla(746, 2, kategori="REELS"))
senaryo("metin_yenile_haber", ["--tur", "haber", "--id", "747", "--hedef", "metin_yenile"], lambda o: o.haber_ekle(747))
senaryo("foto_stok", ["--tur", "haber", "--id", "748", "--hedef", "foto_stok"],
        lambda o: o.haber_ekle(748, detay_metni=DETAY_HABER))
senaryo("foto_ai_reels", ["--tur", "reels", "--id", "749", "--hedef", "foto_ai"],
        lambda o: o.haber_ekle(749, kategori="REELS", detay_metni=DETAY_HABER))
senaryo("foto_ilk_ve_editoryal", ["--tur", "haber", "--id", "750", "--hedef", "foto_ilk"],
        lambda o: o.haber_ekle(750, detay_metni=json.dumps({"format_turu": "dailybrief", "foto_kaynak": "stok", "saf_editoryal": True, "foto_degistir": True})))
senaryo("foto_editoryal", ["--tur", "haber", "--id", "751", "--hedef", "foto_editoryal"], lambda o: o.haber_ekle(751))
senaryo("foto_adaylar", ["--tur", "haber", "--id", "752", "--hedef", "foto_adaylar"], lambda o: o.haber_ekle(752, detay_metni=DETAY_HABER))
senaryo("gorsel_sec_1", ["--tur", "haber", "--id", "753", "--hedef", "gorsel_sec:1"], lambda o: o.haber_ekle(753, detay_metni=DETAY_HABER))
senaryo("gorsel_sec_3", ["--tur", "haber", "--id", "754", "--hedef", "gorsel_sec:3"], lambda o: o.haber_ekle(754, detay_metni=DETAY_HABER))
senaryo("foto_degistir_detaysiz", ["--tur", "haber", "--id", "755", "--hedef", "foto_degistir"], lambda o: o.haber_ekle(755))
senaryo("kapali_icerikte_taslak_islemi_engellenir", ["--tur", "haber", "--id", "756", "--hedef", "yenile"],
        lambda o: o.haber_ekle(756, durum="yayinlandi"))


def _site_sahte(o: "Ortam", haber):
    o.kayitci.kaydet("site_icerik.site_taslagi_gonder", (haber.get("id"),), {})
    if o.donusler.get("site.hata"):
        raise RuntimeError("site 401")
    return {"id": 77}



# --- ikinci dalga: hata/yedek yolları (kapsam ölçümünde altın çıktının görmediği satırlar) -----------------------
import os as _os  # noqa: E402


def _yerel_yok(o, id, adet=3, **kolon):
    """Slayt dosyaları bu makinede YOK (Actions makinesi yeni açıldı), DB'de yalnız yollar/adresler var."""
    yollar = [str(o.tmp / "yok" / f"h{id}_{i}.jpg") for i in range(adet)]
    ek = {"slayt_yollari": json.dumps(yollar)}
    o.haber_ekle(id, **{**ek, **kolon})


DETAY_NEDIR = json.dumps({"format_turu": "nedir_dogrusu", "manset": "Nedir?"}, ensure_ascii=False)

senaryo("haber_url_olmus_yerel_yok_detaydan_cizilir", ["--tur", "haber", "--id", "801", "--hedef", "ig"],
        lambda o: _yerel_yok(o, 801, detay_metni=DETAY_HABER, slayt_urlleri=json.dumps(["https://uguu.se/eski.jpg"])))
senaryo("haber_url_olmus_yerel_yok_otorite_cizici", ["--tur", "haber", "--id", "802", "--hedef", "ig"],
        lambda o: _yerel_yok(o, 802, detay_metni=DETAY_OTORITE.replace('"slayt_4x5_urlleri"', '"_x"'),
                             slayt_urlleri=json.dumps(["https://uguu.se/eski.jpg"])))
senaryo("haber_url_olmus_yerel_yukleme_hatasi", ["--tur", "haber", "--id", "803", "--hedef", "ig"],
        lambda o: o.haber_slaytlariyla(803, 3, detay_metni=DETAY_HABER, slayt_urlleri=json.dumps(["https://uguu.se/eski.jpg"])),
        donusler={"upload_image.coklu_gorsel_yukle": RuntimeError("imgbb 500")})
senaryo("haber_urlsiz_yerel_yok_detaydan_cizilir", ["--tur", "haber", "--id", "804", "--hedef", "ig,threads"],
        lambda o: _yerel_yok(o, 804, detay_metni=DETAY_HABER))
senaryo("haber_urlsiz_yerel_yok_otorite_cizici", ["--tur", "haber", "--id", "805", "--hedef", "ig"],
        lambda o: _yerel_yok(o, 805, detay_metni=DETAY_OTORITE.replace('"slayt_4x5_urlleri"', '"_x"')))
senaryo("haber_slayt_json_bozuk", ["--tur", "haber", "--id", "806", "--hedef", "ig"],
        lambda o: o.haber_ekle(806, slayt_yollari="[bozuk", slayt_urlleri="bozuk", detay_metni=DETAY_HABER))
senaryo("haber_detay_json_bozuk_hata", ["--tur", "haber", "--id", "807", "--hedef", "ig"],
        lambda o: o.haber_slaytlariyla(807, 3, detay_metni="{bozuk"))
senaryo("ilan_bulunamadi_hata", ["--tur", "ilan", "--id", "yok-ilan", "--hedef", "ig"], lambda o: None)
senaryo("haber_id_sayi_degil", ["--tur", "haber", "--id", "abc", "--hedef", "ig"], lambda o: None)
senaryo("story_yukleme_yok_yerel_yedek", ["--tur", "haber", "--id", "808", "--hedef", "story"],
        lambda o: o.haber_slaytlariyla(808, 3, url_var=False),
        donusler={"upload_image.coklu_gorsel_yukle": lambda o, ps, *a, **k: []})
senaryo("reels_kayitli_video_slaytlardan_eski", ["--tur", "reels", "--id", "809", "--hedef", "reels,yt"],
        lambda o: (_os.utime(o.dosya("kayitli", "eski.mp4"), (1_000_000, 1_000_000)),
                   o.haber_slaytlariyla(809, 3, kategori="REELS", detay_metni=DETAY_HABER, video_yolu=str(o.tmp / "kayitli" / "eski.mp4"))))
senaryo("reels_dikey_cizim_hatasi_slayt_yedegi", ["--tur", "reels", "--id", "810", "--hedef", "reels,yt"],
        lambda o: o.haber_slaytlariyla(810, 5, kategori="REELS", detay_metni=DETAY_HABER), donusler={"resim.hata": True})
senaryo("reels_dikey_cizim_hatasi_otorite", ["--tur", "reels", "--id", "811", "--hedef", "yt,story"],
        lambda o: o.haber_slaytlariyla(811, 4, kategori="REELS", detay_metni=DETAY_OTORITE), donusler={"resim.hata": True})
senaryo("video_nedir_dogrusu_uc_slayt", ["--tur", "haber", "--id", "812", "--hedef", "yt"],
        lambda o: o.haber_slaytlariyla(812, 4, detay_metni=DETAY_NEDIR))
senaryo("ilan_video_ilan_yolu_hatasi", ["--tur", "ilan", "--id", "ilan-11", "--hedef", "yt"],
        lambda o: o.ilan_ekle("ilan-11"), donusler={"resim.ilan_hata": True})
senaryo("fon_muzigi_mikslenemedi", ["--tur", "haber", "--id", "813", "--hedef", "yt,fb,reels"],
        lambda o: o.haber_slaytlariyla(813, 3, detay_metni=DETAY_HABER), donusler={"ses.sesli_video_hazirla": RuntimeError("ffmpeg")})
senaryo("telegram_bildirim_hatalari_yayini_bozmaz", ["--tur", "haber", "--id", "814", "--hedef", "yt,ig"],
        lambda o: o.haber_slaytlariyla(814, 3, detay_metni=DETAY_HABER),
        donusler={"telegram_bot.sonucu_yaz": RuntimeError("tg 500")})
senaryo("telegram_video_ve_caption_hatalari", ["--tur", "haber", "--id", "815", "--hedef", "yt,ig"],
        lambda o: o.haber_slaytlariyla(815, 3, detay_metni=DETAY_HABER),
        donusler={"telegram_bot.video_gonder": RuntimeError("video 413"), "telegram_bot.mesaj_gonder": RuntimeError("tg 429")})
senaryo("threads_tekil_basarisiz", ["--tur", "haber", "--id", "816", "--hedef", "threads"],
        lambda o: o.haber_slaytlariyla(816, 1, detay_metni=DETAY_HABER), donusler={"threads.paylas": None})
senaryo("threads_zincir_kok_yok", ["--tur", "haber", "--id", "817", "--hedef", "threads"],
        lambda o: o.haber_slaytlariyla(817, 3, detay_metni=DETAY_HABER),
        donusler={"threads.zincir_paylas_sonuc": {"kok_id": None, "yayinlanan": 0, "toplam": 2, "eksik": [1, 2]}})
senaryo("threads_tek_parca_paylas_hata", ["--tur", "haber", "--id", "818", "--hedef", "threads"],
        lambda o: o.haber_slaytlariyla(818, 3, detay_metni=DETAY_HABER),
        donusler={"threads.metinleri_slaytlara_dagit": lambda o, h, u: ["tek"], "threads.paylas": None})
senaryo("threads_reels_4x5_cizilir", ["--tur", "reels", "--id", "819", "--hedef", "threads"],
        lambda o: o.haber_slaytlariyla(819, 3, kategori="REELS", detay_metni=DETAY_HABER))
senaryo("threads_yerel_kirpma_hatasi", ["--tur", "haber", "--id", "820", "--hedef", "threads"],
        lambda o: o.haber_slaytlariyla(820, 3, detay_metni=DETAY_HABER), donusler={"instagram.gorselleri_4_5_yap": RuntimeError("pillow")})
senaryo("facebook_reels_basarisiz", ["--tur", "haber", "--id", "821", "--hedef", "reels,fb"],
        lambda o: o.haber_slaytlariyla(821, 3, detay_metni=DETAY_HABER), donusler={"facebook.video_yayinla": None})
senaryo("facebook_reels_istisna_ve_video_yok", ["--tur", "haber", "--id", "822", "--hedef", "reels,fb"],
        lambda o: o.haber_slaytlariyla(822, 3, detay_metni=DETAY_HABER),
        donusler={"facebook.video_yayinla": RuntimeError("fb 400"), "video.slaytlardan_reels_uret": RuntimeError("ffmpeg")})
senaryo("tiktok_video_basarisiz_ve_istisna", ["--tur", "haber", "--id", "823", "--hedef", "tt,ses_muzikli"],
        lambda o: o.haber_slaytlariyla(823, 3, detay_metni=DETAY_HABER),
        donusler={"tiktok.video_yukle": {"durum": False, "hata": "kota"}})
senaryo("tiktok_video_istisna", ["--tur", "haber", "--id", "824", "--hedef", "tt,ses_muzikli"],
        lambda o: o.haber_slaytlariyla(824, 3, detay_metni=DETAY_HABER), donusler={"tiktok.video_yukle": RuntimeError("tt 500")})
senaryo("tiktok_video_taslak", ["--tur", "haber", "--id", "825", "--hedef", "tt,ses_muzikli"],
        lambda o: o.haber_slaytlariyla(825, 3, detay_metni=DETAY_HABER),
        donusler={"tiktok.video_yukle": {"durum": True, "taslak_mi": True, "publish_id": "TTD2"}})
senaryo("tiktok_video_yok", ["--tur", "haber", "--id", "826", "--hedef", "tt,reels"],
        lambda o: o.haber_slaytlariyla(826, 3, detay_metni=DETAY_HABER), donusler={"video.slaytlardan_reels_uret": RuntimeError("ffmpeg")})
senaryo("youtube_istisna", ["--tur", "haber", "--id", "827", "--hedef", "yt"],
        lambda o: o.haber_slaytlariyla(827, 3, detay_metni=DETAY_HABER), donusler={"youtube.shorts_yukle": RuntimeError("quota")})
senaryo("instagram_tekil_basarisiz", ["--tur", "haber", "--id", "828", "--hedef", "ig"],
        lambda o: o.haber_slaytlariyla(828, 1, detay_metni=DETAY_HABER), donusler={"instagram.tekil_gorsel_yayinla": None})
senaryo("instagram_istisna", ["--tur", "haber", "--id", "829", "--hedef", "ig"],
        lambda o: o.haber_slaytlariyla(829, 3, detay_metni=DETAY_HABER), donusler={"instagram.carousel_yayinla": RuntimeError("meta 190")})
senaryo("reels_telegram_video_hatasi", ["--tur", "reels", "--id", "830", "--hedef", "reels"],
        lambda o: o.haber_slaytlariyla(830, 3, kategori="REELS", detay_metni=DETAY_HABER),
        donusler={"telegram_bot.video_gonder": RuntimeError("413")})
senaryo("reels_baslik_yok", ["--tur", "reels", "--id", "831", "--hedef", "reels"],
        lambda o: o.haber_slaytlariyla(831, 3, kategori="REELS", detay_metni=DETAY_HABER, manset=None, orijinal_baslik="Başlık"))
senaryo("manuel_paket_detay_bozuk_kapi", ["--tur", "haber", "--id", "832", "--hedef", "manuel_paket"],
        lambda o: o.haber_ekle(832, detay_metni="{bozuk"))
senaryo("manuel_paket_ilan_yok", ["--tur", "ilan", "--id", "yok-ilan", "--hedef", "manuel_paket"], lambda o: None)
senaryo("foto_adaylar_hic_aday_yok", ["--tur", "haber", "--id", "833", "--hedef", "foto_adaylar"],
        lambda o: o.haber_ekle(833, detay_metni=DETAY_HABER), donusler={"resim.aday_yok": True})
senaryo("foto_islemi_haber_yok", ["--tur", "haber", "--id", "996", "--hedef", "foto_stok"], lambda o: None)
senaryo("metin_islemi_haber_yok", ["--tur", "haber", "--id", "995", "--hedef", "metin_ozetle"], lambda o: None)
senaryo("linkedin_detaysiz_haberden_veri", ["--tur", "haber", "--id", "834", "--hedef", "li"],
        lambda o: o.haber_slaytlariyla(834, 3), donusler={"linkedin.kullanilabilir_mi": True})
senaryo("site_taslagi_hatasi", ["--tur", "haber", "--id", "835", "--hedef", "ig"],
        lambda o: o.haber_slaytlariyla(835, 3, detay_metni=DETAY_HABER), env={"EDM_SITE_ICERIK_AKTARIMI": "1"}, donusler={"site.hata": True})
senaryo("mesajdan_ilan_bulunur", ["--hedef", "ig", "--mesaj-id", "78"],
        lambda o: (o.ilan_ekle("ilan-12"), o.onay_ekle("ilan", "ilan-12", 78)))
senaryo("ilan_zaten_yayinda_filtre_haber_degil", ["--tur", "ilan", "--id", "ilan-13", "--hedef", "ig,fb"],
        lambda o: o.ilan_ekle("ilan-13"))


def calistir(sen: dict) -> dict:
    o = Ortam(sen["donusler"])
    cikti = io.StringIO()
    istisna = None
    try:
        o.baslat()
        if sen["kur"]:
            sen["kur"](o)
        with patch.dict(os.environ, sen["env"], clear=False), \
             patch.object(sys, "argv", ["yayinla.py", *sen["argv"]]), \
             patch("src.site_icerik.site_taslagi_gonder", side_effect=lambda h: _site_sahte(o, h)), \
             contextlib.redirect_stdout(cikti):
            try:
                yayinla.main()
            except BaseException as e:  # noqa: BLE001 — kaydedilir: hata türü ve metni davranışın parçası
                istisna = f"{type(e).__name__}: {o.kayitci.norm(str(e))}"
        stdout = [o.kayitci.norm(s) for s in cikti.getvalue().splitlines() if s.startswith("POSTEDM_SONUC=")]
        return {
            "istisna": istisna,
            "stdout": stdout,
            "cagrilar": sorted(o.kayitci.cagrilar),
            "telegram": [o.kayitci.norm(t) for t in o.kayitci.telegram],
            "db": o.db_ozeti(),
        }
    finally:
        o.bitir()


class TestYayinlaAltin(unittest.TestCase):
    maxDiff = None

    def test_senaryolar_altin_cikti_ile_ayni(self):
        mevcut: dict = {}
        for sen in SENARYOLAR:
            mevcut[sen["ad"]] = calistir(sen)
        self.assertEqual(len(mevcut), len(SENARYOLAR), "senaryo adları benzersiz olmalı")

        if KAYDET:
            # YAYIN_ALTIN_SENARYO=ad1,ad2 → yalnız bu senaryolar yeniden kaydedilir (bilinçli davranış düzeltmesi);
            # verilmezse hepsi.
            secili = {a.strip() for a in os.environ.get("YAYIN_ALTIN_SENARYO", "").split(",") if a.strip()}
            kaydedilecek = mevcut
            if secili and ALTIN_YOLU.exists():
                kaydedilecek = json.loads(ALTIN_YOLU.read_text(encoding="utf-8"))
                kaydedilecek.update({ad: v for ad, v in mevcut.items() if ad in secili})
            ALTIN_YOLU.parent.mkdir(parents=True, exist_ok=True)
            ALTIN_YOLU.write_text(json.dumps(kaydedilecek, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            self.skipTest(f"Altın çıktı yeniden kaydedildi: {len(secili) or len(mevcut)} senaryo")

        self.assertTrue(ALTIN_YOLU.exists(), "tests/altin/yayinla.json yok: YAYIN_ALTIN_KAYDET=1 ile kaydedin")
        altin = json.loads(ALTIN_YOLU.read_text(encoding="utf-8"))
        self.assertEqual(sorted(altin), sorted(mevcut), "senaryo kümesi altın çıktıdan farklı")
        farklar = []
        for ad in sorted(mevcut):
            a = json.dumps(altin[ad], ensure_ascii=False, indent=1, sort_keys=True).splitlines()
            m = json.dumps(mevcut[ad], ensure_ascii=False, indent=1, sort_keys=True).splitlines()
            if a != m:
                farklar.append(f"### {ad}\n" + "\n".join(difflib.unified_diff(a, m, "altin", "mevcut", lineterm="", n=2)))
        self.assertFalse(farklar, "\n\n".join(farklar)[:12000])

    def test_senaryolar_kendi_kendini_tutarli_tekrarlanabilir(self):
        """Aynı senaryo iki kez koşunca aynı çıktı: altın çıktı belirlenimci olmalı (zaman/dizin sızıntısı yok)."""
        for sen in SENARYOLAR[:6]:
            self.assertEqual(calistir(sen), calistir(sen), sen["ad"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
