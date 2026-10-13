"""
tests/test_foto_vision.py — Kapak fotoğrafına Vision denetimi (2026-10-07).

`src/gorsel_denetim.py` yazılmış ama hiçbir yerden çağrılmıyordu: kardeş haberin fotoğrafı başka bir
olayı, stok araması alakasız bir kareyi getirebiliyordu. Artık kaynağı belirsiz iki katmanda (kardeş
haber, stok) fotoğrafın içine bakılır. Haberin kendi sayfasındaki fotoğraf (og:image) sorulmaz.
Model cevap vermezse fotoğraf kabul edilir: denetim akışı tıkamaz. Ağ yok; hepsi sahte.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests
from PIL import Image

from src import gorsel_denetim as gd
from src import haber_tasarim as ht

UYGUN = {"fotografta_ne_var": "apartmanlar", "konuyu_gosteriyor_mu": True, "baglam_uyuyor_mu": True, "sebep": "uygun"}
KONU_DISI = {**UYGUN, "fotografta_ne_var": "kedi", "konuyu_gosteriyor_mu": False, "sebep": "kedi fotoğrafı"}
BAGLAM_ters = {**UYGUN, "baglam_uyuyor_mu": False, "sebep": "başka olay"}


def _foto(renk="gray") -> Image.Image:
    return Image.new("RGB", (200, 300), renk)


def _yanit(durum=200, sonuc=None, ham=None):
    r = MagicMock()
    r.status_code = durum
    r.text = "hata"
    if ham is None:
        ham = {"candidates": [{"content": {"parts": [{"text": json.dumps(sonuc)}]}}]}
    r.json.return_value = ham
    return r


class TestVisionModulu(unittest.TestCase):
    def _cagir(self, yanitlar):
        with patch.object(gd, "_anahtarlar", return_value=["anahtar"]), \
             patch.object(gd.requests, "post", side_effect=yanitlar) as post:
            sonuc = gd.gorseli_denetle(_foto(), "Başlık", konu="konu")
        return sonuc, post

    def test_test_modunda_anahtar_yok_ag_yok(self):
        # Ortamda anahtar olsa bile (CI sırrı, geliştiricinin kabuğu) test modunda kullanılmaz
        with patch.dict(os.environ, {"GEMINI_API_KEY": "gizli"}):
            self.assertEqual(gd._anahtarlar(), [])
        with patch.dict(os.environ, {"GEMINI_API_KEY": "gizli", "POSTEDM_TEST_MODU": "0"}):
            # Tam liste değil: başka testlerin sızdırdığı anahtarlar da gelebilir (src/twitter.py
            # içe aktarılırken gerçek .env'i yüklüyor)
            self.assertIn("gizli", gd._anahtarlar())  # koruma yalnız test moduna bağlı
        with patch.object(gd.requests, "post") as post:
            self.assertIsNone(gd.gorseli_denetle(_foto(), "Başlık"))
        post.assert_not_called()

    def test_basarili_yanit_cozulur(self):
        sonuc, post = self._cagir([_yanit(200, UYGUN)])
        self.assertEqual(sonuc, UYGUN)
        self.assertEqual(post.call_count, 1)

    def test_birinci_model_kotada_ikinciye_gecer(self):
        sonuc, post = self._cagir([_yanit(429), _yanit(200, KONU_DISI)])
        self.assertEqual(sonuc, KONU_DISI)
        self.assertEqual(post.call_count, 2)
        self.assertIn(gd.MODELLER[0], post.call_args_list[0][0][0])
        self.assertIn(gd.MODELLER[1], post.call_args_list[1][0][0])

    def test_zaman_asimi_ve_5xx_zincirde_atlanir(self):
        sonuc, _ = self._cagir([requests.Timeout("yavaş"), _yanit(503)])
        self.assertIsNone(sonuc)  # tüm model denendi, hiçbiri cevap vermedi

    def test_bozuk_yanit_sonraki_modele_gecer(self):
        sonuc, post = self._cagir([_yanit(200, ham={"candidates": []}), _yanit(200, UYGUN)])
        self.assertEqual(sonuc, UYGUN)
        self.assertEqual(post.call_count, 2)

    def test_tum_modeller_basarisizsa_none_reddetmek_degil(self):
        sonuc, _ = self._cagir([_yanit(429)] * len(gd.MODELLER))
        self.assertIsNone(sonuc)  # None "soramadık" demek; False "alakasız" demek (docstring uyarısı)

    def test_toplam_sure_siniri(self):
        saat = iter([0.0, 0.0, gd.AZAMI_TOPLAM_SURE + 1, gd.AZAMI_TOPLAM_SURE + 2])
        with patch.object(gd, "_anahtarlar", return_value=["anahtar"]), \
             patch.object(gd.time, "monotonic", side_effect=lambda: next(saat)), \
             patch.object(gd.requests, "post", side_effect=[_yanit(429), _yanit(200, UYGUN)]) as post:
            self.assertIsNone(gd.gorseli_denetle(_foto(), "Başlık"))
        self.assertEqual(post.call_count, 1)  # ikinci model süre dolduğu için denenmedi

    def test_anahtar_yoksa_none(self):
        with patch.object(gd, "_anahtarlar", return_value=[]), patch.object(gd.requests, "post") as post:
            self.assertIsNone(gd.gorseli_denetle(_foto(), "Başlık"))
        post.assert_not_called()


class TestFotoZinciri(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dizin = Path(self.tmp.name)
        self.stok_dosyasi = self.dizin / "stok.jpg"
        _foto("blue").save(self.stok_dosyasi)
        self.haber = {"id": 77, "orijinal_baslik": "Silivri'de arsa fiyatları", "spot": "Arsa fiyatları yükseldi.",
                      "orijinal_url": "https://haber.example/a", "kategori_kodu": "SEKTOREL_HABER_VE_ANALIZ"}

    def tearDown(self):
        self.tmp.cleanup()

    def _sec(self, *, og=None, kardes=(None, None), stoklar=None, vision=UYGUN, haber=None, foto_yolu=None):
        """Katmanları sahte verir. `stoklar`: stok aramasının sırayla döneceği yollar."""
        haber = haber if haber is not None else dict(self.haber)
        if not isinstance(vision, (list, Exception)):
            vision = [vision] * 5
        vision_mock = MagicMock(side_effect=vision if isinstance(vision, list) else vision)
        stok_mock = MagicMock(side_effect=list(stoklar if stoklar is not None else [self.stok_dosyasi]))
        with patch.object(ht, "_foto_ac", side_effect=lambda k: _foto("red") if (k and k == og) else (k if isinstance(k, Image.Image) else None)), \
             patch("src.fetch_article.og_gorseli_cek", return_value=og), \
             patch("src.fetch_article.tum_gorselleri_cek", return_value=[]), \
             patch("src.make_image._haber_gorseli_alternatifi", return_value=kardes), \
             patch("src.fetch_stock.stok_fotografi_ara", stok_mock), \
             patch("src.gorsel_denetim.gorseli_denetle", vision_mock):
            foto = ht.fotografi_sec(haber, foto_yolu, self.dizin)
        return foto, haber, vision_mock, stok_mock

    def test_haberin_kendi_fotografi_sorulmaz(self):
        foto, haber, vision, stok = self._sec(og="https://haber.example/og.jpg")
        self.assertIsNotNone(foto)
        vision.assert_not_called()
        stok.assert_not_called()
        self.assertTrue(Path(haber["foto_yolu"]).exists())

    def test_onaylanan_fotograf_sorulmaz(self):
        foto, _, vision, _ = self._sec(foto_yolu=_foto("green"))
        self.assertIsNotNone(foto)
        vision.assert_not_called()

    def test_kardes_foto_uygunsa_atifla_kullanilir_stoka_inilmez(self):
        kardes = _foto("yellow")
        foto, haber, vision, stok = self._sec(kardes=(kardes, "Basın Kaynağı (x)"))
        self.assertIs(foto, kardes)
        self.assertEqual(haber["foto_atif"], "Basın Kaynağı (x)")
        self.assertEqual(vision.call_count, 1)
        stok.assert_not_called()

    def test_kardes_foto_konu_disiysa_atilir_ve_stoka_gecilir(self):
        kardes = _foto("yellow")
        foto, haber, vision, stok = self._sec(kardes=(kardes, "Basın Kaynağı (x)"), vision=[KONU_DISI, UYGUN])
        self.assertIsNot(foto, kardes)
        self.assertNotIn("foto_atif", haber)  # reddedilen fotoğrafın atfı kayda geçmez
        self.assertEqual(stok.call_count, 1)

    def test_baglama_ters_dusen_kardes_foto_atilir(self):
        kardes = _foto("yellow")
        foto, haber, _, _ = self._sec(kardes=(kardes, "Basın Kaynağı (x)"), vision=[BAGLAM_ters, UYGUN])
        self.assertIsNot(foto, kardes)
        self.assertNotIn("foto_atif", haber)

    def test_ilk_stok_reddedilir_ikincisi_kabul(self):
        ikinci = self.dizin / "stok2.jpg"
        _foto("green").save(ikinci)
        foto, _, vision, stok = self._sec(stoklar=[self.stok_dosyasi, ikinci], vision=[KONU_DISI, UYGUN])
        self.assertIsNotNone(foto)
        self.assertEqual(stok.call_count, 2)
        self.assertEqual(vision.call_count, 2)
        r, g, b = foto.getpixel((5, 5))  # JPEG sıkıştırması rengi birkaç birim oynatır
        self.assertTrue(g > 100 and r < 20 and b < 20, (r, g, b))  # ikinci karenin (yeşil) rengi

    def test_iki_stok_da_reddedilirse_kapak_fotografsiz_cizilir(self):
        foto, haber, _, stok = self._sec(stoklar=[self.stok_dosyasi, self.stok_dosyasi], vision=[KONU_DISI, KONU_DISI])
        self.assertIsNone(foto)
        self.assertEqual(stok.call_count, 2)  # sonsuz döngü yok
        self.assertNotIn("foto_yolu", haber)  # reddedilen kare diske sabitlenmez

    def test_vision_soramazsa_fotograf_kabul_edilir(self):
        for vision in (None, {}, "metin", RuntimeError("kota")):
            with self.subTest(vision=vision):
                kardes = _foto("yellow")
                foto, _, _, _ = self._sec(kardes=(kardes, "x"), vision=[vision] if not isinstance(vision, Exception) else vision)
                self.assertIs(foto, kardes)

    def test_istemde_baslik_ve_kardes_icin_baglam_vardir_stok_icin_yok(self):
        _, _, vision, _ = self._sec(kardes=(_foto("yellow"), "x"))
        cagri = vision.call_args
        self.assertIn("Silivri'de arsa fiyatları", cagri[0])
        self.assertTrue(cagri[1]["konu"])
        self.assertIn("Arsa fiyatları yükseldi", cagri[1]["baglam"])

        _, _, vision, _ = self._sec(kardes=(None, None))
        self.assertEqual(vision.call_args[1]["baglam"], "")  # stok temsili: bağlam aranmaz


if __name__ == "__main__":
    unittest.main()
