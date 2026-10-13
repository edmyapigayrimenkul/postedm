"""
tests/test_sozluk_oto_yayin_guvenceleri.py — Sözlük kartlarının onaysız yayınındaki güvenceler (2026-10-08).

Otomatik yayın (zamanlanmış 12:30 işi `--oto-yayin` bayrağıyla gelir) YALNIZCA şu koşulların hepsinde olur: kart
hazır arşivden (model yazmadı), kanun metni alındı ve kartla tutuyor, anahtar açıkça kapatılmamış, bot
duraklatılmamış, bugün başka otomatik sözlük yayınlanmamış, denetim kapısı UYARISIZ. Biri eksikse kart onaya
düşer; içerik hiçbir zaman kaybolmaz. Bu dosya o koşulların her birini, eksik olunca ne olduğunu ve acil freni
sınar; `test_sozluk_oto_yayin.py` ise zamanlama ve yayın betiği bağlantısını. Ağ yok; yayın betiği ve Telegram sahte.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from src import db, durum_kurali, konu_bankasi, sozluk_arsivi as sa, telegram_bot as tb

KART = {
    "kod": "SZ-950", "terim": "GÜVENCE BEDELİ", "kategori_kodu": "KIRA_VE_TAHLIYE",
    "tanim": "Konut ve çatılı işyeri kiralarında kiracıdan sözleşmeyle istenen güvencedir; üç aylık kira bedelini aşamaz.",
    "puf": ["Para olarak verilirse kiracı vadeli hesaba yatırır.", "Banka güvenceyi iki tarafın rızasıyla geri verir."],
    "mevzuat": "Türk Borçlar Kanunu md. 342",
    "dayanak_alintisi": "Konut ve çatılı işyeri kiralarında sözleşmeyle kiracıya güvence verme borcu getirilmişse, bu güvence üç aylık kira bedelini aşamaz.",
    "kontrol": "2026-10-08",
}


class _DbAyariSahte(unittest.TestCase):
    """DB ayarı sahte: yerel DB'deki gerçek `sozluk_oto_yayin` değeri sonucu etkilemesin (test DB'si gerçeğin kopyası)."""
    db_degeri = None

    def setUp(self):
        self._p = patch.object(db, "ayar_oku", side_effect=lambda a, v=None: self.db_degeri if a == "sozluk_oto_yayin" else v)
        self._p.start()

    def tearDown(self):
        self._p.stop()

    @staticmethod
    def _ortam(deger=None):
        """SOZLUK_OTO_YAYIN yalnız verilen değerle tanımlı (None = hiç tanımsız)."""
        ortam = patch.dict(os.environ)
        ortam.start()
        os.environ.pop("SOZLUK_OTO_YAYIN", None)
        if deger is not None:
            os.environ["SOZLUK_OTO_YAYIN"] = deger
        return ortam


class TestAnahtar(_DbAyariSahte):
    """Açma anahtarı (`oto_yayin=None` yolu): varsayılan KAPALI."""

    def test_varsayilan_kapali(self):
        for deger in ("", None):
            ortam = self._ortam(deger)
            try:
                self.assertFalse(tb.sozluk_oto_yayin_acik_mi(), repr(deger))
            finally:
                ortam.stop()

    def test_acik_degerleri(self):
        for deger in ("1", "true", "TRUE", " 1 ", "evet", "acik", "açık"):
            with patch.dict(os.environ, {"SOZLUK_OTO_YAYIN": deger}):
                self.assertTrue(tb.sozluk_oto_yayin_acik_mi(), deger)

    def test_kapali_degerleri(self):
        for deger in ("0", "false", "hayir", "kapali", "yes", "on", "2"):
            with patch.dict(os.environ, {"SOZLUK_OTO_YAYIN": deger}):
                self.assertFalse(tb.sozluk_oto_yayin_acik_mi(), deger)

    def test_db_ayari_ortam_degiskeni_yokken_acar(self):
        self.db_degeri = "1"
        ortam = self._ortam(None)
        try:
            self.assertTrue(tb.sozluk_oto_yayin_acik_mi())
        finally:
            ortam.stop()

    def test_db_ayari_sifirsa_acmaz(self):
        self.db_degeri = "0"
        ortam = self._ortam(None)
        try:
            self.assertFalse(tb.sozluk_oto_yayin_acik_mi())
        finally:
            ortam.stop()


class TestAcilFren(_DbAyariSahte):
    """`sozluk_oto_yayin_kapatildi_mi`: kod değiştirmeden, bir değişkenle durdurma (yanlış kart yayınlandığında)."""

    def _kapali(self, env=None):
        ortam = self._ortam(env)
        try:
            return tb.sozluk_oto_yayin_kapatildi_mi()
        finally:
            ortam.stop()

    def test_tanimsiz_ya_da_bos_kapatilmis_sayilmaz(self):
        self.assertFalse(self._kapali(None))
        self.assertFalse(self._kapali(""))
        self.assertFalse(self._kapali("   "))

    def test_kapatma_degerleri(self):
        for deger in ("0", "false", "FALSE", "hayir", "hayır", "kapali", "kapalı", " KAPALI "):
            self.assertTrue(self._kapali(deger), deger)

    def test_acik_ya_da_bilinmeyen_degerler_kapatmaz(self):
        for deger in ("1", "true", "evet", "acik", "yes", "2", "belki"):
            self.assertFalse(self._kapali(deger), deger)

    def test_db_ayari_kapatir(self):
        for deger in ("0", "false", "kapali"):
            self.db_degeri = deger
            self.assertTrue(self._kapali(None), deger)

    def test_db_ayari_acikken_kapatmaz(self):
        self.db_degeri = "1"
        self.assertFalse(self._kapali(None))

    def test_ortam_degiskeni_acik_olsa_da_db_kapatabilir(self):
        # iki kaynaktan biri bile "kapalı" diyorsa fren çekilir
        self.db_degeri = "0"
        self.assertTrue(self._kapali("1"))


class TestKartSecimi(unittest.TestCase):
    def setUp(self):
        self.mesajlar = []
        self._m = patch("src.telegram.istemci.mesaj_gonder", side_effect=lambda m, **k: self.mesajlar.append(m))
        self._m.start()

    def tearDown(self):
        self._m.stop()

    def test_taze_kart_secilir(self):
        with patch.object(sa, "sonraki_kart", return_value=KART), patch.object(sa, "kart_kanun_durumu", return_value=(True, [])):
            self.assertEqual(tb._sozluk_karti_sec(), (KART, True))
        self.assertEqual(self.mesajlar, [])

    def test_kanunu_degisen_kart_atlanir_bildirilir_siradaki_alinir(self):
        eski = {**KART, "kod": "SZ-951", "terim": "ESKİ KART"}
        sirali = iter([eski, KART])
        haric_listesi = []

        def sonraki(haric=None, **k):
            haric_listesi.append(set(haric or ()))
            return next(sirali)

        def durum(kart):
            return (False, ["dayanak_alintisi güncel metinde birebir bulunamadı"]) if kart["kod"] == "SZ-951" else (True, [])

        with patch.object(sa, "sonraki_kart", side_effect=sonraki), patch.object(sa, "kart_kanun_durumu", side_effect=durum):
            sonuc = tb._sozluk_karti_sec()
        self.assertEqual(sonuc, (KART, True))
        self.assertEqual(haric_listesi[1], {"SZ-951"})      # reddedilen ikinci seçimde dışlandı
        self.assertEqual(len(self.mesajlar), 1)
        self.assertIn("SZ-951", self.mesajlar[0])
        self.assertIn("durduruldu", self.mesajlar[0])

    def test_kart_kalmadiysa_none(self):
        with patch.object(sa, "sonraki_kart", return_value=None):
            self.assertEqual(tb._sozluk_karti_sec(), (None, None))

    def test_dogrulanamayan_kart_secilir_ama_taze_none(self):
        with patch.object(sa, "sonraki_kart", return_value=KART), patch.object(sa, "kart_kanun_durumu", return_value=(None, ["kanun metni alınamadı"])):
            self.assertEqual(tb._sozluk_karti_sec(), (KART, None))

    def test_hepsi_bayatsa_sonsuz_donmez(self):
        with patch.object(sa, "sonraki_kart", return_value=KART), patch.object(sa, "kart_kanun_durumu", return_value=(False, ["x"])):
            self.assertEqual(tb._sozluk_karti_sec(), (None, None))


class _DbTemizlik(unittest.TestCase):
    @staticmethod
    def _temizle():
        with db._baglanti_al() as conn:
            conn.execute("DELETE FROM haberler WHERE kaynak LIKE 'EDM Sözlük Kartı // SZ-95%'")
            conn.execute("DELETE FROM konu_gecmisi WHERE konu_kodu LIKE 'SZ-95%'")
            conn.execute("DELETE FROM ayarlar WHERE anahtar = 'sozluk_oto_son_gun'")
            conn.commit()

    def setUp(self):
        self._temizle()  # orijinal_url saniye cinsinden zaman damgası taşır: aynı saniyedeki ikinci deneme çakışmasın

    def tearDown(self):
        self._temizle()


class TestKartAkisi(_DbTemizlik):
    def _calistir(self, *, oto, taze=True, duraklatildi=False, son_gun="", yayinda=True):
        self._temizle()
        mesajlar = []
        onay = MagicMock(return_value=True)

        def haber_getir(hid):
            return {"id": hid, "durum": "yayinlandi" if yayinda else "onay_bekliyor",
                    "instagram_post_id": "ig-1" if yayinda else None}

        with patch("src.telegram.akislar.sozluk._sozluk_karti_sec", return_value=(copy.deepcopy(KART), taze)), \
             patch("src.telegram.istemci.mesaj_gonder", side_effect=lambda m, **k: mesajlar.append(m)), \
             patch("src.telegram.ayarlar.bot_duraklatildi_mi", return_value=(duraklatildi, "")), \
             patch("src.telegram.akislar.onay.haber_onayina_sun", onay), \
             patch.object(db, "ayar_oku", side_effect=lambda a, v=None: son_gun if a == "sozluk_oto_son_gun" else v), \
             patch.object(db, "haber_getir", side_effect=haber_getir):
            with patch.dict(os.environ, {"SOZLUK_OTO_YAYIN": "1" if oto else "0"}):
                sonuc = tb.sozluk_karti_hazirla_ve_sun()
        return sonuc, onay, mesajlar

    def test_kart_yoksa_none_doner_cagiran_modele_gecer(self):
        with patch("src.telegram.akislar.sozluk._sozluk_karti_sec", return_value=(None, None)):
            self.assertIsNone(tb.sozluk_karti_hazirla_ve_sun())

    def test_anahtar_kapaliyken_onaya_sunulur(self):
        sonuc, onay, mesajlar = self._calistir(oto=False)
        self.assertTrue(sonuc)
        self.assertFalse(onay.call_args.kwargs["oto_yayin"])
        self.assertFalse(any("otomatik yayınlanmadı" in m for m in mesajlar))  # kapalıyken rahatsız edilmez

    def test_tum_kosullar_tamamsa_otomatik(self):
        sonuc, onay, _ = self._calistir(oto=True)
        self.assertTrue(onay.call_args.kwargs["oto_yayin"])

    def test_her_kosulun_eksigi_onaya_dusurur(self):
        vakalar = {
            "kanun doğrulanamadı": {"taze": None},
            "bot duraklatılmış": {"duraklatildi": True},
            "bugün zaten yayınlandı": {"son_gun": tb._tr_bugun()},
        }
        for ad, ek in vakalar.items():
            with self.subTest(ad):
                _, onay, mesajlar = self._calistir(oto=True, **ek)
                self.assertFalse(onay.call_args.kwargs["oto_yayin"], ad)
                self.assertTrue(any("otomatik yayınlanmadı" in m for m in mesajlar), mesajlar)

    def test_dunku_yayin_bugunku_otomatigi_engellemez(self):
        _, onay, _ = self._calistir(oto=True, son_gun="2000-01-01")
        self.assertTrue(onay.call_args.kwargs["oto_yayin"])

    def test_kayit_ve_kullanim_isareti(self):
        self._calistir(oto=False)
        with db._baglanti_al() as conn:
            satir = conn.execute("SELECT * FROM haberler WHERE kaynak = 'EDM Sözlük Kartı // SZ-950'").fetchone()
            gecmis = conn.execute("SELECT sonuc FROM konu_gecmisi WHERE konu_kodu = 'SZ-950'").fetchone()
        self.assertIsNotNone(satir)
        self.assertEqual(satir["manset"], "GÜVENCE BEDELİ nedir?")
        self.assertEqual(satir["kategori"], "KIRA_VE_TAHLIYE")
        veri = json.loads(satir["detay_metni"])
        self.assertTrue(veri["_brief"]["kart"])
        self.assertEqual(veri["format_turu"], "sozluk")
        self.assertEqual(gecmis["sonuc"], "uretildi:sozluk")   # format başına kullanım takibi (57fdea3)

    def test_basarili_otomatik_yayin_gunluk_siniri_yazar(self):
        kaydedilen = {}
        with patch.object(db, "ayar_yaz", side_effect=lambda a, d: kaydedilen.__setitem__(a, d)):
            self._calistir(oto=True, yayinda=True)
        self.assertEqual(kaydedilen.get("sozluk_oto_son_gun"), tb._tr_bugun())

    def test_yayin_olmadiysa_gunluk_sinir_yazilmaz(self):
        kaydedilen = {}
        with patch.object(db, "ayar_yaz", side_effect=lambda a, d: kaydedilen.__setitem__(a, d)):
            self._calistir(oto=True, yayinda=False)
        self.assertNotIn("sozluk_oto_son_gun", kaydedilen)


class TestOnayaSunOtoYayin(unittest.TestCase):
    """`_haber_onayina_sun(oto_yayin=True)`: kapı, otomatik yayın ve onaya düşüş."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        slayt = Path(self.tmp.name) / "s.jpg"
        Image.new("RGB", (1080, 1350), "white").save(slayt)
        self.slayt = str(slayt)
        veri = {"format_turu": "sozluk", "terim": "GÜVENCE BEDELİ", "tanim_metni": KART["tanim"], "puf_maddeleri": KART["puf"],
                "kategori_kodu": "KIRA_VE_TAHLIYE", "manset_vurgu": "GÜVENCE BEDELİ", "manset_parca_2": "nedir?",
                "_brief": {"mevzuat": KART["mevzuat"], "kart": True}}
        self.haber = {"id": 77, "manset": "GÜVENCE BEDELİ nedir?", "kaynak": "EDM Sözlük Kartı // SZ-950", "kategori": "KIRA_VE_TAHLIYE",
                      "detay_metni": json.dumps(veri, ensure_ascii=False), "ig_caption": "x", "onem_puani": 8}
        self.mesajlar = []
        self.oto = MagicMock(return_value=True)
        self.kapi = MagicMock(return_value=(True, []))
        self.yamalar = [
            patch("src.db.haber_getir", return_value=self.haber),
            patch("src.db.haber_guncelle"),
            patch("src.db.onay_istegi_kaydet"),
            patch("src.telegram.akislar.kapi.yayin_kapisi", self.kapi),
            patch("src.telegram.akislar.otomatik._oto_yayinla", self.oto),
            patch("src.telegram.istemci.mesaj_gonder", side_effect=lambda m, **k: self.mesajlar.append(m) or {"message_id": 1}),
            patch("src.telegram.album.medya_grubu_gonder", return_value=[1]),
            patch("src.telegram.temizlik.icerik_onceki_mesajlarini_temizle"),
            patch("src.upload_image.coklu_gorsel_yukle", return_value=[]),
            patch("src.yeni_formatlar.slaytlari_uret", return_value=[Path(self.slayt)]),
            patch("src.db_senkron.hemen_kaydet"),
        ]
        for y in self.yamalar:
            y.start()

    def tearDown(self):
        for y in reversed(self.yamalar):
            y.stop()
        self.tmp.cleanup()

    def _sun(self, oto):
        return tb._haber_onayina_sun(77, oto_yayin=oto)

    def test_otomatik_yayin_basariliysa_onay_menusu_gonderilmez(self):
        self.assertTrue(self._sun(True))
        self.oto.assert_called_once()
        self.assertFalse(any("ONAY BEKLİYOR" in m for m in self.mesajlar), self.mesajlar)

    def test_otomatik_yayin_basarisizsa_onaya_duser(self):
        self.oto.return_value = False
        self.assertTrue(self._sun(True))
        self.assertTrue(any("otomatik yayınlanamadı" in m for m in self.mesajlar), self.mesajlar)
        self.assertTrue(any("ONAY BEKLİYOR" in m for m in self.mesajlar), self.mesajlar)

    def test_kapi_uyarisi_otomatik_yayini_durdurur(self):
        self.kapi.return_value = (True, ["⚠️ ABARTI DİLİ: \"asla\" geçiyor."])
        self.assertTrue(self._sun(True))
        self.oto.assert_not_called()
        self.assertTrue(any("Otomatik yayın durduruldu" in m for m in self.mesajlar), self.mesajlar)
        self.assertTrue(any("ONAY BEKLİYOR" in m for m in self.mesajlar), self.mesajlar)

    def test_kapi_kritik_bulgusunda_hicbir_sey_yayinlanmaz(self):
        self.kapi.return_value = (False, ["⛔ x"])
        self.assertFalse(self._sun(True))
        self.oto.assert_not_called()

    def test_oto_yayin_istenmediyse_hic_denenmez(self):
        self.assertTrue(self._sun(False))
        self.oto.assert_not_called()
        self.assertTrue(any("ONAY BEKLİYOR" in m for m in self.mesajlar), self.mesajlar)

    def test_uyarili_icerik_onayda_uyariyla_sunulur_otomatik_olmadan(self):
        self.kapi.return_value = (True, ["⚠️ x"])
        self._sun(False)
        self.oto.assert_not_called()

    def test_hazir_kartta_hakem_calistirilmaz(self):
        self._sun(False)
        self.assertFalse(self.kapi.call_args.kwargs["anlam_denetimi"])

    def test_model_uretimi_kayitta_hakem_calisir(self):
        veri = json.loads(self.haber["detay_metni"])
        veri["_brief"].pop("kart")
        self.haber["detay_metni"] = json.dumps(veri, ensure_ascii=False)
        self._sun(False)
        self.assertTrue(self.kapi.call_args.kwargs["anlam_denetimi"])


