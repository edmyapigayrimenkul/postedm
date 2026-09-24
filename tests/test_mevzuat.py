"""
tests/test_mevzuat.py — güncel kanun metni katmanı ve ona karşı içerik denetimi.

Gerçek olay (2026-09-24): canlı 20 içeriğin 9'unun ana iddiası yanlıştı; çoğu
sonradan değişmiş maddelere dayanıyordu. Önalımda "2 yıl" (7571 ile 1 yıl oldu),
kentsel dönüşümde "üçte iki" (2019'dan beri salt çoğunluk). Testler ağa çıkmaz.
"""

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import dogrula, konu_bankasi, mevzuat  # noqa: E402

TMK_ORNEK = (
    "Madde 732- Paylı mülkiyette bir paydaşın payını üçüncü kişiye satması hâlinde diğer paydaşlar "
    "önalım hakkını kullanabilirler. Madde 733- (Değişik birinci fıkra:24/12/2025-7571/35 md.) "
    "Önalım hakkı, satışın hak sahibine bildirildiği tarihin üzerinden üç ay ve her hâlde satışın "
    "üzerinden bir yıl geçmekle düşer. Madde 734- Önalım hakkı, alıcıya karşı dava açılarak kullanılır. "
    "GEÇİCİ MADDE 2 – Geçici hüküm."
)


class TestAtif(unittest.TestCase):
    def test_ad_ve_numarayla_atiflar(self):
        self.assertEqual(mevzuat.atiflari_coz("Türk Medeni Kanunu md. 732-733")[0], [(4721, ["732", "733"])])
        self.assertEqual(mevzuat.atiflari_coz("Harçlar Kanunu md. 63 ve Vergi Usul Kanunu md. 359")[0],
                         [(492, ["63"]), (213, ["359"])])
        self.assertEqual(mevzuat.atiflari_coz("İmar Kanunu md. 5 ve 21")[0], [(3194, ["5", "21"])])
        self.assertEqual(mevzuat.atiflari_coz("İmar Kanunu Geçici md. 16")[0], [(3194, ["geçici 16"])])
        self.assertEqual(mevzuat.atiflari_coz("6502 sayılı Kanun md. 24")[0], [(6502, ["24"])])

    def test_yonetmelik_ve_teblig_cozulemeyen(self):
        atiflar, cozulemeyen = mevzuat.atiflari_coz("Plansız Alanlar İmar Yönetmeliği md. 43-56")
        self.assertEqual(atiflar, [])
        self.assertTrue(cozulemeyen)
        self.assertTrue(mevzuat.atiflari_coz("SPK GYF Esasları Tebliği")[1])

    def test_uzun_aralik_sinirlanir(self):
        maddeler = mevzuat.atiflari_coz("Türk Medeni Kanunu md. 794-822")[0][0][1]
        self.assertLessEqual(len(maddeler), 5)
        self.assertIn("822", maddeler)


class TestMaddeMetni(unittest.TestCase):
    def test_madde_siniri_ve_gecici_madde_ayrimi(self):
        with patch.object(mevzuat, "kanun_metni", return_value=TMK_ORNEK):
            m733 = mevzuat.madde_metni(4721, "733")
            self.assertTrue(m733.startswith("Madde 733"))
            self.assertNotIn("Madde 734", m733)
            self.assertIn("GEÇİCİ MADDE 2", mevzuat.madde_metni(4721, "geçici 2"))
            self.assertIsNone(mevzuat.madde_metni(4721, "999"))

    def test_degisiklik_tarihi(self):
        with patch.object(mevzuat, "kanun_metni", return_value=TMK_ORNEK):
            ozet = mevzuat.brief_mevzuati("Türk Medeni Kanunu md. 733")
        self.assertEqual(ozet["son_degisiklik"], "2025-12-24")


class TestSureIfadeleri(unittest.TestCase):
    def test_rakam_yazi_ve_birlesik_yazim(self):
        s = mevzuat.sure_ifadeleri("oniki aylık, on beş gün, 2 yıllık, üç ay, on dört gün, bir yıl")
        self.assertEqual(s, {("12", "ay"), ("15", "gün"), ("2", "yıl"), ("3", "ay"), ("14", "gün"), ("1", "yıl")})

    def test_noter_onayli_sure_degildir(self):
        self.assertEqual(mevzuat.sure_ifadeleri("noter onaylı feragatname"), set())


class TestKanunMetnineKarsiDenetim(unittest.TestCase):
    def _denetle(self, metin, kaynak):
        return dogrula.denetle({"spot": metin}, {"mevzuat": "TMK md. 733", "mevzuat_metni": kaynak,
                                                 "veri_kaynagi": "x", "yerel": "x"})

    def test_eski_hukuktaki_sure_yakalanir_142(self):
        u = self._denetle("Hisseli tapuda iki yıl boyunca dava açılabilir.", TMK_ORNEK)
        self.assertTrue(any("SÜRE KAYNAKTA YOK" in x and "2 yıl" in x for x in u))

    def test_guncel_sure_gecer(self):
        u = self._denetle("Bildirimden itibaren 3 ay, her hâlde bir yıl içinde.", TMK_ORNEK)
        self.assertFalse(any("SÜRE" in x for x in u))

    def test_eski_cogunluk_yakalanir_68(self):
        u = self._denetle("Üçte iki çoğunluk karar alırsa paylar satılır.", "paydaşların salt çoğunluğu ile karar verilir")
        self.assertTrue(any("ÇOĞUNLUK" in x for x in u))

    def test_uydurma_ictihat(self):
        u = self._denetle("Yargıtay 3. Hukuk Dairesi 2021/4512 E. sayılı kararına göre", TMK_ORNEK)
        self.assertTrue(any("İÇTİHAT" in x for x in u))

    def test_test_modunda_aga_cikilmaz(self):
        with patch("src.mevzuat.requests.get", side_effect=AssertionError("ağa çıkıldı")):
            self.assertEqual(konu_bankasi.guncel_mevzuat({"kod": "X", "mevzuat": "TMK md. 733"}), {})
            self.assertEqual(dogrula._kanun_metni({"mevzuat": "TMK md. 733"}), "")


class TestHaberKaynagi(unittest.TestCase):
    """#170/#171: açılmayan adreslerden 'İBB haberi' üretildi ve yayına çıktı."""

    def _denetle(self, **cevap):
        from unittest.mock import MagicMock
        haber = {"kaynak": "İBB Şehircilik", "orijinal_url": "https://ornek.gov.tr/haber"}
        with patch.object(dogrula, "__name__", dogrula.__name__), \
             patch("src.config.test_modu", return_value=False), \
             patch("requests.get", **cevap):
            return dogrula.kaynak_denetle(haber)

    def test_404_haber_yok(self):
        from unittest.mock import MagicMock
        self.assertTrue(self._denetle(return_value=MagicMock(status_code=404))[0].startswith("⛔"))

    def test_alan_adi_cozulmuyor(self):
        import requests
        self.assertTrue(self._denetle(side_effect=requests.ConnectionError("dns"))[0].startswith("⛔"))

    def test_bot_korumasi_kilitlemez(self):
        from unittest.mock import MagicMock
        self.assertTrue(self._denetle(return_value=MagicMock(status_code=403))[0].startswith("⚠️"))

    def test_edm_uretimi_ve_adres_yoklugu(self):
        self.assertEqual(dogrula.kaynak_denetle({"kaynak": "EDM Konu Bankası // S1-001"}), [])
        self.assertTrue(dogrula.kaynak_denetle({"kaynak": "Habertürk", "orijinal_url": ""})[0].startswith("⛔"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
