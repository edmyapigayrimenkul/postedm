"""
tests/test_haber_tasarimi.py — Haber tasarımı Instabot'la aynıdır (2026-10-07 kararı).

Kullanıcı: "haber içeriğinde her şey Instabot'la aynı olsun, yalnız logo ve renkler farklı."
Çizim kodu Instabot'tan birebir taşındı (src/haber_tasarim.py); bu testler taşımanın
kendi kurallarını sabitler: tek ana kare, 4:5 merkez kutusu, uzun metin yaması, kanca
stilleri ve Türkçe karakter kapsamı.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageChops, ImageDraw

from src import hook_motoru, haber_tasarim as ht

HABER = {
    "id": 9001,
    "kaynak": "Ekonomim",
    "manset": "Enflasyon %29,7'ye indi, MUFG faiz indirimi bekliyor",
    "spot": "Yıllık enflasyon Kasım 2021'den bu yana en düşük seviyeye geriledi.",
    "kanca": "120 BAZ PUAN // SWAP PİYASASI",
    "detay_maddeleri": [
        {"etiket": "ENFLASYON", "metin": "Yıllık enflasyon ağustostaki %31,5 seviyesinden eylülde %29,7'ye geriledi. "
                                           "Aylık enflasyon %1,8 oldu."},
        {"etiket": "BEKLENTİ", "metin": "Bir yıl vadeli swap oranları yaklaşık 120 baz puanlık faiz indirimini fiyatlıyor."},
    ],
    "uzman_notu": "Başvurudan önce e-Devlet'te üzerinize kayıtlı konut olup olmadığına bakın.",
}


def _foto():
    """Gökyüzü gradyanlı yapay yatay fotoğraf (ağ yok)."""
    im = Image.new("RGB", (1280, 720), (90, 120, 160))
    ImageDraw.Draw(im).rectangle([0, 400, 1280, 720], fill=(40, 70, 40))
    return im


def _ciz(haber=None, olcu="story", **k):
    haber = dict(HABER if haber is None else haber)
    with tempfile.TemporaryDirectory() as d:
        with patch.object(ht, "fotografi_sec", return_value=_foto()):
            yollar = ht.slaytlari_uret(haber, Path(d), "t", olcu=olcu, **k)
        return [Image.open(y).convert("RGB").copy() for y in yollar]


class TestAnaKare(unittest.TestCase):
    def test_story_1080x1920_besleme_1080x1350(self):
        story, besleme = _ciz(olcu="story"), _ciz(olcu="besleme")
        self.assertEqual({im.size for im in story}, {(1080, 1920)})
        self.assertEqual({im.size for im in besleme}, {(1080, 1350)})
        self.assertEqual(len(story), len(besleme))

    def test_besleme_ana_karenin_ortadan_kirpilmasidir(self):
        # Instabot mimarisi: ayrı 4:5 yerleşimi yok; akış = 9:16 ana karenin merkezi
        story, besleme = _ciz(olcu="story"), _ciz(olcu="besleme")
        for s, b in zip(story, besleme):
            fark = ImageChops.difference(s.crop((0, 285, 1080, 1635)), b)
            # JPEG kodlama farkı dışında aynı olmalı
            self.assertLess(max(fark.convert("L").getdata()), 40)

    def test_kutu_siniri(self):
        self.assertEqual((ht.KUTU_UST, ht.KUTU_ALT), (285, 1635))
        self.assertEqual(ht.AYARLAR["gorsel"]["dikey_guvenli_pay"], 330)

    def test_eksik_manset_durdurur(self):
        from src.make_image import EksikIcerik
        with self.assertRaises(EksikIcerik):
            _ciz({"id": 1, "kaynak": "x"})

    def test_eski_ve_yeni_alan_adlari(self):
        yeni = {"id": 2, "ig_baslik": "Başlık", "slayt_ozet": "Özet", "detay_yazisi": "Bir.\n\nİki.",
                "vurgu_sayi": "%29,7", "vurgu_etiket": "yıllık enflasyon", "alinti": "Alıntı metni burada", "alinti_sahibi": "MUFG"}
        g = ht.girdiyi_hazirla(yeni)
        self.assertEqual((g["baslik"], g["ozet"]), ("Başlık", "Özet"))
        self.assertEqual(g["vurgu"], ("%29,7", "yıllık enflasyon"))
        self.assertEqual(g["alinti"], ("Alıntı metni burada", "MUFG"))
        eski = ht.girdiyi_hazirla(HABER)
        self.assertIn("swap", eski["detay"])
        self.assertEqual(eski["sana_etkisi"], HABER["uzman_notu"])


class TestYama(unittest.TestCase):
    def test_uzun_tek_kelime_ve_url_bolunur(self):
        # Instabot bölmüyor: tuvali taşırıyordu
        ciz = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        font = ht._font(40, ht.EKSEN_OZET)
        for kelime in ("Gayrimenkulleştirilemeyeceklerindenmişsiniz", "https://edmyapigayrimenkul.com/rehber/hisseli-tapu-onalim"):
            for satir in ht._satirlara_bol(kelime, font, 600, ciz):
                self.assertLessEqual(ciz.textlength(satir, font=font), 600, satir)

    def test_satir_sonlu_baslik_cokmez(self):
        haber = dict(HABER, manset="İki\nsatırlı\n\nbaşlık", kaynak="Kaynak\nAdı")
        self.assertGreaterEqual(len(_ciz(haber)), 2)   # kapak + en az bir detay sayfası

    def test_uzun_kaynak_adi_kisalir(self):
        ciz = ImageDraw.Draw(Image.new("RGB", (1080, 300)))
        ht._kaynak_satiri_ciz(ciz, 80, 100, "SİLİVRİ BELEDİYESİ " * 12)   # çökmemeli, taşmamalı

    def test_ozet_noktalari_kenara_tasmaz(self):
        ciz = ImageDraw.Draw(Image.new("RGB", (10, 10)))
        uzun = " ".join(["bildirilmesinden itibaren üç ay içinde önalım hakkını kullanabilir"] * 6)
        font, satirlar, _ = ht._ozeti_yerlestir(uzun, ciz, 920, azami_satir=4, punto=34)
        self.assertTrue(satirlar[-1].endswith("…"))
        for s in satirlar:
            self.assertLessEqual(ciz.textlength(s.replace("**", ""), font=font), 920)

    def test_kategori_rengi_yok_mürekkep(self):
        self.assertEqual(ht.serit_rengi("ekonomi", {}), ht.ZEMIN)
        self.assertEqual(ht.serit_rengi("spor", {}), ht.ZEMIN)


class TestTema(unittest.TestCase):
    def test_instabot_renkleri_kalmadi(self):
        kaynak = Path(ht.__file__).read_text()
        for yasak in ("(226, 170, 88)", "(6, 182, 212)", "(16, 185, 129)", "(4, 24, 28)", "dailybrief.co"):
            self.assertNotIn(yasak, kaynak)

    def test_font_turkce_karakterleri_tam_kapsar(self):
        # "Türkçe destekleyen font seç": ölçülmüş kapsam; eksik karakter kutu (□) basar
        from fontTools.ttLib import TTFont
        cmap = set(TTFont(ht.FONT_YOLU, lazy=True).getBestCmap())
        eksik = [c for c in "ğĞşŞıİöÖüÜçÇ₺%’“”…—·×" if ord(c) not in cmap]
        self.assertEqual(eksik, [], f"{ht.FONT_YOLU.name} eksik: {eksik}")

    def test_inter_instabot_ile_ayni_dosya(self):
        import hashlib
        ortak = Path.home() / "Dogukan/instabot/assets/fonts/Inter-Variable.ttf"
        if not ortak.exists():
            self.skipTest("Instabot deposu bu makinede yok")
        h = lambda p: hashlib.md5(Path(p).read_bytes()).hexdigest()
        self.assertEqual(h(ht.FONT_YOLU), h(ortak))


class TestKanca(unittest.TestCase):
    def _kanca_kutusu(self, stil):
        eski = hook_motoru.KANCA_STILI
        hook_motoru.KANCA_STILI = stil
        try:
            zemin = Image.new("RGB", (1080, 1920), (200, 40, 40))   # kırmızı zemin: kırmızı metin kaybolurdu
            return hook_motoru.ciz_minimal_vurgu(zemin, 74, 800, "", "120 BAZ PUAN", "SWAP PİYASASI", stil=stil)
        finally:
            hook_motoru.KANCA_STILI = eski

    def test_varsayilan_stil_plaka(self):
        self.assertEqual(hook_motoru.KANCA_STILI, "plaka")

    def test_plaka_ikinci_satir_beyaz_yazi_kirmizi_dolgu(self):
        out = self._kanca_kutusu("plaka")
        renkler = {out.getpixel((x, y)) for x in range(80, 400, 3) for y in range(900, 960, 3)}
        self.assertIn(hook_motoru.PLAKA_KIRMIZI, renkler)
        self.assertIn((255, 255, 255), renkler)

    def test_ikinci_satir_kirmizi_metin_degil(self):
        # Fotoğrafta kırmızı METİN okunmuyordu (Instabot ölçümü: kontrast 2,02 < 3,00)
        for stil in ("plaka", "cubuk"):
            out = self._kanca_kutusu(stil)
            # metin pikselleri beyaz olmalı: beyaz piksel sayısı anlamlı
            beyaz = sum(1 for x in range(74, 700, 2) for y in range(850, 960, 2) if out.getpixel((x, y)) == (255, 255, 255))
            self.assertGreater(beyaz, 50, stil)

    def test_kanca_fontu_inter_ve_turkce(self):
        f = hook_motoru._font(60, "sans_bold")
        self.assertIn("Inter", Path(f.path).name)


if __name__ == "__main__":
    unittest.main()
