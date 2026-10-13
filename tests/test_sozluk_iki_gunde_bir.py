"""
tests/test_sozluk_iki_gunde_bir.py — zamanlanmış (12:30, onaysız) sözlük turu İKİ GÜNDE BİR çıkar (kullanıcı kararı, 2026-10-13)

Kural: son TESLİM edilen zamanlanmış turdan (`ayarlar › sozluk_zamanli_son_gun`) beri `sozluk_arsivi.YAYIN_ARALIK_GUN` gün geçmediyse
12:30 turu sessizce atlanır (kart tüketilmez, model çalışmaz, Telegram'a mesaj düşmez). Başarısız tur işaretlenmez, ertesi gün yeniden denenir.
Elle tetiklenen sözlük (/sozluk) ve diğer çağrılar aralığa girmez.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import sys
import unittest
from pathlib import Path
from unittest import mock

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import sozluk_arsivi
from src import telegram_bot as tb
from src.telegram.akislar import sozluk, uretim

ANAHTAR = "sozluk_zamanli_son_gun"


class SahteAyarlar:
    def __init__(self):
        self.veri: dict = {}

    def oku(self, anahtar, varsayilan=None):
        return self.veri.get(anahtar, varsayilan)

    def yaz(self, anahtar, deger):
        self.veri[anahtar] = str(deger)


class Temel(unittest.TestCase):
    def setUp(self):
        self.ayar = SahteAyarlar()
        self.gun = "2026-10-14"
        self.kart = mock.Mock(return_value=True)
        self.model = mock.Mock(return_value=True)
        self.mesaj = mock.Mock()
        for yama in (
            mock.patch("src.db.ayar_oku", side_effect=self.ayar.oku),
            mock.patch("src.db.ayar_yaz", side_effect=self.ayar.yaz),
            mock.patch("src.telegram.akislar.zamanli._tr_bugun", side_effect=lambda: self.gun),
            mock.patch("src.telegram.akislar.sozluk.sozluk_karti_hazirla_ve_sun", self.kart),
            mock.patch("src.telegram.akislar.uretim.hizli_icerik_uret", self.model),
            mock.patch("src.telegram.istemci.mesaj_gonder", self.mesaj),
        ):
            yama.start()
            self.addCleanup(yama.stop)


class TestAralik(Temel):
    def test_aralik_iki_gun(self):
        self.assertEqual(sozluk_arsivi.YAYIN_ARALIK_GUN, 2)

    def test_hedef_kart_aralikla_uyumlu(self):
        """İki günde bir kartla 2 yıl tekrarsız = 365 kart (eskiden günde bir kartla 730)."""
        self.assertEqual(sozluk_arsivi.HEDEF_KART, 365)
        self.assertEqual(sozluk_arsivi.BEKLEME_GUN, 730)

    def test_hic_tur_yoksa_calisir(self):
        self.assertTrue(sozluk.sozluk_zamanli_gunu_mu())

    def test_dun_teslim_edildiyse_bugun_atlanir(self):
        self.ayar.veri[ANAHTAR] = "2026-10-13"
        self.assertFalse(sozluk.sozluk_zamanli_gunu_mu())

    def test_ayni_gun_teslim_edildiyse_atlanir(self):
        self.ayar.veri[ANAHTAR] = "2026-10-14"
        self.assertFalse(sozluk.sozluk_zamanli_gunu_mu())

    def test_iki_gun_once_teslim_edildiyse_calisir(self):
        self.ayar.veri[ANAHTAR] = "2026-10-12"
        self.assertTrue(sozluk.sozluk_zamanli_gunu_mu())

    def test_bozuk_ya_da_gelecek_tarih_turu_kilitlemez(self):
        for deger in ("bozuk", "2026-13-45", "2099-01-01"):
            with self.subTest(deger=deger):
                self.ayar.veri[ANAHTAR] = deger
                self.assertTrue(sozluk.sozluk_zamanli_gunu_mu(), "bozuk işaret sözlüğü sonsuza dek durdurmamalı")

    def test_gun_donumu_turkiye_gunune_gore(self):
        """İşaret TR gününü yazar (UTC değil): 21:30 UTC = ertesi TR günü."""
        sozluk.sozluk_zamanli_isaretle()
        self.assertEqual(self.ayar.veri[ANAHTAR], "2026-10-14")


class TestSozlukSlotu(Temel):
    def test_dinlenme_gunu_sessizce_atlanir(self):
        self.ayar.veri[ANAHTAR] = "2026-10-13"
        self.assertTrue(uretim._sozluk_slotu(oto_yayin=True), "atlanan gün BAŞARILI sayılmalı (yedek tetik ve hata bildirimi çıkmasın)")
        self.kart.assert_not_called()
        self.model.assert_not_called()
        self.mesaj.assert_not_called()
        self.assertEqual(self.ayar.veri[ANAHTAR], "2026-10-13", "atlanan gün işareti ilerletmemeli")

    def test_sozluk_gunu_kart_yayinlanir_ve_isaretlenir(self):
        self.assertTrue(uretim._sozluk_slotu(oto_yayin=True))
        self.kart.assert_called_once_with(oto_yayin=True)
        self.assertEqual(self.ayar.veri[ANAHTAR], "2026-10-14")

    def test_kart_onaya_dusse_de_tur_teslim_sayilir(self):
        """Denetim uyarısı yüzünden yayınlanmayıp onaya düşen kart da o turun sözlüğüdür (ertesi gün ikincisi gelmez)."""
        self.kart.return_value = True   # haber_onayina_sun True: kart onaya sunuldu
        uretim._sozluk_slotu(oto_yayin=True)
        self.assertEqual(self.ayar.veri[ANAHTAR], "2026-10-14")

    def test_basarisiz_tur_isaretlenmez_ertesi_gun_yeniden_denenir(self):
        self.kart.return_value = False   # kapı durdurdu / üretim çöktü
        self.assertFalse(uretim._sozluk_slotu(oto_yayin=True))
        self.assertNotIn(ANAHTAR, self.ayar.veri)
        self.gun = "2026-10-15"
        self.kart.return_value = True
        self.assertTrue(uretim._sozluk_slotu(oto_yayin=True))
        self.assertEqual(self.kart.call_count, 2, "başarısız turun ertesi günü yine denenmeli, iki gün beklenmemeli")
        self.assertEqual(self.ayar.veri[ANAHTAR], "2026-10-15")

    def test_kart_kalmadiysa_model_yolu_da_ayni_aralikla_calisir(self):
        self.kart.return_value = None
        self.assertTrue(uretim._sozluk_slotu(oto_yayin=True))
        self.model.assert_called_once_with(format_turu="sozluk")
        self.assertEqual(self.ayar.veri[ANAHTAR], "2026-10-14")
        self.gun = "2026-10-15"
        self.model.reset_mock()
        uretim._sozluk_slotu(oto_yayin=True)
        self.model.assert_not_called()   # ertesi gün model sözlüğü de atlanır

    def test_elle_tetiklenen_sozluk_aralikla_sinirlanmaz_ve_isaret_yazmaz(self):
        self.ayar.veri[ANAHTAR] = "2026-10-14"   # bugün zamanlanmış tur zaten teslim edilmiş
        for oto in (False, None):
            with self.subTest(oto_yayin=oto):
                self.kart.reset_mock()
                self.assertTrue(uretim._sozluk_slotu(oto_yayin=oto))
                self.kart.assert_called_once()
        self.assertEqual(self.ayar.veri[ANAHTAR], "2026-10-14")

    def test_elle_sozluk_zamanli_isareti_olusturmaz(self):
        uretim._sozluk_slotu(oto_yayin=False)
        self.assertNotIn(ANAHTAR, self.ayar.veri)


class TestAltiGunluSimulasyon(Temel):
    def test_alti_gunde_uc_sozluk_birer_gun_arayla(self):
        yayin_gunleri = []
        for gun in ("2026-10-14", "2026-10-15", "2026-10-16", "2026-10-17", "2026-10-18", "2026-10-19"):
            self.gun = gun
            self.kart.reset_mock()
            uretim._sozluk_slotu(oto_yayin=True)
            if self.kart.called:
                yayin_gunleri.append(gun)
        self.assertEqual(yayin_gunleri, ["2026-10-14", "2026-10-16", "2026-10-18"])

    def test_slot_icerigi_uzerinden_de_ayni(self):
        """Gerçek giriş noktası: hazirla.py → slot_icerigi_hazirla_ve_sun(slot='sozluk', oto_yayin=True)."""
        self.assertTrue(tb.slot_icerigi_hazirla_ve_sun(slot="sozluk", oto_yayin=True))
        self.gun = "2026-10-15"
        self.kart.reset_mock()
        self.assertTrue(tb.slot_icerigi_hazirla_ve_sun(slot="sozluk", oto_yayin=True))
        self.kart.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
