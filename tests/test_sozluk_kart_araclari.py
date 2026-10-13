"""
tests/test_sozluk_kart_araclari.py — sözlük kartı taslak doğrulayıcısı ve birleştiricisi (SOZLUK-KART-URETIMI.md).

34 → 730 kart planında kartları yazan ajanlar taslağı bu araçlarla denetler, birleştirici arşive yalnız denetimden
yeniden temiz çıkanı ekler. Kanun metni SAHTE (mevzuat.gov.tr bu ortamda kapalıydı); gerçek kanunla ilk koşu açık ağda yapılmalı.
Çizim gerçek (iki ölçü); ağ yok.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import capraz_denetim, make_image, mevzuat, sozluk_arsivi as sa, sozluk_dogrulama as sd, yeni_formatlar  # noqa: E402

KART = {
    "terim": "GÜVENCE BEDELİ", "kategori_kodu": "KIRA_VE_TAHLIYE",
    "tanim": "Konut ve çatılı işyeri kiralarında kiracıdan sözleşmeyle istenen güvencedir; üç aylık kira bedelini aşamaz.",
    "puf": ["Para olarak verilirse kiracı vadeli hesaba yatırır.", "Banka güvenceyi iki tarafın rızasıyla geri verir."],
    "mevzuat": "Türk Borçlar Kanunu md. 342",
    "dayanak_alintisi": "Konut ve çatılı işyeri kiralarında sözleşmeyle kiracıya güvence verme borcu getirilmişse, bu güvence üç aylık kira bedelini aşamaz.",
    "kontrol": "2026-10-12",
}
KANUN_342 = ("[6098 sayılı Türk Borçlar Kanunu] MADDE 342- Konut ve çatılı işyeri kiralarında sözleşmeyle kiracıya güvence verme "
             "borcu getirilmişse, bu güvence üç aylık kira bedelini aşamaz. Güvence olarak para verilmesi kararlaştırılmışsa "
             "kiracı parayı vadeli bir tasarruf hesabına yatırır. Banka güvenceleri ancak iki tarafın rızasıyla geri verebilir.")
OZET_TAM = {"metin": KANUN_342, "son_degisiklik": None, "cozulemeyen": [], "cekildi": "2026-10-12"}

ARSIV_BASLIGI = "# ARŞİV BAŞLIK YORUMU — birleştirme buna dokunmamalı\n# ikinci satır\n\nkartlar:\n"


def _kart(**ek):
    k = copy.deepcopy(KART)
    k.update(ek)
    return k


def _arsiv_karti(kod, terim, **ek):
    k = _kart(terim=terim)
    k["kod"] = kod
    k.update(ek)
    return k


def _yaz(yol: Path, kartlar, baslik=ARSIV_BASLIGI) -> Path:
    govde = yaml.safe_dump(kartlar, allow_unicode=True, sort_keys=False, default_flow_style=False, width=10_000) if kartlar else ""
    yol.write_text(baslik + govde, encoding="utf-8")
    return yol


def _kanunlu(ozet=OZET_TAM):
    """kanun_metni yerine brief_mevzuati'yi sahtele (test_sozluk_arsivi ile aynı yöntem)."""
    return patch.object(mevzuat, "brief_mevzuati", return_value=ozet)


class TestTerimNormallestirme(unittest.TestCase):
    def test_aksan_buyuk_kucuk_ve_bosluk_duyarsiz(self):
        for a, b in (("ZİLYETLİKLE TESCİL", "Zilyetlikle  tescil"), ("ÖNALIM HAKKI", "onalim hakki"),
                     ("IŞIK HAKKI", "isik hakki"), ("Kat İrtifakı", "KAT IRTIFAKI")):
            self.assertEqual(sd.normal_terim(a), sd.normal_terim(b), (a, b))
        self.assertNotEqual(sd.normal_terim("KİRA"), sd.normal_terim("KİRACI"))

    def test_bos_girdi(self):
        self.assertEqual(sd.normal_terim(None), "")


