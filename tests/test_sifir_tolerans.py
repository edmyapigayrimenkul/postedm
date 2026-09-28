"""
tests/test_sifir_tolerans.py — "Yalan bilgiye müsamaha yok" kararının (2026-09-24) sözleşmesi.

Her test canlı hesapta yaşanmış bir yanlışı ya da onu mümkün kılan bir yolu
kapatır: #142 ("İKİ YIL BOYUNCA", önalımda süre 7571 ile bir yıla indi),
#157 (koddaki sabit "Yargıtay" cümlesi), #170/#171 (kaynaksız haber).
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from src import db, dogrula, generate_text, mevzuat

ONALIM_METNI = ("Önalım hakkı, satışın hak sahibine bildirildiği tarihin üzerinden üç ay ve her hâlde "
                "satışın üzerinden bir yıl geçmekle düşer. Dava konusu payın rayiç bedeli hâkim tarafından belirlenir.")


class _GeciciDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_patch = patch("src.db.DB_YOLU", Path(self.tmp.name) / "t.db")
        self.db_patch.start()
        db.tablolari_olustur()

    def tearDown(self):
        self.db_patch.stop()
        self.tmp.cleanup()


class TestDenetim(unittest.TestCase):
    def test_caption_de_hukuki_denetimden_gecer(self):
        """Threads'te okunan şey caption'dır; eski süre orada da yakalanmalı."""
        veri = {"manset": "Hisseli tapuda önalım", "caption_threads": "Ortak iki yıl boyunca dava açabilir."}
        uyarilar = dogrula.denetle(veri, {"mevzuat": "TMK md. 733", "mevzuat_metni": ONALIM_METNI})
        self.assertTrue(any("SÜRE KAYNAKTA YOK" in u for u in uyarilar), uyarilar)
        self.assertTrue(dogrula.kritik_var(uyarilar))

    def test_kaynakta_olmayan_oran_kritik(self):
        veri = {"manset": "Önalımda bedel", "spot": "Hisse %30 indirimle alınır."}
        uyarilar = dogrula.denetle(veri, {"mevzuat": "TMK md. 734", "mevzuat_metni": ONALIM_METNI})
        self.assertTrue(any(u.startswith("⛔ RAKAM KAYNAKTA YOK") for u in uyarilar), uyarilar)

    def test_kanun_metnindeki_yaziyla_oran_gecer(self):
        """Kanun oranı yazıyla verir ('yüzde kırkbeş'); içerikteki %45 onunla eşleşmeli."""
        metin = "Düzenleme ortaklık payı, düzenlemeye tabi alanın yüzde kırkbeşini geçemez."
        uyarilar = dogrula.denetle({"spot": "DOP kesintisi en fazla %45 olabilir."},
                                   {"mevzuat": "İmar Kanunu md. 18", "mevzuat_metni": metin})
        self.assertFalse(any("RAKAM" in u for u in uyarilar), uyarilar)

    def test_dogru_sure_gecer(self):
        veri = {"manset": "Önalımda üst süre", "spot": "Satıştan itibaren bir yıl geçince hak düşer."}
        uyarilar = dogrula.denetle(veri, {"mevzuat": "TMK md. 733", "mevzuat_metni": ONALIM_METNI})
        self.assertFalse(dogrula.kritik_var(uyarilar), uyarilar)

    def test_haber_icerigi_haber_metnine_karsi_denetlenir(self):
        """Triyaj brief'i varken de süre HABER METNİNE karşı denetlenir."""
        haber = {"kaynak": "Emlakkulisi", "orijinal_url": "https://ornek.com/x",
                 "orijinal_baslik": "Plan askıya çıktı", "orijinal_ozet": "Plan 30 gün askıda kalacak."}
        veri = {"manset": "Plan askıda", "spot": "İtiraz için 15 gün var.", "_brief": {"mevzuat": None}}
        uyarilar = dogrula.icerigi_denetle(veri, haber)
        self.assertTrue(any("SÜRE KAYNAKTA YOK" in u for u in uyarilar), uyarilar)
        veri["spot"] = "Plan 30 gün askıda kalacak."
        self.assertFalse(dogrula.kritik_var(dogrula.icerigi_denetle(veri, haber)))

    def test_kaynak_metni_yoksa_sure_uyarisi(self):
        uyarilar = dogrula.denetle({"spot": "On dört gün içinde cayabilirsiniz."}, {"mevzuat": None})
        self.assertTrue(any("SÜRE DOĞRULANAMADI" in u for u in uyarilar), uyarilar)
        self.assertFalse(dogrula.kritik_var(uyarilar))

    def test_oran_ve_atif_yardimcilari(self):
        self.assertEqual(mevzuat.oran_ifadeleri("%45, yüzde kırkbeş, yüzde 12,5"), {"45", "12.5"})
        self.assertEqual(
            mevzuat.atif_satiri("Bkz. 4721 sayılı Kanun md. 733, 734 ve Harçlar Kanunu md. 63."),
            "4721 sayılı Kanun md. 733, 734; 492 sayılı Kanun md. 63",
        )
        self.assertIsNone(mevzuat.atif_satiri("Kanun maddesi yok."))