class TestOtoYayinla(unittest.TestCase):
    def _calistir(self, **sonuc):
        with patch("src.telegram.album.medya_grubu_gonder", return_value=[1]) as album, \
             patch("subprocess.run", **sonuc) as run:
            yanit = tb._oto_yayinla(77, ["a.jpg"], {"manset": "Başlık <b>"})
        return yanit, run, album

    def test_komut_dogru_hedeflerle_kurulur(self):
        _, run, _ = self._calistir(return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""))
        komut = run.call_args.args[0]
        self.assertIn("--hedef", komut)
        self.assertEqual(komut[komut.index("--hedef") + 1], tb.OTO_YAYIN_HEDEFLERI)
        self.assertEqual(komut[komut.index("--id") + 1], "77")
        self.assertEqual(komut[komut.index("--tur") + 1], "haber")

    def test_hedeflerde_linkedin_yok(self):
        # LinkedIn sırları hazirla.yml'de tanımlı değil; finans bülteniyle aynı kanallar
        self.assertNotIn("linkedin", tb.OTO_YAYIN_HEDEFLERI)

    def test_basari_ve_sonuc_satiri(self):
        self.assertTrue(self._calistir(return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""))[0])
        # Bir kanal hata verip betik 1 dönse de sonuç satırı varsa betik çalışmış demektir (rapor Telegram'da)
        self.assertTrue(self._calistir(return_value=subprocess.CompletedProcess([], 1, stdout='POSTEDM_SONUC={"hedefler": []}', stderr=""))[0])

    def test_sonuc_yoksa_ve_cokerse_false(self):
        self.assertFalse(self._calistir(return_value=subprocess.CompletedProcess([], 1, stdout="", stderr="Traceback"))[0])

    def test_zaman_asimi_false(self):
        self.assertFalse(self._calistir(side_effect=subprocess.TimeoutExpired("x", 1))[0])

    def test_album_ve_baslik_html_kacirilir(self):
        _, _, album = self._calistir(return_value=subprocess.CompletedProcess([], 0, stdout="", stderr=""))
        self.assertIn("Başlık &lt;b&gt;", album.call_args.kwargs["caption"])
        self.assertIn("OTOMATİK YAYIN", album.call_args.kwargs["caption"])

    def test_album_gonderilemese_de_yayin_denenir(self):
        with patch("src.telegram.album.medya_grubu_gonder", side_effect=RuntimeError("ağ")), \
             patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, stdout="", stderr="")) as run:
            self.assertTrue(tb._oto_yayinla(77, ["a.jpg"], {"manset": "x"}))
        run.assert_called_once()


