"""
tests/test_kanun_okuma.py — kanun okuma aracı (scripts/kanun_oku.py), yeni kanunlar ve önbelleğe atomik yazım.

Ağ YOK: kanun metni sahte. (2026-10-12'de mevzuat.gov.tr bu geliştirme ortamının ağ politikasıyla kapalıydı;
canlı doğrulama — özellikle yeni kanunların tertip numaraları — ilk açık ortamda `kanun_oku.py kanunlar --dene` ile yapılmalı.)
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import importlib.util
import io
import json
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import kanun_okuma, mevzuat  # noqa: E402

# 12 maddelik sahte kanun + geçici madde. Başlıklar gerçek metindeki gibi satır içinde.
_GOVDELER = {
    1: "Bu kanunun amacı taşınmaz mülkiyetini düzenlemektir.",
    2: "Taşınmaz maliki İPOTEK hakkını tapu sicilinde kurar. Ipotek yazılı yapılır.",
    3: "Rehin hakkı üç ay içinde düşer. (Değişik: 24/12/2025 - 7571/5 md.) Haklar saklıdır.",
    4: "Dördüncü madde kısa.",
}
for _n in range(5, 13):
    _GOVDELER[_n] = f"{_n}. madde metni: ipotek ile ilgili bir hüküm {_n}."
SAHTE = "Sahte Kanun Başlığı 12/1/2026 " + " ".join(f"MADDE {n} - {m}" for n, m in _GOVDELER.items()) \
    + " GEÇİCİ MADDE 1 - Bu madde geçicidir ve ipotek anılmaz."


def _sahte(no):
    return SAHTE if no == 4721 else None


class TestMaddelereBolme(unittest.TestCase):
    def test_maddeler_ve_gecici_madde_ayrilir(self):
        m = kanun_okuma.maddelere_bol(SAHTE)
        self.assertEqual([x["etiket"] for x in m][:3], ["md. 1", "md. 2", "md. 3"])
        self.assertEqual(m[-1]["etiket"], "geçici md. 1")
        self.assertTrue(m[-1]["gecici"])
        # her madde bir sonrakinin başlığında biter, örtüşme yok
        for a, b in zip(m, m[1:]):
            self.assertEqual(a["bit"], b["bas"])
        self.assertEqual(m[-1]["bit"], len(SAHTE))

    def test_metin_icindeki_madde_gondermesi_baslik_sayilmaz(self):
        metin = "MADDE 1 - Bu hüküm 5 inci maddeye göre uygulanır. MADDE 2 - İkinci."
        self.assertEqual([x["etiket"] for x in kanun_okuma.maddelere_bol(metin)], ["md. 1", "md. 2"])


# Ek maddeler normal maddeyle aynı numarayı taşır (3402'de Madde 6 ve Ek Madde 6).
EKLI = ("MADDE 5 - Beşinci madde: kira bedeli. MADDE 6 - Altıncı madde: askı ilanı. Ek Madde 6 - Genel mahkemeler görevlidir. "
        "EK MADDE 7 - Yedinci ek madde: ipotek. GEÇİCİ MADDE 1 - Geçici.")


def _ekli(no):
    return EKLI if no == 4721 else None


class TestEkMaddeler(unittest.TestCase):
    def test_ek_madde_ayri_tur_ve_etiket(self):
        m = kanun_okuma.maddelere_bol(EKLI)
        self.assertEqual([x["etiket"] for x in m], ["md. 5", "md. 6", "ek md. 6", "ek md. 7", "geçici md. 1"])
        self.assertEqual([x["ek"] for x in m], [False, False, True, True, False])

    def test_normal_madde_ek_maddeyle_karismaz(self):
        okunan, yok = kanun_okuma.maddeleri_oku("4721 sayılı Kanun md. 6", kanun_metni=_ekli)
        self.assertEqual(yok, [])
        self.assertIn("askı ilanı", okunan[0]["metin"])
        self.assertNotIn("Genel mahkemeler", okunan[0]["metin"])
        self.assertEqual(okunan[0]["etiket"], "md. 6")

    def test_ek_madde_atifla_okunur(self):
        okunan, yok = kanun_okuma.maddeleri_oku("4721 sayılı Kanun ek md. 6", kanun_metni=_ekli)
        self.assertEqual(yok, [])
        self.assertEqual(okunan[0]["etiket"], "ek md. 6")
        self.assertIn("Genel mahkemeler görevlidir", okunan[0]["metin"])
        self.assertNotIn("askı ilanı", okunan[0]["metin"])
        # Madde metninin sonu bir sonraki EK maddenin başlığında biter ("Ek" sözcüğü bu maddeye sızmaz)
        self.assertFalse(okunan[0]["metin"].rstrip().endswith("EK"))

    def test_olmayan_ek_madde_bulunamayan_listesinde_ek_etiketiyle(self):
        okunan, yok = kanun_okuma.maddeleri_oku("4721 sayılı Kanun ek md. 9", kanun_metni=_ekli)
        self.assertEqual(okunan, [])
        self.assertTrue(any("ek md. 9" in x for x in yok), yok)

    def test_arama_ek_maddedeki_gecisi_ek_etiketiyle_verir(self):
        sonuc, hata = kanun_okuma.ara(4721, ["genel mahkemeler"], kanun_metni=_ekli)
        self.assertIsNone(hata)
        self.assertEqual([x["etiket"] for x in sonuc[0]["sonuclar"]], ["ek md. 6"])

    def test_atif_cozumu_ek_ve_gecici_anahtarlari(self):
        atiflar, _ = mevzuat.atiflari_coz("4721 sayılı Kanun md. 5, ek md. 6 ve geçici md. 1")
        self.assertEqual(atiflar, [(4721, ["5", "ek 6", "geçici 1"])])
        atiflar, _ = mevzuat.atiflari_coz("3402 sayılı Kanun ek madde 6 ve 7")
        self.assertEqual(atiflar, [(3402, ["ek 6", "ek 7"])])

    def test_madde_metni_ek_madde_ve_normal_madde(self):
        with patch.object(mevzuat, "kanun_metni", _ekli):
            self.assertIn("askı ilanı", mevzuat.madde_metni(4721, "6"))
            self.assertNotIn("Genel mahkemeler", mevzuat.madde_metni(4721, "6"))
            ek = mevzuat.madde_metni(4721, "ek 6")
            self.assertIn("Genel mahkemeler", ek)
            self.assertTrue(ek.startswith("Ek Madde 6"))
            self.assertNotIn("EK MADDE 7", ek)
            self.assertIn("ipotek", mevzuat.madde_metni(4721, "ek 7"))
            self.assertIsNone(mevzuat.madde_metni(4721, "7"))      # 7 yalnız EK madde olarak var; normal madde 7 yok


class TestMaddeOkuma(unittest.TestCase):
    def test_atiftaki_maddeler_tam_okunur(self):
        okunan, yok = kanun_okuma.maddeleri_oku("4721 sayılı Kanun md. 2 ve 3", kanun_metni=_sahte)
        self.assertEqual(yok, [])
        self.assertEqual([m["etiket"] for m in okunan], ["md. 2", "md. 3"])
        self.assertIn("İPOTEK hakkını tapu sicilinde kurar", okunan[0]["metin"])
        self.assertNotIn("Rehin hakkı", okunan[0]["metin"])           # sonraki maddenin cümlesi karışmaz
        self.assertEqual(okunan[1]["degisiklikler"], ["2025-12-24"])

    def test_sonraki_madde_basligi_isaretlenir(self):
        okunan, _ = kanun_okuma.maddeleri_oku("4721 sayılı Kanun md. 3", kanun_metni=_sahte)
        self.assertTrue(okunan[0]["sonraki"].startswith("MADDE 4 -"), okunan[0]["sonraki"])
        son, _ = kanun_okuma.maddeleri_oku("4721 sayılı Kanun md. 12", kanun_metni=_sahte)
        self.assertTrue(son[0]["sonraki"].startswith("GEÇİCİ MADDE 1"), son[0]["sonraki"])
        gecici, _ = kanun_okuma.maddeleri_oku("4721 sayılı Kanun geçici md. 1", kanun_metni=_sahte)
        self.assertEqual(gecici[0]["sonraki"], "(kanunun son maddesi)")

    def test_aralik_siniri_yok(self):
        """mevzuat.atiflari_coz aralığı varsayılan olarak 4 maddeyle sınırlar; okuma aracı hepsini okur."""
        okunan, yok = kanun_okuma.maddeleri_oku("4721 sayılı Kanun md. 1-12", kanun_metni=_sahte)
        self.assertEqual(len(okunan), 12)
        self.assertEqual(yok, [])
        varsayilan, _ = mevzuat.atiflari_coz("4721 sayılı Kanun md. 1-12")
        self.assertLess(len(varsayilan[0][1]), 12)     # kapı/brief davranışı değişmedi

    def test_olmayan_madde_ve_alinamayan_kanun_bildirilir(self):
        okunan, yok = kanun_okuma.maddeleri_oku("4721 sayılı Kanun md. 99", kanun_metni=_sahte)
        self.assertEqual(okunan, [])
        self.assertTrue(any("md. 99" in y for y in yok), yok)
        okunan, yok = kanun_okuma.maddeleri_oku("6098 sayılı Kanun md. 1", kanun_metni=_sahte)
        self.assertTrue(any("kanun metni alınamadı" in y for y in yok), yok)

    def test_cozulemeyen_atif_bildirilir(self):
        _, yok = kanun_okuma.maddeleri_oku("Kira Yönetmeliği md. 3", kanun_metni=_sahte)
        self.assertTrue(yok)


class TestArama(unittest.TestCase):
    def test_turkce_buyuk_kucuk_harf_duyarsiz_ve_madde_etiketli(self):
        sonuc, hata = kanun_okuma.ara(4721, ["ipotek"], kanun_metni=_sahte)
        self.assertIsNone(hata)
        # md. 2: "İPOTEK" (1; ASCII "Ipotek" Türkçede ı'dır, eşleşmez) + md. 5-12 (8) + geçici md. 1 (1)
        self.assertEqual(sonuc[0]["toplam"], 10)
        etiketler = [r["etiket"] for r in sonuc[0]["sonuclar"]]
        self.assertEqual(etiketler[0], "md. 2")            # "İPOTEK" büyük İ'li yazımı da bulundu
        self.assertIn("md. 5", etiketler)
        self.assertIn("geçici md. 1", etiketler)

    def test_ikinci_aranan_ve_azami_sonuc(self):
        sonuc, _ = kanun_okuma.ara(4721, ["ipotek", "rehin hakkı"], azami=3, kanun_metni=_sahte)
        self.assertEqual(len(sonuc[0]["sonuclar"]), 3)
        self.assertGreater(sonuc[0]["toplam"], 3)          # toplam gerçek sayı, gösterilen kırpılmış
        self.assertEqual(sonuc[1]["sonuclar"][0]["etiket"], "md. 3")

    def test_bulunmayan_kelime_bos_doner(self):
        sonuc, _ = kanun_okuma.ara(4721, ["kamulaştırma"], kanun_metni=_sahte)
        self.assertEqual(sonuc[0]["toplam"], 0)

    def test_kanun_metni_alinamazsa_hata(self):
        sonuc, hata = kanun_okuma.ara(9999, ["x"], kanun_metni=_sahte)
        self.assertEqual(sonuc, [])
        self.assertIn("alınamadı", hata)


class TestKanunListesi(unittest.TestCase):
    YENI = {2942: "Kamulaştırma", 3621: "Kıyı", 4342: "Mera", 6831: "Orman", 4708: "Yapı Denetimi", 488: "Damga",
            193: "Gelir Vergisi", 3065: "Katma Değer", 6100: "Hukuk Muhakemeleri", 6325: "Arabuluculuk",
            2985: "Toplu Konut", 1163: "Kooperatifler", 2886: "Devlet İhale", 5393: "Belediye"}

    def test_planlanan_14_kanun_eklendi(self):
        for no, parca in self.YENI.items():
            with self.subTest(no=no):
                self.assertIn(no, mevzuat.KANUNLAR)
                self.assertIn(parca, mevzuat.KANUNLAR[no][1])
                self.assertTrue(mevzuat.KANUNLAR[no][0], "en az bir tertip adayı")
        self.assertEqual({k["no"] for k in kanun_okuma.kanun_listesi()} & set(self.YENI), set(self.YENI))

    def test_adla_ve_numarayla_atif_cozulur(self):
        cozulecek = {
            "Kamulaştırma Kanunu md. 10 ve 11": (2942, ["10", "11"]),
            "2942 sayılı Kanun md. 11": (2942, ["11"]),
            "Kıyı Kanunu md. 6": (3621, ["6"]),
            "Orman Kanunu md. 2": (6831, ["2"]),
            "Yapı Denetimi Hakkında Kanun md. 5": (4708, ["5"]),
            "Damga Vergisi Kanunu md. 1": (488, ["1"]),
            "GVK md. 70-72": (193, ["70", "71", "72"]),
            "6100 sayılı HMK md. 107": (6100, ["107"]),
            "Hukuk Muhakemeleri Kanunu md. 114": (6100, ["114"]),
            "Belediye Kanunu md. 15, 18": (5393, ["15", "18"]),
            "Kooperatifler Kanunu md. 1": (1163, ["1"]),
        }
        for atif, beklenen in cozulecek.items():
            with self.subTest(atif=atif):
                sonuc, cozulemeyen = mevzuat.atiflari_coz(atif)
                self.assertEqual(sonuc, [(beklenen[0], beklenen[1])])
                self.assertEqual(cozulemeyen, [])

    def test_eski_kanunlarin_cozumu_bozulmadi(self):
        self.assertEqual(mevzuat.atiflari_coz("Türk Medeni Kanunu md. 826, 827 ve 828")[0], [(4721, ["826", "827", "828"])])
        self.assertEqual(mevzuat.atiflari_coz("İmar Kanunu md. 21 ve 32")[0], [(3194, ["21", "32"])])


class TestOnbellekAtomikYazim(unittest.TestCase):
    def test_yazim_yarida_kesilirse_eski_metin_kalir_gecici_dosya_kalmaz(self):
        with tempfile.TemporaryDirectory() as d:
            dosya = Path(d) / "634.txt"
            dosya.write_text("ESKİ TAM METİN", encoding="utf-8")
            orijinal = Path.write_text

            def yarim(self, veri, *a, **k):
                orijinal(self, veri[:3], *a, **k)
                raise OSError("disk doldu")

            with patch.object(Path, "write_text", yarim):
                with self.assertRaises(OSError):
                    mevzuat._atomik_yaz(dosya, "YENİ TAM METİN")
            self.assertEqual(dosya.read_text(encoding="utf-8"), "ESKİ TAM METİN")
            self.assertEqual([p.name for p in Path(d).iterdir()], ["634.txt"])

    def test_paralel_yazar_okuyucu_hic_yarim_metin_gormez(self):
        with tempfile.TemporaryDirectory() as d:
            dosya = Path(d) / "x.txt"
            tam = [("A" * 50_000), ("B" * 50_000)]
            dosya.write_text(tam[0], encoding="utf-8")
            dur = threading.Event()
            gorulen = set()

            def yaz():
                i = 0
                while not dur.is_set():
                    mevzuat._atomik_yaz(dosya, tam[i % 2])
                    i += 1

            t = threading.Thread(target=yaz)
            t.start()
            try:
                for _ in range(300):
                    gorulen.add(dosya.read_text(encoding="utf-8"))
            finally:
                dur.set()
                t.join()
            self.assertTrue(gorulen <= set(tam), "okuyucu yarım ya da karışık metin gördü")


def _betik():
    spec = importlib.util.spec_from_file_location("kanun_oku_betik", KOK / "scripts" / "kanun_oku.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class TestTertipKesfi(unittest.TestCase):
    def _cevap(self, durum, govde=""):
        from unittest.mock import MagicMock
        r = MagicMock()
        r.status_code = durum
        r.text = govde
        r.content = govde.encode()
        return r

    def test_ilk_calisan_tertip_doner_yanlis_tertip_302(self):
        tam = "<html>" + "x" * 6000 + " MADDE 1 - Amaç. </html>"
        cevaplar = {1: self._cevap(302), 2: self._cevap(302), 3: self._cevap(200, tam)}
        with patch.object(mevzuat.requests, "get", side_effect=lambda url, params, **kw: cevaplar[params["MevzuatTertip"]]):
            self.assertEqual(mevzuat.tertip_kesfet(2942), 3)

    def test_hicbiri_tutmazsa_none(self):
        with patch.object(mevzuat.requests, "get", return_value=self._cevap(302)):
            self.assertIsNone(mevzuat.tertip_kesfet(2942))

    def test_ag_hatasinda_none(self):
        with patch.object(mevzuat.requests, "get", side_effect=mevzuat.requests.ConnectionError("yok")):
            self.assertIsNone(mevzuat.tertip_kesfet(2942))

    def test_kisa_ya_da_madde_icermeyen_sayfa_tertip_sayilmaz(self):
        with patch.object(mevzuat.requests, "get", return_value=self._cevap(200, "<html>kisa</html>")):
            self.assertIsNone(mevzuat.tertip_kesfet(2942))


class TestBetik(unittest.TestCase):
    def setUp(self):
        self.betik = _betik()

    def _calistir(self, argv):
        cikti, hata = io.StringIO(), io.StringIO()
        with patch.object(mevzuat, "kanun_metni", side_effect=_sahte), redirect_stdout(cikti), redirect_stderr(hata):
            kod = self.betik.main(argv)
        return kod, cikti.getvalue(), hata.getvalue()

    def test_madde_cikti_ve_bitis_isareti(self):
        kod, cikti, _ = self._calistir(["madde", "4721 sayılı Kanun md. 3"])
        self.assertEqual(kod, 0)
        self.assertIn("md. 3 ===", cikti)
        self.assertIn("BU MADDE BURADA BİTER", cikti)
        self.assertIn("MADDE 4 -", cikti)

    def test_okunamayan_madde_cikis_kodu_1(self):
        kod, _, hata = self._calistir(["madde", "4721 sayılı Kanun md. 99"])
        self.assertEqual(kod, 1)
        self.assertIn("OKUNAMADI", hata)

    def test_ara_ve_json(self):
        kod, cikti, _ = self._calistir(["ara", "4721", "rehin"])
        self.assertEqual(kod, 0)
        self.assertIn("md. 3", cikti)
        kod, cikti, _ = self._calistir(["--json", "ara", "4721", "rehin"])
        self.assertEqual(json.loads(cikti)[0]["sonuclar"][0]["etiket"], "md. 3")

    def test_dene_basarisiz_kanun_icin_dogru_tertibi_onerir(self):
        """KANUNLAR'daki tertip adayı tutmazsa `--dene` sitede çalışan tertibi bulup yazar (yeni 14 kanunun tertipleri tahmindi)."""
        def metin(no):
            return None if no == 2942 else SAHTE

        with patch.object(mevzuat, "kanun_metni", side_effect=metin), \
             patch.object(mevzuat, "tertip_kesfet", return_value=3) as kesif:
            cikti, hata = io.StringIO(), io.StringIO()
            with redirect_stdout(cikti), redirect_stderr(hata):
                kod = self.betik.main(["kanunlar", "--dene"])
        self.assertEqual(kod, 1)
        kesif.assert_called_once_with(2942)
        self.assertIn("sitede çalışan tertip: 3", cikti.getvalue())

    def test_kanunlar_listesi(self):
        kod, cikti, _ = self._calistir(["kanunlar"])
        self.assertEqual(kod, 0)
        self.assertIn("2942", cikti)
        self.assertIn("Kamulaştırma Kanunu", cikti)


if __name__ == "__main__":
    unittest.main(verbosity=2)