class TestUretimDuzeltmeTuru(unittest.TestCase):
    def test_kritik_bulguda_bir_kez_yeniden_yazdirir(self):
        konu = {"kod": "S1-024", "bicim": "B1", "baslik": "Önalım", "aci": "Açı",
                "mevzuat": "Türk Medeni Kanunu md. 733", "yerel": None}
        yanlis = {"manset": "Hisseli tapuda İKİ YIL BOYUNCA dava açılır"}
        dogru = {"manset": "Hisseli tapuda BİR YIL içinde dava açılır"}
        with patch("src.konu_bankasi.brief_metni", return_value="BRIEF"), \
             patch("src.generate_text._uret", side_effect=[dict(yanlis), dict(dogru)]) as uret, \
             patch("src.dogrula._kanun_metni", return_value=ONALIM_METNI):
            veri = generate_text.konudan_uret(konu)
        self.assertEqual(uret.call_count, 2)
        self.assertIn("YAYIN DENETİMİNDEN KALDI", uret.call_args_list[1].args[0])
        self.assertEqual(veri["manset"], dogru["manset"])
        self.assertEqual(veri["konu_kodu"], "S1-024")

    def test_temiz_icerikte_ikinci_tur_yok(self):
        konu = {"kod": "S1-024", "bicim": "B1", "baslik": "Önalım", "aci": "Açı", "mevzuat": None}
        with patch("src.konu_bankasi.brief_metni", return_value="BRIEF"), \
             patch("src.generate_text._uret", return_value={"manset": "Temiz"}) as uret:
            generate_text.konudan_uret(konu)
        self.assertEqual(uret.call_count, 1)


class TestBriefKorunur(_GeciciDB):
    def test_yenile_banka_icerigini_kendi_briefiyle_uretir(self):
        """Yenile, konu bankası içeriğini B5 haber yorumuna düşürmüyor; brief ve format korunuyor."""
        haber = {"id": 7, "kaynak": "EDM Konu Bankası // S1-001",
                 "detay_metni": json.dumps({"konu_kodu": "S1-001", "format_turu": "net_cevap", "foto_kaynak": "stok"})}
        with db._baglanti_al() as conn:
            conn.execute("INSERT INTO haberler (id, kaynak, orijinal_baslik, orijinal_url, eklenme_tarihi, durum) "
                         "VALUES (7, ?, 'x', 'edm://konu/S1-001/1', '2026-09-24', 'onay_bekliyor')", (haber["kaynak"],))
            conn.commit()
        with patch("src.generate_text.konudan_uret", return_value={"manset": "Yeni", "konu_kodu": "S1-001"}) as ku, \
             patch("src.generate_text.otorite_icerigi_uret") as b5:
            veri = generate_text.haber_metinleri_uret(haber, ek_talimat="Daha kısa")
        b5.assert_not_called()
        self.assertEqual(ku.call_args.kwargs["format_turu"], "net_cevap")
        self.assertEqual(ku.call_args.kwargs["ek_talimat"], "Daha kısa")
        self.assertEqual(ku.call_args.args[0]["kod"], "S1-001")
        self.assertEqual(veri["foto_kaynak"], "stok")
        self.assertEqual(db.haber_getir(7)["manset"], "Yeni")


