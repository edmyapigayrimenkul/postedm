"""
tests/test_konu_dayanak.py — Konu bankasında `dayanak_alintisi` (2026-10-07).

Yeni konular kanunun GÜNCEL metninden birebir alıntıyla eklendi; haftalık denetim alıntının hâlâ
metinde durduğunu doğrular. Gerçek model denemesi iki kapı hatası da buldu: "beşte dört" ve "salt
çoğunluk" kanun metninde "beşte dördünün" / "çoğunluğu" diye geçtiği için doğru içerik yanlışlıkla ⛔ alıyordu.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import unittest
from unittest.mock import patch

from src import dogrula, konu_bankasi, mevzuat

KMK_28 = ("Madde 28 – Yönetim planı yönetim tarzını düzenler. [4] (Değişik: 13/4/1983 - 2814/11 md.) "
          "Yönetim planının değiştirilmesi için bütün kat maliklerinin beşte dördünün oyu şarttır. [5] "
          "Kat maliklerinin 33 üncü maddeye göre mahkemeye başvurma hakları saklıdır.")
KMK_30 = ("Madde 30 – Kat malikleri kurulu, kat maliklerinin sayı ve arsa payı bakımından yarısından fazlasiyle "
          "toplanır ve oy çokluğuyla karar verir. İkinci toplantıda karar yeter sayısı, katılanların salt "
          "çoğunluğudur. Bu kanunda yeter sayı için ayrıca konulmuş olan hükümler saklıdır. Toplantı en geç onbeş gün sonra yapılır.")

KONU = {
    "kod": "T-001", "mevzuat": "Kat Mülkiyeti Kanunu md. 28 ve 30",
    "aci": "Yönetim planını değiştirmek için beşte dördünün oyu şarttır. İkinci toplantı en geç onbeş gün sonra yapılır.",
    "dayanak_alintisi": "Yönetim planının değiştirilmesi için bütün kat maliklerinin beşte dördünün oyu şarttır.",
}


def _metin(**ek):
    return {"metin": KMK_28 + "\n\n" + KMK_30, "son_degisiklik": None, "cozulemeyen": [], "cekildi": "2026-10-07", **ek}


class TestAlinti(unittest.TestCase):
    def test_birebir_alinti_dipnot_ve_bosluk_farkiyla_gecer(self):
        self.assertTrue(mevzuat.alinti_metinde_mi("Yönetim planının değiştirilmesi için  bütün kat\nmaliklerinin beşte dördünün oyu şarttır", KMK_28))
        # dipnot işareti metnin ortasına düşse bile
        self.assertTrue(mevzuat.alinti_metinde_mi("Yönetim planı yönetim tarzını düzenler. (Değişik: 13/4/1983 - 2814/11 md.)", KMK_28))

    def test_degismis_ya_da_uydurma_alinti_gecmez(self):
        self.assertFalse(mevzuat.alinti_metinde_mi("Yönetim planının değiştirilmesi için bütün kat maliklerinin salt çoğunluğu yeterlidir.", KMK_28))

    def test_cok_kisa_alinti_kanit_sayilmaz(self):
        self.assertFalse(mevzuat.alinti_metinde_mi("beşte dördünün", KMK_28))


class TestKonuDayanagi(unittest.TestCase):
    def _sorun(self, **degisen):
        with patch.object(mevzuat, "brief_mevzuati", return_value=_metin()):
            return mevzuat.konu_dayanagi_sorunlari({**KONU, **degisen})

    def test_temiz_konu(self):
        self.assertEqual(self._sorun(), [])

    def test_alintisi_olmayan_eski_konu_denetlenmez(self):
        self.assertEqual(self._sorun(dayanak_alintisi=""), [])

    def test_kanun_degisip_alinti_kaybolursa_kirmizi(self):
        s = self._sorun(dayanak_alintisi="Yönetim planının değiştirilmesi için bütün kat maliklerinin dörtte üçünün oyu şarttır.")
        self.assertTrue(any("birebir bulunamadı" in x for x in s), s)

    def test_acideki_kanunda_olmayan_sure_ve_oran_yakalanir(self):
        self.assertTrue(any("süre" in x for x in self._sorun(aci=KONU["aci"] + " Toplantı otuz gün önce duyurulur.")))
        self.assertTrue(any("oran" in x for x in self._sorun(aci=KONU["aci"] + " Gecikmeye yüzde on faiz uygulanır.")))

    def test_acideki_kanunda_olmayan_cogunluk_yakalanir(self):
        self.assertTrue(any("çoğunluk" in x for x in self._sorun(aci=KONU["aci"] + " Bazı kararlar üçte iki çoğunlukla alınır.")))

    def test_atifsiz_alinti_ve_alinamayan_metin(self):
        self.assertTrue(mevzuat.konu_dayanagi_sorunlari({**KONU, "mevzuat": None}))
        with patch.object(mevzuat, "brief_mevzuati", return_value=_metin(metin="", cozulemeyen=["634 md. 28"])):
            self.assertTrue(any("alınamadı" in x for x in mevzuat.konu_dayanagi_sorunlari(KONU)))


class TestCogunlukKapisi(unittest.TestCase):
    """Kanun 'çoğunluğu', 'dördünün' yazar; içerik 'çoğunluk', 'dört' der. Doğru içerik ⛔ almamalı."""

    def _denetle(self, metin):
        veri = {"manset": "Başlık", "spot": metin}
        brief = {"mevzuat": "Kat Mülkiyeti Kanunu md. 28 ve 30", "mevzuat_metni": KMK_28 + " " + KMK_30, "veri_kaynagi": "kanun"}
        return dogrula.denetle(veri, brief)

    def test_salt_cogunluk_yumusamasi(self):
        self.assertFalse(dogrula.kritik_var(self._denetle("İkinci toplantıda karar yeter sayısı katılanların salt çoğunluk oyudur.")))

    def test_beste_dort_ceki_eki(self):
        self.assertFalse(dogrula.kritik_var(self._denetle("Plan değişikliği için beşte dört oy gerekir.")))

    def test_kanunda_olmayan_cogunluk_hala_kritik(self):
        self.assertTrue(dogrula.kritik_var(self._denetle("Plan değişikliği için üçte iki çoğunluk yeterlidir.")))
        self.assertTrue(dogrula.kritik_var(self._denetle("Plan oybirliğiyle değişir.")))

    def test_katlama(self):
        self.assertIn("salt çoğunluk", mevzuat.cogunluk_katla("salt çoğunluğudur"))
        self.assertIn("salt çoğunluk", mevzuat.cogunluk_katla("salt çoğunluk"))   # zaten düzse değişmez


class TestYuzSayisi(unittest.TestCase):
    """7464 sayılı Kanun "yüz gün" yazar; 99'un üstü tanınmayınca "100 gün" yazan doğru içerik kanunda yok sayılıyordu."""

    def test_yazi_ve_rakam_esdeger(self):
        self.assertEqual(mevzuat.sure_ifadeleri("yüz gün"), mevzuat.sure_ifadeleri("100 gün"))
        self.assertEqual(mevzuat.sure_ifadeleri("yüz yirmi gün"), {("120", "gün")})
        self.assertEqual(mevzuat.sure_ifadeleri("yüz yirmi beş gün"), {("125", "gün")})
        self.assertEqual(mevzuat.sure_ifadeleri("yüz beş gün"), {("105", "gün")})
        self.assertEqual(mevzuat.sure_ifadeleri("on dört gün"), {("14", "gün")})  # eski davranış bozulmadı

    def test_yuzde_ile_karismaz(self):
        self.assertEqual(mevzuat.sure_ifadeleri("yüzde beş oranında artış"), set())
        self.assertEqual(mevzuat.sure_ifadeleri("yüzdelik dilim ay sonu"), set())  # "yüz" + "de/delik" süre başlatmaz
        self.assertEqual(mevzuat.oran_ifadeleri("yüzde yüz"), {"100"})
        self.assertEqual(mevzuat.oran_ifadeleri("yüzde yirmi beş"), {"25"})

    def test_aciklamada_100_gun_kanundaki_yuz_gunle_eslesir(self):
        konu = {"kod": "T-002", "mevzuat": "7464 sayılı Kanun md. 3 ve 4", "aci": "100 günü aşmayan kiralamalarda izin belgesi gerekir."}
        metin = {"metin": "Kiraya verenin konutunu en fazla yüz gün süreyle kiralamasına izin verilmesi amacıyla düzenlenen belge.",
                 "son_degisiklik": None, "cozulemeyen": [], "cekildi": "2026-10-07"}
        with patch.object(mevzuat, "brief_mevzuati", return_value=metin):
            self.assertEqual(mevzuat.konu_dayanagi_sorunlari({**konu, "dayanak_alintisi": "en fazla yüz gün süreyle kiralamasına izin verilmesi amacıyla düzenlenen belge."}), [])

    def test_7464_kanun_defterinde(self):
        self.assertIn(7464, mevzuat.KANUNLAR)
        cozulen, cozulemeyen = mevzuat.atiflari_coz("7464 sayılı Kanun md. 3 ve 4")
        self.assertEqual(cozulen, [(7464, ["3", "4"])])
        self.assertEqual(cozulemeyen, [])