class TestTaslakYukleme(unittest.TestCase):
    def test_kartlar_anahtari_ve_duz_liste_kabul(self):
        with tempfile.TemporaryDirectory() as d:
            a = _yaz(Path(d) / "a.yaml", [_kart()], baslik="kartlar:\n")
            b = Path(d) / "b.yaml"
            b.write_text(yaml.safe_dump([_kart()], allow_unicode=True), encoding="utf-8")
            self.assertEqual(len(sd.taslagi_yukle(a)), 1)
            self.assertEqual(len(sd.taslagi_yukle(b)), 1)

    def test_bozuk_dosya_sessizce_bos_donmez(self):
        with tempfile.TemporaryDirectory() as d:
            for icerik in ("kartlar: 5\n", "x: [\n", "- 3\n", ""):
                yol = Path(d) / "k.yaml"
                yol.write_text(icerik, encoding="utf-8")
                with self.assertRaises(ValueError, msg=icerik):
                    sd.taslagi_yukle(yol)
            with self.assertRaises(ValueError):
                sd.taslagi_yukle(Path(d) / "yok.yaml")


class TestKartDenetimi(unittest.TestCase):
    def _denetle(self, kart, terimler=None, ozet=OZET_TAM, **kw):
        kw.setdefault("ciz", False)
        with _kanunlu(ozet):
            return sd.karti_denetle(kart, terimler, **kw)

    def test_temiz_kart(self):
        r = self._denetle(_kart())
        self.assertTrue(r.temiz, r.sorunlar)

    def test_temiz_kart_iki_olcude_gercekten_cizilir(self):
        r = self._denetle(_kart(), ciz=True)
        self.assertTrue(r.temiz, r.sorunlar)

    def test_yapi_sorunu_diger_katmanlari_calistirmaz(self):
        with _kanunlu() as brief:
            r = sd.karti_denetle(_kart(tanim="kısa"), ciz=False)
        self.assertTrue(any(s.startswith("yapı:") for s in r.sorunlar), r.sorunlar)
        brief.assert_not_called()

    def test_eksik_alan(self):
        k = _kart()
        del k["dayanak_alintisi"]
        r = self._denetle(k)
        self.assertIn("yapı: dayanak_alintisi eksik", r.sorunlar)

    def test_kod_yoksa_yer_tutucu_ile_denetlenir_taslakta_kod_yazilmaz(self):
        k = _kart()
        self.assertNotIn("kod", k)
        self.assertTrue(self._denetle(k).temiz)

    def test_tekrar_terim(self):
        r = self._denetle(_kart(terim="Güvence  Bedeli"), {sd.normal_terim("GÜVENCE BEDELİ"): "SZ-004"})
        self.assertTrue(any(s.startswith("tekrar:") and "SZ-004" in s for s in r.sorunlar), r.sorunlar)

    def test_alinti_guncel_metinde_yoksa_kanun_sorunu(self):
        r = self._denetle(_kart(), ozet=dict(OZET_TAM, metin=KANUN_342.replace("üç aylık", "iki aylık")))
        self.assertTrue(any("birebir bulunamadı" in s for s in r.sorunlar), r.sorunlar)

    def test_kartta_kanunda_olmayan_sure_kanun_sorunu(self):
        r = self._denetle(_kart(puf=["Güvence beş ay içinde iade edilir.", "Banka güvenceyi iki tarafın rızasıyla geri verir."]))
        self.assertTrue(any("süre" in s for s in r.sorunlar), r.sorunlar)

    def test_kanun_metni_alinamazsa_sorun(self):
        r = self._denetle(_kart(), ozet={"metin": "", "son_degisiklik": None, "cozulemeyen": ["Türk Borçlar Kanunu md. 342"], "cekildi": None})
        self.assertTrue(any("metni alınamadı" in s for s in r.sorunlar), r.sorunlar)

    def test_atifta_okunamayan_madde_eksik_atif_sorunu(self):
        """Çoklu atıfta bir madde okunamadıysa kart (kalan maddeler okunsa bile) arşive girmez."""
        r = self._denetle(_kart(), ozet=dict(OZET_TAM, cozulemeyen=["6098 sayılı Türk Borçlar Kanunu md. 343"]))
        self.assertTrue(any("tam çözülemedi" in s and "md. 343" in s for s in r.sorunlar), r.sorunlar)

    def test_kapi_uyarisi_sorun_sayilir(self):
        k = _kart(puf=["Türk Borçlar Kanunu madde 99 uyarınca güvence iade edilir.", "Banka güvenceyi iki tarafın rızasıyla geri verir."])
        r = self._denetle(k)
        self.assertTrue(any(s.startswith("kapı:") for s in r.sorunlar), r.sorunlar)

    def test_cizim_hatasi_sorun_sayilir(self):
        with patch.object(yeni_formatlar, "slaytlari_uret", side_effect=make_image.TasmaHatasi("tanım sığmadı")):
            r = self._denetle(_kart(), ciz=True)
        self.assertTrue(any(s.startswith("çizim (besleme)") and "TasmaHatasi" in s for s in r.sorunlar), r.sorunlar)
        self.assertTrue(any(s.startswith("çizim (story)") for s in r.sorunlar), r.sorunlar)

    def test_kanunsuz_kipi_uyarir_ve_agi_calistirmaz(self):
        with _kanunlu() as brief:
            r = sd.karti_denetle(_kart(), kanun=False, ciz=False)
        brief.assert_not_called()
        self.assertTrue(any("GEÇERSİZ" in i for i in r.ipuclari), r.ipuclari)

    def test_hakem_bulgusu_sorun_calismadiysa_ipucu(self):
        with patch.object(capraz_denetim, "denetle_ayrintili", return_value=(["⚠️ ANLAM KAYMASI (x): y"], True)):
            r = self._denetle(_kart(), hakem=True)
        self.assertIn("hakem: ⚠️ ANLAM KAYMASI (x): y", r.sorunlar)
        with patch.object(capraz_denetim, "denetle_ayrintili", return_value=([], False)):
            r = self._denetle(_kart(), hakem=True)
        self.assertTrue(r.temiz)
        self.assertTrue(any("hakem ÇALIŞMADI" in i for i in r.ipuclari), r.ipuclari)

    def test_hakem_istenmezse_cagrilmaz(self):
        with patch.object(capraz_denetim, "denetle_ayrintili") as hakem:
            self._denetle(_kart(), hakem=False)
        hakem.assert_not_called()

    def test_ortusme_ipucu_yalniz_zayif_cumleyi_isaretler_hukum_vermez(self):
        yabanci = _kart(puf=["Kiracı tüm masrafları bankaya peşin ödemekle yükümlüdür her zaman.",
                             "Banka güvenceyi iki tarafın rızasıyla geri verir."])
        r = self._denetle(yabanci)
        self.assertTrue(any("puf[0]" in i and "örtüşme" in i for i in r.ipuclari), r.ipuclari)
        self.assertFalse(any("puf[1]" in i for i in r.ipuclari), r.ipuclari)
        self.assertEqual(self._denetle(_kart()).ipuclari, [])