class TestYayinKapisi(_GeciciDB):
    def _kayit(self) -> int:
        veri = {"manset_parca_1": "Hisseli tapuda", "manset_vurgu": "İKİ YIL BOYUNCA",
                "manset_parca_2": "dava açılır", "bicim": "B1",
                "_brief": {"mevzuat": "Türk Medeni Kanunu md. 733"}}
        with db._baglanti_al() as conn:
            cur = conn.execute(
                "INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, eklenme_tarihi, manset, detay_metni, durum)"
                " VALUES ('EDM Konu Bankası // S1-001', 'x', 'edm://konu/S1-001/1', '2026-09-24', ?, ?, 'yeni')",
                (generate_text.manset_birlestir(veri), json.dumps(veri, ensure_ascii=False)),
            )
            conn.commit()
            return cur.lastrowid

    def test_kritik_bulguda_onaya_sunulmaz_ve_gorsel_uretilmez(self):
        from src import telegram_bot
        hid = self._kayit()
        with patch("src.dogrula._kanun_metni", return_value=ONALIM_METNI), \
             patch("src.telegram_bot.mesaj_gonder") as mesaj, \
             patch("src.telegram_bot.medya_grubu_gonder") as album, \
             patch("src.make_image.otorite_gonderi_slaytlari_uret") as cizim, \
             patch("src.db_senkron.hemen_kaydet"):
            sonuc = telegram_bot.haber_onayina_sun(hid)
        self.assertFalse(sonuc)
        cizim.assert_not_called()
        album.assert_not_called()
        self.assertEqual(db.haber_getir(hid)["durum"], "engellendi")
        metin = mesaj.call_args.args[0]
        self.assertIn("durduruldu", metin)
        self.assertIn("SÜRE KAYNAKTA YOK", metin)

    def test_denetim_cokerse_kapi_kapali_kalir(self):
        from src import telegram_bot
        hid = self._kayit()
        with patch("src.dogrula.icerigi_denetle", side_effect=RuntimeError("bozuk")), \
             patch("src.telegram_bot.mesaj_gonder") as mesaj, \
             patch("src.db_senkron.hemen_kaydet"):
            gecti, _ = telegram_bot.yayin_kapisi(hid, db.haber_getir(hid), {"manset": "x"})
        self.assertFalse(gecti)
        self.assertIn("DENETİM ÇALIŞMADI", mesaj.call_args.args[0])

    def test_yayin_aninda_da_kapi_calisir(self):
        """Kapıdan önce onaya sunulmuş içerik (#243 gibi) Yayınla'ya basılınca da denetlenir."""
        import importlib.util
        yol = Path(__file__).resolve().parent.parent / "scripts" / "yayinla.py"
        spec = importlib.util.spec_from_file_location("yayinla_kapi_testi", yol)
        yayinla = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(yayinla)
        hid = self._kayit()
        db.haber_guncelle(hid, durum="onay_bekliyor")
        with patch("src.dogrula._kanun_metni", return_value=ONALIM_METNI), \
             patch.object(yayinla.telegram_bot, "mesaj_gonder") as mesaj, \
             patch("src.instagram.carousel_yayinla") as ig, \
             patch("src.db_senkron.hemen_kaydet"), \
             patch.object(yayinla.sys, "argv", ["yayinla.py", "--tur", "haber", "--id", str(hid), "--hedef", "ig"]):
            yayinla.main()
        ig.assert_not_called()
        self.assertIn("durduruldu", mesaj.call_args_list[0].args[0])
        self.assertEqual(db.haber_getir(hid)["durum"], "engellendi")

    def test_engellenen_icerik_yayinlanamaz(self):
        from src import durum_kurali
        self.assertIn("engellendi", durum_kurali.KAPALI)


