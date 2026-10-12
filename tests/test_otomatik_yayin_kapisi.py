"""
tests/test_otomatik_yayin_kapisi.py — Onaysız (otomatik) yayın kapısı

Model yazdığı içerik insan onayı olmadan çıkıyorsa anlam hakemi (ikinci model) GERÇEKTEN çalışıp temiz demiş
olmalı. Hakem kota ya da kaynak yokluğu yüzünden sessizce atlanınca "temiz" görünüyordu (2026-10-07).
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import capraz_denetim, db, dogrula, telegram_bot  # noqa: E402

KAYNAK = "Kat Mülkiyeti Kanunu md. 30: " + "Yönetici, kat malikleri kurulunca seçilir ve görevden alınabilir. " * 6
VERI = {
    "manset": "Yönetici nasıl seçilir",
    "spot": "Yönetici kat malikleri kurulunca seçilir.",
    "caption_instagram": "x", "caption_threads": "y",
    "_brief": {"mevzuat": "KMK md. 30", "mevzuat_metni": KAYNAK},
}


class TestOtomatikYayinaUygunMu(unittest.TestCase):
    def test_hakem_calisip_temiz_derse_uygun(self):
        with patch.object(capraz_denetim, "denetle_ayrintili", return_value=([], True)):
            uygun, nedenler = dogrula.otomatik_yayina_uygun_mu(dict(VERI))
        self.assertTrue(uygun, nedenler)
        self.assertEqual(nedenler, [])

    def test_hakem_calismadiysa_temiz_varsayilmaz(self):
        with patch.object(capraz_denetim, "denetle_ayrintili", return_value=([], False)):
            uygun, nedenler = dogrula.otomatik_yayina_uygun_mu(dict(VERI))
        self.assertFalse(uygun)
        self.assertTrue(any("ANLAM DENETİMİ ÇALIŞMADI" in n for n in nedenler), nedenler)

    def test_hakem_istisna_firlatirsa_uygun_degil(self):
        with patch.object(capraz_denetim, "denetle_ayrintili", side_effect=RuntimeError("kota")):
            uygun, nedenler = dogrula.otomatik_yayina_uygun_mu(dict(VERI))
        self.assertFalse(uygun)
        self.assertTrue(nedenler)

    def test_hakem_bulgu_verirse_uygun_degil(self):
        with patch.object(capraz_denetim, "denetle_ayrintili", return_value=(["⚠️ ANLAM KAYMASI (x): y"], True)):
            uygun, nedenler = dogrula.otomatik_yayina_uygun_mu(dict(VERI))
        self.assertFalse(uygun)
        self.assertIn("⚠️ ANLAM KAYMASI (x): y", nedenler)

    def test_kritik_bulgu_varken_hakem_hic_cagrilmaz(self):
        veri = {**VERI, "spot": "Kat Mülkiyeti Kanunu madde 99 uyarınca karar verilir."}  # uydurma madde ⛔
        with patch.object(capraz_denetim, "denetle_ayrintili", return_value=([], True)) as hakem:
            uygun, nedenler = dogrula.otomatik_yayina_uygun_mu(veri)
        self.assertFalse(uygun)
        hakem.assert_not_called()
        self.assertTrue(dogrula.kritik_var(nedenler), nedenler)

    def test_test_modunda_kaynaksiz_icerik_otomatik_yayina_uygun_degil(self):
        """Gerçek hakem yok (test modu) ⇒ çalışmadı ⇒ onaya düşer; varsayılan davranış güvenli taraf."""
        veri = {k: v for k, v in VERI.items() if k != "_brief"}
        uygun, _ = dogrula.otomatik_yayina_uygun_mu(veri)
        self.assertFalse(uygun)


class TestFinansAkisiKapiyaBagli(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_patcher = patch("src.db.DB_YOLU", Path(self.tmpdir.name) / "kapi.db")
        self.db_patcher.start()
        db.tablolari_olustur()
        self.kullanildi = patch("src.konu_bankasi.kullanildi_isaretle")
        self.kullanildi.start()
        self.resim = Path(self.tmpdir.name) / "k.jpg"
        self.resim.write_bytes(b"x")

    def tearDown(self):
        self.kullanildi.stop()
        self.db_patcher.stop()
        self.tmpdir.cleanup()

    def _calistir(self, kapi_sonucu):
        veri = {"manset": "Faiz", "spot": "Spot", "kategori_kodu": "FINANS_VE_BANKACILIK",
                "caption_instagram": "a", "caption_threads": "b"}
        with (
            patch("src.generate_text.konudan_uret", return_value=veri),
            patch("src.make_image.otorite_gonderi_slaytlari_uret", return_value=[self.resim]),
            patch("src.upload_image.coklu_gorsel_yukle", return_value=["https://cdn.example.com/1.jpg"]),
            patch("src.video.slaytlardan_reels_uret", return_value=None),
            patch("src.dogrula.otomatik_yayina_uygun_mu", return_value=kapi_sonucu),
            patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="POSTEDM_SONUC={}", stderr="")) as yayin,
            patch("src.telegram_bot.mesaj_gonder") as mesaj,
            patch("src.telegram_bot.medya_grubu_gonder"),
            patch("src.telegram_bot.haber_onayina_sun", return_value=True) as onay,
        ):
            telegram_bot.finans_icerigi_hazirla_ve_yayinla(oto_yayin=True)
        return yayin, mesaj, onay

    def test_kapi_gecerse_onaysiz_yayinlanir(self):
        yayin, _, onay = self._calistir((True, []))
        yayin.assert_called_once()
        onay.assert_not_called()

    def test_hakem_calismadiysa_onaya_duser_ve_nedeni_yazilir(self):
        neden = "ℹ️ ANLAM DENETİMİ ÇALIŞMADI: kaynak metin yok ya da ikinci model yanıt vermedi"
        yayin, mesaj, onay = self._calistir((False, [neden]))
        yayin.assert_not_called()
        onay.assert_called_once()
        metin = "\n".join(c.args[0] for c in mesaj.call_args_list)
        self.assertIn("Otomatik yayın durduruldu", metin)
        self.assertIn("ANLAM DENETİMİ ÇALIŞMADI", metin)


if __name__ == "__main__":
    unittest.main(verbosity=2)