class TestTaslaklarArasiDenetim(unittest.TestCase):
    def test_ayni_terim_arsivde_baska_taslakta_ve_ayni_dosyada_yakalanir(self):
        with tempfile.TemporaryDirectory() as d:
            arsiv = _yaz(Path(d) / "arsiv.yaml", [_arsiv_karti("SZ-001", "GÜVENCE BEDELİ")])
            a = _yaz(Path(d) / "a.yaml", [_kart(terim="TAHLİYE TAAHHÜDÜ"), _kart(terim="Tahliye  Taahhüdü"), _kart(terim="Güvence Bedeli")], baslik="kartlar:\n")
            b = _yaz(Path(d) / "b.yaml", [_kart(terim="TAHLİYE TAAHHÜDÜ"), _kart(terim="KEFALET")], baslik="kartlar:\n")
            with _kanunlu():
                sonuc = sd.taslaklari_denetle([a, b], arsiv_yolu=arsiv, ciz=False)
        durum = {(yol.name, i): r.temiz for yol, satirlar in sonuc for i, (_k, r) in enumerate(satirlar)}
        self.assertTrue(durum[("a.yaml", 0)])          # ilk gelen kalır
        self.assertFalse(durum[("a.yaml", 1)])         # dosya içi tekrar
        self.assertFalse(durum[("a.yaml", 2)])         # arşivde var
        self.assertFalse(durum[("b.yaml", 0)])         # başka taslakta var
        self.assertTrue(durum[("b.yaml", 1)])

    def test_reddedilen_kart_ayni_terimi_dogru_yazan_baska_taslagi_engellemez(self):
        with tempfile.TemporaryDirectory() as d:
            arsiv = _yaz(Path(d) / "arsiv.yaml", [])
            a = _yaz(Path(d) / "a.yaml", [_kart(inceleme="red")], baslik="kartlar:\n")
            b = _yaz(Path(d) / "b.yaml", [_kart(inceleme="onay")], baslik="kartlar:\n")
            with _kanunlu():
                sonuc = sd.taslaklari_denetle([a, b], arsiv_yolu=arsiv, ciz=False)
        self.assertTrue(sonuc[1][1][0][1].temiz, sonuc[1][1][0][1].sorunlar)


