"""
tests/test_seslendirme.py — Seslendirme kararlarının sözleşmesi (kullanıcı kararları 2026-09-26).

  * Yalnızca KAPAK okunur; madde/bölüm başlıkları hiçbir biçimde okunmaz.
  * Nedir Doğrusu'nda yanlış inanış okunmaz (etiketsiz okununca doğru bilgi gibi duyulur).
  * Ses Sıla Özalp, "hızlı ve enerjik" ayarla; tek kaynak config.yaml. Ses kütüphaneden
    kalkarsa yedeğe düşülür; eski ELEVENLABS_VOICE_ID ortam değişkeni seçimi ezmez.
  * Son slaytta kapanış çağrısı, videonun SONUNA yaslı; kapak ses bitene kadar ekranda.
  * Onayda seslendirilmiş video yüklemede yeniden karıştırılmaz (anlatım silinirdi).
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src import config, ses, video

HABER_170 = {
    "format_turu": "dailybrief",
    "manset": "Silivri Selimpaşa'da Yeni İmar Planı Askıya Çıktı",
    "spot": "Bakanlıkça onaylanan 1/5000 ölçekli nazım imar planı 30 gün süreyle askıya çıkarıldı.",
    "detay_maddeleri": [
        {"etiket": "KAPSANAN ALANLAR & ADA-PARSEL", "metin": "Selimpaşa E-5 aksındaki muhtelif ada ve parselleri kapsıyor."},
        {"etiket": "30 GÜNLÜK ASKI VE İTİRAZ TAKVİMİ", "metin": "3194 sayılı Kanunun 8. maddesi uyarınca plan 30 gün askıda kalacak."},
    ],
    "uzman_notu": "Parselinizin imar durum belgesini askı süresi dolmadan inceleyin.",
    "rozet_metni": "EDM GÜNDEM // ARSA & İMAR",
}
BASLIKLAR = ["KAPSANAN", "ASKI VE İTİRAZ", "HABERİN AYRINTILARI", "DEĞERLENDİRME", "GÜNDEM", "YATIRIMCI İÇİN"]


class TestNeOkunur(unittest.TestCase):
    def test_haberde_yalniz_manset_ve_spot(self):
        metin = ses.kapak_seslendirme_metni(HABER_170)
        self.assertEqual(metin, f"{HABER_170['manset']}. {HABER_170['spot']}")
        for baslik in BASLIKLAR:
            self.assertNotIn(baslik.lower(), metin.lower())
        self.assertNotIn("muhtelif ada", metin)  # ayrıntı maddeleri okunmaz

    def test_sozlukte_terim_ve_tanim_puf_maddeleri_degil(self):
        veri = {"format_turu": "sozluk", "terim": "İFRAZ", "tanim_metni": "Bir parselin birden fazla parsele bölünmesidir.",
                "puf_maddeleri": ["Belediyeden imar durumu belgesi alın."]}
        self.assertEqual(ses.kapak_seslendirme_metni(veri), "İFRAZ. Bir parselin birden fazla parsele bölünmesidir.")

    def test_nedir_dogrusunda_yanlis_inanis_okunmaz(self):
        veri = {"format_turu": "nedir_dogrusu", "yanlis_metin": "Hisseli tapu satılamaz.",
                "dogru_metin": "Hisseli tapu satılabilir; diğer paydaşların önalım hakkı vardır."}
        metin = ses.kapak_seslendirme_metni(veri)
        self.assertNotIn("satılamaz", metin)
        self.assertEqual(metin, veri["dogru_metin"])

    def test_net_cevapta_soru_cevap_gerekce(self):
        veri = {"format_turu": "net_cevap", "soru": "Kira ödenmezse ev sahibi hemen dava açabilir mi",
                "net_cevap": "Hayır. Önce en az otuz gün süre verilir", "aciklama": "Süre dolmadan dava açılamaz."}
        self.assertEqual(ses.kapak_seslendirme_metni(veri),
                         "Kira ödenmezse ev sahibi hemen dava açabilir mi? Hayır. Önce en az otuz gün süre verilir. "
                         "Süre dolmadan dava açılamaz.")

    def test_vakada_manset_ve_olay_hukum_degil(self):
        veri = {"format_turu": "vaka", "manset": "Ortağına haber vermeden hissesini sattı",
                "olay_detay": "Ayşe Hanım payını üçüncü kişiye sattı.", "yargitay_hukmu": "Paydaşlar önalım hakkını kullanır.",
                "cikarilacak_ders": "Noter bildirimi yapın."}
        metin = ses.kapak_seslendirme_metni(veri)
        self.assertIn("Ayşe Hanım", metin)
        self.assertNotIn("önalım", metin)
        self.assertNotIn("Noter", metin)

    def test_parcali_manset_ve_tekrar_yok(self):
        veri = {"bicim": "B1", "manset_parca_1": "Hisseli tapuda", "manset_vurgu": "ÖNALIM SÜRESİ",
                "manset_parca_2": "bildirimle başlar", "spot": "Hisseli tapuda ÖNALIM SÜRESİ bildirimle başlar."}
        self.assertEqual(ses.kapak_seslendirme_metni(veri), "Hisseli tapuda ÖNALIM SÜRESİ bildirimle başlar.")

    def test_bos_ve_bozuk_veri(self):
        for veri in (None, {}, [], "metin", {"manset": "   "}):
            self.assertIsNone(ses.kapak_seslendirme_metni(veri))  # type: ignore[arg-type]

    def test_kapanis_cagrisi_biçime_gore_ve_begenin_yok(self):
        haber = ses.kapanis_cagrisi(HABER_170)
        rehber = ses.kapanis_cagrisi({"bicim": "B1"})
        self.assertIn("gündem", haber)
        self.assertIn("kaydedin", rehber)
        for cagri in (haber, rehber):
            self.assertIn("istemiyorsanız", cagri)
            self.assertNotIn("beğen", cagri.lower())


class TestSesSecimi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cikti = Path(self.tmp.name) / "s.mp3"

    def tearDown(self):
        self.tmp.cleanup()

    def _yanit(self, kod, icerik=b"x" * 600, metin=""):
        r = MagicMock()
        r.status_code, r.content, r.text = kod, icerik, metin
        return r

    def _env(self, anahtar, varsayilan=""):
        return {"ELEVENLABS_API_KEY": "sahte", "ELEVENLABS_VOICE_ID": "ESKI_ADAM_SESI"}.get(anahtar, varsayilan)

    @patch("src.ses.ses_suresi_ogren", return_value=3.0)
    @patch("src.ses.requests.post")
    def test_config_sesi_ayarlari_ve_okunus(self, post, _):
        post.return_value = self._yanit(200)
        with patch("src.ses.config.env_al", side_effect=self._env):
            self.assertEqual(ses.metin_seslendir("Hz. Ali 1/5000 ölçekli planı açıkladı.", cikti_yolu=self.cikti), self.cikti)
        url = post.call_args[0][0]
        govde = post.call_args[1]["json"]
        self.assertIn(config.ayar_al("seslendirme.ses_id"), url)
        self.assertNotIn("ESKI_ADAM_SESI", url)  # ortam değişkeni seçimi ezmez
        self.assertEqual(govde["voice_settings"], config.ayar_al("seslendirme.ayarlar"))
        self.assertEqual(govde["text"], "Hazreti Ali beş binde bir ölçekli planı açıkladı.")

    @patch("src.ses.time.sleep")
    @patch("src.ses.ses_suresi_ogren", return_value=3.0)
    @patch("src.ses.requests.post")
    def test_ses_kutuphaneden_kalkinca_yedege_duser(self, post, _, __):
        post.side_effect = [self._yanit(404, b"", '{"detail":{"status":"voice_not_found"}}'), self._yanit(200)]
        with patch("src.ses.config.env_al", side_effect=self._env):
            self.assertEqual(ses.metin_seslendir("Deneme metni.", cikti_yolu=self.cikti), self.cikti)
        self.assertIn(config.ayar_al("seslendirme.yedek_ses_id"), post.call_args_list[1][0][0])

    @patch("src.ses.requests.post")
    def test_kota_hatasinda_baska_ses_denenmez(self, post):
        post.return_value = self._yanit(402, b"", "quota_exceeded")
        with patch("src.ses.config.env_al", side_effect=self._env):
            self.assertIsNone(ses.metin_seslendir("Deneme metni.", cikti_yolu=self.cikti))
        self.assertEqual(post.call_count, 1)


class TestSureler(unittest.TestCase):
    def test_yogun_ayrinti_slayti_okuma_suresi_kadar(self):
        yogun = {"detay_maddeleri": [{"etiket": "E", "metin": "kelime " * 80}], "uzman_notu": "kelime " * 20}
        self.assertEqual(video.slayt_surelerini_hesapla(2, haber=yogun), [4.2, video.DETAY_AZAMI_SN])

    def test_seyrek_slayt_asgari_sure(self):
        self.assertEqual(video.slayt_surelerini_hesapla(3, haber={"uzman_notu": "kısa not"})[1:], [6.0, 6.0])

    def test_kapak_ses_bitene_kadar(self):
        self.assertEqual(video.slayt_surelerini_hesapla(2, haber=HABER_170, kapak_konusma_suresi=9.0)[0], 10.7)

    def test_caption_ve_kapak_alanlari_okuma_suresine_girmez(self):
        veri = {"manset": "kelime " * 50, "spot": "kelime " * 50, "caption_instagram": "kelime " * 200}
        self.assertEqual(video.slayt_surelerini_hesapla(2, haber=veri), video.slayt_surelerini_hesapla(2, haber={}))


class TestAnlatimliVideo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.sessiz = Path(self.tmp.name) / "video.mp4"
        self.sessiz.write_bytes(b"v")

    def tearDown(self):
        self.tmp.cleanup()

    def _uret(self, slayt_sayisi, kapak_var=True):
        yakalanan = {}
        kapak, cagri = Path(self.tmp.name) / "kapak.mp3", Path(self.tmp.name) / "cagri.mp3"

        def reels(yollar, **kw):
            yakalanan["sureler"] = kw["slayt_sureleri"]
            return self.sessiz

        def iz(parcalar, toplam, cikti):
            yakalanan["parcalar"], yakalanan["toplam"] = parcalar, toplam
            return cikti

        with patch.object(ses, "metin_seslendir", side_effect=lambda m, **kw: kapak if kapak_var else None) as tts, \
             patch.object(ses, "_onbellekli_seslendir", return_value=cagri), \
             patch.object(ses, "ses_suresi_ogren", side_effect=lambda y: 9.0 if y == kapak else 3.0), \
             patch.object(video, "slaytlardan_reels_uret", side_effect=reels), \
             patch.object(ses, "_anlatim_izi", side_effect=iz), \
             patch.object(ses, "sesli_video_hazirla", side_effect=lambda v, **kw: yakalanan.update(mix=kw) or v):
            ses.anlatimli_video_uret([f"s{i}.jpg" for i in range(slayt_sayisi)], veri=HABER_170)
            yakalanan["tts_metni"] = tts.call_args[0][0] if tts.called else None
        return yakalanan, kapak, cagri

    def test_kapak_basta_cagri_sonda(self):
        y, kapak, cagri = self._uret(2)
        sureler = y["sureler"]
        self.assertEqual(sureler[0], 10.7)  # 0.4 + 9 sn ses + 0.8 + 0.5 geçiş
        self.assertEqual(y["parcalar"][0], (kapak, ses.ANLATIM_ONCESI_SN))
        cagri_bas = y["parcalar"][1][1]
        self.assertEqual(y["parcalar"][1][0], cagri)
        self.assertGreaterEqual(cagri_bas, sureler[0] + ses.CAGRI_ARASI_SN)  # son slayta düşer
        self.assertAlmostEqual(cagri_bas + 3.0 + ses.ANLATIM_SONRASI_SN, sum(sureler) - video.GECIS_SN)
        self.assertEqual(y["mix"]["ses_seviyesi"], 0.14)
        for baslik in BASLIKLAR:
            self.assertNotIn(baslik.lower(), y["tts_metni"].lower())

    def test_tek_slaytta_cagri_kapak_sesinin_ardinda(self):
        y, _, _ = self._uret(1)
        cagri_bas = y["parcalar"][1][1]
        self.assertAlmostEqual(cagri_bas, ses.ANLATIM_ONCESI_SN + 9.0 + ses.CAGRI_ARASI_SN)
        self.assertGreaterEqual(y["sureler"][0], cagri_bas + 3.0 + ses.ANLATIM_SONRASI_SN)

    def test_ses_yoksa_video_muzikle_cikar(self):
        y, _, _ = self._uret(2, kapak_var=False)
        self.assertNotIn("parcalar", y)
        self.assertIsNone(y["mix"]["konusma_sesi"])
        self.assertEqual(y["mix"]["ses_seviyesi"], 0.20)


class TestKaristirma(unittest.TestCase):
    @patch("src.ses.subprocess.run")
    def test_sesli_video_yeniden_karistirilmaz(self, run):
        with tempfile.TemporaryDirectory() as d:
            v = Path(d) / "reels_12_sesli.mp4"
            v.write_bytes(b"v")
            self.assertEqual(ses.sesli_video_hazirla(v, ses_seviyesi=0.20), v)
        run.assert_not_called()

    @patch("src.ses.subprocess.run")
    def test_anlatimli_miks_ses_seviyesi_normallesir(self, run):
        with tempfile.TemporaryDirectory() as d:
            v, k, m = Path(d) / "v.mp4", Path(d) / "k.wav", Path(d) / "m.mp3"
            for p in (v, k, m):
                p.write_bytes(b"x")
            ses.sesli_video_hazirla(v, ses_dosyasi=m, konusma_sesi=k, ses_seviyesi=0.14)
        self.assertIn(f"loudnorm=I={config.ayar_al('seslendirme.hedef_lufs')}", " ".join(run.call_args[0][0]))


class TestOnayAkisi(unittest.TestCase):
    def test_onay_videosu_seslendirmeli_ve_onaydan_once_gonderiliyor(self):
        """Kullanıcı talebi: Onay akışında seslendirmeli video hazırlanır ve menüden önce iletilir."""
        kaynak = (Path(__file__).resolve().parent.parent / "src" / "telegram_bot.py").read_text(encoding="utf-8")
        govde = kaynak[kaynak.index("def _haber_onayina_sun("):]
        govde = govde[:govde.index("\ndef ")]
        self.assertIn("ses.anlatimli_video_uret(", govde)
        self.assertIn("medya_grubu_gonder(", govde)
        self.assertIn("video_gonder(", govde)
        self.assertLess(govde.rindex("video_gonder("), govde.index("reply_markup=butonlar"))


if __name__ == "__main__":
    unittest.main()
