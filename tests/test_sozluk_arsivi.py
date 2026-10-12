"""
tests/test_sozluk_arsivi.py — Hazır sözlük kartları (2026-10-08).

Modelin yazdığı sözlük otomatik yayına uygun değil (gerçek denemede 12 içeriğin en az 4'ünde ince yanlışlık,
hakem kota bitince sessizce çalışmıyor). Kartlar bir kez yazılır ve doğrulanır; yayın anında model yok.
Burada: kart biçimi, seçim, kayda çevirme ve GERÇEK arşivin bütünlüğü (kanun metniyle, çizimle).
Ağ yok.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from PIL import Image

from src import dogrula, generate_text, make_image, mevzuat, sozluk_arsivi as sa, yeni_formatlar

KART = {
    "kod": "SZ-901", "terim": "GÜVENCE BEDELİ", "kategori_kodu": "KIRA_VE_TAHLIYE",
    "tanim": "Konut ve çatılı işyeri kiralarında kiracıdan sözleşmeyle istenen güvencedir; üç aylık kira bedelini aşamaz.",
    "puf": ["Para olarak verilirse kiracı vadeli hesaba yatırır.", "Banka güvenceyi iki tarafın rızasıyla geri verir."],
    "mevzuat": "Türk Borçlar Kanunu md. 342",
    "dayanak_alintisi": "Konut ve çatılı işyeri kiralarında sözleşmeyle kiracıya güvence verme borcu getirilmişse, bu güvence üç aylık kira bedelini aşamaz.",
    "kontrol": "2026-10-08",
}
KANUN_342 = ("[6098 sayılı Türk Borçlar Kanunu] MADDE 342- Konut ve çatılı işyeri kiralarında sözleşmeyle kiracıya güvence verme "
             "borcu getirilmişse, bu güvence üç aylık kira bedelini aşamaz. Güvence olarak para verilmesi kararlaştırılmışsa "
             "kiracı parayı vadeli bir tasarruf hesabına yatırır. Banka güvenceleri ancak iki tarafın rızasıyla geri verebilir.")


def _kart(**ek):
    k = copy.deepcopy(KART)
    k.update(ek)
    return k


class TestYapisalDenetim(unittest.TestCase):
    def test_gecerli_kart_temiz(self):
        self.assertEqual(sa.kart_yapisal_sorunlari(KART), [])

    def test_eksik_alanlar(self):
        for alan in sa.ZORUNLU:
            k = _kart()
            k.pop(alan)
            self.assertTrue(any(alan in s for s in sa.kart_yapisal_sorunlari(k)), alan)

    def test_butce_asimlari(self):
        self.assertTrue(sa.kart_yapisal_sorunlari(_kart(terim="X" * 27)))
        self.assertTrue(sa.kart_yapisal_sorunlari(_kart(tanim="a" * 261)))
        self.assertTrue(sa.kart_yapisal_sorunlari(_kart(tanim="kısa tanım")))
        self.assertTrue(sa.kart_yapisal_sorunlari(_kart(puf=["a" * 116, "b" * 30])))
        self.assertEqual(sa.kart_yapisal_sorunlari(_kart(terim="X" * 26)), [])

    def test_madde_sayisi_iki_ile_uc(self):
        self.assertTrue(sa.kart_yapisal_sorunlari(_kart(puf=["tek madde yeterince uzun bir cümle"])))
        self.assertTrue(sa.kart_yapisal_sorunlari(_kart(puf=["madde bir yeterince uzun metin"] * 4)))
        self.assertEqual(sa.kart_yapisal_sorunlari(_kart(puf=["madde bir yeterince uzun metin"] * 3)), [])

    def test_yasakli_isaretler(self):
        for isaret in ("**kalın**", "#etiket", "ünlem!", "<b>x</b>"):
            self.assertTrue(sa.kart_yapisal_sorunlari(_kart(tanim=KART["tanim"] + " " + isaret)), isaret)

    def test_kod_kategori_tarih_ve_alinti(self):
        self.assertTrue(sa.kart_yapisal_sorunlari(_kart(kod="SZ-1")))
        self.assertTrue(sa.kart_yapisal_sorunlari(_kart(kod="XX-001")))
        self.assertTrue(sa.kart_yapisal_sorunlari(_kart(kategori_kodu="OLMAYAN_KATEGORI")))
        self.assertTrue(sa.kart_yapisal_sorunlari(_kart(kontrol="8 Ekim")))
        self.assertTrue(sa.kart_yapisal_sorunlari(_kart(dayanak_alintisi="çok kısa alıntı")))


class TestYukleme(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.yol = Path(self.tmp.name) / "kartlar.yaml"
        self._yama = patch.object(sa, "ARSIV_YOLU", self.yol)
        self._yama.start()
        sa._onbellek = None

    def tearDown(self):
        self._yama.stop()
        sa._onbellek = None
        self.tmp.cleanup()

    def _yaz(self, kartlar):
        self.yol.write_text(yaml.safe_dump({"kartlar": kartlar}, allow_unicode=True), encoding="utf-8")

    def test_gecerli_kartlar_yuklenir(self):
        self._yaz([_kart(), _kart(kod="SZ-902", terim="CAYMA PARASI")])
        self.assertEqual([k["kod"] for k in sa.kartlari_yukle(tazele=True)], ["SZ-901", "SZ-902"])

    def test_bozuk_ve_tekrar_eden_kart_atlanir(self):
        self._yaz([_kart(), _kart(), _kart(kod="SZ-902"), _kart(kod="SZ-903", terim="Y" * 40), _kart(kod="SZ-904", terim="ÖNALIM HAKKI")])
        kodlar = [k["kod"] for k in sa.kartlari_yukle(tazele=True)]
        self.assertEqual(kodlar, ["SZ-901", "SZ-904"])  # aynı kod, aynı terim ve bütçeyi aşan atlandı

    def test_dosya_yoksa_bos(self):
        self.assertEqual(sa.kartlari_yukle(tazele=True), [])


class TestSecim(unittest.TestCase):
    def setUp(self):
        self.kartlar = [
            _kart(kod="SZ-901", terim="A TERİMİ", kategori_kodu="TAPU_VE_HUKUK"),
            _kart(kod="SZ-902", terim="B TERİMİ", kategori_kodu="KIRA_VE_TAHLIYE"),
            _kart(kod="SZ-903", terim="C TERİMİ", kategori_kodu="KIRA_VE_TAHLIYE"),
        ]
        self._yama = patch.object(sa, "kartlari_yukle", return_value=self.kartlar)
        self._yama.start()

    def tearDown(self):
        self._yama.stop()

    def _gun(self, n):
        from datetime import datetime, timedelta, timezone
        return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()

    def test_bakir_kart_once(self):
        gecmis = {"SZ-901": self._gun(10), "SZ-902": self._gun(10)}
        for _ in range(10):
            self.assertEqual(sa.sonraki_kart(gecmis, son_kategori=None)["kod"], "SZ-903")

    def test_art_arda_ayni_kategori_mumkunse_secilmez(self):
        for _ in range(20):
            self.assertEqual(sa.sonraki_kart({}, son_kategori="KIRA_VE_TAHLIYE")["kod"], "SZ-901")

    def test_baska_secenek_yoksa_ayni_kategori_secilir(self):
        gecmis = {"SZ-901": self._gun(5)}
        self.assertIn(sa.sonraki_kart(gecmis, son_kategori="KIRA_VE_TAHLIYE")["kod"], ("SZ-902", "SZ-903"))

    def test_bekleme_suresi_dolmadan_tekrar_yok(self):
        gecmis = {k["kod"]: self._gun(sa.BEKLEME_GUN - 10) for k in self.kartlar}
        self.assertIsNone(sa.sonraki_kart(gecmis, son_kategori=None))

    def test_bekleme_dolunca_en_eski_kart(self):
        gecmis = {"SZ-901": self._gun(sa.BEKLEME_GUN + 5), "SZ-902": self._gun(sa.BEKLEME_GUN + 50), "SZ-903": self._gun(sa.BEKLEME_GUN + 1)}
        self.assertEqual(sa.sonraki_kart(gecmis, son_kategori=None)["kod"], "SZ-902")

    def test_pasif_ve_haric_kartlar_secilmez(self):
        self.kartlar[0]["pasif"] = True
        for _ in range(10):
            self.assertNotEqual(sa.sonraki_kart({}, son_kategori=None, haric={"SZ-902"})["kod"], "SZ-901")
            self.assertNotEqual(sa.sonraki_kart({}, son_kategori=None, haric={"SZ-902"})["kod"], "SZ-902")

    def test_durum_ozeti(self):
        self.assertEqual(sa.durum_ozeti({"SZ-901": self._gun(1)}), {"toplam": 3, "bakir": 2, "eksik": sa.HEDEF_KART - 3})


class TestKaydaCevirme(unittest.TestCase):
    def setUp(self):
        self.v = sa.karttan_veri(KART)

    def test_model_ciktisiyla_ayni_sekil(self):
        self.assertEqual(self.v["format_turu"], "sozluk")
        self.assertEqual(self.v["terim"], KART["terim"])
        self.assertEqual(self.v["tanim_metni"], KART["tanim"])
        self.assertEqual(self.v["puf_maddeleri"], KART["puf"])
        self.assertEqual(self.v["kategori_kodu"], "KIRA_VE_TAHLIYE")
        self.assertEqual(self.v["konu_kodu"], "SZ-901")
        self.assertEqual(self.v["yasal_dayanak"], KART["mevzuat"])

    def test_kullanilmayan_b1_bloklari_yok(self):
        for alan in ("slayt_2_detay", "slayt_3_cozum", "slayt_4_cta", "soru"):
            self.assertNotIn(alan, self.v)

    def test_baslik_ve_spot_karttan(self):
        self.assertEqual(generate_text.manset_birlestir(self.v), "GÜVENCE BEDELİ nedir?")
        self.assertTrue(self.v["spot"].endswith("aşamaz."))

    def test_hazir_kart_isareti(self):
        self.assertTrue(self.v["_brief"]["kart"])
        self.assertEqual(self.v["_brief"]["mevzuat"], KART["mevzuat"])

    def test_captionlar_hazir_ve_zenginlesmis(self):
        for ad, tavan in (("caption_instagram", None), ("caption_facebook", None), ("caption_threads", 480)):
            metin = self.v[ad]
            self.assertIn("GÜVENCE BEDELİ", metin, ad)
            self.assertIn("#", metin, ad)                     # etiketler eklendi
            self.assertIn("edmyapigayrimenkul", metin, ad)    # site satırı
            if tavan:
                self.assertLessEqual(len(metin), tavan)
        self.assertIn("Dayanak: Türk Borçlar Kanunu md. 342.", self.v["caption_instagram"])
        self.assertIn(KART["puf"][0], self.v["caption_instagram"])

    def test_girdi_kart_degismez(self):
        kart = copy.deepcopy(KART)
        sa.karttan_veri(kart)
        self.assertEqual(kart, KART)

    def test_kapidan_temiz_gecer(self):
        brief = {"mevzuat": KART["mevzuat"], "mevzuat_metni": KANUN_342, "veri_kaynagi": "kanun", "yerel": None}
        self.assertEqual(dogrula.denetle(self.v, brief), [])


class TestKanunDurumu(unittest.TestCase):
    def _durum(self, metin):
        ozet = {"metin": metin, "son_degisiklik": None, "cozulemeyen": [], "cekildi": "2026-10-08"}
        with patch.object(mevzuat, "brief_mevzuati", return_value=ozet):
            return sa.kart_kanun_durumu(KART)

    def test_alinti_metinde_varsa_taze(self):
        taze, sorun = self._durum(KANUN_342)
        self.assertTrue(taze, sorun)

    def test_kanun_degisip_alinti_kaybolursa_taze_degil(self):
        taze, sorun = self._durum(KANUN_342.replace("üç aylık kira bedelini", "iki aylık kira bedelini"))
        self.assertFalse(taze)
        self.assertTrue(any("birebir bulunamadı" in s for s in sorun), sorun)

    def test_kartta_kanunda_olmayan_sure_yakalanir(self):
        kart = _kart(puf=["Güvence beş ay içinde iade edilir.", "Banka güvenceyi iki tarafın rızasıyla geri verir."])
        ozet = {"metin": KANUN_342, "son_degisiklik": None, "cozulemeyen": [], "cekildi": "2026-10-08"}
        with patch.object(mevzuat, "brief_mevzuati", return_value=ozet):
            taze, sorun = sa.kart_kanun_durumu(kart)
        self.assertFalse(taze)
        self.assertTrue(any("süre" in s for s in sorun), sorun)

    def test_kanun_metni_alinamazsa_bilinmiyor(self):
        ozet = {"metin": "", "son_degisiklik": None, "cozulemeyen": ["Türk Borçlar Kanunu md. 342"], "cekildi": None}
        with patch.object(mevzuat, "brief_mevzuati", return_value=ozet):
            taze, sorun = sa.kart_kanun_durumu(KART)
        self.assertIsNone(taze)  # "taze değil" ile "doğrulanamadı" ayrı: ikincisinde otomatik yayın durur
        self.assertTrue(sorun)


class TestHaftalikKartDenetimi(unittest.TestCase):
    """`scripts/mevzuat_denetim.py` kartları da denetler: kanun değişince kart yayından ÖNCE kırmızıya düşer."""

    @classmethod
    def setUpClass(cls):
        import importlib.util
        kok = Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location("mevzuat_denetim_betik", kok / "scripts" / "mevzuat_denetim.py")
        cls.betik = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.betik)

    def _denetle(self, durum, son_degisiklik=None):
        ozet = {"metin": "x", "son_degisiklik": son_degisiklik, "cozulemeyen": [], "cekildi": "2026-10-08"}
        with patch.object(sa, "kart_kanun_durumu", return_value=durum), patch.object(mevzuat, "brief_mevzuati", return_value=ozet):
            return self.betik.kart_denetle(KART)

    def test_temiz_kart(self):
        self.assertEqual(self._denetle((True, [])), ([], []))

    def test_kanunla_uyusmayan_kart_kritik(self):
        kritik, bilgi = self._denetle((False, ["dayanak_alintisi güncel metinde birebir bulunamadı"]))
        self.assertEqual(bilgi, [])
        self.assertTrue(any("birebir bulunamadı" in k for k in kritik), kritik)

    def test_kanun_metni_alinamayan_kart_bilgi_kritik_degil(self):
        kritik, bilgi = self._denetle((None, ["kanun metni alınamadı"]))
        self.assertEqual(kritik, [])
        self.assertTrue(bilgi)

    def test_yakinda_degisen_madde_kritik(self):
        from datetime import date, timedelta
        yeni = (date.today() - timedelta(days=3)).isoformat()
        eski = (date.today() - timedelta(days=400)).isoformat()
        self.assertTrue(any("değişti" in k for k in self._denetle((True, []), yeni)[0]))
        self.assertEqual(self._denetle((True, []), eski)[0], [])


class TestAbartiKelimeSiniri(unittest.TestCase):
    """Alt-dize eşleşmesi "sakınca" ve "paslanmaz" gibi kelimeleri abartı sayıyordu (kart SZ-014)."""

    def _abarti(self, metin):
        return [u for u in dogrula.denetle({"spot": metin}, None) if "ABARTI" in u]

    def test_sıradan_kelimeler_uyarmaz(self):
        for metin in ("fen bakımından sakınca bulunmaz", "paslanmaz çelik korkuluk", "aslan payı", "bombardıman uçağı", "şoke olmuş"):
            self.assertEqual(self._abarti(metin), [], metin)

    def test_gercek_abarti_hala_yakalanir(self):
        for metin in ("sakın ha yapmayın", "asla kabul etmeyin", "bomba gibi haber", "müjde var", "şok edici fiyat", "inanılmaz fırsat"):
            self.assertTrue(self._abarti(metin), metin)


class TestGercekArsiv(unittest.TestCase):
    """data/sozluk_kartlari.yaml: yayınlanacak kartların kendisi."""

    @classmethod
    def setUpClass(cls):
        sa._onbellek = None
        cls.kartlar = sa.kartlari_yukle(tazele=True)
        cls.ham = yaml.safe_load(Path(sa.ARSIV_YOLU).read_text(encoding="utf-8"))["kartlar"]

    def test_hicbir_kart_sessizce_atlanmadi(self):
        self.assertEqual(len(self.kartlar), len(self.ham), "bir kart yapısal denetimden kaldı (günlüğe bakın)")
        self.assertGreaterEqual(len(self.kartlar), 30)

    def test_kodlar_ve_terimler_benzersiz(self):
        self.assertEqual(len({k["kod"] for k in self.kartlar}), len(self.kartlar))
        self.assertEqual(len({k["terim"].upper() for k in self.kartlar}), len(self.kartlar))

    def test_kanun_metniyle_dogrulanir(self):
        # Önbellek yoksa (CI) atlanır: o ortamda kart denetimi yayın anında ve haftalık iş akışında ağla yapılır
        if not (mevzuat.ONBELLEK / "634.txt").exists():
            self.skipTest("kanun metni önbelleği bu ortamda yok")
        for k in self.kartlar:
            taze, sorun = sa.kart_kanun_durumu(k)
            self.assertTrue(taze, f"{k['kod']} {k['terim']}: {sorun}")

    def test_kapidan_temiz_gecer(self):
        if not (mevzuat.ONBELLEK / "634.txt").exists():
            self.skipTest("kanun metni önbelleği bu ortamda yok")
        for k in self.kartlar:
            metin = mevzuat.brief_mevzuati(k["mevzuat"], azami_toplam=200000).get("metin") or ""
            brief = {"mevzuat": k["mevzuat"], "mevzuat_metni": metin, "veri_kaynagi": "kanun", "yerel": None}
            self.assertEqual(dogrula.denetle(sa.karttan_veri(k), brief), [], f"{k['kod']} {k['terim']}")

    def test_her_kart_iki_olcude_tasmadan_cizilir(self):
        # Temsilci örneklem (730 kartta test paketi dakikalar uzamasın): arşiv ≤60 kartken HEPSİ. Her yeni kartın iki ölçüde
        # çizimi zaten scripts/sozluk_kart_dogrula.py ile arşive girerken sınanır.
        with tempfile.TemporaryDirectory() as tmp:
            for k in sa.temsilci_kartlar(self.kartlar):
                veri = sa.karttan_veri(k)
                for olcu, boyut in (("besleme", (1080, 1350)), ("story", (1080, 1920))):
                    with self.subTest(kart=k["kod"], olcu=olcu):
                        yollar = yeni_formatlar.slaytlari_uret(copy.deepcopy(veri), format_turu="sozluk",
                                                               cikti_dizini=Path(tmp), cikti_onek=f"{k['kod']}_{olcu}", olcu=olcu)
                        self.assertEqual(len(yollar), 1)
                        with Image.open(yollar[0]) as im:
                            self.assertEqual(im.size, boyut)

    def test_hicbir_terim_kelimeyi_ortadan_bolmez(self):
        """ZİLYETLİKLE TESCİL gibi uzun kelimeler içeren terimler punto küçültülerek doğal bölünür; ZİLYETLİKL / E gibi bölünemez."""
        for k in self.kartlar:
            terim = k["terim"]
            with self.subTest(kart=k["kod"], terim=terim):
                cozum = None
                for p in range(136, 59, -4):
                    res = yeni_formatlar._sigdir(terim, make_image.FONT_FRAUNCES, [p], 932, 10_000, 1.15, azami_satir=2 if p > 76 else 3)
                    if res:
                        cozum = res
                        break
                self.assertIsNotNone(cozum, f"Terim çözülemedi: {terim}")
                satirlar = cozum[1]
                kelimeler = [w for s in satirlar for w in s.split()]
                self.assertEqual(kelimeler, terim.split(), f"Kelime harf harf bölünmüş: {terim} -> {satirlar}")


class TestStokVeBekleme(unittest.TestCase):
    """Kullanıcı şartı (2026-10-09): günde bir kartla EN AZ 2 YIL tekrara düşmemek. 34 kart 34 gün yeter; 730 kart gerekir."""

    @classmethod
    def setUpClass(cls):
        cls.kartlar = sa.kartlari_yukle(tazele=True)

    @staticmethod
    def _gun(onceki: int) -> str:
        from datetime import datetime, timedelta, timezone
        return (datetime.now(timezone.utc) - timedelta(days=onceki)).isoformat()

    def test_bekleme_iki_yil_ve_hedef_730(self):
        self.assertGreaterEqual(sa.BEKLEME_GUN, 730)
        self.assertEqual(sa.HEDEF_KART, 730)

    def test_kart_iki_yil_dolmadan_tekrar_secilmez(self):
        gecmis = {k["kod"]: self._gun(sa.BEKLEME_GUN - 1) for k in self.kartlar}
        self.assertIsNone(sa.sonraki_kart(gecmis=gecmis, son_kategori=None))
        gecmis = {k["kod"]: self._gun(sa.BEKLEME_GUN + 1) for k in self.kartlar}
        self.assertIsNotNone(sa.sonraki_kart(gecmis=gecmis, son_kategori=None))

    def test_hic_yayinlanmamis_kart_varken_bekleme_aranmaz(self):
        gecmis = {k["kod"]: self._gun(5) for k in self.kartlar[1:]}                   # biri hiç kullanılmadı
        self.assertEqual(sa.sonraki_kart(gecmis=gecmis, son_kategori=None)["kod"], self.kartlar[0]["kod"])

    def test_durum_ozeti_eksik_karti_soyler(self):
        ozet = sa.durum_ozeti(gecmis={})
        self.assertEqual(ozet["toplam"], len(self.kartlar))
        self.assertEqual(ozet["bakir"], len(self.kartlar))
        self.assertEqual(ozet["eksik"], sa.HEDEF_KART - len(self.kartlar))

    def test_stok_kalan_bu_kart_dusulerek_sayilir(self):
        ilk, ikinci = self.kartlar[0], self.kartlar[1]
        self.assertEqual(sa.stok_kalan(ilk, gecmis={}), len(self.kartlar) - 1)         # bu kart da hiç yayınlanmamış
        kullanilmis = {ilk["kod"]: self._gun(3)}
        self.assertEqual(sa.stok_kalan(ikinci, gecmis=kullanilmis), len(self.kartlar) - 2)
        self.assertEqual(sa.stok_kalan(ilk, gecmis=kullanilmis), len(self.kartlar) - 1)  # zaten kullanılmış: ikinci kez düşülmez

    def test_stok_kalan_sifirin_altina_inmez_ve_pasifi_saymaz(self):
        hepsi = {k["kod"]: self._gun(1) for k in self.kartlar}
        self.assertEqual(sa.stok_kalan(self.kartlar[0], gecmis=hepsi), 0)
        pasif = [{**k, "pasif": True} if i == 0 else k for i, k in enumerate(self.kartlar)]
        with patch.object(sa, "kartlari_yukle", return_value=pasif):
            self.assertEqual(sa.stok_kalan(self.kartlar[1], gecmis={}), len(self.kartlar) - 2)


class TestThreadsAciklamasi(unittest.TestCase):
    """Threads sınırı 480: genel kırpma cümle ortasında "…" ile kesiyordu (34 kartın 13'ünde: "Dayanak: Türk…").
    Kartın Threads açıklaması yalnız TAM birimlerden kurulur."""

    @classmethod
    def setUpClass(cls):
        cls.kartlar = sa.kartlari_yukle(tazele=True)

    def test_hicbir_kartin_threads_metni_kesilmez_ve_sinira_sigar(self):
        for k in self.kartlar:
            th = sa.karttan_veri(k)["caption_threads"]
            self.assertNotIn("…", th, k["kod"])
            self.assertLessEqual(len(th), sa.THREADS_SINIRI, k["kod"])

    def test_baslik_ve_tanim_her_zaman_tam(self):
        for k in self.kartlar:
            th = sa.karttan_veri(k)["caption_threads"]
            self.assertTrue(th.startswith(f"{k['terim']} nedir?\n\n{k['tanim']}"), k["kod"])

    def test_maddeler_ya_tam_ya_hic_ve_sirayla(self):
        for k in self.kartlar:
            th = sa.karttan_veri(k)["caption_threads"]
            tam = [m for m in k["puf"] if m in th]
            self.assertGreaterEqual(len(tam), 1, k["kod"])                    # en az bir madde sığıyor
            self.assertEqual(tam, k["puf"][:len(tam)], k["kod"])              # baştan kesintisiz, sırayla
            for m in k["puf"][len(tam):]:                                     # alınmayan maddeden parça sızmaz
                self.assertNotIn(m[:30], th, k["kod"])

    def test_dayanak_yalniz_tam_sigiyorsa_yazilir(self):
        for k in self.kartlar:
            th = sa.karttan_veri(k)["caption_threads"]
            if "Dayanak:" in th:
                self.assertIn(f"Dayanak: {k['mevzuat']}.", th, k["kod"])

    def test_madde_atlanirsa_sonrakiler_eklenmez_sira_bozulmaz(self):
        # 1. madde sığar, 2. çok uzun (sığmaz), 3. kısa (tek başına sığardı): 3. eklenmemeli, yoksa metin 2. maddeyi atlar
        k = next(x for x in self.kartlar if x["kod"] == "SZ-004")
        veri = sa.karttan_veri(k)
        kisa1, uzun, kisa3 = "Birinci kısa madde burada.", "Çok uzun madde. " * 30, "Üçüncü kısa madde."
        th = sa._threads_govdesi(veri, k["terim"], k["tanim"], [kisa1, uzun, kisa3], k["mevzuat"])
        self.assertIn(kisa1, th)
        self.assertNotIn(kisa3, th)
        self.assertNotIn("Çok uzun", th)

    def test_sigmayan_maddeler_dusurulur_kirpilmaz(self):
        k = next(x for x in self.kartlar if x["kod"] == "SZ-004")             # 3 maddeli, uzun
        with patch.object(sa, "THREADS_SINIRI", 360):
            th = sa.karttan_veri(k)["caption_threads"]
        self.assertLess(sum(1 for m in k["puf"] if m in th), len(k["puf"]))
        self.assertNotIn("…", th)

    def test_instagram_ve_facebook_aciklamasi_tum_maddeleri_tasir(self):
        for k in self.kartlar:
            v = sa.karttan_veri(k)
            for alan in ("caption_instagram", "caption_facebook"):
                for m in k["puf"]:
                    self.assertIn(m, v[alan], f"{k['kod']} {alan}")
            self.assertLessEqual(len(v["caption_instagram"]), 2200, k["kod"])


if __name__ == "__main__":
    unittest.main()