class TestSlotYonlendirme(unittest.TestCase):
    def test_sozluk_slotu_kart_varsa_kartla_gider(self):
        with patch("src.telegram.akislar.sozluk.sozluk_karti_hazirla_ve_sun", return_value=True) as kart, \
             patch("src.telegram.akislar.uretim.hizli_icerik_uret") as model, patch("src.telegram.istemci.mesaj_gonder"):
            self.assertTrue(tb._sozluk_slotu())
        kart.assert_called_once()
        model.assert_not_called()

    def test_kart_basarisizsa_modele_gecilmez(self):
        # Kart bulundu ama kapı durdurdu (False): içerik zaten sorunlu, ikinci bir içerik üretilmez
        with patch("src.telegram.akislar.sozluk.sozluk_karti_hazirla_ve_sun", return_value=False), \
             patch("src.telegram.akislar.uretim.hizli_icerik_uret") as model, patch("src.telegram.istemci.mesaj_gonder"):
            self.assertFalse(tb._sozluk_slotu())
        model.assert_not_called()

    def test_kart_kalmadiysa_modelle_ve_onayli(self):
        with patch("src.telegram.akislar.sozluk.sozluk_karti_hazirla_ve_sun", return_value=None), \
             patch("src.telegram.akislar.uretim.hizli_icerik_uret", return_value=True) as model, patch("src.telegram.istemci.mesaj_gonder") as mesaj:
            self.assertTrue(tb._sozluk_slotu())
        model.assert_called_once_with(format_turu="sozluk")
        self.assertIn("hazır sözlük kartı kalmadı", mesaj.call_args.args[0])

    def test_sozluk_slotu_ve_gunluk_donguye_baglanti(self):
        with patch("src.telegram.akislar.uretim._sozluk_slotu", return_value=True) as slot:
            self.assertTrue(tb.slot_icerigi_hazirla_ve_sun(slot="sozluk"))
        slot.assert_called_once()
        with patch("src.telegram.akislar.uretim._sozluk_slotu", return_value=True) as slot, \
             patch.object(konu_bankasi, "siradaki_bilgilendirici_format", return_value="sozluk"), \
             patch.object(konu_bankasi, "bilgilendirici_format_kaydet") as kaydet:
            self.assertTrue(tb.slot_icerigi_hazirla_ve_sun(slot="bilgilendirici"))
        slot.assert_called_once()
        kaydet.assert_called_once_with("sozluk")

    def test_oto_yayin_bayragi_slottan_karta_kadar_iletilir(self):
        # Zamanlanmış tur iki günde bir çalışır (tests/test_sozluk_iki_gunde_bir.py); burada yalnız bayrağın iletilmesi sınanır,
        # paylaşılan test veritabanındaki "son tur" işareti sonucu etkilemesin.
        with patch("src.telegram.akislar.sozluk.sozluk_zamanli_gunu_mu", return_value=True), \
             patch("src.telegram.akislar.sozluk.sozluk_zamanli_isaretle"), \
             patch("src.telegram.akislar.sozluk.sozluk_karti_hazirla_ve_sun", return_value=True) as kart, patch("src.telegram.istemci.mesaj_gonder"):
            tb.slot_icerigi_hazirla_ve_sun(slot="sozluk", oto_yayin=True)
            kart.assert_called_once_with(oto_yayin=True)
        with patch("src.telegram.akislar.sozluk.sozluk_karti_hazirla_ve_sun", return_value=True) as kart, patch("src.telegram.istemci.mesaj_gonder"):
            tb.slot_icerigi_hazirla_ve_sun(slot="sozluk", oto_yayin=False)
            kart.assert_called_once_with(oto_yayin=False)
        with patch("src.telegram.akislar.sozluk.sozluk_karti_hazirla_ve_sun", return_value=True) as kart, patch("src.telegram.istemci.mesaj_gonder"):
            tb.slot_icerigi_hazirla_ve_sun(slot="sozluk")          # bayrak verilmedi: anahtara bakılır
            kart.assert_called_once_with()

    def test_gunluk_dongudeki_sozluk_gunu_bayragi_iletir(self):
        with patch("src.telegram.akislar.sozluk.sozluk_karti_hazirla_ve_sun", return_value=True) as kart, patch("src.telegram.istemci.mesaj_gonder"), \
             patch.object(konu_bankasi, "siradaki_bilgilendirici_format", return_value="sozluk"), \
             patch.object(konu_bankasi, "bilgilendirici_format_kaydet"):
            tb.slot_icerigi_hazirla_ve_sun(slot="bilgilendirici", oto_yayin=False)
            kart.assert_called_once_with(oto_yayin=False)

    def test_model_yolu_oto_yayin_bayragiyla_bile_onaya_gider(self):
        # kart kalmadı: modelin yazdığı sözlük HİÇBİR koşulda onaysız yayınlanmaz (hizli_icerik_uret oto_yayin almaz)
        import inspect
        self.assertNotIn("oto_yayin", inspect.signature(tb.hizli_icerik_uret).parameters)
        with patch("src.telegram.akislar.sozluk.sozluk_karti_hazirla_ve_sun", return_value=None), \
             patch("src.telegram.akislar.uretim.hizli_icerik_uret", return_value=True) as model, patch("src.telegram.istemci.mesaj_gonder"):
            tb.slot_icerigi_hazirla_ve_sun(slot="sozluk", oto_yayin=True)
        model.assert_called_once_with(format_turu="sozluk")

    def test_diger_formatlar_eskisi_gibi(self):
        with patch("src.telegram.akislar.uretim.hizli_icerik_uret", return_value=True) as model, \
             patch.object(konu_bankasi, "siradaki_bilgilendirici_format", return_value="net_cevap"), \
             patch.object(konu_bankasi, "bilgilendirici_format_kaydet"):
            tb.slot_icerigi_hazirla_ve_sun(slot="bilgilendirici")
        model.assert_called_once_with(format_turu="net_cevap")


