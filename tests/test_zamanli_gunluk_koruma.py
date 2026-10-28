"""
tests/test_zamanli_gunluk_koruma.py — günlük tur iki yerden tetiklenir, ama aynı slot günde BİR kez üretilir (2026-10-12)

Günlük tur artık ASIL olarak Cloudflare cron'undan (Worker `scheduled()` → `slot_hazirla` {slot, zamanli: true}) gelir;
GitHub'ın gecikmeli (6-10 saat) cron'u yedek olarak açık kalır. İkisi de çalışırsa ikinci içerik, ikinci konu tüketimi
ve (sözlükte) onay kuyruğuna ikinci kart çıkmasın diye hazirla.py zamanlanmış slotu aynı Türkiye gününde bir kez çalıştırır.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import importlib.util
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import telegram_bot as tb


def _hazirla_modulu():
    spec = importlib.util.spec_from_file_location("hazirla_gunluk_koruma_modul", KOK / "scripts" / "hazirla.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class SahteAyarlar:
    """db.ayar_oku / ayar_yaz yerine bellekte sözlük: gerçek test veritabanına işaret sızdırmaz."""

    def __init__(self, **baslangic):
        self.veri = dict(baslangic)

    def oku(self, anahtar, varsayilan=None):
        return self.veri.get(anahtar, varsayilan)

    def yaz(self, anahtar, deger):
        self.veri[anahtar] = str(deger)


BUGUN = "2026-10-13"
DUN = "2026-10-12"


class TestGunlukKoruma(unittest.TestCase):
    def setUp(self):
        self.hazirla = _hazirla_modulu()
        self.ayar = SahteAyarlar()
        self.sablon = [
            mock.patch("src.db.ayar_oku", side_effect=self.ayar.oku),
            mock.patch("src.db.ayar_yaz", side_effect=self.ayar.yaz),
            mock.patch("src.telegram.akislar.zamanli._tr_bugun", return_value=BUGUN),
        ]
        for m in self.sablon:
            m.start()
            self.addCleanup(m.stop)

    def _calistir(self, argv, zamanlanmis, sonuc=True):
        ortam = {"ZAMANLANMIS": "true" if zamanlanmis else ""}
        with mock.patch.dict(os.environ, ortam), \
             mock.patch.object(sys, "argv", ["hazirla.py", *argv]), \
             mock.patch("src.telegram.ayarlar.bot_duraklatildi_mi", return_value=(False, "")), \
             mock.patch("src.telegram.akislar.uretim.slot_icerigi_hazirla_ve_sun", return_value=sonuc) as slot, \
             mock.patch.object(self.hazirla.db, "eski_kayitlari_temizle", return_value=0), \
             mock.patch.object(self.hazirla.db, "bayat_haberleri_ayikla", return_value=0):
            self.hazirla.main()
        return slot

    def test_ilk_zamanlanmis_tur_calisir_ve_gunu_isaretler(self):
        slot = self._calistir(["--slot", "bilgilendirici"], zamanlanmis=True)
        slot.assert_called_once_with(slot="bilgilendirici", oto_yayin=False)
        self.assertEqual(self.ayar.veri["zamanli_slot_son_gun:bilgilendirici"], BUGUN)

    def test_ayni_gunde_ikinci_zamanlanmis_tur_atlanir(self):
        """Cloudflare 10:00'da çalıştı; 16:37'de gelen GitHub yedeği ikinci içerik ÜRETMEZ."""
        self._calistir(["--slot", "bilgilendirici"], zamanlanmis=True)
        slot = self._calistir(["--slot", "bilgilendirici"], zamanlanmis=True)
        slot.assert_not_called()

    def test_sozluk_icin_de_gunde_bir_kez(self):
        self._calistir(["--slot", "sozluk", "--oto-yayin"], zamanlanmis=True)
        slot = self._calistir(["--slot", "sozluk", "--oto-yayin"], zamanlanmis=True)
        slot.assert_not_called()

    def test_slotlar_birbirinden_bagimsiz(self):
        self._calistir(["--slot", "bilgilendirici"], zamanlanmis=True)
        slot = self._calistir(["--slot", "sozluk", "--oto-yayin"], zamanlanmis=True)
        slot.assert_called_once()

    def test_dunun_isareti_bugunu_engellemez(self):
        self.ayar.veri["zamanli_slot_son_gun:bilgilendirici"] = DUN
        slot = self._calistir(["--slot", "bilgilendirici"], zamanlanmis=True)
        slot.assert_called_once()
        self.assertEqual(self.ayar.veri["zamanli_slot_son_gun:bilgilendirici"], BUGUN)

    def test_basarisiz_tur_isaretlenmez_yedek_yeniden_dener(self):
        slot = self._calistir(["--slot", "bilgilendirici"], zamanlanmis=True, sonuc=False)
        slot.assert_called_once()
        self.assertNotIn("zamanli_slot_son_gun:bilgilendirici", self.ayar.veri)
        slot = self._calistir(["--slot", "bilgilendirici"], zamanlanmis=True)
        slot.assert_called_once()

    def test_elle_tetiklenen_slot_korumaya_takilmaz_ve_isaret_birakmaz(self):
        """Telegram'dan "Günün gönderisi" butonu gün içinde istediği kadar çalışır; zamanlanmış turu da kilitlemez."""
        self.ayar.veri["zamanli_slot_son_gun:bilgilendirici"] = BUGUN
        slot = self._calistir(["--slot", "bilgilendirici"], zamanlanmis=False)
        slot.assert_called_once()
        self.ayar.veri.clear()
        self._calistir(["--slot", "bilgilendirici"], zamanlanmis=False)
        self.assertEqual(self.ayar.veri, {})

    def test_haber_slotu_korunmaz(self):
        self._calistir(["--slot", "haber"], zamanlanmis=True)
        slot = self._calistir(["--slot", "haber"], zamanlanmis=True)
        slot.assert_called_once()
        self.assertFalse(any(k.startswith("zamanli_slot_son_gun") for k in self.ayar.veri))

    def test_yardimcilar_yalniz_gunluk_slotlari_isaretler(self):
        tb.zamanli_slot_isaretle("haber")
        self.assertEqual(self.ayar.veri, {})
        self.assertFalse(tb.zamanli_slot_bugun_yapildi("haber"))
        tb.zamanli_slot_isaretle("sozluk")
        self.assertTrue(tb.zamanli_slot_bugun_yapildi("sozluk"))


