"""
Okunabilirlik, kontrast ve motor yönlendirme testleri.
"""
import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

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
                    'baslik': 'Önalımda bedel rayiç değer',
                    'aciklama': 'Önalımda payın bedelini hâkim rayiç değer olarak belirler.'
                }
            },
            'slayt_3_cozum': {
                'maddeler': [
                    {'baslik': 'Gerçek Bedeli Beyan Edin', 'aciklama': 'Ödenen gerçek tutarı tapuya yazdırın.'}
                ]
            }
        }

        # Örnek olay: 2 olay slaytı + 1 adım + kapanış (2026-09-24'ten beri çok slaytlı)
        slaytlar = yeni_formatlar.slaytlari_uret(ornek_b1, cikti_dizini=self.tmp_dir, cikti_onek='test_vaka')
        self.assertEqual(len(slaytlar), 4)
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

    def test_nedir_dogrusu_ayiklama_ve_cizim(self):
        """B3 şemasından gelen verinin nedir_dogrusu formatında kart_1, kart_2 ve altin_kural olarak ayıklandığını doğrular."""
        ornek_b3 = {
            'bicim': 'B3',
            'format_turu': 'nedir_dogrusu',
            'kategori_kodu': 'Çatılı İşyeri Kiraları',
            'manset_parca_1': 'İşyeri kirasında',
            'manset_vurgu': 'SERBESTİ GEÇERLİ',
            'spot': 'Tacir kiracılarda kanuni konut koruması işlemez.',
            'slayt_2_detay': {
                'kart_1': {
                    'aciklama': 'Tacir veya şirket kiracıysanız konutlardaki depozito sınırı işlemez.'
                },
                'kart_2': {
                    'aciklama': 'Türk Borçlar Kanunu md. 339 uyarınca sözleşme serbestisi esastır.'
                }
            },
            'slayt_3_cozum': {
                'maddeler': [
                    {'baslik': 'Depozito ve iade şartı', 'aciklama': 'Tahliyede kesintisiz iade edileceğini yazdırın.'}
                ]
            }
        }
        # Kapak + 1 adım + kapanış
        slaytlar = yeni_formatlar.slaytlari_uret(ornek_b3, cikti_dizini=self.tmp_dir, cikti_onek='test_nd')
        self.assertEqual(len(slaytlar), 3)
        p = Path(slaytlar[0])
        self.assertTrue(p.exists())
        self.assertGreater(p.stat().st_size, 15000)

    def test_sozluk_ve_net_cevap_ayiklama(self):
        """Sozluk ve net_cevap formatlarında da eksik anahtar durumunda güvenli çıkarım yapıldığını test eder."""
        ornek_sozluk = {
            'bicim': 'B1',
            'format_turu': 'sozluk',
            'manset_vurgu': 'İFRAZ',
            'spot': 'Bir parselin birden çok parçaya bölünmesi işlemidir.',
            'slayt_3_cozum': {
                'maddeler': ['İmar planına uygunluk şarttır.']
            }
        }
        slaytlar_s = yeni_formatlar.slaytlari_uret(ornek_sozluk, cikti_dizini=self.tmp_dir, cikti_onek='test_sozluk')
        self.assertEqual(len(slaytlar_s), 1)
        self.assertTrue(Path(slaytlar_s[0]).exists())

        ornek_cevap = {
            'bicim': 'B3',
            'format_turu': 'net_cevap',
            'soru': 'Tarlaya tiny house koymak yasal mı',
            'manset_vurgu': 'RUHSATA TABİDİR',
            'manset_parca_2': 'yoksa mühürlenir',
            'spot': 'Sabit temelli yapılar ruhsata tabidir.',
        }
        # Kapak + kapanış (adım yok)
        slaytlar_c = yeni_formatlar.slaytlari_uret(ornek_cevap, cikti_dizini=self.tmp_dir, cikti_onek='test_cevap')
        self.assertEqual(len(slaytlar_c), 2)
        self.assertTrue(all(Path(s).exists() for s in slaytlar_c))

    def test_zorunlu_alan_yoksa_uydurma_yerine_durur(self):
        """Eksik alan koddaki genel cümleyle doldurulmaz (#157: sabit 'Yargıtay' hükmü yayına çıktı)."""
        for eksik in (
            {'format_turu': 'vaka', 'olay_detay': 'Bir olay.'},                 # hüküm yok
            {'format_turu': 'nedir_dogrusu', 'dogru_metin': 'Doğrusu şu.'},     # yanlış inanış yok
            {'format_turu': 'net_cevap', 'aciklama': 'Gerekçe.'},               # soru/cevap yok
            {'format_turu': 'sozluk', 'terim': 'İFRAZ'},                        # tanım yok
        ):
            with self.assertRaises(yeni_formatlar.EksikIcerik, msg=str(eksik)):
                yeni_formatlar.slaytlari_uret(eksik, cikti_dizini=self.tmp_dir, cikti_onek='test_eksik')


if __name__ == '__main__':
    unittest.main()

