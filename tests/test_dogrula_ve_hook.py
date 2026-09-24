"""
tests/test_dogrula_ve_hook.py — Boş övgü, zayıf vurgu ve kanca (hook) kapıları testi.
"""

import unittest
from src import dogrula, hook_motoru


class TestDogrulaVeHook(unittest.TestCase):
    def test_bos_ovgu_ve_toren_dili(self):
        # Duygu atfı ve tören dili
        self.assertTrue(dogrula.bos_ovgu_mu("Tüm Türkiye'de büyük bir coşku ve gurur kaynağı oldu."))
        self.assertTrue(dogrula.bos_ovgu_mu("Tarihinin en büyük başarısı olarak kayda geçiyor."))
        self.assertTrue(dogrula.bos_ovgu_mu("Bölgenin parlayan yıldızı olarak yatırımcıların gözdesi haline geldi."))

        # Somut sayı içeren olgusal tanımlar elenmez
        self.assertFalse(dogrula.bos_ovgu_mu("Tarihinin en büyük ihalesi 450 milyon TL bedelle tamamlandı."))
        self.assertFalse(dogrula.bos_ovgu_mu("Silivri'de 35 parsel için imar planı askıya çıktı."))

        # ovguyu_ele fonksiyonu
        self.assertEqual(dogrula.ovguyu_ele("Büyük bir gurur kaynağı oldu."), "")
        self.assertEqual(dogrula.ovguyu_ele("Silivri 142 ada için askı süresi başladı."), "Silivri 142 ada için askı süresi başladı.")

    def test_vurgu_zayif_mi(self):
        # 1. Çıplak tek haneli sayı
        self.assertEqual(dogrula.vurgu_zayif_mi("3", "gün"), "çıplak tek haneli sayı")
        self.assertEqual(dogrula.vurgu_zayif_mi("8", "katlı bina"), "çıplak tek haneli sayı")

        # Güçlü iki/üç haneli veya oran/para
        self.assertIsNone(dogrula.vurgu_zayif_mi("30", "GÜN"))
        self.assertIsNone(dogrula.vurgu_zayif_mi("%25", "ORAN"))
        self.assertIsNone(dogrula.vurgu_zayif_mi("142", "ADA"))

        # 2. Etiket sayı ekiyle başlıyor
        self.assertEqual(dogrula.vurgu_zayif_mi("38", "yaşındaki mülk sahibi"), "etiket rakama yapışan ekle başlıyor")
        self.assertEqual(dogrula.vurgu_zayif_mi("15", "katlı bina inşaatı"), "etiket rakama yapışan ekle başlıyor")

        # 3. Etiket fiille bitiyor
        self.assertEqual(dogrula.vurgu_zayif_mi("15", "itiraz süresi bitti"), "etiket cümle parçası (fiille bitiyor)")
        self.assertEqual(dogrula.vurgu_zayif_mi("500", "bin TL ceza kesildi"), "etiket cümle parçası (fiille bitiyor)")

    def test_hook_olustur_bos_ovgu_ve_zayif_vurgu_eleme(self):
        haber = {
            "baslik": "Silivri Alibey Mahallesi Yeni İmar Planı",
            "spot": "3 günlük itiraz süresi başladı ve tarihin en büyük başarısı olarak kayda geçiyor.",
            "kategori": "İMAR",
            "detay_maddeleri": [
                {"etiket": "GURUR", "metin": "Tüm bölge halkı için büyük bir gurur ve sevinç kaynağı oldu."},
                {"etiket": "YASAL SÜREÇ", "metin": "Askı süresi boyunca Çevre ve Şehircilik Müdürlüğüne itiraz yapılabilir."}
            ]
        }
        hook = hook_motoru.hook_olustur(haber)
        # 3 günlük vurgu çıplak tek haneli sayı olduğu için stat_punch "3 GÜN" OLMAMALI!
        # İlk detay maddesi de boş övgü olduğu için elenip 2. detay maddesi kicker/t1/t2 olmalı.
        self.assertNotEqual(hook.get("num_txt"), "3")
        self.assertIn("YASAL SÜREÇ", hook.get("kicker", ""))


if __name__ == "__main__":
    unittest.main()