class TestWorkflowVeWorkerSozlesmesi(unittest.TestCase):
    """Worker'ın yolladığı yük ile workflow'un okuduğu alanlar aynı olmalı; yoksa dispatch "elle" sayılır, koruma ve duraklatma atlanır."""

    def test_workflow_dispatch_zamanli_yuku_zamanlanmis_sayilir(self):
        metin = (KOK / ".github/workflows/hazirla.yml").read_text(encoding="utf-8")
        self.assertIn("github.event.client_payload.zamanli == true", metin)
        w = yaml.safe_load(metin)
        self.assertIn("slot_hazirla", w[True]["repository_dispatch"]["types"])
        adim = next(a for a in w["jobs"]["hazirla"]["steps"] if a.get("name") == "Günlük İçerik Hazırla ve Paylaş")
        self.assertIn("github.event.action == 'slot_hazirla'", adim["if"])
        self.assertIn("client_payload.zamanli", adim["env"]["ZAMANLANMIS"])
        self.assertEqual(adim["env"]["SLOT"], "${{ github.event.client_payload.slot }}")

    def test_worker_slot_hazirla_zamanli_yuk_gonderiyor(self):
        kaynak = (KOK / "worker/index.js").read_text(encoding="utf-8")
        self.assertIn("slot: is.slot, zamanli: true", kaynak)
        for cron, slot in (("0 7 * * *", "bilgilendirici"), ("30 9 * * *", "sozluk")):
            self.assertRegex(kaynak, rf'"{re.escape(cron)}":\s*\{{ olay: "slot_hazirla", slot: "{slot}"')

    def test_gunluk_slotlar_workflow_cronlariyla_ayni_saatte(self):
        """20 Ekim sonrası: yedek günlük GitHub cron'ları kaldırıldı; tetikleyici Cloudflare cron'udur."""
        import tomllib
        cf = set(tomllib.loads((KOK / "worker/wrangler.toml").read_text(encoding="utf-8"))["triggers"]["crons"])
        w = yaml.safe_load((KOK / ".github/workflows/hazirla.yml").read_text(encoding="utf-8"))
        gh = {c["cron"] for c in w[True]["schedule"]}
        self.assertTrue({"0 7 * * *", "30 9 * * *"} <= cf)
        self.assertNotIn("0 7 * * *", gh)
        self.assertNotIn("30 9 * * *", gh)


if __name__ == "__main__":
    unittest.main(verbosity=2)
