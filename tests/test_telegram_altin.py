"""
tests/test_telegram_altin.py — src/telegram_bot.py "ALTIN ÇIKTI" (golden master) güvencesi (Faz 2, 2026-10-13)

NİYE: telegram_bot.py 2919 satırlık, beş ayrı işi (API istemcisi, menüler, kartlar, duraklatma/kanal ayarı, içerik akışları) yapan
tek dosya ve bölünecek. Bölme davranışı DEĞİŞTİRMEMELİ. Bu dosya botun dış dünyaya yaptığı her şeyi kaydeder:

  • Telegram'a giden HER HTTP isteği (`requests.post` sınırı: yöntem adı, gövde, yüklenen dosyaların adı/boyutu, zaman aşımı)
  • işlevlerin döndürdüğü değer (menüler/kartlar saf işlevdir, çıktıları doğrudan karşılaştırılır)
  • veritabanı son durumu, dış modüllere (üretim, görsel, konu bankası, ...) yapılan çağrılar, fırlatılan hata

Sınır HTTP olduğu için kayıt, kodun içinde nasıl bölündüğünden BAĞIMSIZDIR: işlevler `telegram_bot.<ad>` üzerinden çağrılır.

  python -m unittest tests.test_telegram_altin                          # karşılaştır
  TELEGRAM_ALTIN_KAYDET=1 python -m unittest tests.test_telegram_altin  # YENİDEN KAYDET (yalnız davranış bilerek değişirse)
  TELEGRAM_ALTIN_SENARYO=ad1,ad2 ile yalnız o senaryolar yeniden kaydedilir.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import contextlib
import copy
import difflib
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests
from PIL import Image

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import (db, db_senkron, dogrula, facebook, fetch_listings, generate_text, haber_oneri, konu_bankasi, make_image,
                 rapor_uretici, ses, sozluk_arsivi, telegram_bot, threads, upload_image, video, yeni_formatlar)

ALTIN_YOLU = KOK / "tests" / "altin" / "telegram.json"
KAYDET = os.environ.get("TELEGRAM_ALTIN_KAYDET") == "1"
tb = telegram_bot


def _jpeg_bayt(boyut=(1080, 1350)) -> bytes:
    tampon = io.BytesIO()
    Image.new("RGB", boyut, (40, 70, 100)).save(tampon, "JPEG")
    return tampon.getvalue()


def _jpeg(yol: Path, boyut=(1080, 1350)) -> Path:
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_bytes(_jpeg_bayt(boyut))
    return yol


def _bugun_tr() -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=3)).date().isoformat()


class Normallestirici:
    def __init__(self, tmp: Path):
        self.tmp = str(tmp)

    def __call__(self, v):
        if isinstance(v, Path):
            return "P:" + v.name
        if isinstance(v, str):
            s = v.replace(self.tmp, "<TMP>").replace(str(KOK), "<KOK>").replace(sys.executable, "<PY>")  # yorumlayıcı yolu makineye göre değişir
            s = re.sub(r"(Geçen Süre|Toplam Dağıtım Süresi): [0-9.]+ sn", r"\1: <S> sn", s)
            s = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(\+00:00|Z)?", "<ISO>", s)
            s = s.replace(_bugun_tr(), "<BUGUN>")  # uygulama "bugün"ü TR gününe göre yazar (ayarlar › *_son_gun); altın dosya günlük bozulmasın
            s = re.sub(r"(edm://[a-z]+/(?:[A-Za-z0-9-]+/)?)\d{9,11}", r"\1<UNIX>", s)  # edm:// sahte url'lerine saniye damgası gömülür
            return s
        if isinstance(v, bytes):
            return f"<bytes {len(v)}>"
        if v is None or isinstance(v, (bool, int, float)):
            return v
        if isinstance(v, dict):
            return {str(k): self(x) for k, x in sorted(v.items(), key=lambda kv: str(kv[0]))}
        if isinstance(v, (set, frozenset)):
            return sorted((self(x) for x in v), key=repr)
        if isinstance(v, (list, tuple)):
            return [self(x) for x in v]
        return f"<{type(v).__name__}>"


class SahteTelegram:
    """`requests.post` yerine geçer ve Telegram'a giden her isteği kaydeder. `betik[metot]`: sıradaki cevaplar
    (Exception → fırlatılır; (durum, gövde) → o cevap; "ok" → varsayılan başarı)."""

    def __init__(self, norm: Normallestirici, betik: dict | None = None):
        self.norm = norm
        self.istekler: list = []
        self.sayac = 5000
        self.betik = {k: list(v) for k, v in (betik or {}).items()}

    def _yeni(self) -> int:
        self.sayac += 1
        return self.sayac

    def _dosya(self, deger) -> list:
        ad, boyut = None, None
        icerik = deger
        if isinstance(deger, tuple):
            ad = deger[0]
            icerik = deger[1] if len(deger) > 1 else b""
        if isinstance(icerik, (bytes, bytearray)):
            boyut = len(icerik)
        elif isinstance(icerik, io.BytesIO):
            boyut = icerik.getbuffer().nbytes
        elif hasattr(icerik, "read"):
            boyut = len(icerik.read())
        return [ad, boyut]

    def post(self, url, json=None, data=None, files=None, timeout=None, **k):
        metot = str(url).rsplit("/", 1)[-1]
        kayit: dict = {"metot": metot, "zaman_asimi": self.norm(timeout)}
        if json is not None:
            kayit["json"] = self.norm(json)
        if data is not None:
            d = dict(data)
            for anahtar in ("media", "reply_markup"):
                if isinstance(d.get(anahtar), str):
                    try:
                        d[anahtar] = _json.loads(d[anahtar])
                    except ValueError:
                        pass
            kayit["data"] = self.norm(d)
        if files:
            kayit["dosyalar"] = {ad: self.norm(self._dosya(v)) for ad, v in sorted(files.items())}
        self.istekler.append(kayit)

        kuyruk = self.betik.get(metot)
        durum, govde = None, None
        if kuyruk:
            adim = kuyruk.pop(0)
            if isinstance(adim, BaseException):
                raise adim
            if adim != "ok":
                durum, govde = adim
        if durum is None:
            durum, govde = 200, {"ok": True, "result": self._varsayilan(metot, json, data)}
        yanit = MagicMock()
        yanit.status_code = durum
        yanit.json.return_value = govde
        yanit.text = _json.dumps(govde)
        yanit.content = yanit.text.encode()
        return yanit

    def _varsayilan(self, metot, json, data):
        if metot == "sendMediaGroup":
            medya = json["media"] if json else _json.loads(data["media"])
            return [{"message_id": self._yeni()} for _ in medya]
        if metot in ("deleteMessage", "setMyCommands", "answerCallbackQuery"):
            return True
        return {"message_id": self._yeni()}


_json = json


class Kayitci:
    GURULTU: frozenset = frozenset()

    def __init__(self, norm: Normallestirici):
        self.norm = norm
        self.cagrilar: list = []
        self.kilit = threading.Lock()

    def kaydet(self, ad, args, kwargs):
        if ad in self.GURULTU:
            return
        girdi = {"islev": ad, "args": self.norm(list(args)), "kwargs": self.norm(dict(kwargs))}
        with self.kilit:
            self.cagrilar.append(_json.dumps(girdi, ensure_ascii=False, sort_keys=True))


KONU = {"kod": "S1-001", "sutun": "S1", "bicim": "B1", "baslik": "Önalım hakkı nedir?", "aci": "Süre ve şartlar", "onem_puani": 8}
VERI = {"manset": "Üretilen Manşet", "spot": "Spot metni", "kategori_kodu": "TAPU_VE_HUKUK", "caption_instagram": "IG açıklama",
        "caption_threads": "Threads metni", "onem_puani": 8, "yasal_dayanak": "TMK md. 732"}
KART = {"kod": "SZ-001", "terim": "İPOTEK", "kategori_kodu": "TAPU_VE_HUKUK"}
OZET = {"toplam": 120, "kullanilmis": 40, "bakir": 80, "bakir_sutun_dagilimi": {"S1": 20, "S2": 25, "S3": 20, "S4": 15},
        "kalan_gun": 45, "gunluk_tuketim": 1.8, "kalan_hafta": 11}
ILAN = {"id": "ilan-1", "baslik": "Satılık 3+1 Daire", "fiyat": 5250000.0, "paraBirimi": "TRY", "ilce": "Silivri", "tip": "Daire", "mahalle": "Merkez"}


class Ortam:
    VARSAYILAN = {
        "generate_text.konudan_uret": lambda o, konu, format_turu=None, **k: dict(VERI, format_turu=format_turu) if format_turu else dict(VERI),
        "generate_text.manset_birlestir": lambda o, veri, *a, **k: (veri or {}).get("manset", ""),
        "generate_text.caption_zenginlestir": lambda o, c, **k: f"[{k.get('platform')}] {c}",
        "generate_text.haber_metinleri_uret": True,
        "generate_text.otorite_icerigi_uret": lambda o, konu, kategori_kodu=None: dict(VERI, format_turu="otorite"),
        "generate_text.ilan_metinleri_uret": {"ig_caption": "İlan açıklaması"},
        "konu_bankasi.sonraki_konu": lambda o, **k: dict(KONU),
        "konu_bankasi.sonraki_finans_konusu": lambda o, **k: dict(KONU, kod="F1-001", sutun="S5"),
        "konu_bankasi.kullanildi_isaretle": None,
        "konu_bankasi.siradaki_bilgilendirici_format": "b1",
        "konu_bankasi.bilgilendirici_format_kaydet": None,
        "konu_bankasi.havuzu_yukle": lambda o, *a, **k: [dict(KONU)],
        "konu_bankasi.durum_ozeti": lambda o: dict(OZET),
        "sozluk_arsivi.sonraki_kart": lambda o, **k: dict(KART),
        "sozluk_arsivi.kart_kanun_durumu": (True, []),
        "sozluk_arsivi.stok_kalan": 30,
        "sozluk_arsivi.karttan_veri": lambda o, kart: dict(VERI, format_turu="sozluk", terim=kart["terim"]),
        "haber_oneri.onerileri_gonder": 0,
        "rapor_uretici.kota_gonder": {"message_id": 7777},
        "dogrula.icerigi_denetle": [],
        "dogrula.otomatik_yayina_uygun_mu": (True, []),
        "db_senkron.hemen_kaydet": True,
        "fetch_listings.aktif_ilanlar": lambda o, limit=20: [dict(ILAN), dict(ILAN, id="ilan-2", baslik="Satılık Arsa", tip="Arsa", fiyat=2100000.0)],
        "facebook.postu_sil": True,
        "threads.zinciri_sil": (3, 3),
        "upload_image.coklu_gorsel_yukle": lambda o, ps, *a, **k: [f"https://cdn.example.com/{Path(str(p)).name}" for p in ps],
        "video.slaytlardan_reels_uret": lambda o, slaytlar, **k: o.dosya("video", "finans.mp4"),
        "ses.sesli_video_hazirla": lambda o, v, **k: v,
    }
    MODULLER = {"generate_text": generate_text, "konu_bankasi": konu_bankasi, "sozluk_arsivi": sozluk_arsivi, "haber_oneri": haber_oneri,
                "rapor_uretici": rapor_uretici, "dogrula": dogrula, "db_senkron": db_senkron, "fetch_listings": fetch_listings,
                "facebook": facebook, "threads": threads, "upload_image": upload_image, "video": video, "ses": ses}

    def __init__(self, donusler: dict | None = None, betik: dict | None = None, token: bool = True):
        self.tmp = Path(tempfile.mkdtemp(prefix="tg_altin_"))
        self.norm = Normallestirici(self.tmp)
        self.tg = SahteTelegram(self.norm, betik)
        self.kayitci = Kayitci(self.norm)
        self.donusler = {**self.VARSAYILAN, **(donusler or {})}
        self.token = token
        self.yamalar: list = []

    def dosya(self, alt: str, ad: str) -> Path:
        yol = self.tmp / alt / ad
        yol.parent.mkdir(parents=True, exist_ok=True)
        if not yol.exists():
            yol.write_bytes(b"sahte-video")
        return yol

    def slaytlar(self, adet: int, onek: str = "slayt", boyut=(1080, 1350)) -> list[Path]:
        return [_jpeg(self.tmp / "slaytlar" / f"{onek}_{i + 1}.jpg", boyut) for i in range(adet)]

    def _sahte(self, tam_ad: str):
        modul_ad, islev = tam_ad.split(".", 1)
        donus = self.donusler[tam_ad]

        def f(*a, **k):
            self.kayitci.kaydet(tam_ad, a, k)
            if isinstance(donus, BaseException):
                raise donus
            if callable(donus):
                return donus(self, *a, **k)
            return copy.deepcopy(donus)

        return patch.object(self.MODULLER[modul_ad], islev, side_effect=f)

    def _resim(self):
        o = self

        def slaytlari_uret(veri, format_turu=None, cikti_onek="x", olcu="besleme", **k):
            o.kayitci.kaydet("yeni_formatlar.slaytlari_uret", (veri,), {"format_turu": format_turu, "cikti_onek": cikti_onek, "olcu": olcu})
            if o.donusler.get("resim.eksik"):
                raise yeni_formatlar.EksikIcerik("zorunlu alan yok")
            adet = 1 if format_turu == "sozluk" else 4
            boyut = (1080, 1920) if olcu == "story" else (1080, 1350)
            return [_jpeg(o.tmp / "cizim" / f"{cikti_onek}_{olcu}_{i}.jpg", boyut) for i in range(1, adet + 1)]

        def otorite(veri, cikti_onek="x", olcu="besleme", **k):
            o.kayitci.kaydet("make_image.otorite_gonderi_slaytlari_uret", (veri,), {"cikti_onek": cikti_onek, "olcu": olcu})
            if o.donusler.get("resim.eksik"):
                raise make_image.EksikIcerik("zorunlu alan yok")
            boyut = (1080, 1920) if olcu == "story" else (1080, 1350)
            return [_jpeg(o.tmp / "cizim" / f"{cikti_onek}_{olcu}_{i}.jpg", boyut) for i in (1, 2, 3, 4)]

        def ilan_slayti(ad):
            def f(ilan, *a, **k):
                o.kayitci.kaydet(f"make_image.{ad}", (ilan.get("id"),), {})
                return _jpeg(o.tmp / "ilan" / f"{ad}_{ilan.get('id')}.jpg")
            return f

        return [
            patch.object(yeni_formatlar, "slaytlari_uret", side_effect=slaytlari_uret),
            patch.object(make_image, "otorite_gonderi_slaytlari_uret", side_effect=otorite),
            patch.object(make_image, "ilan_kapak_slayti_ciz", side_effect=ilan_slayti("ilan_kapak_slayti_ciz")),
            patch.object(make_image, "ilan_detay_slayti_ciz", side_effect=ilan_slayti("ilan_detay_slayti_ciz")),
            patch.object(make_image, "ilan_kapanis_slayti_ciz", side_effect=ilan_slayti("ilan_kapanis_slayti_ciz")),
        ]

    def baslat(self):
        def env(anahtar, varsayilan=""):
            if anahtar == "TELEGRAM_BOT_TOKEN":
                return "tok" if self.token else ""
            if anahtar == "TELEGRAM_CHAT_ID":
                return "-100123"
            return varsayilan

        self.yamalar = [
            patch("src.db.DB_YOLU", self.tmp / "altin.db"),
            patch("src.config.env_al", side_effect=env),
            patch("requests.post", side_effect=self.tg.post),
            patch("requests.get", return_value=MagicMock(status_code=200, content=_jpeg_bayt())),
            patch("time.sleep"),
            patch("subprocess.run", side_effect=self._subprocess),
            *[self._sahte(ad) for ad in self.donusler if ad.split(".")[0] in self.MODULLER],
            *self._resim(),
        ]
        for y in self.yamalar:
            y.start()
        db.tablolari_olustur()
        konu_bankasi.tabloyu_kur()

    def _subprocess(self, komut, **k):
        self.kayitci.kaydet("subprocess.run", (komut,), {})
        basari = not self.donusler.get("alt_surec.hata")
        return subprocess.CompletedProcess(komut, 0 if basari else 1, stdout="POSTEDM_SONUC={}" if basari else "", stderr="" if basari else "boom")

    def bitir(self):
        for y in reversed(self.yamalar):
            try:
                y.stop()
            except RuntimeError:
                pass
        shutil.rmtree(KOK / "data/output/adaylar", ignore_errors=True)
        shutil.rmtree(self.tmp, ignore_errors=True)

    # --- veritabanı -------------------------------------------------------------------------------------------
    def haber_ekle(self, id: int, **kolon):
        varsayilan = {"kaynak": "EDM Konu Bankası // S1-001", "orijinal_baslik": f"Orijinal başlık {id}", "orijinal_url": f"edm://altin/{id}",
                      "eklenme_tarihi": "2026-10-01T10:00:00+00:00", "onem_puani": 8, "kategori": "TAPU_VE_HUKUK", "manset": f"Manşet {id}",
                      "ig_caption": f"Açıklama {id}", "threads_metin": f"Threads {id}", "durum": "yeni", "detay_metni": None}
        veri = {**varsayilan, **kolon, "id": id}
        with db._baglanti_al() as conn:
            conn.execute(f"INSERT INTO haberler ({', '.join(veri)}) VALUES ({', '.join('?' for _ in veri)})", tuple(veri.values()))
            conn.commit()

    def ilan_ekle(self, id: str = "ilan-1", **kolon):
        varsayilan = {"baslik": "Satılık 3+1 Daire", "fiyat": 5250000.0, "ilce": "Silivri", "mahalle": "Merkez", "durum": "aktif",
                      "kaynak_url": "https://edmyapigayrimenkul.com/ilan/1", "gorseller_json": "[]"}
        veri = {**varsayilan, **kolon, "id": id}
        with db._baglanti_al() as conn:
            conn.execute(f"INSERT INTO ilanlar ({', '.join(veri)}) VALUES ({', '.join('?' for _ in veri)})", tuple(veri.values()))
            conn.commit()

    def onay_ekle(self, tur: str, ref: str, mesaj_id: int, durum: str = "bekliyor"):
        mid = db.onay_istegi_kaydet(tur, str(ref), mesaj_id, -100123)
        if durum != "bekliyor":
            with db._baglanti_al() as conn:
                conn.execute("UPDATE onay_istekleri SET durum = ? WHERE id = ?", (durum, mid))
                conn.commit()

    def db_ozeti(self) -> dict:
        n = self.norm
        sonuc: dict = {}
        with db._baglanti_al() as conn:
            sonuc["haberler"] = [n({k: dict(r).get(k) for k in (
                "id", "kaynak", "durum", "kategori", "manset", "slayt_yollari", "slayt_urlleri", "video_yolu", "detay_metni", "ig_caption",
                "threads_metin", "onem_puani", "planlanan_yayin") if k in dict(r)}) for r in conn.execute("SELECT * FROM haberler ORDER BY id")]
            sonuc["ilanlar"] = [n({k: dict(r).get(k) for k in ("id", "durum")}) for r in conn.execute("SELECT * FROM ilanlar ORDER BY id")]
            sonuc["onay_istekleri"] = [n({k: dict(r).get(k) for k in ("tur", "referans_id", "telegram_mesaj_id", "telegram_chat_id", "durum")})
                                       for r in conn.execute("SELECT * FROM onay_istekleri ORDER BY id")]
            sonuc["ayarlar"] = [n({"anahtar": r["anahtar"], "deger": r["deger"]}) for r in conn.execute("SELECT * FROM ayarlar ORDER BY anahtar")]
            sonuc["konu_gecmisi"] = [n({k: dict(r).get(k) for k in ("konu_kodu", "haber_id", "sonuc")}) for r in conn.execute("SELECT * FROM konu_gecmisi ORDER BY id")]
            sonuc["hata_kayitlari"] = [n({k: dict(r).get(k) for k in ("nerede", "baslik", "ham_hata")}) for r in conn.execute("SELECT * FROM hata_kayitlari ORDER BY id")]
        return sonuc


SENARYOLAR: list[dict] = []


def senaryo(ad: str, cagri, kur=None, donusler: dict | None = None, betik: dict | None = None, token: bool = True, env: dict | None = None):
    SENARYOLAR.append({"ad": ad, "cagri": cagri, "kur": kur, "donusler": donusler or {}, "betik": betik or {}, "token": token, "env": env or {}})


OK = "ok"
HATA_400 = (400, {"ok": False, "description": "Bad Request: wrong file identifier"})
PARSE_400 = (400, {"ok": False, "description": "Bad Request: can't parse entities: Unsupported start tag"})
ZAMAN_ASIMI = requests.exceptions.ReadTimeout("zaman aşımı")
BAGLANTI = requests.exceptions.ConnectionError("ağ yok")
DEGISMEDI_400 = (400, {"ok": False, "description": "Bad Request: message is not modified"})
SILINMIS_400 = (400, {"ok": False, "description": "Bad Request: message to delete not found"})
LIMIT_429 = (429, {"ok": False, "description": "Too Many Requests", "parameters": {"retry_after": 3}})
SUNUCU_502 = (502, {"ok": False, "description": "Bad Gateway"})
TASINDI = (400, {"ok": False, "description": "group chat was upgraded", "parameters": {"migrate_to_chat_id": -100999}})
CURL_400 = (400, {"ok": False, "description": "Bad Request: failed to send message #1 with error WEBPAGE_CURL_FAILED"})

# --- G1 mesaj_gonder ----------------------------------------------------------------------------------------------
senaryo("mesaj_basit", lambda o: tb.mesaj_gonder("Merhaba <b>dünya</b>"))
senaryo("mesaj_butonlu", lambda o: tb.mesaj_gonder("Seç", reply_markup={"inline_keyboard": [[{"text": "Evet", "callback_data": "evet"}]]}))
senaryo("mesaj_butonlar_takma_adi", lambda o: tb.mesaj_gonder("Seç", butonlar={"inline_keyboard": [[{"text": "A", "callback_data": "a"}]]}))
senaryo("mesaj_uzun_kesilir", lambda o: tb.mesaj_gonder("x" * 5000))
senaryo("mesaj_html_kapali", lambda o: tb.mesaj_gonder("<b>düz</b>", html=False))
senaryo("mesaj_html_hatasi_duz_metne_duser", lambda o: tb.mesaj_gonder("5 < 10 <b>kalın</b> &amp; x"), betik={"sendMessage": [PARSE_400, OK]})
senaryo("mesaj_429_bekler", lambda o: tb.mesaj_gonder("sınır"), betik={"sendMessage": [LIMIT_429, OK]})
senaryo("mesaj_sunucu_hatasi_yeniden", lambda o: tb.mesaj_gonder("502"), betik={"sendMessage": [SUNUCU_502, SUNUCU_502, OK]})
senaryo("mesaj_ag_hatasi_uc_deneme", lambda o: tb.mesaj_gonder("ağ"), betik={"sendMessage": [BAGLANTI, BAGLANTI, BAGLANTI]})
senaryo("mesaj_grup_tasindi", lambda o: tb.mesaj_gonder("göç"), betik={"sendMessage": [TASINDI, OK]})
senaryo("mesaj_kalici_hata", lambda o: tb.mesaj_gonder("red"), betik={"sendMessage": [HATA_400]})
senaryo("mesaj_token_yok", lambda o: tb.mesaj_gonder("jeton yok"), token=False)
senaryo("mesaj_callback_data_64_bayt_kesilir",
        lambda o: tb.mesaj_gonder("uzun", reply_markup={"inline_keyboard": [[{"text": "x", "callback_data": "k" * 90}]]}))
senaryo("istek_mesaj_degismedi_none", lambda o: tb._istek("editMessageText", message_id=1, text="a"), betik={"editMessageText": [DEGISMEDI_400]})
senaryo("istek_silinmis_mesaj_none", lambda o: tb._istek("deleteMessage", message_id=1), betik={"deleteMessage": [SILINMIS_400]})

# --- G2 fotograf / G3 video ---------------------------------------------------------------------------------------
senaryo("foto_yerel_dosya", lambda o: tb.fotograf_gonder(o.slaytlar(1)[0], caption="<b>Başlık</b>"))
senaryo("foto_butonlu", lambda o: tb.fotograf_gonder(o.slaytlar(1)[0], caption="b", reply_markup={"inline_keyboard": [[{"text": "t", "callback_data": "c"}]]}))
senaryo("foto_url_indirilip_yuklenir", lambda o: tb.fotograf_gonder("https://cdn.example.com/a.jpg", caption="url"))
senaryo("foto_url_indirilemez_dogrudan_url",
        lambda o: tb.fotograf_gonder("https://cdn.example.com/b.jpg", caption="url"),
        )
senaryo("foto_baslik_parse_hatasi", lambda o: tb.fotograf_gonder(o.slaytlar(1)[0], caption="<b>5 < 6"), betik={"sendPhoto": [PARSE_400, OK]})
senaryo("foto_zaman_asimi_yeniden", lambda o: tb.fotograf_gonder(o.slaytlar(1)[0]), betik={"sendPhoto": [ZAMAN_ASIMI, OK]})
senaryo("foto_hepsi_basarisiz", lambda o: tb.fotograf_gonder(o.slaytlar(1)[0]), betik={"sendPhoto": [ZAMAN_ASIMI, ZAMAN_ASIMI]})
senaryo("foto_token_yok", lambda o: tb.fotograf_gonder(o.slaytlar(1)[0]), token=False)
senaryo("foto_uzun_baslik_kesilir", lambda o: tb.fotograf_gonder(o.slaytlar(1)[0], caption="y" * 1500))
senaryo("video_yerel_butonlu", lambda o: tb.video_gonder(o.dosya("v", "a.mp4"), aciklama="<b>Video</b>",
                                                       butonlar={"inline_keyboard": [[{"text": "t", "callback_data": "c"}]]}))
senaryo("video_butonlar_liste", lambda o: tb.video_gonder(o.dosya("v", "a.mp4"), butonlar=[[{"text": "t", "callback_data": "c"}]]))
senaryo("video_dosya_yok", lambda o: tb.video_gonder(Path("/yok/yok.mp4")))
senaryo("video_parse_hatasi", lambda o: tb.video_gonder(o.dosya("v", "a.mp4"), aciklama="<b>5 < 6"), betik={"sendVideo": [PARSE_400, OK]})
senaryo("video_uc_hata", lambda o: tb.video_gonder(o.dosya("v", "a.mp4")), betik={"sendVideo": [ZAMAN_ASIMI, ZAMAN_ASIMI, ZAMAN_ASIMI]})

# --- G4 medya grubu -----------------------------------------------------------------------------------------------
senaryo("album_tekil_slayt", lambda o: tb.medya_grubu_gonder(o.slaytlar(1), caption="<b>Tek</b>"))
senaryo("album_tekil_yedek_url", lambda o: tb.medya_grubu_gonder(o.slaytlar(1), caption="t", yedek_urller=["https://cdn.example.com/1.jpg"]),
        betik={"sendPhoto": [ZAMAN_ASIMI, ZAMAN_ASIMI, OK]})
senaryo("album_uc_yerel", lambda o: tb.medya_grubu_gonder(o.slaytlar(3), caption="<b>Albüm</b>"))
senaryo("album_on_ikiden_ilk_on", lambda o: tb.medya_grubu_gonder(o.slaytlar(12), caption="c"))
senaryo("album_yerel_zaman_asimi_ikinci_deneme", lambda o: tb.medya_grubu_gonder(o.slaytlar(3), caption="c"),
        betik={"sendMediaGroup": [ZAMAN_ASIMI, OK]})
senaryo("album_yerel_zaman_asimi_yedek_url_albumu",
        lambda o: tb.medya_grubu_gonder(o.slaytlar(3), caption="c", yedek_urller=[f"https://cdn.example.com/{i}.jpg" for i in range(3)]),
        betik={"sendMediaGroup": [ZAMAN_ASIMI, OK]})
senaryo("album_yedek_url_sayisi_eslesmez_tek_tek",
        lambda o: tb.medya_grubu_gonder(o.slaytlar(3), caption="c", yedek_urller=["https://cdn.example.com/0.jpg"]),
        betik={"sendMediaGroup": [ZAMAN_ASIMI, ZAMAN_ASIMI]})
senaryo("album_hicbir_yol_tutmaz", lambda o: tb.medya_grubu_gonder(o.slaytlar(3), caption="c",
                                                                   yedek_urller=[f"https://cdn.example.com/{i}.jpg" for i in range(3)]),
        betik={"sendMediaGroup": [ZAMAN_ASIMI, ZAMAN_ASIMI, ZAMAN_ASIMI, ZAMAN_ASIMI], "sendPhoto": [ZAMAN_ASIMI] * 6})
senaryo("album_url_girdisi_webpage_curl_failed_indirip_yukler",
        lambda o: tb.medya_grubu_gonder([f"https://cdn.example.com/{i}.jpg" for i in range(3)], caption="c"),
        betik={"sendMediaGroup": [CURL_400, OK]})
senaryo("album_baslik_parse_hatasi", lambda o: tb.medya_grubu_gonder(o.slaytlar(3), caption="<b>5 < 6"), betik={"sendMediaGroup": [PARSE_400, OK]})
senaryo("album_429_bekler", lambda o: tb.medya_grubu_gonder(o.slaytlar(3), caption="c"), betik={"sendMediaGroup": [LIMIT_429, OK]})
senaryo("album_eksik_teslim_hata_kaydi", lambda o: tb.medya_grubu_gonder(o.slaytlar(3), caption="c"),
        betik={"sendMediaGroup": [ZAMAN_ASIMI, ZAMAN_ASIMI], "sendPhoto": [OK, HATA_400, OK]})
senaryo("album_bos_liste", lambda o: tb.medya_grubu_gonder([], caption="c"))
senaryo("album_token_yok", lambda o: tb.medya_grubu_gonder(o.slaytlar(3)), token=False)
senaryo("slaytlari_gonder_baslik_ilk", lambda o: tb.slaytlari_gonder(o.slaytlar(2), ["1. başlık", "2. başlık"]))

# --- G5 mesaj yaşam döngüsü ---------------------------------------------------------------------------------------
senaryo("mesaji_sil_tamam", lambda o: tb.mesaji_sil(11))
senaryo("mesaji_sil_bulunamadi", lambda o: tb.mesaji_sil(11), betik={"deleteMessage": [SILINMIS_400]})
senaryo("mesaji_guncelle_tamam", lambda o: tb.mesaji_guncelle(11, "yeni <b>metin</b>", reply_markup={"inline_keyboard": []}))
senaryo("mesaji_guncelle_degismedi", lambda o: tb.mesaji_guncelle(11, "aynı"), betik={"editMessageText": [DEGISMEDI_400]})
senaryo("menuyu_degistir_tamam", lambda o: tb.menuyu_degistir(11, {"inline_keyboard": [[{"text": "x", "callback_data": "y"}]]}))
senaryo("onceki_mesajlari_temizle", lambda o: tb.icerik_onceki_mesajlarini_temizle("haber", 5),
        kur=lambda o: [o.onay_ekle("haber", "5", 31), o.onay_ekle("haber", "5", 32), o.onay_ekle("haber", "5", 33, durum="silindi")])
senaryo("onceki_mesajlari_temizle_haric", lambda o: tb.icerik_onceki_mesajlarini_temizle("haber", 5, haric_mesaj_id=32),
        kur=lambda o: [o.onay_ekle("haber", "5", 31), o.onay_ekle("haber", "5", 32)])
senaryo("onceki_mesajlari_temizle_reels_haber_ortak", lambda o: tb.icerik_onceki_mesajlarini_temizle("reels", 6),
        kur=lambda o: [o.onay_ekle("haber", "6", 41), o.onay_ekle("reels", "6", 42)])
senaryo("son_mesajlari_sil", lambda o: tb.son_mesajlari_sil(2), kur=lambda o: [o.onay_ekle("haber", "1", 51), o.onay_ekle("haber", "2", 52)])

# --- G6 durum metinleri ve sonuç kartları -------------------------------------------------------------------------
senaryo("aciklama_kutusu", lambda o: tb.aciklama_metni_kutusu("  <metin> & ek  "))
senaryo("durum_metni_surerken", lambda o: tb.yayin_durum_metni_olustur("Başlık", 1, 3, {"instagram": "✅ Yayında", "threads": "⏳ Yükleniyor...", "x": "⏱️ Sırada"}))
senaryo("durum_metni_tamamlandi", lambda o: tb.yayin_durum_metni_olustur("Başlık", 2, 2, {"instagram": "✅ Yayında", "youtube": "❌ Hata"}, baslangic_ts=1.0))
senaryo("durum_metni_telafi", lambda o: tb.yayin_durum_metni_olustur("", 0, 0, {"tt": "⏱️ Sırada"}, is_telafi=True))
senaryo("canli_durum_mesaj_yok", lambda o: tb.canli_yayin_durumu_guncelle(None, "b", 0, 1, {}))
senaryo("canli_durum_guncellenir", lambda o: tb.canli_yayin_durumu_guncelle(11, "b", 1, 2, {"ig": "✅ Yayında"}))
senaryo("sonucu_yaz_duzenler", lambda o: tb.sonucu_yaz(11, "sonuç", reply_markup={"inline_keyboard": []}))
senaryo("sonucu_yaz_bildir", lambda o: tb.sonucu_yaz(None, "sonuç", bildir=True))
senaryo("sonucu_yaz_ek_dugmeler", lambda o: tb.sonucu_yaz(11, "sonuç", bildir=True, ek_dugmeler=[[{"text": "a", "callback_data": "b"}]]))
senaryo("durum_guncelle_cubuk", lambda o: tb.durum_guncelle(11, "<Başlık>", 2, 4, "ayrıntı <i>"))
senaryo("durum_guncelle_sinirlar", lambda o: tb.durum_guncelle(11, "B", 99, 0))
senaryo("yayindan_kaldir_tum_kimlikler", lambda o: tb.yayindan_kaldir("haber", 60, mesaj_id=70, basan="Ali <x>"),
        kur=lambda o: o.haber_ekle(60, durum="yayinlandi", facebook_post_id="FB1", threads_post_id="TH1", instagram_post_id="IG1",
                                   youtube_video_id="YT1", linkedin_post_id="LI1"))
senaryo("yayindan_kaldir_kimliksiz", lambda o: tb.yayindan_kaldir("haber", 61), kur=lambda o: o.haber_ekle(61, durum="hata"))
senaryo("yayindan_kaldir_silinemedi", lambda o: tb.yayindan_kaldir("haber", 62),
        kur=lambda o: o.haber_ekle(62, durum="yayinlandi", facebook_post_id="FB2", threads_post_id="TH2"),
        donusler={"facebook.postu_sil": False, "threads.zinciri_sil": (0, 3)})
senaryo("yayindan_kaldir_ilan", lambda o: tb.yayindan_kaldir("ilan", "ilan-1"), kur=lambda o: o.ilan_ekle("ilan-1", durum="hata"))
senaryo("yayindan_kaldir_bulunamadi", lambda o: tb.yayindan_kaldir("haber", 999))
senaryo("yayindan_kaldir_uygun_degil", lambda o: tb.yayindan_kaldir("haber", 63), kur=lambda o: o.haber_ekle(63, durum="iptal"))

# --- G7 duraklatma ve kanal ayarı ---------------------------------------------------------------------------------
senaryo("duraklat_suresiz", lambda o: (tb.bot_duraklat(0), tb.bot_duraklatildi_mi()))
senaryo("duraklat_uc_saat", lambda o: (tb.bot_duraklat(3), tb.bot_duraklatildi_mi()))
senaryo("duraklat_bitmis_temizlenir", lambda o: tb.bot_duraklatildi_mi(),
        kur=lambda o: db.ayar_yaz("bot_duraklatildi_bitis", (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()))
senaryo("duraklat_bozuk_deger", lambda o: tb.bot_duraklatildi_mi(), kur=lambda o: db.ayar_yaz("bot_duraklatildi_bitis", "yarin"))
senaryo("duraklat_devam_et", lambda o: (tb.bot_duraklat(0), tb.bot_devam_et(), tb.bot_duraklatildi_mi()))
senaryo("duraklat_hic_ayarlanmamis", lambda o: tb.bot_duraklatildi_mi())
senaryo("kanallar_varsayilan", lambda o: tb.varsayilan_kanallar())
senaryo("kanallar_kayitli", lambda o: tb.varsayilan_kanallar(), kur=lambda o: db.ayar_yaz("aktif_kanallar", json.dumps({"ig": False, "reels": True})))
senaryo("kanallar_bozuk_kayit", lambda o: tb.varsayilan_kanallar(), kur=lambda o: db.ayar_yaz("aktif_kanallar", "{bozuk"))
senaryo("kanal_ayarla_reels_ig_kapatir", lambda o: tb.kanal_ayarla("reels", True))
senaryo("kanal_ayarla_ig_reels_kapatir", lambda o: (tb.kanal_ayarla("reels", True), tb.kanal_ayarla("ig", True)))
senaryo("kanal_ayarla_kapat", lambda o: tb.kanal_ayarla("threads", False))
senaryo("kanal_butonlari_varsayilan", lambda o: tb.kanal_butonlari())
senaryo("kanal_butonlari_ozel", lambda o: tb.kanal_butonlari({"ig": False, "reels": True, "linkedin": False}))
senaryo("secili_kanallar_bos", lambda o: (tb.secili_kanallari_cikar(None), tb.secili_kanallari_cikar([]), tb.secili_kanallari_cikar([[{"text": "x", "callback_data": "y"}]])))
senaryo("secili_kanallar_menuden", lambda o: tb.secili_kanallari_cikar(tb.kanal_butonlari({"ig": False, "reels": True, "story": False})))
senaryo("kanal_toggle_reels", lambda o: tb.kanal_toggle(tb.kanal_butonlari(), "reels"))
senaryo("kanal_toggle_ig_reelsi_kapatir", lambda o: tb.kanal_toggle(tb.kanal_butonlari({"ig": False, "reels": True}), "ig"))
senaryo("kanal_toggle_threads", lambda o: tb.kanal_toggle(tb.kanal_butonlari(), "threads"))
senaryo("kanal_toggle_olmayan", lambda o: tb.kanal_toggle(tb.kanal_butonlari(), "yok"))

# --- G8 menüler (saf işlevler) ------------------------------------------------------------------------------------
KANAL_OZEL = {"ig": False, "reels": True, "story": True, "threads": False, "facebook": True, "youtube": False, "tiktok": True, "linkedin": False}
senaryo("menu_ana_varsayilan", lambda o: tb.ana_menu())
senaryo("menu_ana_ozel", lambda o: tb.ana_menu(adet=5, kanallar=KANAL_OZEL))
senaryo("menu_yayin_zamani", lambda o: tb.yayin_zamani_menusu(adet=3, kanallar=KANAL_OZEL))
senaryo("menu_ses", lambda o: tb.ses_menusu(adet=4))
senaryo("menu_sesli_zaman_muzikli", lambda o: tb.sesli_yayin_zamani_menusu("muzikli", 2))
senaryo("menu_sesli_zaman_muziksiz", lambda o: tb.sesli_yayin_zamani_menusu("muziksiz", 2, KANAL_OZEL))
senaryo("menu_sesli_zaman_bozuk_kip", lambda o: tb.sesli_yayin_zamani_menusu("bilinmeyen", 2))
senaryo("menu_foto", lambda o: tb.foto_menusu(adet=3))
senaryo("menu_metin", lambda o: tb.metin_menusu(adet=3))
senaryo("menu_slayt_secim_tek", lambda o: tb.slayt_secim_menusu(adet=1))
senaryo("menu_slayt_secim_uc", lambda o: tb.slayt_secim_menusu(adet=3))
senaryo("menu_slayt_secim_yedi", lambda o: tb.slayt_secim_menusu(adet=7))
senaryo("menu_slayt_islem_tek_slayt", lambda o: tb.slayt_islem_menusu(1, 1))
senaryo("menu_slayt_islem_ilk_uc", lambda o: tb.slayt_islem_menusu(1, 3))
senaryo("menu_slayt_islem_orta", lambda o: tb.slayt_islem_menusu(2, 3))
senaryo("menu_slayt_islem_son", lambda o: tb.slayt_islem_menusu(3, 3))
senaryo("menu_slayt_islem_iki_slayt", lambda o: tb.slayt_islem_menusu(2, 2))
senaryo("menu_onay_geriye_uyum", lambda o: tb.onay_menusu(5))
senaryo("menu_reels_onay_geriye_uyum", lambda o: (tb.reels_onay_menusu(5), tb.reels_onay_menusu(5, KANAL_OZEL)))
senaryo("menu_metin_foto_secim_geriye_uyum", lambda o: (tb.metin_secim_menusu(5), tb.foto_secim_menusu(5, "reels")))
senaryo("menu_format_secim", lambda o: tb.format_secim_menusu(42))
senaryo("menu_kontrol_merkezi", lambda o: (tb.kontrol_merkezi_menusu(), tb.kontrol_merkezi_menusu(True, "2 sa 5 dk")))
senaryo("menu_duraklatma_secenekleri", lambda o: tb.duraklatma_secenekleri_menusu())
senaryo("menu_ayar", lambda o: tb.ayar_menusu())

# --- G9 kartlar ---------------------------------------------------------------------------------------------------
DETAY_KART = json.dumps({"format_turu": "dailybrief", "spot": "Spot " * 80}, ensure_ascii=False)
senaryo("kart_incele_bulunamadi", lambda o: tb.icerik_incele_karti(999))
senaryo("kart_incele_icerik", lambda o: tb.icerik_incele_karti(80),
        kur=lambda o: o.haber_ekle(80, durum="onay_bekliyor", detay_metni=DETAY_KART, slayt_yollari=json.dumps(["a.jpg", "b.jpg"])))
senaryo("kart_incele_bozuk_detay", lambda o: tb.icerik_incele_karti(81), kur=lambda o: o.haber_ekle(81, durum="cop", detay_metni="{bozuk"))
senaryo("kart_incele_ham_haber", lambda o: tb.icerik_incele_karti(82),
        kur=lambda o: o.haber_ekle(82, kaynak="Emlakkulisi", orijinal_baslik="Ham haber başlığı", orijinal_ozet="Ham özet", manset=None))
senaryo("incele_gonder_bulunamadi", lambda o: tb.icerik_incele_gonder(999))
senaryo("incele_gonder_fotografli", lambda o: tb.icerik_incele_gonder(83),
        kur=lambda o: o.haber_ekle(83, durum="onay_bekliyor", slayt_urlleri=json.dumps(["https://cdn.example.com/s1.jpg"])))
senaryo("incele_gonder_yerel_yoldan", lambda o: tb.icerik_incele_gonder(84),
        kur=lambda o: o.haber_ekle(84, durum="yayinlandi", slayt_yollari=json.dumps([str(o.slaytlar(1, onek="x84")[0])])))
senaryo("incele_gonder_gorselsiz_metin", lambda o: tb.icerik_incele_gonder(85), kur=lambda o: o.haber_ekle(85, durum="iptal"))
senaryo("incele_gonder_foto_basarisiz_metne_duser", lambda o: tb.icerik_incele_gonder(86),
        kur=lambda o: o.haber_ekle(86, durum="onay_bekliyor", gorsel_url="https://cdn.example.com/g.jpg"),
        betik={"sendPhoto": [HATA_400, HATA_400]})
senaryo("havuz_mesaji", lambda o: tb.havuz_mesaji())
senaryo("havuz_mesaji_tuketim_yok", lambda o: tb.havuz_mesaji(), donusler={"konu_bankasi.durum_ozeti": lambda o: dict(OZET, kalan_gun=None, gunluk_tuketim=0)})
senaryo("son_postlar_bos", lambda o: tb.son_postlar_raporu())
senaryo("son_postlar_dolu", lambda o: tb.son_postlar_raporu(),
        kur=lambda o: [o.haber_ekle(90, durum="yayinlandi"), o.haber_ekle(91, durum="onay_bekliyor"), o.haber_ekle(92, durum="iptal", manset=None),
                       o.haber_ekle(93), o.haber_ekle(94), o.haber_ekle(95)])
senaryo("yayin_kontrol_bulunamadi", lambda o: tb.yayin_kontrol_karti(999))
senaryo("yayin_kontrol_kismi", lambda o: tb.yayin_kontrol_karti(96),
        kur=lambda o: o.haber_ekle(96, durum="hata", instagram_post_id="IG9", youtube_video_id="YT9"))
senaryo("yayin_kontrol_tam", lambda o: tb.yayin_kontrol_karti(97),
        kur=lambda o: o.haber_ekle(97, durum="yayinlandi", instagram_post_id="IG", threads_post_id="TH", facebook_post_id="FB",
                                   youtube_video_id="YT", tiktok_publish_id="TT", linkedin_post_id="LI"))
senaryo("panel_yeni_mesaj", lambda o: tb.panel_gonder())
senaryo("panel_mesaji_gunceller", lambda o: tb.panel_gonder(mesaj_id=11))
senaryo("panel_duraklatilmis", lambda o: tb.panel_gonder(), kur=lambda o: db.ayar_yaz("bot_duraklatildi_bitis", "suresiz"))
senaryo("durum_raporu_yeni", lambda o: tb.durum_raporu_gonder(),
        kur=lambda o: o.haber_ekle(98, durum="yayinlandi", yayin_tarihi="2026-10-01"))
senaryo("durum_raporu_guncelle_kayit_yok", lambda o: tb.durum_raporu_gonder(mesaj_id=11))
senaryo("kota_gonder", lambda o: tb.kota_gonder(mesaj_id=11, kategori=2))
senaryo("komut_menusu_kaydet", lambda o: tb.komut_menusu_kaydet())
senaryo("komut_menusu_bir_kapsam_basarisiz", lambda o: tb.komut_menusu_kaydet(), betik={"setMyCommands": ["ok", HATA_400]})
senaryo("komut_menusu_token_yok", lambda o: tb.komut_menusu_kaydet(), token=False)

# --- G10 akışlar: onay kartı --------------------------------------------------------------------------------------
def _onay_haber(id: int, detay: dict | None, adet: int = 0, **kolon):
    def kur(o):
        ek = dict(kolon)
        if adet:
            ek["slayt_yollari"] = json.dumps([str(p) for p in o.slaytlar(adet, onek=f"k{id}")])
        o.haber_ekle(id, detay_metni=json.dumps(detay, ensure_ascii=False) if detay is not None else None, **ek)
    return kur


senaryo("onay_sozluk_tek_slayt", lambda o: tb.haber_onayina_sun(101), kur=_onay_haber(101, dict(VERI, format_turu="sozluk")))
senaryo("onay_nedir_dogrusu", lambda o: tb.haber_onayina_sun(102), kur=_onay_haber(102, dict(VERI, format_turu="nedir_dogrusu")))
senaryo("onay_vaka", lambda o: tb.haber_onayina_sun(103), kur=_onay_haber(103, dict(VERI, format_turu="vaka")))
senaryo("onay_net_cevap", lambda o: tb.haber_onayina_sun(104), kur=_onay_haber(104, dict(VERI, format_turu="net_cevap")))
senaryo("onay_dailybrief_haber", lambda o: tb.haber_onayina_sun(105), kur=_onay_haber(105, dict(VERI, format_turu="dailybrief")))
senaryo("onay_reels_story_olcu", lambda o: tb.haber_onayina_sun(106), kur=_onay_haber(106, dict(VERI, format_turu="reels", bicim="dailybrief"), kategori="REELS"))
senaryo("onay_otorite_b1", lambda o: tb.haber_onayina_sun(107), kur=_onay_haber(107, dict(VERI, bicim="B1", rozet_metni="ÖZEL ROZET & TEST", yasal_dayanak="A < B & C")))
senaryo("onay_ham_haber_detaysiz", lambda o: tb.haber_onayina_sun(108), kur=_onay_haber(108, None, orijinal_ozet="Ham özet"))
senaryo("onay_manset_yok_metin_uretilir", lambda o: tb.haber_onayina_sun(109), kur=_onay_haber(109, None, manset=None, orijinal_baslik="Başlık"))
senaryo("onay_metin_uretilemez", lambda o: tb.haber_onayina_sun(110), kur=_onay_haber(110, None, manset=None),
        donusler={"generate_text.haber_metinleri_uret": None})
senaryo("onay_haber_yok", lambda o: tb.haber_onayina_sun(999))
senaryo("onay_mevcut_slaytlar_yeniden_cizilmez", lambda o: tb.haber_onayina_sun(111, yeniden_ciz=False),
        kur=_onay_haber(111, dict(VERI, format_turu="dailybrief"), adet=3))
senaryo("onay_album_gitmez_uyari_notu", lambda o: tb.haber_onayina_sun(112), kur=_onay_haber(112, dict(VERI, format_turu="dailybrief")),
        betik={"sendMediaGroup": [ZAMAN_ASIMI] * 10, "sendPhoto": [ZAMAN_ASIMI] * 10})
senaryo("onay_karti_ilk_deneme_gitmez_kisa_kart", lambda o: tb.haber_onayina_sun(113), kur=_onay_haber(113, dict(VERI, format_turu="sozluk")),
        betik={"sendMessage": [HATA_400]})
senaryo("onay_oncesi_mesajlar_temizlenir", lambda o: tb.haber_onayina_sun(114),
        kur=lambda o: [_onay_haber(114, dict(VERI, format_turu="sozluk"))(o), o.onay_ekle("haber", "114", 21), o.onay_ekle("haber_album", "114", 22)])
senaryo("onay_kapi_durdurur", lambda o: tb.haber_onayina_sun(115), kur=_onay_haber(115, dict(VERI, format_turu="sozluk")),
        donusler={"dogrula.icerigi_denetle": ["⛔ SÜRE KAYNAKTA YOK: 2 yıl"]})
senaryo("onay_uyari_baslikli", lambda o: tb.haber_onayina_sun(116), kur=_onay_haber(116, dict(VERI, format_turu="sozluk")),
        donusler={"dogrula.icerigi_denetle": ["⚠️ ABARTI DİLİ: \"kaçırmayın\" geçiyor."]})
senaryo("onay_eksik_icerik_bildirilir", lambda o: tb.haber_onayina_sun(117), kur=_onay_haber(117, dict(VERI, format_turu="dailybrief")),
        donusler={"resim.eksik": True})
senaryo("onay_oto_yayin_basarili", lambda o: tb.haber_onayina_sun(118, oto_yayin=True), kur=_onay_haber(118, dict(VERI, format_turu="sozluk")))
senaryo("onay_oto_yayin_alt_surec_hatasi", lambda o: tb.haber_onayina_sun(119, oto_yayin=True), kur=_onay_haber(119, dict(VERI, format_turu="sozluk")),
        donusler={"alt_surec.hata": True})
senaryo("onay_oto_yayin_uyari_onaya_duser", lambda o: tb.haber_onayina_sun(120, oto_yayin=True), kur=_onay_haber(120, dict(VERI, format_turu="sozluk")),
        donusler={"dogrula.icerigi_denetle": ["⚠️ ABARTI DİLİ"]})
senaryo("onay_yeniden_cizim_ilan_degil_cok_slayt_sozluk_kart_anlam_yok", lambda o: tb.haber_onayina_sun(121),
        kur=_onay_haber(121, dict(VERI, format_turu="sozluk", _brief={"kart": True})))

# --- G11 akışlar: üretim zinciri ----------------------------------------------------------------------------------
senaryo("sozluk_karti_otomatik", lambda o: tb.sozluk_karti_hazirla_ve_sun(oto_yayin=True))
senaryo("sozluk_karti_onaya", lambda o: tb.sozluk_karti_hazirla_ve_sun(oto_yayin=False))
senaryo("sozluk_karti_anahtara_bakar_kapali", lambda o: tb.sozluk_karti_hazirla_ve_sun())
senaryo("sozluk_karti_anahtar_db_acik", lambda o: tb.sozluk_karti_hazirla_ve_sun(), kur=lambda o: db.ayar_yaz("sozluk_oto_yayin", "1"))
senaryo("sozluk_karti_anahtar_kapatilmis", lambda o: tb.sozluk_karti_hazirla_ve_sun(oto_yayin=True), kur=lambda o: db.ayar_yaz("sozluk_oto_yayin", "0"))
senaryo("sozluk_karti_kanun_dogrulanamadi", lambda o: tb.sozluk_karti_hazirla_ve_sun(oto_yayin=True), donusler={"sozluk_arsivi.kart_kanun_durumu": (None, [])})
senaryo("sozluk_karti_bot_duraklatilmis", lambda o: tb.sozluk_karti_hazirla_ve_sun(oto_yayin=True), kur=lambda o: db.ayar_yaz("bot_duraklatildi_bitis", "suresiz"))
senaryo("sozluk_karti_bugun_zaten_yayinlandi", lambda o: tb.sozluk_karti_hazirla_ve_sun(oto_yayin=True),
        kur=lambda o: db.ayar_yaz("sozluk_oto_son_gun", _bugun_tr()))
senaryo("sozluk_karti_stok_azaliyor", lambda o: tb.sozluk_karti_hazirla_ve_sun(oto_yayin=False), donusler={"sozluk_arsivi.stok_kalan": 5})
senaryo("sozluk_karti_kart_yok_none", lambda o: tb.sozluk_karti_hazirla_ve_sun(oto_yayin=True), donusler={"sozluk_arsivi.sonraki_kart": None})
senaryo("sozluk_karti_kanunla_uyusmuyor_sonrakine_gecer", lambda o: tb.sozluk_karti_hazirla_ve_sun(oto_yayin=False),
        donusler={"sozluk_arsivi.kart_kanun_durumu": lambda o, kart: (False, ["md. 5 değişmiş"]) if kart["kod"] == "SZ-001" else (True, []),
                  "sozluk_arsivi.sonraki_kart": lambda o, haric=None, **k: dict(KART, kod="SZ-002", terim="İRTİFAK") if haric else dict(KART)})
senaryo("slot_sozluk", lambda o: tb.slot_icerigi_hazirla_ve_sun("sozluk", oto_yayin=True))
senaryo("slot_sozluk_kart_kalmadi_modelle", lambda o: tb.slot_icerigi_hazirla_ve_sun("sozluk"), donusler={"sozluk_arsivi.sonraki_kart": None})
senaryo("slot_haber", lambda o: tb.slot_icerigi_hazirla_ve_sun("haber"))
senaryo("slot_bilgilendirici_b1", lambda o: tb.slot_icerigi_hazirla_ve_sun("bilgilendirici"))
senaryo("slot_bilgilendirici_nedir_dogrusu", lambda o: tb.slot_icerigi_hazirla_ve_sun(), donusler={"konu_bankasi.siradaki_bilgilendirici_format": "nedir_dogrusu"})
senaryo("slot_bilgilendirici_sozluk_formati", lambda o: tb.slot_icerigi_hazirla_ve_sun(oto_yayin=False),
        donusler={"konu_bankasi.siradaki_bilgilendirici_format": "sozluk"})
senaryo("slot_bilgilendirici_basarisiz_format_kaydedilmez", lambda o: tb.slot_icerigi_hazirla_ve_sun(),
        donusler={"konu_bankasi.sonraki_konu": None})
senaryo("hizli_nedir_dogrusu", lambda o: tb.hizli_icerik_uret("nedir_dogrusu"))
senaryo("hizli_sozluk", lambda o: tb.hizli_icerik_uret("sozluk"))
senaryo("hizli_vaka_konu_yok", lambda o: tb.hizli_icerik_uret("vaka"), donusler={"konu_bankasi.sonraki_konu": None})
senaryo("hizli_net_cevap_uretim_yok", lambda o: tb.hizli_icerik_uret("net_cevap"), donusler={"generate_text.konudan_uret": None})
senaryo("hizli_format_yok", lambda o: tb.hizli_icerik_uret())
senaryo("hizli_reels_yonlendirir", lambda o: tb.hizli_icerik_uret("reels"))
senaryo("hizli_rotasyon_yonlendirir", lambda o: tb.hizli_icerik_uret("rotasyon"))
senaryo("hizli_haber_yonlendirir", lambda o: tb.hizli_icerik_uret("haber"))
senaryo("hizli_b1_yonlendirir", lambda o: tb.hizli_icerik_uret("b1"))
senaryo("konu_bankasindan_ok", lambda o: tb.konu_bankasindan_hazirla(gun=2))
senaryo("konu_bankasindan_konu_yok", lambda o: tb.konu_bankasindan_hazirla(), donusler={"konu_bankasi.sonraki_konu": None})
senaryo("konu_bankasindan_uretim_yok", lambda o: tb.konu_bankasindan_hazirla(), donusler={"generate_text.konudan_uret": None})
senaryo("reels_hazirla_ok", lambda o: tb.reels_hazirla_ve_sun())
senaryo("reels_hazirla_konu_kodu_verildi", lambda o: tb.reels_hazirla_ve_sun("S1-001"))
senaryo("reels_hazirla_konu_kodu_bulunamadi", lambda o: tb.reels_hazirla_ve_sun("YOK-9"))
senaryo("reels_hazirla_konu_yok", lambda o: tb.reels_hazirla_ve_sun(), donusler={"konu_bankasi.sonraki_konu": None})
senaryo("reels_hazirla_uretim_yok", lambda o: tb.reels_hazirla_ve_sun(), donusler={"generate_text.konudan_uret": None})
senaryo("reels_hazirla_eksik_icerik", lambda o: tb.reels_hazirla_ve_sun(), donusler={"resim.eksik": True})
senaryo("format_degistir_ok", lambda o: tb.format_degistir_ve_sun(130, "nedir_dogrusu"), kur=_onay_haber(130, dict(VERI, format_turu="sozluk"), adet=2))
senaryo("format_degistir_detaysiz", lambda o: tb.format_degistir_ve_sun(131, "vaka"), kur=lambda o: o.haber_ekle(131))
senaryo("format_degistir_yok", lambda o: tb.format_degistir_ve_sun(999, "vaka"))
HABER_HAM = {"id": 140, "orijinal_baslik": "Emlak vergisinde yeni dönem", "orijinal_ozet": "Özet", "kaynak": "Emlakkulisi",
             "gorsel_url": "https://haber.example/g.jpg", "orijinal_url": "https://haber.example/h", "makale_metni": "Gövde " * 200}
BRIEF = {"sutun": "S1", "bicim": "B5", "_guven": 7, "baslik": "", "aci": "A"}
senaryo("haberden_icerik_ok", lambda o: tb.haberden_icerik_hazirla(dict(HABER_HAM), dict(BRIEF)),
        kur=lambda o: o.haber_ekle(140, kaynak="Emlakkulisi", manset=None, orijinal_baslik="Emlak vergisinde yeni dönem"))
senaryo("haberden_icerik_uretim_yok", lambda o: tb.haberden_icerik_hazirla(dict(HABER_HAM), dict(BRIEF)),
        kur=lambda o: o.haber_ekle(140), donusler={"generate_text.konudan_uret": None})
senaryo("otorite_postu_ok", lambda o: tb.otorite_postu_hazirla_ve_sor("Tapu harcı nasıl hesaplanır? " * 4, "TAPU_VE_HUKUK"))
senaryo("otorite_postu_uretim_yok", lambda o: tb.otorite_postu_hazirla_ve_sor("Konu"), donusler={"generate_text.otorite_icerigi_uret": None})
senaryo("ilan_menusu_dolu", lambda o: tb.tek_tikla_ilan_menusu_gonder())
senaryo("ilan_menusu_bos", lambda o: tb.tek_tikla_ilan_menusu_gonder(), donusler={"fetch_listings.aktif_ilanlar": []})
senaryo("ilan_postu_ok", lambda o: tb.ilan_postunu_hazirla_ve_sor("ilan-1"), kur=lambda o: o.ilan_ekle("ilan-1"))
senaryo("ilan_postu_bulunamadi", lambda o: tb.ilan_postunu_hazirla_ve_sor("yok"))
senaryo("ilan_postu_cdn_yuklenemez", lambda o: tb.ilan_postunu_hazirla_ve_sor("ilan-1"), kur=lambda o: o.ilan_ekle("ilan-1"),
        donusler={"upload_image.coklu_gorsel_yukle": RuntimeError("imgbb")})
senaryo("ilan_postu_metin_uretilemez_varsayilan_caption", lambda o: tb.ilan_postunu_hazirla_ve_sor("ilan-1"), kur=lambda o: o.ilan_ekle("ilan-1"),
        donusler={"generate_text.ilan_metinleri_uret": None})
senaryo("ilan_postu_album_gitmez", lambda o: tb.ilan_postunu_hazirla_ve_sor("ilan-1"), kur=lambda o: o.ilan_ekle("ilan-1"),
        betik={"sendMediaGroup": [ZAMAN_ASIMI] * 10, "sendPhoto": [ZAMAN_ASIMI] * 10})
senaryo("finans_oto_yayin", lambda o: tb.finans_icerigi_hazirla_ve_yayinla(oto_yayin=True))
senaryo("finans_onaya_duser_oto_kapali", lambda o: tb.finans_icerigi_hazirla_ve_yayinla(oto_yayin=False))
senaryo("finans_kapi_oto_yayini_durdurur", lambda o: tb.finans_icerigi_hazirla_ve_yayinla(oto_yayin=True),
        donusler={"dogrula.otomatik_yayina_uygun_mu": (False, ["⚠️ RAKAM KAYNAKSIZ", "⚠️ ABARTI"])})
senaryo("finans_konu_yok", lambda o: tb.finans_icerigi_hazirla_ve_yayinla(), donusler={"konu_bankasi.sonraki_finans_konusu": None})
senaryo("finans_uretim_yok", lambda o: tb.finans_icerigi_hazirla_ve_yayinla(), donusler={"generate_text.konudan_uret": None})
senaryo("finans_eksik_icerik", lambda o: tb.finans_icerigi_hazirla_ve_yayinla(), donusler={"resim.eksik": True})
senaryo("finans_alt_surec_hatasi", lambda o: tb.finans_icerigi_hazirla_ve_yayinla(oto_yayin=True), donusler={"alt_surec.hata": True})
senaryo("finans_video_uretilemez_yine_yayinlar", lambda o: tb.finans_icerigi_hazirla_ve_yayinla(oto_yayin=True),
        donusler={"video.slaytlardan_reels_uret": RuntimeError("ffmpeg")})


def calistir(sen: dict) -> dict:
    o = Ortam(sen["donusler"], sen["betik"], sen["token"])
    istisna = None
    donus = None
    try:
        o.baslat()
        if sen["kur"]:
            sen["kur"](o)
        with patch.dict(os.environ, sen["env"], clear=False):
            try:
                donus = sen["cagri"](o)
            except BaseException as e:  # noqa: BLE001 — hata türü ve metni davranışın parçasıdır
                istisna = f"{type(e).__name__}: {o.norm(str(e))}"
        return {
            "donus": o.norm(donus),
            "istisna": istisna,
            "http": o.tg.istekler,
            "cagrilar": sorted(o.kayitci.cagrilar),
            "db": o.db_ozeti(),
        }
    finally:
        o.bitir()


class TestTelegramAltin(unittest.TestCase):
    maxDiff = None

    def test_senaryolar_altin_cikti_ile_ayni(self):
        adlar = [s["ad"] for s in SENARYOLAR]
        self.assertEqual(len(adlar), len(set(adlar)), "senaryo adları benzersiz olmalı")
        mevcut = {sen["ad"]: calistir(sen) for sen in SENARYOLAR}

        if KAYDET:
            secili = {a.strip() for a in os.environ.get("TELEGRAM_ALTIN_SENARYO", "").split(",") if a.strip()}
            kaydedilecek = mevcut
            if secili and ALTIN_YOLU.exists():
                kaydedilecek = json.loads(ALTIN_YOLU.read_text(encoding="utf-8"))
                kaydedilecek.update({ad: v for ad, v in mevcut.items() if ad in secili})
            ALTIN_YOLU.parent.mkdir(parents=True, exist_ok=True)
            ALTIN_YOLU.write_text(json.dumps(kaydedilecek, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            self.skipTest(f"Altın çıktı yeniden kaydedildi: {len(secili) or len(mevcut)} senaryo")

        self.assertTrue(ALTIN_YOLU.exists(), "tests/altin/telegram.json yok: TELEGRAM_ALTIN_KAYDET=1 ile kaydedin")
        altin = json.loads(ALTIN_YOLU.read_text(encoding="utf-8"))
        self.assertEqual(sorted(altin), sorted(mevcut), "senaryo kümesi altın çıktıdan farklı")
        farklar = []
        for ad in sorted(mevcut):
            a = json.dumps(altin[ad], ensure_ascii=False, indent=1, sort_keys=True).splitlines()
            m = json.dumps(mevcut[ad], ensure_ascii=False, indent=1, sort_keys=True).splitlines()
            if a != m:
                farklar.append(f"### {ad}\n" + "\n".join(difflib.unified_diff(a, m, "altin", "mevcut", lineterm="", n=2)))
        self.assertFalse(farklar, "\n\n".join(farklar)[:12000])

    def test_senaryolar_tekrarlanabilir(self):
        """Aynı senaryo iki kez koşunca aynı çıktı: altın çıktı belirlenimci olmalı."""
        for sen in SENARYOLAR[::9]:
            self.assertEqual(calistir(sen), calistir(sen), sen["ad"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
