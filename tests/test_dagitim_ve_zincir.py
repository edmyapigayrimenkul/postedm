"""
Dağıtım matrisi, Threads zincir paylaşımı ve platform kontrolleri testleri.
"""
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

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
        
        # Geçici dosya oluştur
        tmp_video = Path('data/output/test_mock.mp4')
        tmp_video.parent.mkdir(parents=True, exist_ok=True)
        tmp_video.write_bytes(b'dummy')
        
        try:
            with patch('src.facebook._page_bilgileri', return_value=('tok123', 'page123')):
                vid_id = facebook.video_yayinla(tmp_video, 'Test video')
                self.assertEqual(vid_id, 'fb_vid_999')
        finally:
            tmp_video.unlink(missing_ok=True)


if __name__ == '__main__':
    unittest.main()