class TestZamanlanmisCalistirma(unittest.TestCase):
    """`sozluk_karti_hazirla_ve_sun(oto_yayin=...)`: zamanlanmış işin bayrağı ve acil fren."""

    def setUp(self):
        self._temizle()

    def tearDown(self):
        self._temizle()

    @staticmethod
    def _temizle():
        with db._baglanti_al() as conn:
            conn.execute("DELETE FROM haberler WHERE kaynak LIKE 'EDM Sözlük Kartı // SZ-95%'")
            conn.execute("DELETE FROM konu_gecmisi WHERE konu_kodu LIKE 'SZ-95%'")
            conn.commit()

    def _calistir(self, oto_yayin, env=None, db_degeri=None):
        self._temizle()   # orijinal_url saniye cinsinden zaman damgası taşır: aynı saniyedeki ikinci çağrı çakışmasın
        mesajlar = []
        onay = MagicMock(return_value=True)

        def ayar(anahtar, varsayilan=None):
            return db_degeri if anahtar == "sozluk_oto_yayin" else varsayilan

        haber = {"id": 1, "durum": "yayinlandi", "instagram_post_id": "ig-1"}
        with patch.dict(os.environ):
            os.environ.pop("SOZLUK_OTO_YAYIN", None)
            if env is not None:
                os.environ["SOZLUK_OTO_YAYIN"] = env
            with patch("src.telegram.akislar.sozluk._sozluk_karti_sec", return_value=(copy.deepcopy(KART), True)), \
                 patch("src.telegram.istemci.mesaj_gonder", side_effect=lambda m, **k: mesajlar.append(m)), \
                 patch("src.telegram.ayarlar.bot_duraklatildi_mi", return_value=(False, "")), \
                 patch("src.telegram.akislar.onay.haber_onayina_sun", onay), \
                 patch.object(db, "ayar_oku", side_effect=ayar), \
                 patch.object(db, "haber_getir", return_value=haber):
                tb.sozluk_karti_hazirla_ve_sun(oto_yayin=oto_yayin)
        return onay.call_args.kwargs["oto_yayin"], mesajlar

    def test_zamanlanmis_calistirma_anahtar_tanimsizken_otomatik(self):
        otomatik, _ = self._calistir(True)
        self.assertTrue(otomatik)

    def test_zamanlanmis_calistirma_acik_anahtarla_otomatik(self):
        otomatik, _ = self._calistir(True, env="1")
        self.assertTrue(otomatik)

    def test_ortam_degiskeni_kapatinca_onaya_duser_ve_nedeni_soylenir(self):
        otomatik, mesajlar = self._calistir(True, env="0")
        self.assertFalse(otomatik)
        self.assertTrue(any("anahtarı kapatılmış" in m for m in mesajlar), mesajlar)

    def test_db_ayari_kapatinca_onaya_duser(self):
        otomatik, mesajlar = self._calistir(True, db_degeri="0")
        self.assertFalse(otomatik)
        self.assertTrue(any("anahtarı kapatılmış" in m for m in mesajlar), mesajlar)

    def test_oto_yayin_false_acik_anahtarla_bile_otomatik_olmaz(self):
        otomatik, mesajlar = self._calistir(False, env="1")
        self.assertFalse(otomatik)
        self.assertFalse(any("otomatik yayınlanmadı" in m for m in mesajlar), mesajlar)   # istenmediyse rahatsız edilmez

    def test_stok_azalinca_her_yayinda_hatirlatma_gider(self):
        with patch.object(sa, "stok_kalan", return_value=sa.STOK_UYARI_ESIGI):
            _, mesajlar = self._calistir(True)
        uyari = [m for m in mesajlar if "stoğu azalıyor" in m]
        self.assertEqual(len(uyari), 1, mesajlar)
        self.assertIn(f"{sa.STOK_UYARI_ESIGI} kart kaldı", uyari[0])
        self.assertIn(f"{sa.HEDEF_KART} kart", uyari[0])

    def test_stok_boldyken_hatirlatma_yok(self):
        with patch.object(sa, "stok_kalan", return_value=sa.STOK_UYARI_ESIGI + 1):
            _, mesajlar = self._calistir(True)
        self.assertFalse(any("stoğu" in m for m in mesajlar), mesajlar)

    def test_stok_hatirlatmasi_otomatigi_engellemez(self):
        with patch.object(sa, "stok_kalan", return_value=0):
            otomatik, _ = self._calistir(True)
        self.assertTrue(otomatik)

    def test_oto_yayin_none_anahtara_bakar(self):
        self.assertTrue(self._calistir(None, env="1")[0])
        self.assertFalse(self._calistir(None)[0])