class TestHaberOnerisi(_GeciciDB):
    def test_tarih_metni(self):
        from src import haber_oneri
        simdi = datetime(2026, 9, 24, 14, 0, tzinfo=timezone.utc)
        self.assertEqual(haber_oneri.tarih_metni("2026-09-24T11:05:00+00:00", simdi),
                         "24 Eylül 2026 Perşembe, 14:05 · 2 saat önce")
        self.assertIn("gün önce", haber_oneri.tarih_metni("2026-09-21T11:05:00+00:00", simdi))
        self.assertEqual(haber_oneri.tarih_metni("bozuk", simdi), "tarih bilinmiyor")

    def test_icerige_cevir_triyaj_reddederse_uretmez(self):
        from src import haber_oneri
        with db._baglanti_al() as conn:
            conn.execute("INSERT INTO haberler (id, kaynak, orijinal_baslik, orijinal_url, eklenme_tarihi, durum)"
                         " VALUES (9, 'Emlakkulisi', 'Fiyatlar arttı', 'https://ornek.com/9', '2026-09-24', 'onerildi')")
            conn.commit()

        def reddet(haber, asgari_guven=6, *args, **kwargs):
            haber["_red_gerekcesi"] = "somut bir kural/süre/oran değişimi yok"
            return None

        with patch("src.haber_triyaj.triyaj_et", side_effect=reddet), \
             patch("src.telegram_bot.haberden_icerik_hazirla") as uret, \
             patch("src.telegram_bot.mesaj_gonder") as mesaj:
            self.assertFalse(haber_oneri.haberden_icerige(9))
        uret.assert_not_called()
        self.assertIn("somut bir kural", mesaj.call_args.args[0])
        self.assertEqual(db.haber_getir(9)["durum"], "elendi")

    def test_icerige_cevir_islenmis_haberi_tekrar_uretmez(self):
        from src import haber_oneri
        with db._baglanti_al() as conn:
            conn.execute("INSERT INTO haberler (id, kaynak, orijinal_baslik, orijinal_url, eklenme_tarihi, durum)"
                         " VALUES (10, 'Emlakkulisi', 'x', 'https://ornek.com/10', '2026-09-24', 'yayinlandi')")
            conn.commit()
        with patch("src.haber_triyaj.triyaj_et") as triyaj, patch("src.telegram_bot.mesaj_gonder"):
            self.assertFalse(haber_oneri.haberden_icerige(10))
        triyaj.assert_not_called()

    def test_icerige_cevir_elendi_durumunu_da_kabul_eder(self):
        from src import haber_oneri
        with db._baglanti_al() as conn:
            conn.execute("INSERT INTO haberler (id, kaynak, orijinal_baslik, orijinal_url, eklenme_tarihi, durum)"
                         " VALUES (11, 'Emlakkulisi', 'Elendi haberi', 'https://ornek.com/11', '2026-09-24', 'elendi')")
            conn.commit()
        with patch("src.haber_triyaj.triyaj_et", return_value={"kod": "HABER-11", "bicim": "B5"}) as triyaj, \
             patch("src.telegram_bot.haberden_icerik_hazirla", return_value=True) as uret:
            self.assertTrue(haber_oneri.haberden_icerige(11))
        triyaj.assert_called_once()
        self.assertTrue(triyaj.call_args.kwargs.get("zorla"))
        uret.assert_called_once()

    def test_triyaj_et_zorla_kabul(self):
        from src import haber_triyaj
        haber = {
            "id": 12,
            "orijinal_baslik": "TOKİ Kura Çekilişi Başladı",
            "orijinal_ozet": "TOKİ kuraları çekilmeye başlandı.",
            "kategori": "konut",
        }
        # Model olgusal olarak somut kural bulamasa bile (ör. red) zorla=True olduğunda kabul etmeli
        fake_llm = json.dumps({
            "somut_kural": "hayir",
            "okuyucu_eylemi": None,
            "dayanak_alintisi": None,
            "yerel_gecis": "hayir",
            "mevzuat_alintisi": None,
            "kalicilik": "guncel",
            "zaten_biliniyor": "hayir",
            "tekil_segment": "hayir",
            "baslik": "TOKİ Kurası",
            "aci": "Kura çekimi süreci ve başvuranlara etkisi.",
            "sutun": "S4",
            "bicim": "B5",
            "kanca_kalip": "yaygin_yanlis",
        })
        with patch("src.generate_text._gemini_cagri", return_value=fake_llm):
            # Normal triyaj reddeder
            self.assertIsNone(haber_triyaj.triyaj_et(haber, asgari_guven=6, zorla=False))
            # zorla=True kabul eder
            brief = haber_triyaj.triyaj_et(haber, asgari_guven=6, zorla=True)
            self.assertIsNotNone(brief)
            self.assertEqual(brief["bicim"], "B5")
            self.assertEqual(brief["kod"], "HABER-12")

    def test_gunluk_sinir(self):
        from src import haber_oneri
        simdi = datetime.now(timezone.utc)
        db.ayar_yaz("haber_oneri_gunluk", f"{haber_oneri._gunluk_sayac_anahtari(simdi)}:{haber_oneri.GUNLUK_AZAMI}")
        with patch("src.haber_oneri.adaylari_sec") as sec, patch("src.telegram_bot.mesaj_gonder"):
            self.assertEqual(haber_oneri.onerileri_gonder(tara=False), 0)
        sec.assert_not_called()