class TestBankaSemasi(unittest.TestCase):
    def setUp(self):
        self.konular = konu_bankasi.havuzu_yukle()
        self.dayanakli = [k for k in self.konular if k.get("dayanak_alintisi")]

    def test_kodlar_benzersiz(self):
        kodlar = [k["kod"] for k in self.konular]
        self.assertEqual(len(kodlar), len(set(kodlar)))

    def test_dayanakli_konular_eksiksiz(self):
        self.assertGreaterEqual(len(self.dayanakli), 12)
        for k in self.dayanakli:
            self.assertTrue(k.get("mevzuat"), k["kod"])
            self.assertGreaterEqual(len(k["dayanak_alintisi"]), 40, k["kod"])
            self.assertTrue(k.get("mevzuat_kontrol"), k["kod"])
            self.assertFalse(k.get("engel"), k["kod"])

    def test_s4_017_kanundaki_gercek_kuralla_acik(self):
        k = next(k for k in self.konular if k["kod"] == "S4-017")
        self.assertFalse(k.get("engel"))
        # Eski, kanunda olmayan iddialar geri gelmemeli
        self.assertNotIn("yarısı", k["aci"])
        self.assertNotIn("4 yılda", k["aci"])
        self.assertIn("yeniden değerleme oranında", k["aci"])

    def test_brief_dayanakli_konuda_kanun_sinirini_ekler(self):
        k = self.dayanakli[0]
        self.assertIn("KANUN SINIRI", konu_bankasi.brief_metni(k))
        eski = next(x for x in self.konular if not x.get("dayanak_alintisi"))
        self.assertNotIn("KANUN SINIRI", konu_bankasi.brief_metni(eski))

    def test_onbellekteki_gercek_kanun_metniyle_dogrulanir(self):
        # Önbellek yoksa (CI) atlanır: o ortamda haftalık mevzuat-denetimi.yml ağla doğrular
        if not (mevzuat.ONBELLEK / "634.txt").exists():
            self.skipTest("kanun metni önbelleği bu ortamda yok")
        for k in self.dayanakli:
            self.assertEqual(mevzuat.konu_dayanagi_sorunlari(k), [], k["kod"])


if __name__ == "__main__":
    unittest.main()