def _hazirla_modulu():
    import importlib.util
    yol = Path(__file__).resolve().parent.parent / "scripts" / "hazirla.py"
    spec = importlib.util.spec_from_file_location("hazirla_betik_sozluk", yol)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class TestHazirlaBayragi(unittest.TestCase):
    """`scripts/hazirla.py`: `--oto-yayin` yalnız sözlük kartı yoluna iletilir; başka format asla otomatik yayınlanmaz."""

    @classmethod
    def setUpClass(cls):
        cls.hz = _hazirla_modulu()

    def _calistir(self, *argv):
        hz = self.hz
        with patch.object(sys, "argv", ["hazirla.py", *argv]), \
             patch("src.telegram.ayarlar.bot_duraklatildi_mi", return_value=(False, "")), \
             patch.object(hz.db, "eski_kayitlari_temizle", return_value=0), \
             patch.object(hz.db, "bayat_haberleri_ayikla", return_value=0), \
             patch("src.telegram.akislar.uretim.slot_icerigi_hazirla_ve_sun") as slot, \
             patch("src.telegram.akislar.sozluk.sozluk_karti_hazirla_ve_sun") as kart, \
             patch("src.telegram.akislar.uretim.hizli_icerik_uret") as model:
            hz.main()
        return slot, kart, model

    def test_slot_sozluk_oto_yayin_bayragi_iletilir(self):
        slot, kart, model = self._calistir("--slot", "sozluk", "--oto-yayin")
        slot.assert_called_once_with(slot="sozluk", oto_yayin=True)

    def test_slot_sozluk_bayraksiz_otomatik_degil(self):
        slot, _, _ = self._calistir("--slot", "sozluk")
        slot.assert_called_once_with(slot="sozluk", oto_yayin=False)

    def test_gunluk_dongu_bayraksiz_otomatik_degil(self):
        # 10:00 işi: döngüdeki sözlük günü de onaya düşer; otomatik yalnız 12:30 işinde
        slot, _, _ = self._calistir("--slot", "bilgilendirici")
        slot.assert_called_once_with(slot="bilgilendirici", oto_yayin=False)

    def test_format_sozluk_karta_gider(self):
        _, kart, model = self._calistir("--format", "sozluk", "--oto-yayin")
        kart.assert_called_once_with(oto_yayin=True)
        model.assert_not_called()
        _, kart, _ = self._calistir("--format", "sozluk")
        kart.assert_called_once_with(oto_yayin=False)

    def test_baska_format_oto_yayin_bayragiyla_bile_modelle_onaya_gider(self):
        for format_turu in ("nedir_dogrusu", "net_cevap", "b1", "vaka"):
            with self.subTest(format_turu):
                slot, kart, model = self._calistir("--format", format_turu, "--oto-yayin")
                model.assert_called_once_with(format_turu=format_turu)
                kart.assert_not_called()


if __name__ == "__main__":
    unittest.main()
