"""
Okunabilirlik, kontrast ve motor yönlendirme testleri.
"""
import unittest
from pathlib import Path
import tempfile
import shutil

from src import yeni_formatlar, make_image


class TestOkunabilirlikVeYonlendirme(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_vaka_formati_kart_1_ve_kart_2_ayiklama(self):
        """B1 şemasından gelen kart_1 ve kart_2 verisinin vaka formatında doğru ayıklanıp kullanıldığını doğrular."""
        ornek_b1 = {
            'bicim': 'B1',
            'format_turu': 'vaka',
            'kategori_kodu': 'TAPU_VE_HUKUK',
            'manset_parca_1': 'Tapuda bedeli',
            'manset_vurgu': 'DÜŞÜK GÖSTERMEK',
            'manset_parca_2': 'mülkü kaybettirir',
            'spot': 'Tapuda harçtan kaçmak için bedeli düşük göstermek büyük risk taşır.',
            'slayt_2_detay': {
                'kart_1': {
                    'baslik': 'Maliye Eksik Harcı Faizle Alır',
                    'aciklama': 'Tapuda gerçek satış bedelini yazmazsanız vergi ziyaı cezası kesilir.'
                },
                'kart_2': {
                    'baslik': 'Ön Alım Davası Riski',
                    'aciklama': 'Hissedar tapudaki düşük fiyattan gayrimenkulü elinizden alabilir.'
                }
            },
            'slayt_3_cozum': {
                'maddeler': [
                    {'baslik': 'Gerçek Bedeli Beyan Edin', 'aciklama': 'Rayiç değil, ödenen reel tutarı yazın.'}
                ]
            }
        }
        
        slaytlar = yeni_formatlar.slaytlari_uret(ornek_b1, cikti_dizini=self.tmp_dir, cikti_onek='test_vaka')
        self.assertEqual(len(slaytlar), 2)
        for s in slaytlar:
            self.assertTrue(Path(s).exists())
            self.assertGreater(Path(s).stat().st_size, 10000)

    def test_vaka_slaytlari_kontrast_ve_cizim(self):
        """uret_vaka_slayt1 ve uret_vaka_slayt2 fonksiyonlarının hatasız çizildiğini doğrular."""
        p1 = self.tmp_dir / 'vaka1.jpg'
        p2 = self.tmp_dir / 'vaka2.jpg'
        
        yeni_formatlar.uret_vaka_slayt1(
            p1,
            vaka_kodu='01 / EMSAL DOSYA',
            yargitay_kaynak='Yargıtay 1. Hukuk Dairesi',
            manset='Tapuda Düşük Bedel Göstermek Mülkü Kaybettirir',
            olay_detay='Davacı hissedar, taşınmazın tapuda 500 bin TL olarak gösterildiğini öğrenmiş ve ön alım davası açmıştır.'
        )
        self.assertTrue(p1.exists())
        self.assertGreater(p1.stat().st_size, 10000)

        yeni_formatlar.uret_vaka_slayt2(
            p2,
            vaka_kodu='01 / EMSAL DOSYA',
            yargitay_hukmu='Tapudaki resmi satış bedeli esas alınarak taşınmazın davacıya devrine karar verilmiştir.',
            cikarilacak_ders='Tapu devirlerinde gerçek rayiç bedeli yazın, aksi halde mülkünüz tapudaki fiyattan kaybedilebilir.'
        )
        self.assertTrue(p2.exists())
        self.assertGreater(p2.stat().st_size, 10000)


if __name__ == '__main__':
    unittest.main()
