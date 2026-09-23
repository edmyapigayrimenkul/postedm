"""
tests/test_metrik_toplayici.py — Sessiz Analitik Veri Toplayıcı Testleri
"""

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from scripts import metrik_topla
from src import db, instagram


class TestMetrikToplayici(unittest.TestCase):
    def test_db_metrik_kaydet_ve_getir(self):
        """Veritabanına metrik kaydedilmeli ve eksiksiz geri okunmalı."""
        haber_id = 99999
        m_id = db.metrik_kaydet(
            haber_id=haber_id,
            platform="instagram",
            medya_id="180123456789",
            reach=1420,
            impressions=1950,
            saved=48,
            shares=12,
            comments=6,
            likes=135,
            ham_veri={"test": "veri"},
        )
        self.assertIsNotNone(m_id)
        self.assertGreater(m_id, 0)

        kayitlar = db.haber_metrikleri_getir(haber_id)
        self.assertGreaterEqual(len(kayitlar), 1)
        k = kayitlar[0]
        self.assertEqual(k["haber_id"], haber_id)
        self.assertEqual(k["platform"], "instagram")
        self.assertEqual(k["reach"], 1420)
        self.assertEqual(k["saved"], 48)
        self.assertEqual(k["likes"], 135)
        self.assertEqual(k["shares"], 12)

    def test_yayinlanmis_ve_metrik_bekleyenler(self):
        """Sadece yayınlanmış ve 24-168 saatlik postlar aday olmalı."""
        import uuid
        uid = uuid.uuid4().hex[:8]
        simdi = datetime.now(timezone.utc)
        eski_zaman = (simdi - timedelta(hours=36)).isoformat()
        cok_eski_zaman = (simdi - timedelta(hours=200)).isoformat()
        cok_yeni_zaman = (simdi - timedelta(hours=2)).isoformat()

        post_36_id = f"post_36_{uid}"
        post_200_id = f"post_200_{uid}"
        post_2_id = f"post_2_{uid}"

        # Test verilerini hazırla
        with db._baglanti_al() as conn:
            conn.execute(
                """INSERT INTO haberler (kaynak, orijinal_baslik, orijinal_url, eklenme_tarihi,
                                         durum, yayin_zamani, instagram_post_id)
                   VALUES ('Test', '36 Saatlik Haber', ?, ?, 'yayinlandi', ?, ?),
                          ('Test', '200 Saatlik Haber', ?, ?, 'yayinlandi', ?, ?),
                          ('Test', '2 Saatlik Haber', ?, ?, 'yayinlandi', ?, ?)""",
                (
                    f"url://36_{uid}", eski_zaman, eski_zaman, post_36_id,
                    f"url://200_{uid}", cok_eski_zaman, cok_eski_zaman, post_200_id,
                    f"url://2_{uid}", cok_yeni_zaman, cok_yeni_zaman, post_2_id,
                )
            )
            conn.commit()

        bekleyenler = db.yayinlanmis_ve_metrik_bekleyenler(min_yas_saat=24.0, max_yas_saat=168.0)
        post_idler = [b["instagram_post_id"] for b in bekleyenler]

        self.assertIn(post_36_id, post_idler)
        self.assertNotIn(post_200_id, post_idler)
        self.assertNotIn(post_2_id, post_idler)

    @patch("src.instagram.requests.get")
    @patch("src.instagram._hesap_bilgileri", return_value=("17841400", "test_token"))
    def test_medya_metrikleri_al_basarili(self, mock_hesap, mock_get):
        """Graph API'den gelen yanıtların başarıyla parse edilmesi."""
        # 1. çağrı temel alanlar, 2. çağrı insights
        def side_effect(url, params=None, timeout=None):
            resp = MagicMock()
            resp.status_code = 200
            if "insights" in url:
                resp.json.return_value = {
                    "data": [
                        {"name": "reach", "values": [{"value": 2450}]},
                        {"name": "saved", "values": [{"value": 85}]},
                        {"name": "shares", "values": [{"value": 19}]},
                        {"name": "impressions", "values": [{"value": 3100}]},
                    ]
                }
            else:
                resp.json.return_value = {
                    "id": "180123",
                    "like_count": 142,
                    "comments_count": 18,
                    "media_type": "CAROUSEL_ALBUM",
                }
            return resp

        mock_get.side_effect = side_effect

        sonuc = instagram.medya_metrikleri_al("180123")
        self.assertIsNotNone(sonuc)
        self.assertEqual(sonuc["reach"], 2450)
        self.assertEqual(sonuc["saved"], 85)
        self.assertEqual(sonuc["shares"], 19)
        self.assertEqual(sonuc["likes"], 142)
        self.assertEqual(sonuc["comments"], 18)

    @patch("src.instagram.requests.get")
    @patch("src.instagram._hesap_bilgileri", return_value=("17841400", "test_token"))
    def test_medya_metrikleri_al_hata_durumunda_sessiz_fallback(self, mock_hesap, mock_get):
        """API hatasında çökmez; ölçülemeyen değer 0 DEĞİL None'dır ve neden taşınır.

        Eski sürüm hata anında 0 yazıyordu: izin eksikliği (#10) yüzünden her postun
        erişimi "0" kaydedildi ve ölçüm 12 gün boyunca fark edilmeden kör kaldı.
        """
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.text = "OAuthException: Invalid access token"
        mock_resp.json.return_value = {"error": {"code": 190, "message": "Invalid access token"}}
        mock_get.return_value = mock_resp

        sonuc = instagram.medya_metrikleri_al("180123")
        self.assertIsInstance(sonuc, dict)
        self.assertIsNone(sonuc["reach"])
        self.assertIsNone(sonuc["saved"])
        self.assertTrue(sonuc["insights_hata"])

    @patch("src.instagram.requests.get")
    @patch("src.instagram._hesap_bilgileri", return_value=("17841400", "test_token"))
    def test_insights_izni_yoksa_ayirt_edilir(self, mock_hesap, mock_get):
        izinsiz = MagicMock(status_code=400, text="(#10) Application does not have permission")
        izinsiz.json.return_value = {"error": {"code": 10, "message": "Application does not have permission"}}
        temel = MagicMock(status_code=200)
        temel.json.return_value = {"like_count": 3, "comments_count": 0, "media_type": "IMAGE"}
        mock_get.side_effect = [temel, izinsiz]
        sonuc = instagram.medya_metrikleri_al("180123")
        self.assertEqual(sonuc["likes"], 3)
        self.assertIsNone(sonuc["reach"])
        self.assertEqual(sonuc["insights_hata"], "izin_yok")


if __name__ == "__main__":
    unittest.main()
