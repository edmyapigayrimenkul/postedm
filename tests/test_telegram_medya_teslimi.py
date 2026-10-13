"""
tests/test_telegram_medya_teslimi.py — Slayt albümü ve onay kartı Telegram'a GÜVENİLİR ulaşsın (2026-10-12).

Olay: günlük içeriğin albüm yüklemesi 60 sn okuma zaman aşımına uğradı; eski yedek yol yerel dosya yollarını
Telegram'a "URL" diye gönderip sessizce 400 aldı, albüm hiç gelmedi ve kimseye haber verilmedi.
Burada ağ gerçek değildir: `requests.post` sahtelenir, `time.sleep` bekletmez.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import db, telegram_bot
from src.telegram import album as album_modulu


def cevap(durum: int, govde: dict) -> MagicMock:
    r = MagicMock()
    r.status_code = durum
    r.json.return_value = govde
    r.text = json.dumps(govde)
    r.content = r.text.encode()
    return r


def tamam_grup(*idler: int) -> MagicMock:
    return cevap(200, {"ok": True, "result": [{"message_id": i} for i in idler]})


def tamam_foto(mid: int) -> MagicMock:
    return cevap(200, {"ok": True, "result": {"message_id": mid}})


class MedyaTeslimiTesti(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_yolu = Path(self.tmp.name) / "teslim.db"
        self.dbp = patch("src.db.DB_YOLU", self.db_yolu)
        self.dbp.start()
        db.tablolari_olustur()
        self.slaytlar = []
        for i in range(1, 4):
            y = Path(self.tmp.name) / f"slayt_{i}.jpg"
            y.write_bytes(b"\xff\xd8fake-jpeg" + bytes([i]))
            self.slaytlar.append(str(y))
        self.urller = [f"https://i.ibb.co/x{i}/slayt_{i}.jpg" for i in range(1, 4)]
        self.bot = patch("src.telegram.istemci._bot_bilgileri", return_value=("tok", "-100"))  # akışlar (telegram_bot) bunu çağırır
        self.bot.start()
        self.bot_istemci = patch("src.telegram.istemci._bot_bilgileri", return_value=("tok", "-100"))  # albüm/foto bunu çağırır
        self.bot_istemci.start()
        self.uyku = patch("time.sleep")
        self.uyku_mock = self.uyku.start()

    def tearDown(self):
        self.uyku.stop()
        self.bot_istemci.stop()
        self.bot.stop()
        self.dbp.stop()
        self.tmp.cleanup()

    # --- albüm -----------------------------------------------------------------------------------------------

    def test_okuma_zaman_asimindan_sonra_ikinci_deneme_teslim_eder(self):
        cagrilar = [requests.exceptions.ReadTimeout("Read timed out. (read timeout=40)"), tamam_grup(11, 12, 13)]
        with patch("requests.post", side_effect=cagrilar) as post:
            sonuc = telegram_bot.medya_grubu_gonder(self.slaytlar, caption="<b>Başlık</b>")
        self.assertEqual(sonuc, [11, 12, 13])
        self.assertEqual(post.call_count, 2)
        # Her denemede dosyalar baştan açılır: iki çağrıda da üç dosya taşınır
        for c in post.call_args_list:
            self.assertEqual(len(c.kwargs["files"]), 3)
        self.assertEqual(telegram_bot.son_medya_grubu_mesaj_idleri(), [11, 12, 13])

    def test_yerel_yuklemeler_tutmazsa_yedek_url_albumu_gonderilir_yerel_yol_degil(self):
        """Eski hata: yedek yol `media: '/home/runner/.../slayt.jpg'` gönderiyordu. Artık yalnız https adresleri."""
        def sahte(url, **kw):
            if "files" in kw:
                raise requests.exceptions.ReadTimeout("zaman aşımı")
            return tamam_grup(21, 22, 23)

        with patch("requests.post", side_effect=sahte) as post:
            sonuc = telegram_bot.medya_grubu_gonder(self.slaytlar, caption="Başlık", yedek_urller=self.urller)
        self.assertEqual(sonuc, [21, 22, 23])
        url_cagrisi = [c for c in post.call_args_list if "json" in c.kwargs][0]
        medya = [m["media"] for m in url_cagrisi.kwargs["json"]["media"]]
        self.assertEqual(medya, self.urller)
        for m in medya:
            self.assertTrue(m.startswith("https://"))

    def test_yedek_url_sayisi_eslesmezse_kullanilmaz(self):
        """Kısmi ImgBB yüklemesi (3 slayttan 2'si) sıra kaydırır; yanlış görsel yerine yedek hiç kullanılmaz."""
        def sahte(url, **kw):
            if "sendMediaGroup" in url:
                raise requests.exceptions.ConnectTimeout("bağlanamadı")
            return tamam_foto(31)

        with patch("requests.post", side_effect=sahte) as post:
            telegram_bot.medya_grubu_gonder(self.slaytlar, yedek_urller=self.urller[:2])
        self.assertFalse(any("json" in c.kwargs and "media" in c.kwargs["json"] for c in post.call_args_list))

    def test_albumun_hicbir_yolu_tutmazsa_foto_foto_gonderilir_baslik_ilkine(self):
        sayac = {"foto": 0}

        def sahte(url, **kw):
            if "sendMediaGroup" in url:
                raise requests.exceptions.ReadTimeout("zaman aşımı")
            sayac["foto"] += 1
            return tamam_foto(40 + sayac["foto"])

        with patch("requests.post", side_effect=sahte) as post:
            sonuc = telegram_bot.medya_grubu_gonder(self.slaytlar, caption="<b>Başlık</b>")
        self.assertEqual(sonuc, [41, 42, 43])
        fotolar = [c for c in post.call_args_list if "sendPhoto" in c.args[0]]
        self.assertEqual(len(fotolar), 3)
        self.assertEqual(fotolar[0].kwargs["data"]["caption"], "<b>Başlık</b>")
        self.assertEqual(fotolar[1].kwargs["data"]["caption"], "")
        self.assertEqual(telegram_bot.son_medya_grubu_mesaj_idleri(), [41, 42, 43])

    def test_eksik_teslim_hata_gunlugune_yazilir(self):
        sayac = {"foto": 0}

        def sahte(url, **kw):
            if "sendMediaGroup" in url:
                raise requests.exceptions.ReadTimeout("zaman aşımı")
            sayac["foto"] += 1
            if sayac["foto"] == 2:
                return cevap(400, {"ok": False, "description": "Bad Request: wrong file"})
            return tamam_foto(50 + sayac["foto"])

        with patch("requests.post", side_effect=sahte):
            sonuc = telegram_bot.medya_grubu_gonder(self.slaytlar)
        self.assertEqual(len(sonuc), 2)
        kayitlar = db.son_hata_kayitlari(saat=1)
        self.assertTrue(any("eksik" in k["ham_hata"] and "2/3" in k["ham_hata"] for k in kayitlar), kayitlar)

    def test_hicbir_yol_tutmazsa_false_doner_hata_kaydi_yazar_ve_eski_idler_sizmaz(self):
        album_modulu._son_medya_grubu_mesaj_idleri = [901, 902]  # önceki içeriğin albümü
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError("ağ yok")):
            sonuc = telegram_bot.medya_grubu_gonder(self.slaytlar, caption="x", yedek_urller=self.urller)
        self.assertIs(sonuc, False)
        self.assertEqual(telegram_bot.son_medya_grubu_mesaj_idleri(), [], "eski içeriğin mesaj kimlikleri bu içeriğe karışmamalı")
        kayitlar = db.son_hata_kayitlari(saat=1)
        self.assertTrue(any(k["nerede"] == "telegram.medya" for k in kayitlar), kayitlar)

    def test_429_retry_after_kadar_beklenip_yeniden_denenir(self):
        cagrilar = [cevap(429, {"ok": False, "description": "Too Many Requests", "parameters": {"retry_after": 4}}),
                    tamam_grup(61, 62, 63)]
        with patch("requests.post", side_effect=cagrilar):
            sonuc = telegram_bot.medya_grubu_gonder(self.slaytlar)
        self.assertEqual(sonuc, [61, 62, 63])
        self.uyku_mock.assert_any_call(5)

    def test_baslik_html_hatasi_deneme_hakki_harcamadan_duz_metinle_tekrarlanir(self):
        cagrilar = [cevap(400, {"ok": False, "description": "Bad Request: can't parse entities: Unsupported start tag"}),
                    tamam_grup(71, 72, 73)]
        with patch("requests.post", side_effect=cagrilar) as post:
            sonuc = telegram_bot.medya_grubu_gonder(self.slaytlar, caption="<b>5 < 10</b>")
        self.assertEqual(sonuc, [71, 72, 73])
        ikinci = json.loads(post.call_args_list[1].kwargs["data"]["media"])
        self.assertNotIn("parse_mode", ikinci[0])
        self.assertNotIn("<b>", ikinci[0]["caption"])

    def test_tekil_slayt_yedek_urle_duser(self):
        cagrilar = [requests.exceptions.ReadTimeout("z"), requests.exceptions.ReadTimeout("z"),
                    tamam_foto(81)]
        with patch("requests.post", side_effect=cagrilar), patch("requests.get") as get:
            get.return_value = MagicMock(status_code=200, content=b"jpeg")
            sonuc = telegram_bot.medya_grubu_gonder(self.slaytlar[:1], caption="s", yedek_urller=self.urller[:1])
        self.assertEqual(sonuc, [81])

    # --- onay kartı ------------------------------------------------------------------------------------------

    def test_album_notu_gorsel_gelmediginde_baglantilari_verir(self):
        bos = telegram_bot._album_teslim_notu(False, 3, self.urller)
        self.assertIn("iletilemedi", bos)
        self.assertIn('href="https://i.ibb.co/x1/slayt_1.jpg"', bos)
        kismi = telegram_bot._album_teslim_notu([1, 2], 3, self.urller)
        self.assertIn("2/3", kismi)
        self.assertEqual(telegram_bot._album_teslim_notu([1, 2, 3], 3, self.urller), "")
        self.assertEqual(telegram_bot._album_teslim_notu(True, 3, self.urller), "")

    def test_onay_karti_ilk_deneme_olmazsa_kisa_kartla_dugmeleri_yine_gonderir(self):
        butonlar = {"inline_keyboard": [[{"text": "✅", "callback_data": "x"}]]}
        with patch("src.telegram.istemci.mesaj_gonder", side_effect=[None, {"message_id": 5}]) as mg:
            res = telegram_bot._onay_kartini_gonder(7, "uzun kart", butonlar, "Manşet", "haber")
        self.assertEqual(res, {"message_id": 5})
        self.assertEqual(mg.call_count, 2)
        self.assertIn("#7", mg.call_args_list[1].args[0])
        self.assertEqual(mg.call_args_list[1].kwargs["reply_markup"], butonlar)

    def test_onay_karti_hic_gitmezse_hata_gunlugune_yazilir(self):
        with patch("src.telegram.istemci.mesaj_gonder", return_value=None):
            res = telegram_bot._onay_kartini_gonder(8, "kart", {"inline_keyboard": []}, "M", "haber")
        self.assertIsNone(res)
        self.assertTrue(any(k["nerede"] == "telegram.onay_karti" for k in db.son_hata_kayitlari(saat=1)))

    def _haber_ekle(self, manset: str) -> int:
        detay = {"format_turu": "sozluk", "manset": manset, "yasal_dayanak": "4721 sayılı TMK md. 1 & 2"}
        with db._baglanti_al() as conn:
            cur = conn.execute(
                """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, eklenme_tarihi,
                                         onem_puani, kategori, manset, detay_metni, durum)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'yeni')""",
                ("EDM Sözlük", "T", "edm://t/1", "2026-10-12T00:00:00Z", 8, "TAPU_VE_HUKUK", manset, json.dumps(detay)),
            )
            conn.commit()
            return cur.lastrowid

    def test_haber_karti_albüm_gelmese_de_gider_notlu_ve_eski_idleri_kaydetmez(self):
        haber_id = self._haber_ekle("A & B <C>")
        album_modulu._son_medya_grubu_mesaj_idleri = [999]
        with patch("src.yeni_formatlar.slaytlari_uret", return_value=[Path(s) for s in self.slaytlar]), \
             patch("src.upload_image.coklu_gorsel_yukle", return_value=self.urller), \
             patch("src.telegram.akislar.kapi.yayin_kapisi", return_value=(True, [])), \
             patch("src.telegram.album.medya_grubu_gonder", return_value=False) as album, \
             patch("src.telegram.istemci.mesaj_gonder", return_value={"message_id": 123}) as mesaj:
            ok = telegram_bot._haber_onayina_sun(haber_id)
        self.assertTrue(ok)
        self.assertEqual(album.call_args.kwargs["yedek_urller"], self.urller)
        kart = mesaj.call_args.args[0]
        self.assertIn("Slayt görselleri Telegram'a iletilemedi", kart)
        self.assertIn("https://i.ibb.co/x1/slayt_1.jpg", kart)
        self.assertIn("A &amp; B &lt;C&gt;", kart, "manşet HTML'e kaçırılmalı")
        self.assertIn("reply_markup", mesaj.call_args.kwargs)
        self.assertEqual(db.onay_mesajlarini_getir("haber_album", str(haber_id)), [], "eski albümün kimlikleri kaydedilmemeli")
        self.assertEqual(db.onay_mesajlarini_getir("haber", str(haber_id)), [123])


if __name__ == "__main__":
    unittest.main()