class TestBirlestirme(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        # Kod boşluklu (SZ-040 pasif, 041 sonrası yok) — yeni kodlar max+1'den devam etmeli, boşluk doldurmamalı
        self.arsiv = _yaz(self.d / "arsiv.yaml", [
            _arsiv_karti("SZ-001", "KEFALET"),
            _arsiv_karti("SZ-040", "TAHLİYE TAAHHÜDÜ", pasif=True),
        ])
        self._cizim = patch.object(sd, "cizim_sorunlari", return_value=[])
        self._cizim.start()

    def tearDown(self):
        self._cizim.stop()
        self.tmp.cleanup()

    def _taslak(self, kartlar, ad="t.yaml"):
        return _yaz(self.d / ad, kartlar, baslik="kartlar:\n")

    def _birlestir(self, yollar, **kw):
        with _kanunlu():
            return sd.birlestir(yollar, arsiv_yolu=self.arsiv, **kw)

    def test_yalniz_onayli_ve_temiz_kartlar_eklenir_kodlar_maxtan_devam_eder(self):
        t = self._taslak([
            _kart(terim="GÜVENCE BEDELİ", inceleme="onay"),
            _kart(terim="ÖNALIM HAKKI", inceleme="duzeltildi", inceleme_notu="süre düzeltildi"),
            _kart(terim="BAĞLANMA PARASI", inceleme="red", inceleme_notu="kaynakta yok"),
            _kart(terim="CAYMA PARASI"),                                      # inceleme yok
            _kart(terim="KEFALET", inceleme="onay"),                          # arşivde var
            _kart(terim="KISA", inceleme="onay", tanim="kısa"),               # yapı bozuk
        ])
        r = self._birlestir([t])
        self.assertIsNone(r.hata)
        self.assertTrue(r.yazildi)
        self.assertEqual([(k["kod"], k["terim"]) for k in r.eklenen], [("SZ-041", "GÜVENCE BEDELİ"), ("SZ-042", "ÖNALIM HAKKI")])
        atlanan = dict(r.atlanan)
        self.assertIn("inceleme 'red'", atlanan["BAĞLANMA PARASI"])
        self.assertIn("inceleme 'yok'", atlanan["CAYMA PARASI"])
        self.assertIn("tekrar", atlanan["KEFALET"])
        self.assertIn("yapı", atlanan["KISA"])

    def test_arsiv_basligi_korunur_taslak_alanlari_arsive_girmez_dosya_yuklenir(self):
        t = self._taslak([_kart(terim="GÜVENCE BEDELİ", inceleme="onay", inceleme_notu="not")])
        self._birlestir([t])
        metin = self.arsiv.read_text(encoding="utf-8")
        self.assertTrue(metin.startswith(ARSIV_BASLIGI), "başlık yorumları korunmalı")
        self.assertNotIn("inceleme", metin)
        yuklenen = yaml.safe_load(metin)["kartlar"]
        self.assertEqual([k["kod"] for k in yuklenen], ["SZ-001", "SZ-040", "SZ-041"])
        self.assertEqual(list(yuklenen[-1])[:3], ["kod", "terim", "kategori_kodu"])     # sabit alan sırası
        self.assertEqual(yuklenen[-1]["kontrol"], "2026-10-12")                         # tarih metin kalır
        self.assertEqual(sa.kart_yapisal_sorunlari(yuklenen[-1]), [])

    def test_kuru_calisma_yazmaz(self):
        onceki = self.arsiv.read_text(encoding="utf-8")
        t = self._taslak([_kart(terim="GÜVENCE BEDELİ", inceleme="onay")])
        r = self._birlestir([t], kuru=True)
        self.assertEqual([k["kod"] for k in r.eklenen], ["SZ-041"])
        self.assertFalse(r.yazildi)
        self.assertEqual(self.arsiv.read_text(encoding="utf-8"), onceki)

    def test_onaylanmis_olsa_bile_yeniden_denetimden_kalan_kart_girmez(self):
        """Birleştirici kimsenin 'geçti' sözüne güvenmez: kanun metni arada değiştiyse kart girmez."""
        t = self._taslak([_kart(terim="GÜVENCE BEDELİ", inceleme="onay")])
        with _kanunlu(dict(OZET_TAM, metin=KANUN_342.replace("üç aylık", "iki aylık"))):
            r = sd.birlestir([t], arsiv_yolu=self.arsiv)
        self.assertEqual(r.eklenen, [])
        self.assertIn("birebir bulunamadı", dict(r.atlanan)["GÜVENCE BEDELİ"])

    def test_eklenecek_yoksa_dosyaya_dokunmaz(self):
        onceki = self.arsiv.stat().st_mtime_ns
        t = self._taslak([_kart(terim="GÜVENCE BEDELİ", inceleme="red")])
        r = self._birlestir([t])
        self.assertFalse(r.yazildi)
        self.assertEqual(self.arsiv.stat().st_mtime_ns, onceki)

    def test_yazim_sonrasi_dogrulama_tutmazsa_arsiv_eski_haline_doner(self):
        onceki = self.arsiv.read_text(encoding="utf-8")
        t = self._taslak([_kart(terim="GÜVENCE BEDELİ", inceleme="onay")])
        # İlk çağrı (taslak denetimi) temiz; yazımdan SONRAKİ doğrulama (arşivdeki kartlar) bozuk görür.
        cagrilar = iter([[]])
        with patch.object(sa, "kart_yapisal_sorunlari", side_effect=lambda k: next(cagrilar, ["bozuk"])):
            r = self._birlestir([t])
        self.assertFalse(r.yazildi)
        self.assertIn("eski haline döndürüldü", r.hata)
        self.assertEqual(self.arsiv.read_text(encoding="utf-8"), onceki)

    def test_birlestirilen_arsiv_ardisik_ikinci_birlestirmede_kodlari_surdurur(self):
        self._birlestir([self._taslak([_kart(terim="GÜVENCE BEDELİ", inceleme="onay")], "a.yaml")])
        r = self._birlestir([self._taslak([_kart(terim="ÖNALIM HAKKI", inceleme="onay")], "b.yaml")])
        self.assertEqual([k["kod"] for k in r.eklenen], ["SZ-042"])

    def test_sonraki_kod_pasif_ve_bos_arsivi_dogru_sayar(self):
        self.assertEqual(sd.sonraki_kod_numarasi([]), 1)
        self.assertEqual(sd.sonraki_kod_numarasi([{"kod": "SZ-009"}, {"kod": "SZ-100", "pasif": True}, {"kod": "bozuk"}]), 101)


def _betik(ad):
    spec = importlib.util.spec_from_file_location(ad, KOK / "scripts" / f"{ad}.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class TestBetikler(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.arsiv = _yaz(self.d / "arsiv.yaml", [_arsiv_karti("SZ-001", "KEFALET")])
        self.dogrula = _betik("sozluk_kart_dogrula")
        self.birlestir = _betik("sozluk_kart_birlestir")

    def tearDown(self):
        self.tmp.cleanup()

    def _calistir(self, betik, argv):
        cikti, hata = io.StringIO(), io.StringIO()
        with patch.object(sa, "ARSIV_YOLU", self.arsiv), redirect_stdout(cikti), redirect_stderr(hata):
            kod = betik.main(argv)
        return kod, cikti.getvalue(), hata.getvalue()

    def test_dogrula_temiz_ve_sorunlu_cikis_kodlari(self):
        temiz = _yaz(self.d / "temiz.yaml", [_kart()], baslik="kartlar:\n")
        sorunlu = _yaz(self.d / "sorunlu.yaml", [_kart(tanim="kısa")], baslik="kartlar:\n")
        with _kanunlu():
            kod, cikti, _ = self._calistir(self.dogrula, [str(temiz), "--cizimsiz"])
            self.assertEqual(kod, 0, cikti)
            self.assertIn("✓ GÜVENCE BEDELİ", cikti)
            kod, cikti, _ = self._calistir(self.dogrula, [str(sorunlu), "--cizimsiz"])
            self.assertEqual(kod, 1)
            self.assertIn("✗ yapı:", cikti)

    def test_dogrula_bozuk_dosya_cikis_kodu_2(self):
        kod, _, hata = self._calistir(self.dogrula, [str(self.d / "yok.yaml")])
        self.assertEqual(kod, 2)
        self.assertIn("okunamadı", hata)

    def test_dogrula_json_ve_kanunsuz_uyarisi(self):
        temiz = _yaz(self.d / "temiz.yaml", [_kart()], baslik="kartlar:\n")
        kod, cikti, _ = self._calistir(self.dogrula, [str(temiz), "--cizimsiz", "--kanunsuz", "--json"])
        self.assertEqual(kod, 0)
        veri = json.loads(cikti)
        self.assertTrue(veri[0]["kartlar"][0]["temiz"])
        self.assertTrue(any("GEÇERSİZ" in i for i in veri[0]["kartlar"][0]["ipuclari"]))

    def test_birlestir_kuru_ve_gercek(self):
        t = _yaz(self.d / "t.yaml", [_kart(inceleme="onay")], baslik="kartlar:\n")
        with _kanunlu(), patch.object(sd, "cizim_sorunlari", return_value=[]):
            kod, cikti, _ = self._calistir(self.birlestir, [str(t), "--kuru"])
            self.assertEqual(kod, 0)
            self.assertIn("[KURU]", cikti)
            self.assertEqual(len(yaml.safe_load(self.arsiv.read_text(encoding="utf-8"))["kartlar"]), 1)
            kod, cikti, _ = self._calistir(self.birlestir, [str(t)])
            self.assertEqual(kod, 0, cikti)
            self.assertIn("+ SZ-002", cikti)
            self.assertEqual(len(yaml.safe_load(self.arsiv.read_text(encoding="utf-8"))["kartlar"]), 2)


class TestBetikDByeDokunmaz(unittest.TestCase):
    """Kart üretim araçları paralel ajanlarca depo kopyasında koşar: data/edm.db baytları değişmemeli.
    Alt süreç POSTEDM_TEST_MODU olmadan başlatılır (betiğin kendi korumasını sınamak için)."""

    def _alt_surec(self, betik, *argv):
        import hashlib
        import subprocess
        db_yolu = KOK / "data" / "edm.db"
        once = hashlib.sha256(db_yolu.read_bytes()).hexdigest() if db_yolu.exists() else None
        ortam = {k: v for k, v in os.environ.items() if k != "POSTEDM_TEST_MODU"}
        cikti = subprocess.run([sys.executable, str(KOK / "scripts" / betik), *argv], cwd=KOK, env=ortam,
                               capture_output=True, text=True, timeout=120)
        sonra = hashlib.sha256(db_yolu.read_bytes()).hexdigest() if db_yolu.exists() else None
        return cikti, once, sonra

    def test_dogrula_ve_birlestir_kuru_db_baytlarini_degistirmez(self):
        with tempfile.TemporaryDirectory() as d:
            taslak = _yaz(Path(d) / "t.yaml", [_kart(terim="ÇOK ÖZGÜN TEST TERİMİ")], baslik="kartlar:\n")
            for betik, argv in (("sozluk_kart_dogrula.py", [str(taslak), "--kanunsuz", "--cizimsiz"]),
                                ("sozluk_kart_birlestir.py", [str(taslak), "--kuru"])):
                with self.subTest(betik=betik):
                    cikti, once, sonra = self._alt_surec(betik, *argv)
                    self.assertEqual(once, sonra, f"{betik} data/edm.db'yi değiştirdi\n{cikti.stderr[-400:]}")
                    self.assertNotIn("Traceback", cikti.stderr)


class TestBaslikYerlesimTabani(unittest.TestCase):
    """2026-10-13 pilotu: iki kart çizim hatası vermeden ama başlık ≥114 pt tabanının altında yerleşerek incelemeden
    geçti ve arşiv tipografi testinde düştü. Doğrulayıcı artık aynı ölçütü uygular."""

    def test_kisa_ve_sigan_basliklar_sorunsuz(self):
        for terim in ("ASKI İLANI", "KESİNLEŞME", "TESPİTE İTİRAZ", "KADASTRO KOMİSYONU", "KAT İRTİFAKI"):
            self.assertIsNone(sd.baslik_sigma_sorunu(terim), terim)

    def test_iki_satira_bile_sigmayan_baslik_sorun(self):
        sorun = sd.baslik_sigma_sorunu("KADASTRO TESPİTİNE İTİRAZ")
        self.assertIsNotNone(sorun)
        self.assertIn("sığmıyor", sorun)

    def test_tabanin_altina_dusen_baslik_sorun(self):
        sorun = sd.baslik_sigma_sorunu("KADASTRO KESİNLEŞMESİ")
        self.assertIsNotNone(sorun)
        self.assertIn("taban", sorun)

    def test_cizim_sorunlari_basligi_da_denetler(self):
        kart = _arsiv_karti("SZ-900", "KADASTRO TESPİTİNE İTİRAZ")
        self.assertTrue(any("başlık" in x for x in sd.cizim_sorunlari(kart)))

    def test_arsivdeki_tum_basliklar_tabana_uyar(self):
        from src import sozluk_arsivi
        sorunlu = [(k["kod"], k["terim"]) for k in sozluk_arsivi.kartlari_yukle(tazele=True) if sd.baslik_sigma_sorunu(k["terim"])]
        self.assertEqual(sorunlu, [])


class TestTemsilciKartlar(unittest.TestCase):
    def _kartlar(self, n):
        return [_arsiv_karti(f"SZ-{i:03d}", f"TERİM {i}") for i in range(1, n + 1)]

    def test_kucuk_arsivde_hepsi(self):
        kartlar = self._kartlar(sa.TEMSILCI_ESIK)
        self.assertEqual(sa.temsilci_kartlar(kartlar), kartlar)

    def test_buyuk_arsivde_orneklem_kucuk_sirali_ve_uc_degerleri_icerir(self):
        kartlar = self._kartlar(730)
        kartlar[301]["tanim"] = "uzun tanım " * 20                                   # en uzun tanım
        kartlar[402]["puf"] = ["çok uzun madde " * 6, "kısa madde burada"]            # en uzun madde
        kartlar[503]["terim"] = "ÇOK UZUN BİR TERİM ADAYI İKİ"                          # en uzun terim
        kartlar[604]["terim"] = "ZİLYETLİKLERİNDEN"                                   # en uzun tek sözcük
        sec = sa.temsilci_kartlar(kartlar)
        kodlar = [k["kod"] for k in sec]
        self.assertLessEqual(len(sec), 60)
        self.assertEqual(kodlar, sorted(kodlar))                                      # arşiv sırası korunur
        for i in (301, 402, 503, 604):
            self.assertIn(kartlar[i]["kod"], kodlar, i)
        self.assertIn(kartlar[0]["kod"], kodlar)
        self.assertIn(kartlar[25]["kod"], kodlar)

    def test_gercek_arsiv_bugun_tamami_doner(self):
        sa._onbellek = None
        kartlar = sa.kartlari_yukle(tazele=True)
        self.assertEqual(sa.temsilci_kartlar(), kartlar)


if __name__ == "__main__":
    unittest.main(verbosity=2)
