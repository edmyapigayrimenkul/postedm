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

    def test_denetim_fontta_olmayan_karakteri_yakaliyor(self):
        """"●" IBM Plex Sans'ta yok; kutu (□) basılır ve taşma denetimi bunu görmez."""
        from src import make_image as mi
        self.assertEqual(gorsel_denetim.eksik_glifler("● NE DEĞİŞTİ", str(mi.FONT_SANS_BOLD)), ["●"])
        self.assertEqual(gorsel_denetim.eksik_glifler("Hisseli tapu İŞĞÜ ₺", str(mi.FONT_FRAUNCES)), [])


class TestGorselMetinSuzgeci(unittest.TestCase):
    """Model emojisi, görünmez karakter ve yön işareti kartta kutu olarak basılıyordu."""

    def test_kutu_basilacak_karakterler_ayiklanir(self):
        from src import make_image as mi
        vakalar = {
            "✅ Tapuyu kontrol edin": "Tapuyu kontrol edin",
            "O\u200br\u200bt\u200bak": "Ortak",
            "\u202etersine": "tersine",
            "Tapu → İmar": "Tapu – İmar",
            "satır 🏠\nikinci": "satır\nikinci",
        }
        for girdi, beklenen in vakalar.items():
            self.assertEqual(mi.gorsel_metni(girdi), beklenen, repr(girdi))

    def test_temiz_turkce_metne_dokunulmaz(self):
        from src import make_image as mi
        for metin in ("Hisseli tapuda şuyulandırma: %45 ₺ — \"önalım\" & İĞÜŞÇÖ", "iki  boşluk korunur"):
            self.assertIs(mi.gorsel_metni(metin), metin)

    def test_cagiranin_verisi_ve_yollar_degismez(self):
        """Süzgeç kopyaya uygulanır: caption'daki emoji ve dosya yolu yerinde kalmalı."""
        from src import make_image as mi
        veri = {"caption_instagram": "Yeni rehber ✅", "gorsel_yolu": "/tmp/a  ✅.jpg",
                "maddeler": [{"metin": "✅ Noter"}]}
        kopya = mi.gorsel_verisi_temizle(veri)
        self.assertEqual(veri["caption_instagram"], "Yeni rehber ✅")
        self.assertEqual(veri["maddeler"][0]["metin"], "✅ Noter")
        self.assertEqual(kopya["maddeler"][0]["metin"], "Noter")
        self.assertEqual(kopya["gorsel_yolu"], "/tmp/a  ✅.jpg")


if __name__ == "__main__":
    unittest.main()
