import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import fetch_article as fa


class TestFetchArticleKokVeKuyruk(unittest.TestCase):
    def test_turkce_kok_ve_3_harfli_kelimeler(self):
        """Türkçe ekler ve 3 harfli kritik kelimeler alaka denetiminden geçmeli."""
        baslik = "Motorine zam geliyor: Tarih belli oldu"
        govde = (
            "Petrol piyasasındaki hareketlilik akaryakıt fiyatlarını da etkiledi. "
            "Motorinin litre fiyatına yarından itibaren 2,55 lira zam gelmesi bekleniyor. "
            "Zamla birlikte motorinin litre fiyatının İstanbul'da 93,45 liraya çıkması bekleniyor."
        )
        self.assertTrue(fa._baslikla_ilgili_mi(govde, baslik))

        # Emlak ve tapu odaklı test
        baslik_tapu = "Tapuya yeni harç: Arsa alımında vergi oranı değişti"
        govde_tapu = (
            "Hazine ve Maliye Bakanlığı gayrimenkul işlemlerinde yeni düzenlemeye gitti. "
            "Tapu işlemlerinde alınan harç oranları yeniden düzenlendi. "
            "Arsalar için tapuda yapılacak devirlerde harçların hesaplanması değişiyor."
        )
        self.assertTrue(fa._baslikla_ilgili_mi(govde_tapu, baslik_tapu))

        # Tamamen alakasız metin elenmeli
        alakasiz = "Milli voleybol takımı dünya şampiyonasında finale yükseldi. Maç pazar günü."
        self.assertFalse(fa._baslikla_ilgili_mi(alakasiz, baslik_tapu))

    def test_kuyrugu_kes(self):
        """Gövde sonundaki okur yorumları ve yasal uyarılar kırpılmalı."""
        gercek = "Silivri'de arsa ve tarla fiyatları son bir yılda yüzde 40 artış gösterdi. " * 8
        yorumlar = (
            "Sayfada yer alan bilgiler tavsiye niteliği taşımayıp yatırım danışmanlığı kapsamında değildir. "
            "Tüm yorumlar: Ahmet: 'Fiyatlar çok şişti almayın'. Mehmet: 'Yatırım tavsiyesi midir?'. "
        )
        metin = gercek + yorumlar
        kesilmis = fa.kuyrugu_kes(metin)
        self.assertIn("Silivri'de arsa ve tarla", kesilmis)
        self.assertNotIn("tavsiye niteliği taşımayıp", kesilmis)
        self.assertNotIn("Tüm yorumlar", kesilmis)


if __name__ == "__main__":
    unittest.main()