class TestTakipci(_GeciciDB):
    def test_kayit_ve_degisim(self):
        from src import takipci
        gun1 = datetime(2026, 9, 17, 9, 0, tzinfo=timezone.utc)
        gun8 = gun1 + timedelta(days=7)
        with patch.dict(takipci.KANALLAR, {"instagram": lambda: 60, "threads": lambda: None}, clear=True):
            takipci.kaydet(gun1)
        with patch.dict(takipci.KANALLAR, {"instagram": lambda: 67, "threads": lambda: 10}, clear=True):
            takipci.kaydet(gun8)
            takipci.kaydet(gun8)  # aynı gün ikinci koşu güncellenir, çoğaltmaz
        d = takipci.degisim(gun=7)
        self.assertEqual(d["instagram"], {"sayi": 67, "fark": 7})
        self.assertEqual(d["threads"], {"sayi": 10, "fark": None})  # 7 gün önce okunamamıştı
        with db._baglanti_al() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM takipci_gecmisi").fetchone()[0], 4)

    def test_bir_kanalin_hatasi_digerlerini_durdurmaz(self):
        from src import takipci

        def patla():
            raise ValueError("izin yok")

        with patch.dict(takipci.KANALLAR, {"instagram": lambda: 60, "facebook": patla}, clear=True):
            sonuc = takipci.kaydet(datetime(2026, 9, 24, tzinfo=timezone.utc))
        self.assertEqual(sonuc, {"instagram": 60, "facebook": None})


class TestPromptSozlesmesi(unittest.TestCase):
    def test_eski_hukuk_ornekleri_promptta_yok(self):
        """Prompttaki örnekler modele eski hukuku ezberletiyordu (#142 'İKİ YIL BOYUNCA')."""
        kurallar = generate_text.ORTAK_KURALLAR
        for yasak in ("İKİ YIL BOYUNCA", "iki yıl", "2 yıllık", "%65 DAHA UCUZ", "hisseniz gider", "elinizden gidebilir"):
            self.assertNotIn(yasak, kurallar)
        self.assertIn("CÜMLE DÜZENİNDE", kurallar)
        self.assertIn("SORU YOK", kurallar)


if __name__ == "__main__":
    unittest.main()
