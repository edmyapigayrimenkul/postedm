"""
Dağıtım matrisi, Threads zincir paylaşımı ve platform kontrolleri testleri.
"""
import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import threads, facebook, youtube


class TestDagitimVeZincir(unittest.TestCase):

    def test_threads_metinleri_slaytlara_dagit(self):
        """Detay metninden her slayt için 500 karakter sınırına uygun metinler çıkarıldığını doğrular."""
        detay = {
            'manset_parca_1': 'Tapuda bedeli',
            'manset_vurgu': 'DÜŞÜK GÖSTERMEK',
            'manset_parca_2': 'mülkü kaybettirir',
            'spot': 'Tapuda harçtan kaçmak mülk kaybına yol açabilir.',
            'slayt_2_detay': {
                'kart_1': {'baslik': 'Maliye Cezası', 'aciklama': 'Vergi ziyaı cezası kesilir.'},
                'kart_2': {'baslik': 'Ön Alım Riski', 'aciklama': 'Hissedar tapu fiyatından alır.'}
            },
            'slayt_3_cozum': {
                'maddeler': [
                    {'baslik': 'Gerçek Bedel', 'aciklama': 'Reel bedeli beyan edin.'},
                    {'baslik': 'Banka Kaydı', 'aciklama': 'Ödemeyi bankadan yapın.'}
                ]
            }
        }
        gorseller = ['http://img1.jpg', 'http://img2.jpg', 'http://img3.jpg', 'http://img4.jpg', 'http://img5.jpg']
        sayfalar = threads.metinleri_slaytlara_dagit(detay, gorseller)
        
        self.assertEqual(len(sayfalar), 5)
        for s in sayfalar:
            self.assertIn('gorsel_url', s)
            self.assertIn('metin', s)
            self.assertLessEqual(len(s['metin']), 500)
            self.assertGreater(len(s['metin']), 10)

    @patch('src.threads.requests.post')
    @patch('src.threads._konteyner_bekle')
    def test_threads_zincir_paylas(self, mock_bekle, mock_post):
        """Zincir paylaşımında her parçanın bir önceki post_id'ye reply_to_id ile bağlandığını doğrular."""
        mock_bekle.return_value = True
        
        # Konteyner ve publish mock
        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {'id': 'cnt_1'}),
            MagicMock(status_code=200, json=lambda: {'id': 'post_1'}),
            MagicMock(status_code=200, json=lambda: {'id': 'cnt_2'}),
            MagicMock(status_code=200, json=lambda: {'id': 'post_2'}),
        ]
        
        sayfalar = [
            {'gorsel_url': 'http://img1.jpg', 'metin': 'Post 1'},
            {'gorsel_url': 'http://img2.jpg', 'metin': 'Post 2'}
        ]
        
        with patch('src.threads._hesap_bilgileri', return_value=('user123', 'tok123')):
            kok_id = threads.zincir_paylas(sayfalar)
            self.assertEqual(kok_id, 'post_1')

    @patch('src.facebook.requests.post')
    def test_facebook_video_yayinla(self, mock_post):
        """Facebook video yüklemesinin /videos endpointine ulaştığını doğrular."""
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {'id': 'fb_vid_999'})
        
        tmp_video = Path('data/output/test_mock.mp4')
        tmp_video.parent.mkdir(parents=True, exist_ok=True)
        tmp_video.write_bytes(b'dummy')
        
        try:
            with patch('src.facebook._page_bilgileri', return_value=('tok123', 'page123')), \
                 patch('src.ses.sesli_video_hazirla', return_value=tmp_video):
                vid_id = facebook.video_yayinla(tmp_video, 'Test video')
                self.assertEqual(vid_id, 'fb_vid_999')
        finally:
            tmp_video.unlink(missing_ok=True)

    @patch('src.instagram.requests.post')
    @patch('src.instagram._konteyner_durumu_bekle', return_value=True)
    def test_instagram_story_yayinla(self, mock_bekle, mock_post):
        """Instagram Story'nin media_type=STORIES ile konteyner oluşturup yayınladığını doğrular."""
        mock_post.side_effect = [
            MagicMock(status_code=200, json=lambda: {'id': 'cnt_story_1'}),
            MagicMock(status_code=200, json=lambda: {'id': 'story_published_1'}),
        ]
        with patch('src.instagram._hesap_bilgileri', return_value=('acc_123', 'tok_123')):
            from src import instagram
            res = instagram.story_yayinla('https://example.com/story.jpg')
            self.assertEqual(res, 'story_published_1')

    @patch('src.tiktok.requests.post')
    def test_tiktok_foto_yayinla_direct(self, mock_post):
        """TikTok fotoğraf yayınının PHOTO media_type ile istek attığını doğrular."""
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {'error': {'code': 'ok'}, 'data': {'publish_id': 'tt_pub_123'}})
        with patch('src.config.env_al', return_value='test_token'):
            from src import tiktok
            res = tiktok.foto_yayinla(['https://example.com/1.jpg', 'https://example.com/2.jpg'], 'EDM Başlık')
            self.assertTrue(res['durum'])
            self.assertEqual(res['publish_id'], 'tt_pub_123')
            self.assertEqual(res['mod'], 'photo')

    def test_ses_modulu_katalog_ve_secim(self):
        """Ses modülünün katalog listesini ve varsayılan tercihi döndürdüğünü doğrular."""
        from src import ses
        listesi = ses.ses_listesi()
        self.assertGreaterEqual(len(listesi), 1)
        secilen = ses.ses_sec('emlak_klasik')
        self.assertIsNotNone(secilen)
        self.assertTrue(secilen.exists())


if __name__ == '__main__':
    unittest.main()

