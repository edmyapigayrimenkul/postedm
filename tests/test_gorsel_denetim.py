"""
tests/test_gorsel_denetim.py — Bütün görsel formatlarda taşma, çakışma ve kırpılma sözleşmesi.

2026-09-25: sözlük kartında (#243) tanımın son satırları alttaki kutunun
arkasında kaldı, kutu üç maddenin ikisini gösterdi; kapak manşeti uzun olunca
tuvalin dışına çiziliyordu; karşılaştırma tablosu veri yokken kendi rakamlarını
basıyordu. Denetim çizim çağrılarını dinler (scripts/gorsel_denetim.py).

Buradaki alt küme her formatın temsili vakalarıdır (≈15 sn). Tam paket
(164 vaka, iki ölçü) CI'da ayrı adımda çalışır.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")

import importlib.util
import unittest
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("gorsel_denetim", KOK / "scripts" / "gorsel_denetim.py")
gorsel_denetim = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gorsel_denetim)

VAKALAR = {"gercekci", "uretim_243", "iki_kat_uzun", "manset_uzun", "cok_madde", "tamamen_bos", "bozuk_tip"}


class TestGorselDenetim(unittest.TestCase):
    def test_temsili_vakalarda_tasma_cakisma_kirpilma_yok(self):
        rapor = gorsel_denetim.denetle(sessiz=True, vaka_filtre=VAKALAR, olcu_filtre={"besleme"})
        hatalar = [f"{v['format']}/{v['vaka']}: {s}" for v in rapor["vakalar"] for s in v["sorunlar"] if "PUNTO:" not in s]
        self.assertEqual(hatalar, [], "\n".join(hatalar[:20]))
        self.assertGreaterEqual(len(rapor["vakalar"]), 40)

    def test_243_sozluk_karti_artik_sigiyor(self):
        rapor = gorsel_denetim.denetle(format_filtre="sozluk", sessiz=True, vaka_filtre={"uretim_243"})
        vaka = rapor["vakalar"][0]
        self.assertEqual(vaka["slayt"], 1)
        self.assertEqual(vaka["sorunlar"], [])

    def test_denetim_gercek_ortuleni_yakaliyor(self):
        """Denetimin kendisi: kutunun sonradan örttüğü metin hata sayılmalı."""
        from PIL import Image, ImageDraw
        gorsel_denetim.kaydi_ac()
        try:
            gorsel_denetim._OLAYLAR.clear()
            gorsel_denetim._SLAYTLAR.clear()
            img = Image.new("RGB", (1080, 1350), "white")
            d = ImageDraw.Draw(img)
            d.text((100, 1000), "Kutunun altında kalan tanım satırı", fill="black",
                   font=__import__("src.make_image", fromlist=["x"])._font_yukle(
                       __import__("src.make_image", fromlist=["x"]).FONT_SANS_MEDIUM, 38))
            d.rounded_rectangle([(78, 980), (1002, 1220)], radius=12, fill=(18, 19, 22))
            yol = gorsel_denetim.CIKTI / "oz_denetim.jpg"
            yol.parent.mkdir(parents=True, exist_ok=True)
            img.save(yol)
            sorunlar = gorsel_denetim.slayt_denetle(gorsel_denetim._SLAYTLAR[-1])
            yol.unlink(missing_ok=True)
        finally:
            gorsel_denetim.kaydi_kapat()
        self.assertTrue(any(s.startswith("ÖRTÜLDÜ") for s in sorunlar), sorunlar)


if __name__ == "__main__":
    unittest.main()
