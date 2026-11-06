#!/usr/bin/env python3
"""
scripts/otorite_stres_testi.py — Otorite İçerikleri Kapsamlı Stres ve Sabotaj Test Paketi

5 Temel Format × 20 İçerik = 100 İçerik
10 Hukuki & Gayrimenkul Alanı
10 Değerlendirme Ekseni:
  1. Mantık & Bütünlük (Logic & Coherence)
  2. Format Şeması & Bütçe (Schema & Budgets)
  3. Tasarım & Çizim (Visual Layout, Besleme 4:5 & Story 9:16)
  4. Hukuki Doğruluk (Legal Accuracy & Citations)
  5. Kanca Etkisi & Sakin Otorite (Hook & Tone)
  6. Seslendirme & Okunuş (TTS Pronunciation & Timing)
  7. Sabotaj & Uç Durumlar (Edge Cases & Resilience)
  8. Platform Metinleri (LinkedIn, Threads, TikTok, Instagram)
  9. Konu Çeşitliliği & Tekrar Engeli (Deduplication & Rotation)
  10. Telegram Arayüzü & Buton Sözleşmesi (Telegram UI & Callbacks)
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")

import json
import logging
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import (
    config,
    dogrula,
    generate_text,
    linkedin,
    make_image,
    okunus,
    threads,
    tiktok,
    yeni_formatlar,
)
from src.telegram.akislar import onay_karti

log = logging.getLogger("otorite_stres")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

CIKTI_DIZINI = config.yol_al("data/output/otorite_stres")
CIKTI_DIZINI.mkdir(parents=True, exist_ok=True)


# ==============================================================================
# 10 HUKUKİ VE GAYRİMENKUL ALANI (HER ALANDA 2 KONU = 20 FARKLI KONU)
# ==============================================================================

KONU_HAVUZU = [
    # Alan 1: Şufa & Hisseli Tapu
    {
        "id": "ALAN_01_A",
        "alan": "Şufa & Hisseli Tapu",
        "mevzuat": "Türk Medeni Kanunu md. 732, 733 ve 734",
        "terim": "ÖNALIM HAKKI",
        "tanim": "Hisseli taşınmazda bir paydaşın hissesini üçüncü kişiye satması durumunda, diğer paydaşların aynı koşullarla öncelikle satın alma yetkisidir.",
        "puf_maddeleri": ["Noter bildirimiyle 3 ay, her hâlde 1 yıl içinde dava açılmalıdır.", "Payın bedeli tapudaki harç bedeli değil mahkemenin belirleyeceği rayiç değerdir.", "Fiili taksim varsa önalım hakkı kullanılamaz."],
        "manset": "Hisseli Tapuda Şufa Tuzağı",
        "spot": "Hisseli arsa alırken noter bildirimi yapılmazsa diğer hissedarlar 1 yıl içinde tapunuzu iptal ettirebilir.",
        "yanlis": "Hisseli tapuda istediğim kişiye payımı kimseye sormadan dilediğim fiyata satabilirim.",
        "dogru": "Türk Medeni Kanunu md. 732 gereği diğer paydaşların yasal önalım hakkı vardır; noter bildirimi şarttır.",
        "altin_kural": "Satıştan önce tüm paydaşlardan noter onaylı feragatname temin edin.",
        "soru": "Hisseli arsamı diğer hissedarlardan habersiz satabilir miyim?",
        "net_cevap": "HAYIR.",
        "aciklama": "Satış geçerlidir ancak diğer ortaklar 1 yıl içinde önalım davası açarak tapuyu devralabilir.",
        "tavsiye": "Satış öncesi noter kanalıyla yazılı bildirim gönderin ve 3 aylık yasal süreyi işletin.",
        "vaka_kodu": "01 / ŞUFA DAVASI",
        "olay": "Yatırımcı hisseli bir tarlayı rayiç bedelinin yarısına satın aldı, noter bildirimi yaptırmadı.",
        "hukum": "Mahkeme diğer hissedarın talebini haklı bularak taşınmazın rayiç bedel üzerinden devrine hükmetti.",
        "ders": "Noter tebligatı yapılmadan hisseli taşınmaz alımı ağır mülkiyet riski doğurur.",
    },
    {
        "id": "ALAN_01_B",
        "alan": "Şufa & Hisseli Tapu",
        "mevzuat": "Türk Medeni Kanunu md. 698 ve 733",
        "terim": "FİİLİ TAKSİM",
        "tanim": "Hisseli taşınmazda paydaşların kullanım alanlarını kendi aralarında fiilen bölerek rızaen kullanmaları durumudur.",
        "puf_maddeleri": ["Fiili taksim olan yerde paydaşlar birbirine karşı şufa davası açamaz.", "Rızai taksimin harita veya krokiyle belgelenmesi ispat kolaylığı sağlar.", "Tapuda resmen ifraz yapılmadıkça bağımsız parsel hakkı vermez."],
        "manset": "Fiili Taksim Olan Yerde Şufa Davası",
        "spot": "Hissedarlar tarlayı aralarında fiilen bölüp kullanıyorsa sonradan önalım davası açamazlar.",
        "yanlis": "Fiili taksim olsa bile her hissedar istediği an diğerinin payına şufa davası açabilir.",
        "dogru": "Yargıtay içtihatlarına göre taşınmaz fiilen taksim edilmişse paydaşın önalım hakkı dürüstlük kuralına aykırıdır.",
        "altin_kural": "Alım öncesinde parselin fiilen bölünmüş sınırlarını kroki ve tutanakla imza altına alın.",
        "soru": "Fiilen bölünmüş hisseli arsada şufa davası açılabilir mi?",
        "net_cevap": "AÇILAMAZ.",
        "aciklama": "Taşınmaz kullanım alanlarına ayrılmış ve herkes kendi yerini kullanıyorsa hak düşer.",
        "tavsiye": "Kullanım sınırlarını gösteren muvafakatnameyi noter onaylı olarak saklayın.",
        "vaka_kodu": "02 / FİİLİ TAKSİM",
        "olay": "20 yıldır tarlasını tel çitle ayıran paydaş, komşu hisse satılınca şufa davası açtı.",
        "hukum": "Yargıtay fiili taksim sebebiyle dürüstlük kuralı uyarınca davayı kesin olarak reddetti.",
        "ders": "Yıllardır süregelen fiili kullanım sınırları dava hakkını ortadan kaldırır.",
    },

    # Alan 2: Kira Tahliye & İhtiyaç
    {
        "id": "ALAN_02_A",
        "alan": "Kira Tahliye & İhtiyaç",
        "mevzuat": "6098 sayılı Türk Borçlar Kanunu md. 350 ve 355",
        "terim": "İHTİYAÇTAN TAHLİYE",
        "tanim": "Kiraya verenin kendisi, eşi, altsoyu, üstsoyu veya bakmakla yükümlü olduğu kişilerin konut ya da işyeri gereksinimi nedeniyle sözleşmeyi feshetmesidir.",
        "puf_maddeleri": ["İhtiyacın gerçek, samimi ve zorunlu olması şarttır; geçici hevesler kabul edilmez.", "Tahliye sonrası taşınmaz haklı sebep olmaksızın 3 yıl süreyle başkasına kiralanamaz.", "Yasağa aykırılıkta eski kiracıya 1 yıllık kira bedelinden az olmamak üzere tazminat ödenir."],
        "manset": "Ev Sahibi İhtiyaç Nedeniyle Çıkarabilir mi?",
        "spot": "Ev sahibinin tahliye isteyebilmesi için ihtiyacın gerçek, samimi ve zorunlu olması şarttır.",
        "yanlis": "Ev sahibi 'Oğlum evlenecek' dediği an kiracı hemen evi boşaltmak zorundadır.",
        "dogru": "TBK md. 350 uyarınca dava açılması ve ihtiyacın mahkemede somut delillerle ispatı zorunludur.",
        "altin_kural": "Dava süresi kira dönemi sonundan itibaren 1 ay içinde açılmalıdır.",
        "soru": "Ev sahibi ihtiyaç sebebiyle beni hemen evden çıkarabilir mi?",
        "net_cevap": "HAYIR.",
        "aciklama": "Dönem sonu beklenmeli, ihtar çekilmeli ve mahkemede samimi ihtiyaç ispatlanmalıdır.",
        "tavsiye": "Sözlü tahliye taleplerine itibar etmeyin, resmî dava tebligatını bekleyin.",
        "vaka_kodu": "03 / İHTİYAÇ TAHLİYESİ",
        "olay": "Ev sahibi kızının oturacağını belirterek kiracıyı çıkardı, 4 ay sonra evi yüksek bedelle başkasına verdi.",
        "hukum": "Mahkeme TBK md. 355 uyarınca ev sahibini kiracıya 1 yıllık kira tutarında tazminata mahkum etti.",
        "ders": "TBK md. 355 gereği 3 yıllık yeniden kiralama süresi dolmadan ev başkasına kiraya verilemez.",
    },
    {
        "id": "ALAN_02_B",
        "alan": "Kira Tahliye & İhtiyaç",
        "mevzuat": "Türk Borçlar Kanunu md. 352",
        "terim": "TAHLİYE TAAHHÜDÜ",
        "tanim": "Kiracının kiralananı belirli bir tarihte boşaltacağını kiraya verene yazılı olarak beyan ettiği tek taraflı irade açıklamasıdır.",
        "puf_maddeleri": ["Kira sözleşmesiyle aynı gün imzalanan taahhütname Yargıtayca geçersiz sayılır.", "Taahhüt tarihinden itibaren 1 ay içinde icra takibi veya dava açılmalıdır.", "Tahliye tarihi açık ve tereddütsüz biçimde yazılmış olmalıdır."],
        "manset": "Tahliye Taahhüdünde İmza Tuzağı",
        "spot": "Kira sözleşmesi yapılırken imzalatılan tarihsiz tahliye taahhüdü baskı altında alındığı için risklidir.",
        "yanlis": "Kira kontratının altına konulan tahliye taahhüdü maddesi her zaman geçerlidir.",
        "dogru": "TBK md. 352 gereği taahhüdün kiralananın tesliminden sonraki serbest iradeyle verilmesi şarttır.",
        "altin_kural": "Taahhütnamenin düzenleme tarihini mutlaka kira sözleşmesinden en az 15 gün sonra atın.",
        "soru": "Sözleşmeyle aynı gün verilen tahliye taahhüdü geçerli midir?",
        "net_cevap": "GEÇERSİZDİR.",
        "aciklama": "Yargıtay yerleşik içtihatlarına göre kiralama anında verilen taahhüt serbest irade taşımaz.",
        "tavsiye": "Taahhütnameyi kiralanana fiilen yerleştikten sonraki tarihte düzenleyin.",
        "vaka_kodu": "04 / TAAHHÜT İPTALİ",
        "olay": "Ev sahibi kira sözleşmesiyle aynı gün imzalattığı boş taahhüdü 2 yıl sonra doldurup icraya koydu.",
        "hukum": "Bilirkişi incelemesiyle imza ve sözleşme tarihi tespiti yapılarak tahliye takibi iptal edildi.",
        "ders": "Aynı gün alınan tahliye taahhütleri yargı denetiminde kolaylıkla iptal edilmektedir.",
    },

    # Alan 3: Kira Artışı, Depozito & Yan Gider
    {
        "id": "ALAN_03_A",
        "alan": "Kira Artışı, Depozito & Yan Gider",
        "mevzuat": "Türk Borçlar Kanunu md. 344",
        "terim": "KİRA ARTIŞ TAVANI",
        "tanim": "Konut ve çatılı işyeri kiralarında yenilenen kira dönemlerinde uygulanabilecek azami yasal artış oranıdır.",
        "puf_maddeleri": ["Artış oranı bir önceki kira yılının tüketici fiyat endeksindeki 12 aylık ortalamayı geçemez.", "Sözleşmede daha yüksek oran kararlaştırılsa dahi yasal tavanı aşan kısım geçersizdir.", "5 yıl dolmadan rayiç bedel tespiti davası açılamaz."],
        "manset": "Kira Artışında Yasal Tavan",
        "spot": "Kira artışında yasal tavan 12 aylık TÜFE ortalamasıdır; ev sahibi keyfi zam talep edemez.",
        "yanlis": "Ev sahibi enflasyon yüksek diyerek dilediği oranda kira artışı dayatabilir.",
        "dogru": "TBK md. 344 emredicidir; 12 aylık TÜFE ortalamasının üzerindeki sözleşme şartları yok hükmündedir.",
        "altin_kural": "Artış gününde TÜİK tarafından açıklanan resmî 12 aylık TÜFE ortalamasını baz alın.",
        "soru": "Ev sahibi TÜFE üzerinde zam yapmazsam evi tahliye ettirebilir mi?",
        "net_cevap": "ETTİREMEZ.",
        "aciklama": "Yasal artışını TÜFE oranında yapan ve kirasını ödeyen kiracı bu gerekçeyle çıkarılamaz.",
        "tavsiye": "Kiranızı TÜFE artışıyla bankadan açıklama kısmına 'Kira Bedeli' yazarak yatırın.",
        "vaka_kodu": "05 / KİRA ARTIŞ UYUŞMAZLIĞI",
        "olay": "Ev sahibi yüzde 80 artış talep etti, kiracı yasal tavan olan yüzde 53 TÜFE artışını ödedi.",
        "hukum": "Ev sahibinin eksik ödeme iddiasıyla açtığı tahliye davası yasal tavana uyulduğu için reddedildi.",
        "ders": "Yasal TÜFE sınırında yapılan ödemeler kiracıyı tahliye riskine karşı tam korur.",
    },
    {
        "id": "ALAN_03_B",
        "alan": "Kira Artışı, Depozito & Yan Gider",
        "mevzuat": "Türk Borçlar Kanunu md. 342",
        "terim": "KİRA GÜVENCE BEDELİ",
        "tanim": "Kiracının kiralanana verebileceği zararlara karşı teminat olarak kiraya verene teslim ettiği depozito bedelidir.",
        "puf_maddeleri": ["Güvence bedeli 3 aylık kira tutarından fazla olamaz.", "Para vadeli tasarruf hesabına yatırılmalı, faiziyle birlikte korunmalıdır.", "Kiraya veren sözleşme bitiminde 3 ay içinde dava veya takip açmazsa banka parayı kiracıya iade eder."],
        "manset": "Depozitoda 3 Ay Kuralı",
        "spot": "Depozito ev sahibinin şahsi hesabına değil vadeli ortak banka hesabına yatırılmalıdır.",
        "yanlis": "Ev sahibi sözleşme bittiğinde canı isterse depozitoyu hiç geri vermeyebilir.",
        "dogru": "TBK md. 342 uyarınca depozito bankada vadeli hesapta tutulmalı ve hasar yoksa eksiksiz iade edilmelidir.",
        "altin_kural": "Evi teslim alırken ve boşaltırken detaylı fotoğraflı hasar teslim tutanağı düzenleyin.",
        "soru": "Ev sahibi depozitoyu gerekçesiz olarak alıkoyabilir mi?",
        "net_cevap": "ALIKOYAMAZ.",
        "aciklama": "Taşınmazda olağan kullanım dışı hasar yoksa depozito yasal faiziyle iade edilmelidir.",
        "tavsiye": "Tahliye anında anahtarı tutanakla teslim edip derhal yazılı iade talep edin.",
        "vaka_kodu": "06 / DEPOZİTO İADESİ",
        "olay": "Ev sahibi badana ve olağan eskimeyi bahane ederek 40 bin TL depozitoyu iade etmedi.",
        "hukum": "Mahkeme olağan yıpranmanın kiracıya yüklenemeyeceğine hükmederek depozitoyu faiziyle iade ettirdi.",
        "ders": "Olağan kullanım izleri depozito kesinti sebebi yapılamaz.",
    },

    # Alan 4: Arsa, İmar, Ruhsat & Tiny House
    {
        "id": "ALAN_04_A",
        "alan": "Arsa, İmar, Ruhsat & Tiny House",
        "mevzuat": "3194 sayılı İmar Kanunu md. 21 ve Plansız Alanlar Yönetmeliği",
        "terim": "YAPI RUHSATI",
        "tanim": "Belediye veya mücavir alan sınırlarında yapılacak her türlü yapının inşasına başlanabilmesi için yetkili idareden alınan resmî izin belgesidir.",
        "puf_maddeleri": ["Ruhsatsız başlanan yapılar kaçak sayılır ve derhal mühürlenir.", "İmar Kanunu 32 ve 42. maddeler uyarınca ağır para cezası ve yıkım kararı uygulanır.", "Ruhsat alındığı tarihten itibaren 2 yıl içinde inşaata başlanmalıdır."],
        "manset": "İmarsız Tarlaya Yapı Yapılır mı?",
        "spot": "İmarsız tarla veya bağ vasıflı yerlere belediyeden ruhsat almadan hiçbir kalıcı yapı yapılamaz.",
        "yanlis": "Kendi tapulu tarlama kimseye sormadan dilediğim büyüklükte prefabrik ev koyabilirim.",
        "dogru": "3194 sayılı İmar Kanunu md. 21 gereği ruhsatsız tüm yapılar kaçak işlemine tabidir.",
        "altin_kural": "Herhangi bir yapılaşma girişiminden önce ilgili belediyeden imar durum belgesi alın.",
        "soru": "Tapulu tarlama ruhsatsız prefabrik konut yapabilir miyim?",
        "net_cevap": "YAPAMAZSINIZ.",
        "aciklama": "Prefabrik yapılar da İmar Kanununa göre ruhsata tabidir; kaçak yapı yıkılır ve para cezası kesilir.",
        "tavsiye": "Parselin plansız alan şartlarına uyup uymadığını fen işlerinden teyit edin.",
        "vaka_kodu": "07 / KAÇAK YAPI YIKIMI",
        "olay": "Silivri'de tarlasına ruhsatsız çelik konstrüksiyon ev yapan parsel sahibine encümen kararıyla ceza kesildi.",
        "hukum": "İdare Mahkemesi yapının ruhsatsız inşa edildiğini tespit ederek yıkım kararını onadı.",
        "ders": "İmarsız arazilere ruhsat alınmadan yapılan yapılar kaçınılmaz olarak yıkım riski taşır.",
    },
    {
        "id": "ALAN_04_B",
        "alan": "Arsa, İmar, Ruhsat & Tiny House",
        "mevzuat": "Karayolları Trafik Kanunu ve 3194 sayılı İmar Kanunu",
        "terim": "TİNY HOUSE MEVZUATI",
        "tanim": "Tekerlekli ve plakalı römork niteliğindeki mobil evlerin arazi üzerindeki hukuki statüsü ve barınma sınırlarıdır.",
        "puf_maddeleri": ["Plaka ve ruhsat aracın trafiğe çıkışını sağlar, imarsız arazide yapılaşma hakkı vermez.", "Toprağa sabitlenen, elektrik/su şebekesine bağlanan mobil evler yapı vasfı kazanır.", "Belediyeler sabit kullanım tespit ettiğinde İmar Kanunu md. 32 kapsamında işlem yapar."],
        "manset": "Tarlaya Tiny House Koymak Yasal mı?",
        "spot": "Plakalı ve ruhsatlı da olsa toprağa sabitlenen veya şebeke bağlanan Tiny House kaçak yapı sayılır.",
        "yanlis": "Tiny House tekerlekli olduğu için Türkiye'deki her parsele süresiz olarak konulabilir.",
        "dogru": "Sabit bağlantı yapıldığı ve barınma amacıyla sürekli durduğu an İmar Kanunu kapsamına girer.",
        "altin_kural": "Tiny House koyacağınız arazide çevre düzeni planı ve belediye kısıtlarını kontrol edin.",
        "soru": "İmarsız tarlaya tekerlekli Tiny House koymak tamamen serbest midir?",
        "net_cevap": "DEĞİLDİR.",
        "aciklama": "Belediyeler kalıcı konaklama ve şebeke altyapısı kurulan mobil evleri mühürlemektedir.",
        "tavsiye": "Aracı zemine sabitlemeyin, foseptik ve beton tabla dökmeyin.",
        "vaka_kodu": "08 / TİNY HOUSE MÜHÜRLEME",
        "olay": "Arsasına plakalı Tiny House koyup etrafına beton zemin ve çit yapan vatandaşa tutanak tutuldu.",
        "hukum": "Belediye encümeni aracın yapı niteliği kazandığı gerekçesiyle kaldırılmasına karar verdi.",
        "ders": "Plaka güvencesi zemine beton ve altyapı döküldüğü an geçerliliğini yitirir.",
    },

    # Alan 5: Tarla, Kadastro, İfraz & Tevhid
    {
        "id": "ALAN_05_A",
        "alan": "Tarla, Kadastro, İfraz & Tevhid",
        "mevzuat": "5403 sayılı Toprak Koruma ve Arazi Kullanımı Kanunu md. 8",
        "terim": "ASGARİ TARIMSAL ARAZİ",
        "tanim": "Tarımsal arazilerin ekonomik ve verimli işletilmesini sağlamak amacıyla kanunla belirlenen bölünemez büyüklükteki asgari parsel sınırıdır.",
        "puf_maddeleri": ["Asgari büyüklüğün altındaki tarım arazileri ifraz edilemez ve bölünemez.", "Dikili tarım arazilerinde sınır 5 dekar, örtüaltında 3 dekar, tarlalarda 20 dekardır.", "Miras yoluyla dahi asgari büyüklük altındaki parçalara ayrılamaz."],
        "manset": "Tarlayı Böldürüp Satabilir miyim?",
        "spot": "5403 sayılı Kanun gereği tarlalar belirlenen dönüm sınırının altına ifraz edilemez.",
        "yanlis": "5 dönüm tarlamı ikiye bölüp 2.5 dönüm olarak iki ayrı tapu çıkartabilirim.",
        "dogru": "Tarımsal araziler 20 dönümden (mutlak tarım arazisinde 20 dekar) küçük parçalara bölünemez.",
        "altin_kural": "Tarla alırken İl Tarım Müdürlüğünün güncel ifraz kısıtlamalarını sorgulayın.",
        "soru": "5 dönümlük tarlamı resmen bölüp ayrı tapu alabilir miyim?",
        "net_cevap": "ALAMAZSINIZ.",
        "aciklama": "Toprak Koruma Kanunu tarım arazilerinin ufak parçalara bölünmesini kesinlikle yasaklamıştır.",
        "tavsiye": "Resmî ifraz yapılamıyorsa hisseli tapu alımlarında fiili riskleri değerlendirin.",
        "vaka_kodu": "09 / İFRAZ TALEBİ REDDİ",
        "olay": "Miras kalan 12 dönüm tarlayı kardeşler eşit olarak 4 parçaya bölmek için tapuya başvurdu.",
        "hukum": "Kadastro ve İl Tarım Müdürlüğü 5403 sayılı Kanun uyarınca ifraz işlemini reddetti.",
        "ders": "Tarım arazilerinde yasal büyüklük şartı sağlanmadan ifraz işlemi yapılamaz.",
    },
    {
        "id": "ALAN_05_B",
        "alan": "Tarla, Kadastro, İfraz & Tevhid",
        "mevzuat": "3402 sayılı Kadastro Kanunu md. 12",
        "terim": "KADASTRO TESCİLİ",
        "tanim": "Taşınmazların geometrik ve hukuki durumlarının tespit edilerek tapu kütüğüne tescil edilmesi işlemidir.",
        "puf_maddeleri": ["Kadastro tutanaklarının kesinleştiği tarihten itibaren 10 yıl geçtikten sonra dava açılamaz.", "10 yıllık süre hak düşürücü süredir; hakim tarafından resen dikkate alınır.", "Hata iddiası varsa bu 10 yıllık süre içinde kadastro mahkemesine başvurulmalıdır."],
        "manset": "Kadastro Tespitinde 10 Yıl Sınırı",
        "spot": "Kadastro kesinleştikten sonra 10 yıl geçerse sınır hatası veya hak iddiasıyla dava açılamaz.",
        "yanlis": "Kadastroda tarlam yanlış yazılmışsa 20 yıl sonra da olsa mahkemede hakkımı alırım.",
        "dogru": "3402 sayılı Kanun md. 12/3 gereği 10 yıllık hak düşürücü süre geçtikten sonra dava açılamaz.",
        "altin_kural": "Bölgenizde kadastro geçtiğinde askı ilanlarını ve kesinleşme tarihlerini takip edin.",
        "soru": "15 yıl önce kesinleşen kadastro tespitine karşı bugün dava açabilir miyim?",
        "net_cevap": "AÇAMAZSINIZ.",
        "aciklama": "10 yıllık hak düşürücü süre kamu düzenindendir ve süre geçince dava hakkı tamamen düşer.",
        "tavsiye": "Aplikasyon krokisi ile zilyetlik sınırlarınızı askı ilan süresinde kontrol edin.",
        "vaka_kodu": "10 / KADASTRO DAVA SÜRESİ",
        "olay": "Kadastro sırasında tarlasından yol geçen parsel sahibi 12 yıl sonra tapu iptal davası açtı.",
        "hukum": "Mahkeme 3402 sayılı Kanun md. 12 gereğince 10 yıllık sürenin dolması sebebiyle davayı reddetti.",
        "ders": "Kadastro tespitlerine karşı yasal itiraz ve dava süreleri asla geciktirilmemelidir.",
    },

    # Alan 6: Tapu Harcı, Düşük Bedel & Beyan
    {
        "id": "ALAN_06_A",
        "alan": "Tapu Harcı, Düşük Bedel & Beyan",
        "mevzuat": "492 sayılı Harçlar Kanunu md. 63 ve Vergi Usul Kanunu md. 344",
        "terim": "TAPU HARCI BEYANI",
        "tanim": "Gayrimenkul alım satımında tapu dairesine bildirilen ve harç hesaplamasına esas olan devir bedelidir.",
        "puf_maddeleri": ["Harç oranı alıcı ve satıcı için ayrı ayrı binde 20 (toplam yüzde 4) olarak tahsil edilir.", "Beyan edilen bedel belediyenin belirlediği emlak vergisi değerinden düşük olamaz.", "Eksik beyanda aradaki fark vergi ziyaı cezası ve gecikme faiziyle tahsil edilir."],
        "manset": "Tapuda Bedeli Düşük Göstermenin Cezası",
        "spot": "Harçtan kaçmak için tapuda düşük bedel gösterenler vergi ziyaı cezası ve faizle karşılaşır.",
        "yanlis": "Tapuda evin bedelini belediye rayicinden gösterirsek hiçbir şekilde ceza gelmez.",
        "dogru": "Gerçek satış bedeli beyan edilmelidir; banka transferleri incelenerek fark 5 yıl geriye dönük istenir.",
        "altin_kural": "Tapudaki beyan tutarı ile bankadan gönderilen para transferi tutarını birebir eşitleyin.",
        "soru": "Tapuda bedeli rayiçten gösterip kalanı elden nakit ödemek yasal mıdır?",
        "net_cevap": "YASAL DEĞİLDİR.",
        "aciklama": "Vergi müfettişleri para hareketlerini inceleyerek eksik harcı 1 kat vergi ziyaı cezasıyla talep eder.",
        "tavsiye": "Pişmanlık dilekçesi vererek aradaki harç farkını cezasız olarak beyan edebilirsiniz.",
        "vaka_kodu": "11 / TAPU HARCI CEZASI",
        "olay": "4 milyon TL'ye satılan daire tapuda 1.5 milyon TL gösterildi; alıcı bankadan 4 milyon transfer etti.",
        "hukum": "Maliye para transferini tespit ederek eksik harcı 1 kat ceza ve gecikme zammıyla tahsil etti.",
        "ders": "Banka hareketleri ile tapu beyanı arasındaki uyumsuzluk doğrudan vergi incelemesi doğurur.",
    },
    {
        "id": "ALAN_06_B",
        "alan": "Tapu Harcı, Düşük Bedel & Beyan",
        "mevzuat": "193 sayılı Gelir Vergisi Kanunu Mükerrer md. 80",
        "terim": "DEĞER ARTIŞ KAZANCI",
        "tanim": "Gayrimenkulün iktisap tarihinden itibaren 5 yıl içinde elden çıkarılmasından doğan kazancın vergilendirilmesidir.",
        "puf_maddeleri": ["Satın alındığı tarihten itibaren 5 yıl geçtikten sonra satılan konutlarda vergi doğmaz.", "Miras veya bağış yoluyla intikal eden gayrimenkullerde 5 yıl kuralı ve vergi uygulanmaz.", "Maliyet bedeli Türkiye İstatistik Kurumunun ÜFE endeksi oranında güncellenir."],
        "manset": "5 Yıl Dolmadan Evini Satan Vergi Öder",
        "spot": "Satın aldığı gayrimenkulü 5 yıl dolmadan satanlar değer artış kazancı vergisi ödemekle yükümlüdür.",
        "yanlis": "Kendi adıma olan tapulu evimi ne zaman satarsam satayım hiçbir vergi ödemem.",
        "dogru": "5 yıl dolmadan yapılan satışlarda enflasyondan arındırılmış net kazanç gelir vergisine tabidir.",
        "altin_kural": "5 yıllık süreyi gün hesabı yaparak tapu tescil tarihi üzerinden hesaplayın.",
        "soru": "3 yıl önce aldığım dairemi satarsam gelir vergisi öder miyim?",
        "net_cevap": "ÖDERSİNİZ.",
        "aciklama": "Alış ve satış arasındaki istisnayı aşan kâr tutarı değer artış kazancı olarak vergilendirilir.",
        "tavsiye": "Satış için imkanınız varsa 5 yıllık yasal muafiyet süresinin dolmasını bekleyin.",
        "vaka_kodu": "12 / DEĞER ARTIŞ VERGİSİ",
        "olay": "2 yıl önce 1 milyon TL'ye aldığı arsayı 3.5 milyon TL'ye satan yatırımcı beyanname vermedi.",
        "hukum": "Vergi dairesi kazancı tespit ederek gelir vergisi tarhiyatı ve usulsüzlük cezası kesti.",
        "ders": "5 yıllık elde tutma süresi dolmadan yapılan satışlar mutlaka vergi beyanına konu edilmelidir.",
    },

    # Alan 7: Kaparo, Bağlanma Parası & Satış Vaadi
    {
        "id": "ALAN_07_A",
        "alan": "Kaparo, Bağlanma Parası & Satış Vaadi",
        "mevzuat": "Türk Borçlar Kanunu md. 177 ve 178",
        "terim": "BAĞLANMA PARASI",
        "tanim": "Sözleşmenin kurulduğu sırada taraflardan birinin diğerine sözleşmenin yapıldığını kanıtlamak amacıyla verdiği paradır.",
        "puf_maddeleri": ["Aksine sözleşme yoksa bağlanma parası esas satış bedelinden düşülür.", "Vazgeçen tarafın parayı yakması kuralı bağlanma parası için değil cayma parası için geçerlidir.", "Cayma parası kararlaştırılmamışsa haksız vazgeçen taraf karşı tarafın zararını tazmin eder."],
        "manset": "Verilen Kaparo Her Zaman Yanar mı?",
        "spot": "Hukuken kaparo bağlanma parasıdır; cayma parası kararlaştırılmadıkça vazgeçenin parası otomatikman yanmaz.",
        "yanlis": "Emlakçıya veya satıcıya kaparo verip almaktan vazgeçersem param anında yok olur.",
        "dogru": "TBK md. 177 uyarınca bağlanma parası esastan düşülür; cayma parası ise açık yazılı şart gerektirir.",
        "altin_kural": "Ödeme yaparken banka dekontuna 'Bağlanma Parası' veya 'Cayma Parası' ayrımını net yazın.",
        "soru": "Ev almaktan vazgeçtiğimde verdiğim kaparoyu geri alabilir miyim?",
        "net_cevap": "DURUMA GÖRE.",
        "aciklama": "Sözleşmede 'vazgeçen kaparoyu yakar' şeklinde açık cayma şartı yoksa iade talep edilebilir.",
        "tavsiye": "Kaparo protokolü imzalarken vazgeçme şartlarını ve cezai şartı açıkça belirleyin.",
        "vaka_kodu": "13 / KAPARO İADESİ",
        "olay": "Kredi çıkmadığı için arsa alımından vazgeçen alıcının 50 bin TL kaparosunu satıcı iade etmedi.",
        "hukum": "Tüketici Mahkemesi açık cayma parası kararlaştırılmadığı için kaparonun iadesine karar verdi.",
        "ders": "Kaparo protokolünde vazgeçme halleri ve mücbir sebepler net yazılmalıdır.",
    },
    {
        "id": "ALAN_07_B",
        "alan": "Kaparo, Bağlanma Parası & Satış Vaadi",
        "mevzuat": "Türk Borçlar Kanunu md. 237 ve Tapu Kanunu md. 26",
        "terim": "GAYRİMENKUL SATIŞ VAADİ",
        "tanim": "İleride taşınmaz mülkiyetinin devredilmesini taahhüt eden ve noterde resen düzenlenmesi zorunlu olan ön sözleşmedir.",
        "puf_maddeleri": ["Adi yazılı şekilde veya emlakçı sözleşmesiyle yapılan satış vaadi hukuken geçersizdir.", "Satış vaadi tapu kütüğüne şerh edildiğinde üçüncü kişilere karşı 5 yıl ileri sürülebilir.", "5 yıl içinde satış yapılmazsa veya dava açılmazsa şerh re'sen terkin edilebilir."],
        "manset": "Emlakçıda İmzalanan Satış Vaadi Geçerli mi?",
        "spot": "Taşınmaz satış vaadi sözleşmesi yalnızca noterde düzenleme şeklinde yapılırsa hukuken geçerlidir.",
        "yanlis": "Emlak ofisinde adi kağıda imzaladığımız gayrimenkul satış vaadi tapuyu garanti eder.",
        "dogru": "TBK md. 237 gereği resmi şekle (notere) uyulmayan taşınmaz satış vaatleri kesin olarak geçersizdir.",
        "altin_kural": "Satış vaadi sözleşmesini mutlaka noterde yapın ve derhal tapu kütüğüne şerh ettirin.",
        "soru": "Emlakçı protokolüne dayanarak tapu tescil davası açabilir miyim?",
        "net_cevap": "AÇAMAZSINIZ.",
        "aciklama": "Noterde yapılmayan satış vaadi sözleşmeleri mahkemeler tarafından geçersiz sayılarak reddedilir.",
        "tavsiye": "Yalnızca verdiğiniz paranın sebepsiz zenginleşme hükümlerine göre iadesini isteyebilirsiniz.",
        "vaka_kodu": "14 / SATIŞ VAADİ GEÇERSİZLİĞİ",
        "olay": "Adi sözleşmeyle arsa bedelini ödeyen alıcı, satıcı tapuyu vermeyince tescil davası açtı.",
        "hukum": "Yargıtay şekil şartına uyulmadığı için sözleşmeyi geçersiz saydı, sadece ödenen paranın iadesine hükmetti.",
        "ders": "Gayrimenkul devir taahhütleri yalnızca noterde ve resmî senetle yapıldığında hak doğurur.",
    },

    # Alan 8: Kat Mülkiyeti, Ortak Alan & Aidat
    {
        "id": "ALAN_08_A",
        "alan": "Kat Mülkiyeti, Ortak Alan & Aidat",
        "mevzuat": "634 sayılı Kat Mülkiyeti Kanunu md. 19",
        "terim": "ORTAK ALAN İHLALİ",
        "tanim": "Apartman ve sitelerde bağımsız bölümler dışında kalan sığınak, çatı, bahçe gibi alanların onay alınmadan kullanılmasıdır.",
        "puf_maddeleri": ["Ortak alanlarda inşaat veya değişiklik için kat maliklerinin beşte dördünün yazılı rızası gerekir.", "Çatı veya ortak bahçeyi tek başına kapatıp şahsi kullanımına tahsis etmek yasaktır.", "Her kat maliki hakimin müdahalesini isteyerek eski hale getirme davası açabilir."],
        "manset": "Apartman Bahçesini Kapatıp Kendinize Alamazsınız",
        "spot": "Ortak bahçe, sığınak veya teras kat maliklerinin 4/5 yazılı rızası olmadan şahsi kullanıma kapatılamaz.",
        "yanlis": "Zemin kattaki dairemin önündeki bahçe bana aittir, istediğim gibi çitle çeviririm.",
        "dogru": "KMK md. 19 uyarınca bahçe tüm maliklerin ortak yeridir; izinsiz müdahaleler eski hale getirtilir.",
        "altin_kural": "Ortak alanda herhangi bir tadilat yapmadan önce kat malikleri kurulu kararı alın.",
        "soru": "Zemin kattaki dairemin bahçesini çitle çevirip kapatabilir miyim?",
        "net_cevap": "KAPATAMAZSINIZ.",
        "aciklama": "Kat maliklerinin 4/5 yazılı rızası yoksa diğer komşular dava açıp çiti kaldırtabilir.",
        "tavsiye": "Yönetim planında lehinize tahsis edilmiş bir eklenti maddesi olup olmadığını inceleyin.",
        "vaka_kodu": "15 / BAHÇE İŞGALİ",
        "olay": "Zemin kat maliki ortak bahçeye kış bahçesi yaptı, üst kat komşusu eski hale getirme davası açtı.",
        "hukum": "Sulh Hukuk Mahkemesi 4/5 rıza bulunmadığından kış bahçesinin yıkılarak eski hale getirilmesine hükmetti.",
        "ders": "Ortak alanlara yapılan izinsiz eklentiler her malikin tek bir davasıyla yıktırılabilir.",
    },
    {
        "id": "ALAN_08_B",
        "alan": "Kat Mülkiyeti, Ortak Alan & Aidat",
        "mevzuat": "Kat Mülkiyeti Kanunu md. 20",
        "terim": "AİDAT VE GECİKME TAZMİNATI",
        "tanim": "Kat maliklerinin ana gayrimenkulün ortak giderlerine payları oranında katılma yükümlülüğü ve temerrüt yaptırımıdır.",
        "puf_maddeleri": ["Gider ve avans payını ödemeyen malike aylık yüzde 5 gecikme tazminatı uygulanır.", "Yönetici veya diğer kat malikleri borçluya karşı icra takibi başlatabilir.", "Borç ödenmezse bağımsız bölüm üzerine kanuni ipotek hakkı tescil ettirilebilir."],
        "manset": "Site Aidatını Ödemeyene Aylık Yüzde 5 Ceza",
        "spot": "Ortak gider ve aidat borcunu zamanında ödemeyen kat maliklerine kanunen aylık yüzde 5 tazminat işler.",
        "yanlis": "Hizmetten memnun değilsem aidat ödemeyi kesebilirim, bana hiçbir şey yapamazlar.",
        "dogru": "KMK md. 20 emredicidir; hizmet kalitesi bahane edilerek aidat ödemekten kaçınılamaz.",
        "altin_kural": "Hizmet kusuru varsa aidatı kesmek yerine denetim kuruluna ve sulh hukuk mahkemesine başvurun.",
        "soru": "Asansör çalışmıyor diye site aidatını ödememe hakkım var mı?",
        "net_cevap": "YOKTUR.",
        "aciklama": "Kat maliki ortak yerleri kullanmadığını iddia ederek aidat yükümlülüğünden kurtulamaz.",
        "tavsiye": "Aidatı geciktirmeden ödeyip aksaklıklar için yönetime yazılı ihtarname çekin.",
        "vaka_kodu": "16 / AİDAT İCRA TAKİBİ",
        "olay": "Havuzu kullanmadığını belirterek 1 yıl boyunca aidat ödemeyen daire sahibine icra takibi yapıldı.",
        "hukum": "İtirazın iptali davasında mahkeme borcun aylık yüzde 5 gecikme tazminatıyla tahsiline karar verdi.",
        "ders": "Ortak alanlardan yararlanmama iddiası yasal aidat borcunu ortadan kaldırmaz.",
    },

    # Alan 9: Gayrimenkul Finansı, İpotek & Ekspertiz
    {
        "id": "ALAN_09_A",
        "alan": "Gayrimenkul Finansı, İpotek & Ekspertiz",
        "mevzuat": "6502 sayılı Tüketicinin Korunması Kanunu md. 24",
        "terim": "KREDİ CAYMA HAKKI",
        "tanim": "Tüketicinin konut finansmanı veya tüketici kredisi sözleşmesinden herhangi bir gerekçe göstermeksizin vazgeçme yetkisidir.",
        "puf_maddeleri": ["Cayma hakkı sözleşmenin kurulduğu tarihten itibaren 14 gün içinde kullanılabilir.", "Tüketici hiçbir cezai şart ödemekle yükümlü tutulamaz.", "Kredi tutarı çekilmişse anapara ve geçen günün faizi 30 gün içinde iade edilmelidir."],
        "manset": "Konut Kredisinde 14 Günlük Cayma Hakkı",
        "spot": "Kredi sözleşmesi imzalayan tüketici 14 gün içinde ceza ödemeden krediden cayabilir.",
        "yanlis": "Konut kredisi onaylanıp sözleşme imzalandıktan sonra bankadan asla vazgeçilemez.",
        "dogru": "6502 sayılı Kanun md. 24 uyarınca 14 gün içinde yazılı bildirimle cezasız cayma hakkı vardır.",
        "altin_kural": "Cayma bildirimini mutlaka noter veya iadeli taahhütlü mektupla 14 gün dolmadan iletin.",
        "soru": "İmzaladığım konut kredisinden ceza ödemeden vazgeçebilir miyim?",
        "net_cevap": "VAZGEÇEBİLİRSİNİZ.",
        "aciklama": "14 günlük yasal cayma süresi içinde bankaya yazılı bildirim yaparak sözleşmeyi feshedebilirsiniz.",
        "tavsiye": "Ekspertiz ücreti gibi resmi üçüncü şahıs masrafları hariç banka ceza kesemez.",
        "vaka_kodu": "17 / KREDİ CAYMA TAZMİNATI",
        "olay": "Konut kredisinden 5. günde cayan tüketiciden banka yüzde 2 erken kapama cezası kesti.",
        "hukum": "Tüketici Hakem Heyeti 14 gün içinde cezai şart alınamayacağına hükmederek parayı iade ettirdi.",
        "ders": "Yasal 14 günlük sürede kullanılan kredi cayma hakkı hiçbir cezai şarta tabi tutulamaz.",
    },
    {
        "id": "ALAN_09_B",
        "alan": "Gayrimenkul Finansı, İpotek & Ekspertiz",
        "mevzuat": "Türk Medeni Kanunu md. 883",
        "terim": "İPOTEK TERKİNİ",
        "tanim": "Borcun tamamen ödenip sona ermesiyle birlikte tapu kütüğündeki ipotek kaydının silinmesi işlemidir.",
        "puf_maddeleri": ["Kredi borcu bitince ipotek tapudan kendiliğinden otomatik olarak düşmez.", "Alacaklı bankanın tapuya elektronik veya yazılı fek yazısı göndermesi zorunludur.", "Alacaklı terkinden kaçınırsa malik mahkemeden ipoteğin terkinini talep edebilir."],
        "manset": "Kredisi Biten Evin İpoteği Kendiliğinden Düşmez",
        "spot": "Konut kredisini son kuruşuna kadar ödeseniz dahi tapudaki ipotek fek yazısı verilmeden silinmez.",
        "yanlis": "Banka borcu bittiği gün tapudaki ipotek kaydı sistemden otomatikman silinir.",
        "dogru": "TMK md. 883 gereği bankanın tapu müdürlüğüne fek yazısı yollaması ve harcın ödenmesi gerekir.",
        "altin_kural": "Kredi bittiğinde bankadan ipotek fek yazısını talep edin ve WebTapu'dan terkinini doğrulayın.",
        "soru": "Kredi borcum bitti, evimin tapusundaki ipotek otomatik kalkar mı?",
        "net_cevap": "KALKMAZ.",
        "aciklama": "Banka tapu dairesine fek bildirimi yapmalıdır; aksi halde tapu kaydında rehin görünmeye devam eder.",
        "tavsiye": "WebTapu sisteminden kütük örneği alarak şerhler ve rehin hanesini bizzat kontrol edin.",
        "vaka_kodu": "18 / İPOTEK FEK GECİKMESİ",
        "olay": "Borcu biten dairesini satmak isteyen malik, tapuda banka ipoteği durduğu için satışı yapamadı.",
        "hukum": "Banka fek yazısını geciktirdiği için oluşan alıcı kaybı zararını tazmin etmek zorunda kaldı.",
        "ders": "Gayrimenkul satışından önce ipotek fek işlemlerinin tamamlandığı tapudan teyit edilmelidir.",
    },

    # Alan 10: Miras Taksimi & Ortaklığın Giderilmesi
    {
        "id": "ALAN_10_A",
        "alan": "Miras Taksimi & Ortaklığın Giderilmesi",
        "mevzuat": "Türk Medeni Kanunu md. 640 ve 676",
        "terim": "MİRAS TAKSİM SÖZLEŞMESİ",
        "tanim": "Mirasçıların terekeye dahil taşınmazları kendi aralarında nasıl paylaşacaklarını karara bağladıkları yazılı sözleşmedir.",
        "puf_maddeleri": ["Geçerli olması için tüm mirasçıların katılımı ve yazılı şekil zorunludur.", "Mirasçılardan biri dahi imza atmazsa taksim sözleşmesi hukuken hükümsüzdür.", "Taşınmaz devri için sözleşmenin noterde düzenlenmesi veya tapuda tescili gerekir."],
        "manset": "Miras Kalan Yerde Tek Kişinin İmzası Eksikse",
        "spot": "Miras kalan gayrimenkulün paylaşımında tüm mirasçıların oybirliği şarttır; tek imza eksikse işlem iptal olur.",
        "yanlis": "Kardeşlerin çoğunluğu anlaştıysa diğer kardeşe sormadan tarlayı paylaşabiliriz.",
        "dogru": "TMK md. 640 gereği tereke üzerinde elbirliği mülkiyeti vardır; tasarruf için oybirliği zorunludur.",
        "altin_kural": "Miras paylaşımı yaparken tüm mirasçıların eksiksiz yer aldığı taksim sözleşmesi düzenleyin.",
        "soru": "5 mirasçıdan 4'ü anlaştıysa miras kalan tarla satılabilir mi?",
        "net_cevap": "SATILAMAZ.",
        "aciklama": "Elbirliği mülkiyetinde tek bir mirasçının dahi rızası yoksa taşınmazın devri mümkün değildir.",
        "tavsiye": "Anlaşma sağlanamıyorsa ortaklığın giderilmesi (izale-i şuyu) davası yoluna başvurun.",
        "vaka_kodu": "19 / MİRAS TAKSİM İPTALİ",
        "olay": "3 kardeş yurt dışındaki diğer kardeşin imzasını almadan mirası paylaşıp tapuda işlem yaptı.",
        "hukum": "Mahkeme oybirliği bulunmadığından yapılan taksimi geçersiz sayarak tapuyu eski haline getirdi.",
        "ders": "Miras taksiminde tek bir mirasçının dışlandığı sözleşmeler kesin hükümsüzdür.",
    },
    {
        "id": "ALAN_10_B",
        "alan": "Miras Taksimi & Ortaklığın Giderilmesi",
        "mevzuat": "Türk Medeni Kanunu md. 698 ve 699",
        "terim": "İZALE-İ ŞUYU",
        "tanim": "Paylı veya elbirliği mülkiyetindeki taşınmazda ortaklığın aynen taksim veya mahkemece satış yoluyla sona erdirilmesidir.",
        "puf_maddeleri": ["Her paydaş veya mirasçı diğer ortaklara karşı bu davayı açma hakkına sahiptir.", "Taşınmaz fiziken ve hukuken bölünemiyorsa açık artırma usulüyle icra yoluyla satılır.", "Satışın sadece paydaşlar arasında yapılması için tüm paydaşların oybirliğiyle rızası şarttır."],
        "manset": "Ortaklığın Giderilmesi Davasında İhale Riski",
        "spot": "İzale-i şuyu davasında taşınmaz bölünemiyorsa açık artırmayla herkese açık ihalede satılır.",
        "yanlis": "Mahkemeye gidersek hakim tarlayı sadece kardeşlerin arasında paylaştırıp satar.",
        "dogru": "Tüm paydaşlar kabul etmezse satış herkese açık genel ihale usulüyle yapılır ve yabancı alabilir.",
        "altin_kural": "Açık artırmada değer kaybı yaşamamak için dava öncesi sulh ve uzlaşma yollarını tüketin.",
        "soru": "Açılan izale-i şuyu davasında tarlayı yabancı birinin alma riski var mı?",
        "net_cevap": "VARDIR.",
        "aciklama": "Ortaklar satışın kendi aralarında yapılmasını oybirliğiyle onaylamazsa ihale halka açık yapılır.",
        "tavsiye": "Açık artırma şartnamesini inceleyip satış gününde pey sürmek üzere hazırlık yapın.",
        "vaka_kodu": "20 / İZALE-İ ŞUYU SATIŞI",
        "olay": "Anlaşamayan mirasçıların davasında kıymetli sahil arsası genel açık artırmayla satışa çıktı.",
        "hukum": "Mirasçılar oybirliği sağlayamadığı için taşınmaz en yüksek teklifi veren üçüncü şahsa ihale edildi.",
        "ders": "İzale-i şuyu davası aile mülkünün mahkeme kanalıyla üçüncü kişilere satışıyla sonuçlanabilir.",
    },
]


def _manset_bol_18(manset: str) -> Tuple[str, str, str]:
    """Manşeti 18 karakter satır bütçesine uyacak 3 parçaya böler."""
    kelimeler = manset.split()
    parcalar: List[str] = ["", "", ""]
    idx = 0
    for k in kelimeler:
        aday = f"{parcalar[idx]} {k}".strip() if parcalar[idx] else k
        if len(aday) <= 18 or idx == 2:
            parcalar[idx] = aday[:18] if idx < 2 and len(aday) > 18 else aday
        else:
            idx += 1
            parcalar[idx] = k[:18] if idx < 2 else k
    if not parcalar[0]:
        parcalar[0] = "Önemli Kural"
    if not parcalar[1]:
        parcalar[1] = "YASAL HAKKINIZ"
    if len(parcalar[2]) > 18:
        parcalar[2] = " ".join(parcalar[2].split()[:2])[:18]
    return parcalar[0], make_image.tr_buyuk(parcalar[1]), parcalar[2]


def veri_hazirla(konu: Dict[str, Any], format_turu: str) -> Dict[str, Any]:
    """Belirtilen formata göre tam JSON veri yapısını üretir."""
    kategori_kodu = "TAPU_VE_HUKUK"
    if "Kira" in konu["alan"]:
        kategori_kodu = "EV_SAHIBI_VE_KIRACI"
    elif "Arsa" in konu["alan"] or "Tarla" in konu["alan"]:
        kategori_kodu = "ARSA_IMAR_VE_TINY_HOUSE"
    elif "Finans" in konu["alan"]:
        kategori_kodu = "FINANS_VE_KREDI"

    if format_turu == "b1":
        p1, vurgu, p2 = _manset_bol_18(konu["manset"])
        return {
            "bicim": "B1",
            "format_turu": "b1",
            "konu_kodu": konu["id"],
            "kategori_kodu": kategori_kodu,
            "yasal_dayanak": konu["mevzuat"],
            "rozet_metni": f"HUKUK REHBERİ // {make_image.tr_buyuk(konu['alan'])}",
            "manset": konu["manset"],
            "manset_parca_1": p1,
            "manset_vurgu": vurgu,
            "manset_parca_2": p2,
            "spot": konu["spot"][:145],
            "slayt_2_detay": {
                "baslik_satir_1": "Hukuki Risk",
                "baslik_vurgu": "DİKKAT EDİN",
                "kartlar": [
                    {
                        "etiket": "YASAL RİSK",
                        "renk": "kirmizi",
                        "baslik": konu["yanlis"][:30],
                        "aciklama": konu["dogru"][:155],
                    },
                    {
                        "etiket": "MEVZUAT HÜKMÜ",
                        "renk": "kagit",
                        "baslik": "Dayanak Kuralı",
                        "aciklama": f"{konu['mevzuat']} gereğince yasal koruma adımları işletilmelidir."[:155],
                    },
                ],
            },
            "slayt_3_cozum": {
                "tip": "adim_adim_rehber",
                "baslik_ust": "Hak Kaybını Önleyen",
                "baslik_vurgu": "YOL HARİTASI",
                "maddeler": [
                    {"no": "01", "baslik": "Resmî İnceleme Yapın", "aciklama": konu["puf_maddeleri"][0][:140]},
                    {"no": "02", "baslik": "Yasal Süreyi İzleyin", "aciklama": konu["puf_maddeleri"][1][:140]},
                    {"no": "03", "baslik": "Uzman Desteği Alın", "aciklama": konu["altin_kural"][:140]},
                ],
            },
            "slayt_4_cta": {
                "slogan_parca_1": "Yatırımınızı",
                "slogan_vurgu": "KORUYUN",
                "aciklama": "Silivri ve Trakya gayrimenkul işlemlerinizde yanınızdayız.",
                "kaydet_metni": "Hukuki haklarınızı korumak için bu rehberi kaydedin.",
            },
        }

    elif format_turu == "nedir_dogrusu":
        return {
            "bicim": "B1",
            "format_turu": "nedir_dogrusu",
            "konu_kodu": konu["id"],
            "kategori_kodu": kategori_kodu,
            "yasal_dayanak": konu["mevzuat"],
            # Bilerek hem mükerrer önek hem küçük 'i' içeren metin veriyoruz ki temizleyici ve tr_buyuk sınansın:
            "konu": f"NEDİR DOĞRUSU // {konu['alan']}",
            "manset": f"Nedir Doğrusu: {konu['manset']}",
            "spot": konu["spot"],
            "yanlis_metin": konu["yanlis"][:180],
            "dogru_metin": konu["dogru"][:260],
            "altin_kural": konu["altin_kural"][:120],
            "slayt_3_cozum": {
                "maddeler": [
                    {"no": "01", "baslik": "Resmî Belge İnceleyin", "aciklama": konu["puf_maddeleri"][0][:140]},
                    {"no": "02", "baslik": "Kanuni Süreyi İzleyin", "aciklama": konu["puf_maddeleri"][1][:140]},
                ]
            },
        }

    elif format_turu == "vaka":
        return {
            "bicim": "B1",
            "format_turu": "vaka",
            "konu_kodu": konu["id"],
            "kategori_kodu": kategori_kodu,
            # İlk 2 vakada eski prompt çıktısı '01 / ÖRNEK OLAY' sabotajını bizzat sına:
            "vaka_kodu": "01 / ÖRNEK OLAY" if konu["id"] == "ALAN_01_A" else konu["vaka_kodu"],
            "yargitay_kaynak": konu["mevzuat"],
            "yasal_dayanak": konu["mevzuat"],
            "manset": konu["manset"][:50],
            "spot": konu["spot"],
            "olay_detay": konu["olay"][:280],
            "yargitay_hukmu": konu["hukum"][:280],
            "cikarilacak_ders": konu["ders"][:200],
            "slayt_3_cozum": {
                "maddeler": [
                    {"no": "01", "baslik": "Alınacak Önlem", "aciklama": konu["puf_maddeleri"][0][:140]},
                    {"no": "02", "baslik": "Temel Hukuki Kural", "aciklama": konu["altin_kural"][:140]},
                ]
            },
        }

    elif format_turu == "net_cevap":
        return {
            "bicim": "B3",
            "format_turu": "net_cevap",
            "konu_kodu": konu["id"],
            "kategori_kodu": kategori_kodu,
            "yasal_dayanak": konu["mevzuat"],
            "kategori": f"NET CEVAP // {konu['alan']}",
            "soru": konu["soru"][:70],
            "net_cevap": konu["net_cevap"][:30],
            "aciklama": konu["aciklama"][:200],
            "tavsiye_metin": konu["tavsiye"][:140],
            "manset": f"{konu['soru']} - {konu['net_cevap']}",
            "spot": konu["aciklama"],
            "slayt_3_cozum": {
                "maddeler": [
                    {"no": "01", "baslik": "Hukuki Dayanak", "aciklama": f"{konu['mevzuat']} hükmü uygulanır."},
                    {"no": "02", "baslik": "Yapılması Gereken", "aciklama": konu["tavsiye"][:140]},
                ]
            },
        }

    elif format_turu == "sozluk":
        return {
            "bicim": "sozluk",
            "format_turu": "sozluk",
            "konu_kodu": konu["id"],
            "kategori_kodu": kategori_kodu,
            "yasal_dayanak": konu["mevzuat"],
            "terim": konu["terim"],
            "tanim_metni": konu["tanim"][:240],
            "puf_maddeleri": [m[:140] for m in konu["puf_maddeleri"][:3]],
            "manset": f"EDM Sözlük: {konu['terim']}",
            "spot": konu["tanim"][:150],
        }

    raise ValueError(f"Bilinmeyen format: {format_turu}")


# ==============================================================================
# 10 DEĞERLENDİRME EKSENİ DENETÇİSİ
# ==============================================================================

class OtoriteDenetci:
    def __init__(self):
        self.sonuclar: List[Dict[str, Any]] = []

    def denetle(self, veri: Dict[str, Any], format_turu: str, konu: Dict[str, Any]) -> Dict[str, Any]:
        kod = veri["konu_kodu"]
        rapor: Dict[str, Any] = {
            "kod": kod,
            "format": format_turu,
            "alan": konu["alan"],
            "puanlar": {},
            "hatalar": [],
            "uyarilar": [],
            "basarili": True,
        }

        # Eksen 1: Mantık & Bütünlük
        self._eksen_mantik(veri, format_turu, rapor)

        # Eksen 2: Format Standartları & Bütçeler
        self._eksen_format(veri, format_turu, rapor)

        # Eksen 3: Tasarım & Çizim (4:5 ve 9:16)
        self._eksen_tasarim(veri, format_turu, rapor)

        # Eksen 4: Hukuki Doğruluk & Mevzuat
        self._eksen_hukuk(veri, konu, rapor)

        # Eksen 5: Kanca Etkisi & Sakin Otorite
        self._eksen_kanca(veri, format_turu, rapor)

        # Eksen 6: Seslendirme & Okunuş
        self._eksen_ses(veri, format_turu, rapor)

        # Eksen 7: Sabotaj & Uç Durum Direnci
        self._eksen_sabotaj(veri, format_turu, rapor)

        # Eksen 8: Platform Metinleri (LinkedIn, Threads, TikTok, IG)
        self._eksen_platformlar(veri, format_turu, rapor)

        # Eksen 9: Konu Çeşitliliği & Tekrar Engeli
        self._eksen_cesitlilik(veri, konu, rapor)

        # Eksen 10: Telegram Arayüzü & Buton Sözleşmesi
        self._eksen_telegram(veri, format_turu, rapor)

        if rapor["hatalar"]:
            rapor["basarili"] = False

        self.sonuclar.append(rapor)
        return rapor

    def _eksen_mantik(self, veri: Dict[str, Any], fmt: str, rapor: Dict[str, Any]):
        puan = 10
        # Fluff denetimi
        uyarilar = dogrula.denetle(veri)
        flufflar = [u for u in uyarilar if "BOŞ TAVSİYE (FLUFF)" in u]
        if flufflar:
            rapor["hatalar"].append(f"MANTIK: Boş tavsiye tespit edildi: {flufflar[0]}")
            puan -= 5

        # Çözüm adımları mantığı
        if fmt in ("b1", "nedir_dogrusu", "vaka", "net_cevap"):
            adimlar = (veri.get("slayt_3_cozum") or {}).get("maddeler", [])
            if len(adimlar) < 2:
                rapor["hatalar"].append("MANTIK: En az 2 somut çözüm adımı bulunmalıdır.")
                puan -= 5

        rapor["puanlar"]["1_mantik"] = max(0, puan)

    def _eksen_format(self, veri: Dict[str, Any], fmt: str, rapor: Dict[str, Any]):
        puan = 10
        ihlaller = generate_text.butce_ihlalleri(veri)
        if ihlaller:
            rapor["uyarilar"].append(f"FORMAT: Bütçe aşımı: {ihlaller[:2]}")
            puan -= min(4, len(ihlaller) * 2)

        # Zorunlu alan kontrolü
        if fmt == "sozluk" and not (veri.get("terim") and veri.get("tanim_metni")):
            rapor["hatalar"].append("FORMAT: Sözlük için 'terim' ve 'tanim_metni' zorunludur.")
            puan = 0
        elif fmt == "nedir_dogrusu" and not (veri.get("yanlis_metin") and veri.get("dogru_metin")):
            rapor["hatalar"].append("FORMAT: Nedir Doğrusu için 'yanlis_metin' ve 'dogru_metin' zorunludur.")
            puan = 0
        elif fmt == "vaka" and not (veri.get("olay_detay") and veri.get("yargitay_hukmu")):
            rapor["hatalar"].append("FORMAT: Vaka için 'olay_detay' ve 'yargitay_hukmu' zorunludur.")
            puan = 0
        elif fmt == "net_cevap" and not (veri.get("soru") and veri.get("net_cevap")):
            rapor["hatalar"].append("FORMAT: Net Cevap için 'soru' ve 'net_cevap' zorunludur.")
            puan = 0

        rapor["puanlar"]["2_format"] = max(0, puan)

    def _eksen_tasarim(self, veri: Dict[str, Any], fmt: str, rapor: Dict[str, Any]):
        puan = 10
        onek_45 = f"test_{veri['konu_kodu']}_{fmt}_4x5"
        onek_916 = f"test_{veri['konu_kodu']}_{fmt}_9x16"
        from src.cizim import bilesenler
        rozet_kayitlari: List[Tuple[int, int, int, str, int]] = []
        gercek_rozet = bilesenler._rozet_ciz

        def izlenen_rozet_ciz(draw, x, y, metin, *args, **kwargs):
            bw = gercek_rozet(draw, x, y, metin, *args, **kwargs)
            rozet_kayitlari.append((x, y, bw, str(metin or ""), make_image.YUKSEKLIK))
            return bw

        try:
            bilesenler._rozet_ciz = izlenen_rozet_ciz
            make_image._rozet_ciz = izlenen_rozet_ciz

            # 1. 4:5 Besleme Carousel Çizimi
            if fmt == "b1":
                yollar_45 = make_image.otorite_gonderi_slaytlari_uret(veri, cikti_onek=onek_45, olcu="besleme")
            else:
                yollar_45 = yeni_formatlar.slaytlari_uret(veri, cikti_dizini=CIKTI_DIZINI, cikti_onek=onek_45, format_turu=fmt, olcu="besleme")

            if not yollar_45 or not all(Path(p).exists() and Path(p).stat().st_size > 15_000 for p in yollar_45):
                rapor["hatalar"].append("TASARIM: 4:5 görseller üretilemedi veya dosya boyutu yetersiz.")
                puan -= 5

            # 2. 9:16 Dikey Story/Reels Çizimi
            if fmt == "b1":
                yollar_916 = make_image.otorite_gonderi_slaytlari_uret(veri, cikti_onek=onek_916, olcu="story")
            else:
                yollar_916 = yeni_formatlar.slaytlari_uret(veri, cikti_dizini=CIKTI_DIZINI, cikti_onek=onek_916, format_turu=fmt, olcu="story")

            if not yollar_916 or not all(Path(p).exists() and Path(p).stat().st_size > 15_000 for p in yollar_916):
                rapor["hatalar"].append("TASARIM: 9:16 görseller üretilemedi veya dosya boyutu yetersiz.")
                puan -= 5

            # 3. Rozet-Logo Çakışması, Mükerrer '//' Öneki ve Türkçe 'İ' Denetimi
            bozuk_ascii_kelimeler = ("HISSELI", "MIRAS", "INTIKAL", "FIILI", "ISGAL", "IFRAZ", "TEVHID", "KREDI", "MULKIYET")
            for rx, ry, rbw, rmetin, tuval_h in rozet_kayitlari:
                # Üst barda logo x = 1080 - 72 - 285 = 723 civarı başlar; rozet x + bw <= 705 olmalı
                ust_y_sinir = 325 if tuval_h >= 1700 else 90
                if rx < 200 and ry <= ust_y_sinir and (rx + rbw) > 708:
                    rapor["hatalar"].append(f"TASARIM: Rozet EDM logosunun üstüne bindi (x+bw={rx + rbw}): '{rmetin}'")
                    puan -= 5
                # Mükerrer format öneki kontrolü
                if rmetin.count("//") >= 2 or "ÖRNEK OLAY // 01 / ÖRNEK OLAY" in rmetin:
                    rapor["hatalar"].append(f"TASARIM: Mükerrer rozet öneki tespit edildi: '{rmetin}'")
                    puan -= 4
                for bozuk in bozuk_ascii_kelimeler:
                    if bozuk in rmetin:
                        rapor["hatalar"].append(f"TASARIM: Rozette Türkçe büyük harf ('İ') kaybı ({bozuk}): '{rmetin}'")
                        puan -= 4

            # 4. 9:16 Dikey Reels Karelerinde Kaydırma Oku ('›') Yasağı
            with make_image.tuval("story"):
                if yeni_formatlar._sayfa(1, 4) != "":
                    rapor["hatalar"].append("TASARIM: 9:16 dikey karelerde kaydırma oku ('›') gizlenmedi.")
                    puan -= 3

        except Exception as e:
            rapor["hatalar"].append(f"TASARIM: Çizim motoru çöktü: {e}")
            puan = 0
        finally:
            bilesenler._rozet_ciz = gercek_rozet
            make_image._rozet_ciz = gercek_rozet

        rapor["puanlar"]["3_tasarim"] = max(0, puan)

    def _eksen_hukuk(self, veri: Dict[str, Any], konu: Dict[str, Any], rapor: Dict[str, Any]):
        puan = 10
        dayanak = veri.get("yasal_dayanak") or ""
        if not any(k in dayanak for k in ("Kanun", "md.", "Mevzuat", "Yönetmelik")):
            rapor["hatalar"].append(f"HUKUK: Yasal dayanak maddesi eksik veya geçersiz: '{dayanak}'")
            puan -= 5

        # Sahte Yargıtay numarası kontrolü (2023/1234 E. gibi uydurma numara olmamalı)
        tum_metin = json.dumps(veri, ensure_ascii=False)
        if re.search(r"\b\d{4}/\d+\s*(?:E\.|K\.)", tum_metin):
            rapor["hatalar"].append("HUKUK: Uydurma Yargıtay Esas/Karar numarası tespit edildi!")
            puan -= 8

        rapor["puanlar"]["4_hukuk"] = max(0, puan)

    def _eksen_kanca(self, veri: Dict[str, Any], fmt: str, rapor: Dict[str, Any]):
        puan = 10
        tum_metin = json.dumps(veri, ensure_ascii=False).upper()
        yasaklilar = ["ŞOK!", "BOMBA!", "DİKKAT!", "İNANILMAZ!", "KAÇIRMAYIN!", "ÖNEMLİ DUYURU!"]
        for y in yasaklilar:
            if y in tum_metin:
                rapor["hatalar"].append(f"KANCA: Sakin otoriteye aykırı yasaklı ifade: '{y}'")
                puan -= 4

        # Manşet satır uzunluğu
        manset = veri.get("manset") or ""
        if len(manset) > 90:
            rapor["uyarilar"].append(f"KANCA: Manşet çok uzun ({len(manset)} kr.): '{manset[:40]}...'")
            puan -= 2

        rapor["puanlar"]["5_kanca"] = max(0, puan)

    def _eksen_ses(self, veri: Dict[str, Any], fmt: str, rapor: Dict[str, Any]):
        puan = 10
        # Metin seslendirme ve okunuş testi
        ham_metin = f"{veri.get('manset', '')}. {veri.get('spot', '')}"
        islenmis = okunus.ses_icin_kesme_kaynat(ham_metin)

        # Kesme işareti kalmamış olmalı (ElevenLabs hece kopması koruması)
        if "'" in islenmis or "’" in islenmis:
            rapor["uyarilar"].append("SES: Kesme işareti temizlenmemiş kelimeler var.")
            puan -= 2

        # Okuma süresi: 140 kelime/dakika * 1.22 hız ≈ 170 kelime/dk = 2.8 kelime/saniye
        kelime_sayisi = len(ham_metin.split())
        tahmini_sn = kelime_sayisi / 2.8
        if tahmini_sn < 3.0:
            rapor["uyarilar"].append("SES: Çok kısa okuma süresi (<3 sn).")
            puan -= 1
        elif tahmini_sn > 60.0:
            rapor["uyarilar"].append("SES: 60 saniyelik Shorts/Reels süresini aşıyor.")
            puan -= 2

        rapor["puanlar"]["6_ses"] = max(0, puan)

    def _eksen_sabotaj(self, veri: Dict[str, Any], fmt: str, rapor: Dict[str, Any]):
        puan = 10
        # Sabotaj 1: Dev metin enjeksiyonunda çökme testi
        sabotaj_veri = json.loads(json.dumps(veri))
        sabotaj_veri["spot"] = "Aşırı uzun metin testi " * 40  # ~800 karakter
        sabotaj_veri["manset"] = "Çok Dev Başlık " * 10
        try:
            if fmt == "b1":
                make_image.otorite_gonderi_slaytlari_uret(sabotaj_veri, cikti_onek=f"sabotaj_{veri['konu_kodu']}", olcu="besleme")
            else:
                yeni_formatlar.slaytlari_uret(sabotaj_veri, cikti_dizini=CIKTI_DIZINI, cikti_onek=f"sabotaj_{veri['konu_kodu']}", format_turu=fmt, olcu="besleme")
        except yeni_formatlar.EksikIcerik:
            # Beklenen güvenli savunma mekanizması: Aşırı taşmada veya eksik alanda motor çökmez, güvenle TasmaHatasi/EksikIcerik fırlatır
            pass
        except Exception as e:
            rapor["hatalar"].append(f"SABOTAJ: Aşırı uzun metin motoru çökertti: {e}")
            puan -= 5

        # Sabotaj 2: XSS / HTML karakterleri
        html_veri = json.loads(json.dumps(veri))
        html_veri["manset"] = "<script>alert('xss')</script> & <b>Test</b> \"Tırnak\" 'Tek'"
        try:
            if fmt == "b1":
                make_image.otorite_gonderi_slaytlari_uret(html_veri, cikti_onek=f"html_{veri['konu_kodu']}", olcu="besleme")
            else:
                yeni_formatlar.slaytlari_uret(html_veri, cikti_dizini=CIKTI_DIZINI, cikti_onek=f"html_{veri['konu_kodu']}", format_turu=fmt, olcu="besleme")
        except yeni_formatlar.EksikIcerik:
            pass
        except Exception as e:
            rapor["hatalar"].append(f"SABOTAJ: HTML / Tırnak karakterleri motoru çökertti: {e}")
            puan -= 5

        rapor["puanlar"]["7_sabotaj"] = max(0, puan)

    def _eksen_platformlar(self, veri: Dict[str, Any], fmt: str, rapor: Dict[str, Any]):
        puan = 10
        haber_taklidi = {
            "id": 999,
            "manset": veri.get("manset"),
            "spot": veri.get("spot"),
            "kategori": veri.get("kategori_kodu"),
            "yasal_dayanak": veri.get("yasal_dayanak"),
            "detay_metni": json.dumps(veri, ensure_ascii=False),
        }

        # 1. LinkedIn B2B Metni
        li_metin = linkedin.linkedin_metni_hazirla(haber_taklidi)
        if not ("MEVZUAT" in li_metin or "HUKUK" in li_metin or "ANALİZ" in li_metin):
            rapor["hatalar"].append("PLATFORM: LinkedIn metninde kurumsal B2B analizi eksik.")
            puan -= 3

        # 2. Threads Zinciri
        gorseller = ["https://cdn.example.com/1.jpg", "https://cdn.example.com/2.jpg"]
        th_parcalar = threads.metinleri_slaytlara_dagit(veri, gorseller)
        if not th_parcalar or len(th_parcalar[0]["metin"]) > 480:
            rapor["hatalar"].append("PLATFORM: Threads zinciri oluşturulamadı veya 480 karakter sınırını aştı.")
            puan -= 3

        # 3. TikTok Başlık ve Açıklaması
        tt_baslik = tiktok.baslik_kur(haber_taklidi)
        tt_aciklama = tiktok.aciklama_kur(haber_taklidi)
        if len(tt_baslik) > 150 or len(tt_aciklama) > 4000:
            rapor["hatalar"].append("PLATFORM: TikTok başlık/açıklama bütçesi aşıldı.")
            puan -= 2

        rapor["puanlar"]["8_platformlar"] = max(0, puan)

    def _eksen_cesitlilik(self, veri: Dict[str, Any], konu: Dict[str, Any], rapor: Dict[str, Any]):
        puan = 10
        # 10 farklı alandan dengeli dağılım
        if not konu.get("alan"):
            rapor["hatalar"].append("ÇEŞİTLİLİK: Alan tanımlı değil.")
            puan -= 5
        rapor["puanlar"]["9_cesitlilik"] = max(0, puan)

    def _eksen_telegram(self, veri: Dict[str, Any], fmt: str, rapor: Dict[str, Any]):
        puan = 10
        haber_taklidi = {
            "id": 999,
            "kaynak": "EDM Yapı & Gayrimenkul",
            "manset": veri.get("manset"),
            "kategori": "REELS" if fmt in ("vaka", "nedir_dogrusu") else "TAPU_VE_HUKUK",
        }
        is_reels = (fmt in ("vaka", "nedir_dogrusu"))
        rozet, dayanak, album_caption, kart_baslik = onay_karti.kart_basliklari(
            999, haber_taklidi, veri, fmt, is_reels, False, veri.get("manset", "")
        )

        if not rozet or not album_caption or not kart_baslik:
            rapor["hatalar"].append("TELEGRAM: Onay kartı başlıkları eksik.")
            puan -= 5

        rapor["puanlar"]["10_telegram"] = max(0, puan)


# ==============================================================================
# ANA ÇALIŞTIRICI: 100 İÇERİĞİ ÇALIŞTIR VE RAPORLA
# ==============================================================================

def main():
    log.info("=" * 70)
    log.info("OTORİTE İÇERİKLERİ KAPSAMLI STRES VE SABOTAJ TESTİ BAŞLATILIYOR")
    log.info("5 Format × 20 İçerik = 100 İçerik | 10 Hukuki Alan | 10 Eksen")
    log.info("=" * 70)

    baslangic = time.time()
    denetci = OtoriteDenetci()
    formatlar = ["b1", "nedir_dogrusu", "vaka", "net_cevap", "sozluk"]

    toplam_icerik = 0
    basarili_sayisi = 0

    for fmt in formatlar:
        log.info("\n>>> FORMAT TEST EDİLİYOR: [%s] (20 İçerik)...", fmt.upper())
        for konu in KONU_HAVUZU:
            veri = veri_hazirla(konu, fmt)
            rapor = denetci.denetle(veri, fmt, konu)
            toplam_icerik += 1
            if rapor["basarili"]:
                basarili_sayisi += 1
            else:
                log.warning("❌ Hata [%s - %s]: %s", fmt, konu["id"], rapor["hatalar"])

    sure = time.time() - baslangic

    log.info("\n" + "=" * 70)
    log.info("TEST TAMAMLANDI: %.2f saniyede %d içerik denetlendi.", sure, toplam_icerik)
    log.info("BAŞARILI: %d / %d (%%%0.1f)", basarili_sayisi, toplam_icerik, (basarili_sayisi / toplam_icerik) * 100)
    log.info("=" * 70)

    # Eksen ortalama puanları
    eksen_toplamlari: Dict[str, float] = {}
    for r in denetci.sonuclar:
        for k, v in r["puanlar"].items():
            eksen_toplamlari[k] = eksen_toplamlari.get(k, 0.0) + v

    log.info("\n10 EKSEN ORTALAMA PUANLARI (10 ÜZERİNDEN):")
    for k in sorted(eksen_toplamlari):
        ort = eksen_toplamlari[k] / toplam_icerik
        bar = "█" * int(ort) + "░" * (10 - int(ort))
        log.info("  %-25s: [%s] %0.2f / 10", k, bar, ort)

    if basarili_sayisi == toplam_icerik:
        log.info("\n🎉 TÜM FORMATLAR 100/100 MÜKEMMEL SKORLA STRES VE SABOTAJ TESTİNİ GEÇTİ!")
        return 0
    else:
        log.error("\n⛔ BAZI İÇERİKLER STRES TESTİNDE BAŞARISIZ OLDU!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
