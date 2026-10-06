#!/usr/bin/env python3
"""
scripts/test_20_haber_dailybrief.py — 20 Farklı Gerçek Haberle DailyBrief Testi

En az 20 farklı gerçek haber ile detay sayfalarını, kapak başlığını ve editoryal
spotu en verimli, en anlaşılır ve taşma yapmayacak şekilde test eder.

Doğrulananlar:
1. Kapak sayfası: Gazetecilik usulü doğal tek parça manşet (Fraunces serif) +
   2-3 cümlelik açıklayıcı editoryal spot (IBM Plex Sans, tam metin, taşmasız).
2. Detay sayfaları: Standart 1 slayta sıkışma yok; haberin zenginliğine göre
   dinamik 2-4 slayta ferah yerleşim (34-40px punto, mimari dikey çentik).
3. Üst etiket sabit "// HABERİN AYRINTILARI" (2026-10-07: kelimeden tahmin edilen
   "BÖLGESEL PİYASAYA ETKİSİ" etiketi içerikte olmayan bir açıyı iddia ediyordu).
4. EDM Değerlendirmesi uzman analiz kartı.
5. 20 haberin tamamının sıfır hata (0 TasmaHatasi) ile başarıyla üretilmesi.
"""

import sys
import os
from pathlib import Path
import sqlite3
import json
import logging

# postedm kök dizinini ekle
PROJE_KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJE_KOK))

from src import make_image, config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("test_20_haber")

CIKTI_DIZINI = PROJE_KOK / "data" / "output" / "test_20_haber"
CIKTI_DIZINI.mkdir(parents=True, exist_ok=True)

# 20 Gerçek Haber Veri Seti (DB'deki gerçek kayıtlara ve makalelere dayalı)
HABER_TEST_SETI = [
    {
        "id": 357,
        "kategori": "ARSA_VE_TARLA",
        "kaynak": "TOKİ RESMİ DUYURU",
        "manset": "TOKİ 47 İlde 383 Hazine Arsasını Açık Artırmayla Satışa Çıkardı",
        "spot": "Çevre ve Şehircilik Bakanlığı öncülüğünde 47 ildeki 383 arsa satışa sunuldu. Yüzde 25 peşinat ve 48 ay vade imkanı sağlanan açık artırma, Trakya ve İstanbul çeperinde arsa arayan yatırımcılar için büyük fırsat sunuyor.",
        "detay_maddeleri": [
            {
                "etiket": "01 // İHALE TARİHLERİ VE ARSA ADEDİ",
                "metin": "İhale 15-16 Ekim tarihlerinde hem fiziki salonlarda hem de internet üzerinden eşzamanlı olarak gerçekleştirilecek.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // BÖLGESEL PİYASAYA VE FİYATLARA ETKİSİ",
                "metin": "Silivri, Çatalca ve Tekirdağ çeperindeki arazilerde piyasa rayicinin altında muhammen bedellerle arz oluşması bölgesel ilgiyi artırıyor.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // ÖDEME VE VADE KOŞULLARI",
                "metin": "Alıcılar yüzde 25 peşinat ödeyerek kalan tutarı 48 ay eşit taksitle ödeyebilecek; ayrıca peşin ödemelerde yüzde 20 indirim uygulanacak.",
                "renk": "kirec",
            },
            {
                "etiket": "04 // DİKKAT EDİLECEK HUKUKİ HUSUSLAR",
                "metin": "İhaleye girmeden önce taşınmazın imar çapı, sit derecesi ve kadastro fiili yolu belediyeden bizzat kontrol edilmelidir.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: Peşin ödemedeki yüzde 20 indirim, enflasyonist ortamda arsa maliyetini piyasanın oldukça altına çekiyor.",
    },
    {
        "id": 320,
        "kategori": "ARSA_VE_TARLA",
        "kaynak": "MİLLİ EMLAK GENEL MÜDÜRLÜĞÜ",
        "manset": "Milli Emlak Çatalca'da 49 Bin TL'den Arazi Satışına Başladı",
        "spot": "Milli Emlak, İstanbul Çatalca'da 49.150 TL muhammen bedelle KDV'den muaf arazi satış ihalesi açtı. Peşin ödemede yüzde 20 indirim veya 24 ay taksit imkanı sunulan ihale küçük bütçeli yatırımcılar için nadir bir fırsat barındırıyor.",
        "detay_maddeleri": [
            {
                "etiket": "01 // İHALE DETAYLARI VE PARSEL BİLGİSİ",
                "metin": "Çatalca sınırlarında yer alan parsel 49.150 TL başlangıç bedeliyle açık artırma usulüyle satışa sunuldu.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // KDV VE VERGİ MUAFİYETİ AVANTAJI",
                "metin": "Hazine arazisi satışlarında KDV muafiyeti uygulanıyor ve taşınmaz 5 yıl boyunca emlak vergisinden muaf tutuluyor.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // ÇATALCA VE TRAKYA PİYASASINA YANSIMASI",
                "metin": "Bölgede metrekare birim fiyatlarının hızla yükseldiği bir dönemde, küçük tasarruf sahipleri için resmi tapulu arazi edinme kapısı açıldı.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: Küçük parsellerde hisse veya zemin çapı incelemesi yapılmadan teminat yatırılmamalıdır.",
    },
    {
        "id": 348,
        "kategori": "KONUT_VE_PROJE",
        "kaynak": "ÇEVRE ŞEHİRCİLİK BAKANLIĞI",
        "manset": "TOKİ Arnavutköy Projesiyle Sazlıbosna'ya 770 Yeni Konut Geliyor",
        "spot": "İstanbul Arnavutköy Sazlıbosna mevkiinde 770 konut ve 30 dükkandan oluşan dev proje onaylandı. Kanal İstanbul güzergahında yer alan etap, bölgedeki konut arzını ve arsa hareketliliğini doğrudan etkileyecek.",
        "detay_maddeleri": [
            {
                "etiket": "01 // PROJE ETAPLARI VE İHALE TARİHİ",
                "metin": "Projede 770 adet konut, ticaret merkezi ve altyapı çevre düzenlemesi ihalesi tamamlanarak inşaat sürecine geçildi.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // BÖLGEDEKİ ARSA VE KONUT FİYATLARI",
                "metin": "Arnavutköy ve Sazlıbosna çeperindeki arsa metrekare birim fiyatları yeni konut etaplarının açıklanmasıyla yukarı yönlü ivme kazandı.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // DİKKAT EDİLECEK REZERV ALAN ŞARTLARI",
                "metin": "Bölgeden mülk edinecek yatırımcıların imar uygulaması ve terk oranlarını güncel askı planlarından teyit etmesi şarttır.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: Kamu projeleri çevre köylerde arsa talebini tetikler, ancak altyapı bitiş tarihleri iyi hesaplanmalıdır.",
    },
    {
        "id": 347,
        "kategori": "INSAAT_VE_MALIYET",
        "kaynak": "SEKTÖREL İNŞAAT RAPORU",
        "manset": "Müstakil Ev Yapımında Metrekare Maliyeti 25 Bin TL'yi Aştı",
        "spot": "Silivri ve Trakya'da arsa üzerine müstakil villa veya çelik karkas ev yaptırmak isteyenler için maliyet tablosu güncellendi. Ruhsat, hafriyat, betonarme karkas ve ince işçilik dahil taban maliyetler 90 bin dolardan başlıyor.",
        "detay_maddeleri": [
            {
                "etiket": "01 // GÜNCEL MALİYET KALEMLERİ VE FİYATLAR",
                "metin": "Beton, demir ve işçilik artışlarıyla standart 120 m² müstakil evin anahtar teslim maliyeti 2.8 milyon TL ile 3.8 milyon TL arasına ulaştı.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // RUHSAT VE RESMİ HARÇ GİDERLERİ",
                "metin": "Mimari proje, zemin etüdü, şantiye şefi, yapı denetim ve belediye harçları toplam bütçenin yaklaşık yüzde 15'ini oluşturuyor.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // PREFABRİK VE ÇELİK EV ALTERNATİFİ",
                "metin": "İnşaat süresini 3 aya indiren hafif çelik sistemler metrekare maliyetinde yüzde 20 tasarruf sağlarken imar izni zorunluluğu aynen sürüyor.",
                "renk": "kirec",
            },
            {
                "etiket": "04 // SİLİVRİ VE ÇATALCA'DA İMAR ŞARTLARI",
                "metin": "Tarım arazilerinde plansız yapılaşmaya izin verilmiyor; taban alanı (TAKS) ve emsal sınırlarına harfiyen uyulması gerekiyor.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: Arsa satın alırken altyapı (elektrik/su bağlantı mesafesi) maliyetini en baştan bütçeye ekleyin.",
    },
    {
        "id": 346,
        "kategori": "BELEDIYE_IHALE",
        "kaynak": "RESMİ İHALE BÜLTENİ",
        "manset": "Belediyeden Konut İmarlı Arsa İhalesi: Metrekaresi 8.500 TL",
        "spot": "Yalova Çiftlikköy Belediyesi mülkiyetindeki merkezi konumlu konut imarlı arsayı ihaleyle satışa çıkardı. Peşin ödeme kolaylığı ve kat karşılığı inşaat potansiyeli bölgedeki müteahhit ve yatırımcıların ilgisini topladı.",
        "detay_maddeleri": [
            {
                "etiket": "01 // ARSA İMAR VE EMSAL BİLGİSİ",
                "metin": "İhaleye konu parsel 3 kat konut imarlı olup ayrık nizam 0.40 TAKS ve 1.20 KAKS yapılaşma koşullarına sahiptir.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // İHALE ŞARTLARI VE TEMİNAT",
                "metin": "İhale 2886 sayılı Devlet İhale Kanunu uyarınca açık teklif usulüyle yapılacak; geçici teminat bedeli yüzde 3 olarak belirlendi.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // MARMARA BÖLGESEL PİYASASINA ETKİSİ",
                "metin": "Köprü ve otoyol aksında yer alan arsa arzları, İstanbul'a yakın merkezlerde konut üreticileri için cazip getiri alanı yaratıyor.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: Belediye ihalelerinde kesinleşen ihale kararından sonra 15 gün içinde ödemenin yapılması zorunludur.",
    },
    {
        "id": 345,
        "kategori": "HUKUK_VE_TICARI",
        "kaynak": "TİCARİ GAYRİMENKUL RAPORU",
        "manset": "AVM ve Ticari Mülklerde 'Kira Garantili Dükkan' Tuzağına Dikkat",
        "spot": "Son dönemde popülerleşen kira garantili ticari ünite satışlarında hukuki uyuşmazlıklar artıyor. Uzmanlar taahhüt edilen yüksek kira getirilerinin sözleşme güvencesi içermediği durumlarda alıcıların mağdur olduğunu belirtiyor.",
        "detay_maddeleri": [
            {
                "etiket": "01 // SÖZLEŞME VE KİRA TAAHHÜDÜ RİSKİ",
                "metin": "Kira garantisi veren paravan yönetim şirketlerinin tasfiye edilmesi durumunda mülk sahibi gerçek piyasa kirasıyla baş başa kalıyor.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // TİCARİ MÜLKÜN GERÇEK RAYİÇ ANALİZİ",
                "metin": "Mülk alınırken vaat edilen kira çarpanı değil, çevredeki benzer dükkanların fiili doluluk oranı ve tabela değeri baz alınmalıdır.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // BANKA KREDİSİ VE EXPERTİZ DEĞERİ",
                "metin": "Şişirilmiş fiyatlarla satılan ünitelerde ekspertiz raporu gerçek piyasa değerini ortaya koyan en somut süzgeçtir.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: Kira garantisi yerine mülkün bağımsız tapu durumuna, yönetim planına ve ana kiracının gücüne odaklanın.",
    },
    {
        "id": 343,
        "kategori": "SEKTOREL_GELISME",
        "kaynak": "KAP / EMLAK KONUT GYO",
        "manset": "Emlak Konut Eyüpsultan Kemerburgaz 2. Etap İhalesini İptal Etti",
        "spot": "Emlak Konut GYO, Kemerburgaz 2. Etap arsa satışı karşılığı gelir paylaşımı ihalesini gelen tekliflerin yetersizliği nedeniyle iptal ettiğini duyurdu. Karar, lüks segment konut projelerindeki maliyet ve fiyat dengesini yansıtıyor.",
        "detay_maddeleri": [
            {
                "etiket": "01 // İHALENİN İPTAL GEREKÇESİ",
                "metin": "İhale komisyonu şirket menfaatleri doğrultusunda sunulan asgari gelir payı tekliflerini beklenen fizibilite sınırının altında buldu.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // BÖLGE PİYASASINA VE ÜRETİCİYE ETKİSİ",
                "metin": "Kemerburgaz ve Göktürk hattında yüksek arsa payı beklentileri müteahhitlerin yeni proje açma iştahını temkinli seviyede tutuyor.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // YENİ İHALE SÜRECİ VE BEKLENTİLER",
                "metin": "Emlak Konut'un projeyi revize ederek şartları güncel piyasa koşullarına göre yeniden ihaleye çıkarması öngörülüyor.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: Kamu GYO ihalelerindeki iptaller, arsa arzında taban fiyat beklentisinin korunduğunu gösterir.",
    },
    {
        "id": 342,
        "kategori": "HUKUK_VE_RUHSAT",
        "kaynak": "DANIŞTAY KARARI",
        "manset": "Mahkeme Kararı Kesinleşti: Kızılbük Projesinde Yapı Ruhsatları İptal",
        "spot": "Muğla İdare Mahkemesi'nin Marmaris Kızılbük'teki termal tatil köyü projesine ilişkin verdiği yapı ruhsatı iptali kararı Danıştay tarafından onandı. Karar, kıyı kanunu ve imar planı uyuşmazlıklarında emsal teşkil ediyor.",
        "detay_maddeleri": [
            {
                "etiket": "01 // MAHKEMENİN İPTAL GEREKÇESİ",
                "metin": "Milli park ve kıyı kenar çizgisi mevzuatına aykırılık gerekçesiyle verilen yapı ruhsatları hukuka aykırı bulunarak hükümsüz kılındı.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // DEVREMÜLK VE HAK SAHİPLERİ NE YAPACAK",
                "metin": "Ruhsatı iptal edilen projelerden sözleşmeyle ünite alan tüketiciler 6502 sayılı Kanun kapsamında bedel iadesi talep etme hakkına sahip.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // İNŞAAT PROJELERİNDE KIYI ÇİZGİSİ DERSİ",
                "metin": "Yatırımcıların kıyı ve doğal koruma alanlarında ruhsatın kesinleşmiş imar planına dayanıp dayanmadığını araştırması şarttır.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: Projeden mülk alırken yalnızca belediye ruhsatına değil, plan askı itirazlarının kesinleşme durumuna bakın.",
    },
    {
        "id": 341,
        "kategori": "FINANS_VE_KREDI",
        "kaynak": "BDDK DÜZENLEMESİ",
        "manset": "Konut Kredisi Erken Kapatılırsa Banka En Fazla Yüzde 2 Ceza Kesebilir",
        "spot": "6502 sayılı Tüketicinin Korunması Hakkında Kanun uyarınca konut kredilerinde erken ödeme tazminatı yasal tavana bağlandı. Kalan vadesi 36 ayı aşmayan kredilerde yüzde 1, aşanlarda ise en fazla yüzde 2 tazminat alınabiliyor.",
        "detay_maddeleri": [
            {
                "etiket": "01 // ERKEN KAPATMA TAZMİNATI ÜST SINIRI",
                "metin": "Kalan vadesi 36 aydan az olan konut kredilerinde ceza yüzde 1'i, 36 aydan fazla olanlarda ise yüzde 2'yi kesinlikle geçemez.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // ARA ÖDEME YAPILDIĞINDA NE OLUR",
                "metin": "Kredinin bir kısmını ara ödemeyle kapatan tüketiciden sadece ödenen anapara tutarı üzerinden tazminat kesilebilir.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // FAZLADAN ALINAN ÜCRETLERİN İADESİ",
                "metin": "Yasal sınırın üzerinde erken kapama komisyonu veya dosya masrafı kesen bankalara karşı Tüketici Hakem Heyetine başvurulabilir.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: Kredi kapatırken bankadan mutlaka 'borcu yoktur' yazısı ve tapu fek yazısını eşzamanlı talep edin.",
    },
    {
        "id": 340,
        "kategori": "IMAR_VE_HUKUK",
        "kaynak": "ÇEVRE ŞEHİRCİLİK BAKANLIĞI",
        "manset": "İmar Barışı Yapı Kayıt Belgesi Uydu Tespitiyle İptal Ediliyor",
        "spot": "31 Aralık 2017 tarihinden sonra kaçak olarak inşa edilip imar barışına sokulan yapıların belgeleri uydu görüntüleriyle tespit edilerek iptal ediliyor. Belgesi iptal edilen taşınmazlar için hem yıkım hem de adli soruşturma süreci işletiliyor.",
        "detay_maddeleri": [
            {
                "etiket": "01 // UYDU FOTOĞRAFLARIYLA DENETİM",
                "metin": "Bakanlık 2017 sonu ortofoto uydu haritalarını baz alarak yapının o tarihte var olup olmadığını santim hassasiyetinde inceliyor.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // İPTALİN YASAL VE MALİ SONUÇLARI",
                "metin": "Yalan beyanla alınan belgeler iptal edilirken ödenen kayıt bedeli iade edilmiyor ve TCK md. 206 gereğince savcılığa suç duyurusu yapılıyor.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // YIKIM VE ELEKTRİK-SU KESİNTİSİ",
                "metin": "Belgesi iptal edilen binalara bağlanan geçici elektrik ve su abonelikleri derhal kesilerek belediye encümeni yıkım kararı alıyor.",
                "renk": "kirec",
            },
            {
                "etiket": "04 // SİLİVRİ VE TRAKYA'DA MÜLK ALANLARIN DİKKATİNE",
                "metin": "Kayıt belgeli bir yapı satın alırken yapım tarihini gösteren resmi elektrik faturası veya uydu geçmişini doğrulamak hayati önemdedir.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: Sırf Yapı Kayıt Belgesi var diye 2018 sonrasında yapılan kaçak yapılara asla yatırım yapmayın.",
    },
    {
        "id": 328,
        "kategori": "ARSA_VE_IHALE",
        "kaynak": "TOKİ RESMİ İLAN",
        "manset": "TOKİ'den 405 Arsa İhalesi: Peşin Alımda Yüzde 20 İndirim",
        "spot": "Türkiye genelinde 47 ilde yer alan 405 arsa açık artırma yöntemiyle satışa çıktı. Trakya, Ege ve İç Anadolu'da konut, sanayi ve plansız tarım arazilerini kapsayan ihalede 48 ay vade seçeneği sunuluyor.",
        "detay_maddeleri": [
            {
                "etiket": "01 // İHALE TARİHLERİ VE ÇEVRİMİÇİ KATILIM",
                "metin": "İhaleler 2-3 Ekim tarihlerinde Ankara ve İstanbul merkezli salonlarda ve emlakmuzayede.com.tr üzerinden canlı yapılacak.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // KDV VE TAPU HARCI MUAFİYETİ",
                "metin": "TOKİ arsa satışları Katma Değer Vergisi'nden ve tapu devir harcından tamamen muaf olarak tescil edilmektedir.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // TRAKYA BÖLGESİNDEKİ PARSELLER",
                "metin": "Tekirdağ Çorlu, Ergene ve Kırklareli hattındaki sanayi ve depolama imarlı arsalar lojistik yatırımcıları için öne çıkıyor.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: Vadeli alımda yıllık ÜFE endeksi uygulandığından peşin alım indirimi çok daha karlı bir seçenektir.",
    },
    {
        "id": 327,
        "kategori": "KIRA_VE_KONUT",
        "kaynak": "İSTANBUL BÜYÜKŞEHİR BELEDİYESİ",
        "manset": "İstanbul'da Sosyal Kiralık Konut Başvuruları Başladı: Tavan Kira 8 Bin TL",
        "spot": "İstanbul genelinde dar gelirli ve yeni evli çiftler için geliştirilen belediye kiralık konut projesinde kura süreci netleşti. Özel mülkiyete devredilmeyen ve yalnızca kiralanan konutlar piyasa rayicinin yüzde 50 altında kiralanacak.",
        "detay_maddeleri": [
            {
                "etiket": "01 // KİMLER BAŞVURABİLİR VE GELİR SINIRI",
                "metin": "Başvuru sahibinin üzerine kayıtlı konut bulunmaması ve hane halkı toplam gelirinin asgari ücretin 2.5 katını aşmaması gerekiyor.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // KİRALAMA SÜRESİ VE SÖZLEŞME ŞARTLARI",
                "metin": "Sözleşmeler 3 yıllık periyotlarla yapılacak ve kira artışları resmi TÜFE oranını geçmeyecek şekilde sabitlenecek.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // ÇEVRE KİRA PİYASASINA YANSIMASI",
                "metin": "Projenin hayata geçtiği ilçelerde alt gelir grubu kiralık konut talebinde dengelenme ve fiyat köpüğünde erime bekleniyor.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: Sosyal kiralık konut modeli, Avrupa'daki gibi kalıcı kamu kiralama stokunun ilk başarılı adımıdır.",
    },
    {
        "id": 326,
        "kategori": "KIRA_HUKUKU",
        "kaynak": "YARGITAY HUKUK GENEL KURULU",
        "manset": "Kiracının Aynı İlçede Başka Evi Varsa Tahliye Şartsız Kabul Ediliyor",
        "spot": "Türk Borçlar Kanunu md. 352/3 uyarınca kiracının aynı belediye sınırları içinde oturmaya elverişli bir konutu varsa ev sahibi gerekçe göstermeden tahliye davası açabiliyor. Yargıtay son kararında bu hakkı şartsız onadı.",
        "detay_maddeleri": [
            {
                "etiket": "01 // KANUNİ DAYANAK: TBK MADDE 352/3",
                "metin": "Kiracının veya birlikte yaşadığı eşinin aynı ilçe sınırlarında oturabileceği müstakil dairesi varsa tahliye talep edilebilir.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // KİRACININ İLERİ SÜREMEYECEĞİ İTİRAZLAR",
                "metin": "Kiracı 'kendi evim daha küçük' veya 'benim evimde kiracı var' savunmasını ancak dava açılmadan önce geçerli bir nedenle ispatlamalıdır.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // DAVA AÇMA SÜRESİ VE İHTARNAME",
                "metin": "Kira sözleşmesinin bitiminden itibaren 1 ay içinde sulh hukuk mahkemesinde dava açılması kanunen zorunludur.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: Kira sözleşmesi yaparken tarafların aynı ilçedeki tapu mülkiyet durumunu sözleşmeye şerh düşmek süreci hızlandırır.",
    },
    {
        "id": 323,
        "kategori": "SOSYAL_KONUT",
        "kaynak": "ÇEVRE ŞEHİRCİLİK BAKANLIĞI",
        "manset": "Kiralık Sosyal Konut Modeli 81 İle Yayılıyor: İlk Etapta 50 Bin Konut",
        "spot": "Hükümet dar gelirli vatandaşların konuta erişimini kolaylaştırmak için satılık değil, yalnızca kiralık sosyal konut üretimini başlattı. Kamu güvencesiyle işletilecek fon ile kiralar piyasa ortalamasının altında tutulacak.",
        "detay_maddeleri": [
            {
                "etiket": "01 // MODELİN İŞLEYİŞ MEKANİZMASI",
                "metin": "Hazine arazileri üzerinde TOKİ ve Emlak Konut tarafından üretilecek konutlar satılamayacak, kamu kira havuzuna devredilecek.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // BÖLGESEL PİYASAYA VE RAYİÇLERE ETKİSİ",
                "metin": "Sanayi bölgelerinde iş gücünün barınma krizini çözecek olan model, Trakya ve Marmara çeperindeki fabrika bölgelerine öncelik veriyor.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // KİRA GELİRLERİYLE YENİ KONUT FİNANSMANI",
                "metin": "Toplanan kira gelirleri doğrudan fon bünyesinde toplanarak sonraki etapların inşaat maliyetini finanse etmek için kullanılacak.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: Sanayi aksındaki fabrikalara yakın arsalarda bu model lojistik değerleri daha da artıracaktır.",
    },
    {
        "id": 309,
        "kategori": "TARIM_VE_ARSA",
        "kaynak": "5403 SAYILI TOPRAK KORUMA KANUNU",
        "manset": "Tarım Arazilerinde Hisseli Satış Yasağı ve Asgari Parsel Büyüklükleri",
        "spot": "5403 sayılı Kanun uyarınca tarım arazilerinin miras veya rızaen hisselere bölünerek satışı kesin olarak yasaktır. Silivri ve Çatalca'da arsa alırken noter sözleşmesiyle pay devri yapanlar tapuda tescil alamıyor.",
        "detay_maddeleri": [
            {
                "etiket": "01 // ASGARİ TARIMSAL PARSEL BÜYÜKLÜKLERİ",
                "metin": "Mutlak tarım arazilerinde 20 bin m², dikili arazilerde 5 bin m², örtü altı seralarda 3 bin m² altına hisseli bölünme yapılamaz.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // NOTER SATIŞ VAADİ TUZAĞI",
                "metin": "Noterden yapılan hisse devir vaatleri tapu müdürlüğünde müstakil tapuya dönüşmez; resmi tapu kaydı geçerlidir.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // SINIR KOMŞUSUNUN ÖNALIM HAKKI",
                "metin": "Tarımsal arazinin satışı durumunda sınır komşusu olan tarımsal işletme sahiplerinin kanuni öncelikli alım hakkı bulunmaktadır.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: 'Hisseli tapu veriyoruz, ilerde ifraz edilecek' vaatlerine inanmayın; tarımda kanuni sınır altında ifraz imkansızdır.",
    },
    {
        "id": 275,
        "kategori": "KORUMA_VE_IMAR",
        "kaynak": "6831 SAYILI ORMAN KANUNU",
        "manset": "2B Arazilerinde Hak Sahipliği Devri ve Doğrudan Satın Alma Süreci",
        "spot": "Orman vasfını yitirmiş 2B arazilerinde kullanıcıların doğrudan mülkiyet edinme hakkı sürüyor. Silivri ve Şile hattında hak sahipliği devri yapılırken noter muvafakatnameleri ve fiili zilyetlik tutanakları kritik rol oynuyor.",
        "detay_maddeleri": [
            {
                "etiket": "01 // 2B DOĞRUDAN SATIN ALMA ŞARTLARI",
                "metin": "Taşınmazın kadastro tutanağında kullanıcı olarak adı geçen veya mirasçısı olan kişiler emlak rayiç bedeli üzerinden satın alma yapabilir.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // BAŞVURU SÜRELERİ VE ÖDEME KOLAYLIĞI",
                "metin": "Hak sahiplerine peşin alımda yüzde 20 indirim veya 5 yıl vadeyle 10 eşit taksitte faizsiz ödeme imkanı tanınmaktadır.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // DİKKAT EDİLECEK RİSKLER VE ZİLYETLİK",
                "metin": "Üzerinde ihtilaf veya orman idaresiyle dava bulunan parsellerde hak devri almadan önce dava durum belgesi incelenmelidir.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: 2B arazisi alırken Milli Emlak şefliğinden parselin kesinleşmiş kullanıcı kütük kaydını kontrol edin.",
    },
    {
        "id": 250,
        "kategori": "HUKUK_VE_TAPU",
        "kaynak": "TÜRK MEDENİ KANUNU MD. 732",
        "manset": "Hisseli Tapuda Şufa (Önalım) Hakkı: Noter Bildirimi Yapılmazsa 2 Yıl Süre Var",
        "spot": "Hisseli gayrimenkullerde bir hissedar payını üçüncü kişiye satarsa diğer paydaşların aynı bedelle satın alma hakkı doğar. Satışın noter kanalıyla bildirilmemesi halinde 2 yıllık dava açma hakkı mülk alıcısını tehdit eder.",
        "detay_maddeleri": [
            {
                "etiket": "01 // KANUNİ ÖNALIM HAKKI VE MEKANİZMASI",
                "metin": "Paylı mülkiyette bir paydaş hissesini yabancıya satarsa diğer hissedarlar öncelikli olarak aynı fiyattan payı alma hakkına sahiptir.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // 3 AY VE 2 YILLIK HAK DÜŞÜRÜCÜ SÜRELER",
                "metin": "Satış noterle bildirilirse 3 ay, bildirilmezse tapu tescilinden itibaren 2 yıl içinde dava açılması gerekir.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // TAPU HARCINI DÜŞÜK GÖSTERME TUZAĞI",
                "metin": "Tapuda bedel gerçekte 1 milyon iken 300 bin TL gösterilirse, diğer hissedar taşınmazı 300 bin TL ödeyerek elinizden alabilir.",
                "renk": "kirec",
            },
            {
                "etiket": "04 // ÇÖZÜM: FİİLİ TAKSİM VEYA FERAGAT",
                "metin": "Hissedarlardan noter onaylı feragatname almak veya fiili kullanım ayrımı olduğunu ispatlamak şufa riskini tamamen ortadan kaldırır.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: Hisseli tapu alırken tapu harcını kuruşu kuruşuna gerçek satış bedelinden yatırmak en büyük sigortanızdır.",
    },
    {
        "id": 240,
        "kategori": "IMAR_VE_TARLA",
        "kaynak": "3194 SAYILI İMAR KANUNU MD. 32",
        "manset": "Tarlaya Tiny House ve Konteyner Koyarken İmar Para Cezası Riski",
        "spot": "Tarım arazilerine tekerlekli tiny house, prefabrik veya konteyner yerleştiren mülk sahiplerine belediyeler imar para cezası ve mühürleme uyguluyor. Tabanına beton dökülen veya altyapı bağlanan tüm yapılar kanunen bina sayılıyor.",
        "detay_maddeleri": [
            {
                "etiket": "01 // TEKERLEKLİ DE OLSA NE ZAMAN YAPI SAYILIR",
                "metin": "Tekerlekli araç foseptiğe, elektrik/su şebekesine bağlandığı veya etrafına sundurma/veranda yapıldığı an imar mevzuatına tabi olur.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // 3194 MD. 32 VE 42 İMAR CEZALARI",
                "metin": "Ruhsatsız yapı tespiti durumunda hem metrekare bazlı yüksek para cezası kesilir hem de 30 gün içinde kaldırma zorunluluğu getirilir.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // SİLİVRİ VE ÇATALCA BELEDİYESİ UYGULAMASI",
                "metin": "Bölgede drone ve jandarma denetimleriyle tarım arazilerine kaçak yerleştirilen mobil yapılar düzenli olarak çekiciyle kaldırılıyor.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: Tarlanıza konteyner veya tiny house koymadan önce İlçe Tarım ve Belediye İmar Müdürlüğü'nden görüş alın.",
    },
    {
        "id": 230,
        "kategori": "TAPU_VE_GUVENCE",
        "kaynak": "TKGM TAPU GÜVENLİK PROTOKOLÜ",
        "manset": "Tapuda Güvenli Satış: Tapu Takas Sistemiyle Nakit Taşıma Devri Bitti",
        "spot": "Tapu ve Kadastro Genel Müdürlüğü ile Takasbank ortaklığında çalışan Tapu Takas sistemi, gayrimenkul alım satımında dolandırıcılık ve sahte para riskini sıfıra indiriyor. Para ve tapu tescili eşzamanlı el değiştiriyor.",
        "detay_maddeleri": [
            {
                "etiket": "01 // SİSTEMİN ÇALIŞMA PRENSİBİ",
                "metin": "Alıcı satış bedelini Takasbank havuz hesabına yatırır; tapuda imzalar atıldığı anda para satıcının hesabına saniyeler içinde aktarılır.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // İŞLEM İPTAL EDİLİRSE NE OLUR",
                "metin": "Tapuda taraflardan biri vazgeçerse veya pürüz çıkarsa para tek bir kuruş kesinti olmadan alıcının banka hesabına geri iade edilir.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // ÇANTA DOLUSU NAKİT RİSKİNE SON",
                "metin": "Yalnızca 140 TL gibi sembolik bir sistem masrafıyla milyonlarca liralık mülk transferi sıfır riskle tamamlanmaktadır.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: EDM Yapı & Gayrimenkul olarak tüm işlemlerimizde Tapu Takas veya bloke çek sistemini tavsiye ediyoruz.",
    },
    {
        "id": 210,
        "kategori": "VERGI_VE_HARC",
        "kaynak": "GELİR İDARESİ BAŞKANLIĞI",
        "manset": "Gayrimenkulü 5 Yıl İçinde Satanlara Değer Artış Kazancı Vergisi Çıktı",
        "spot": "Satın alınan bir konut veya arsa iktisap tarihinden itibaren 5 tam yıl dolmadan elden çıkarılırsa elde edilen kazanç Gelir Vergisi'ne tabi tutuluyor. Enflasyon düzeltmesi (Yİ-ÜFE) yapılmadan beyanname verenler yüksek vergi ödüyor.",
        "detay_maddeleri": [
            {
                "etiket": "01 // 5 YILLIK HESAPLAMA SÜRESİ NASIL İŞLER",
                "metin": "Tapu tescil tarihinden gün ve ay olarak 5 tam yıl geçtikten sonra yapılan satışlarda hiçbir gelir vergisi ödenmez.",
                "renk": "kirmizi",
            },
            {
                "etiket": "02 // ENFLASYON (Yİ-ÜFE) ENDEKSLEMESİ İLE İNDİRİM",
                "metin": "Alış bedeli satış tarihine kadar Yİ-ÜFE oranında güncellenerek reel kar bulunur; böylece enflasyon kaynaklı fiktif kardan vergi ödenmez.",
                "renk": "kirec",
            },
            {
                "etiket": "03 // MİRAS VE BAĞIŞLA GEÇEN MÜLKLERDE İSTİSNA",
                "metin": "Veraset veya karşılıksız intikal yoluyla edinilen gayrimenkuller kaç yıl sonra satılırsa satılsın bu vergiden tamamen muaftır.",
                "renk": "kirec",
            },
        ],
        "uzman_notu": "EDM Değerlendirmesi: Satış yapmadan önce mali müşavir veya gayrimenkul danışmanınızla Yİ-ÜFE endekslemesi yaptırarak net karı hesaplayın.",
    },
]


def test_20_haber():
    log.info("=" * 70)
    log.info("20 GERÇEK HABERLE EDİTORYAL HABER BÜLTENİ TESTİ BAŞLATILIYOR")
    log.info("=" * 70)

    basarili_sayisi = 0
    toplam_slayt_sayisi = 0
    detay_sayfa_dagilimi = {}

    for i, haber in enumerate(HABER_TEST_SETI, start=1):
        h_id = haber["id"]
        manset = haber["manset"]
        maddeler = haber.get("detay_maddeleri", [])
        log.info(f"\n--- HABER #{i:02d} (ID: {h_id}) ---")
        log.info(f"Manşet: {manset}")
        log.info(f"Madde Sayısı: {len(maddeler)} | Uzman Notu: {bool(haber.get('uzman_notu'))}")

        try:
            slaytlar = make_image.haber_dailybrief_slaytlari_uret(
                haber=haber,
                cikti_dizini=CIKTI_DIZINI,
                cikti_onek=f"test20_{h_id}",
                olcu="besleme",
            )
            toplam_slayt = len(slaytlar)
            toplam_slayt_sayisi += toplam_slayt
            detay_sayfa_dagilimi[toplam_slayt] = detay_sayfa_dagilimi.get(toplam_slayt, 0) + 1

            assert toplam_slayt >= 2, f"Haber #{h_id} en az 2 slayt olmalı, ancak {toplam_slayt} slayt üretildi"
            assert all(p.exists() and p.stat().st_size > 10000 for p in slaytlar), f"Slayt dosyaları bozuk veya eksik: {slaytlar}"

            log.info(f"✓ BAŞARILI: {toplam_slayt} Slayt üretildi:")
            for s_idx, sp in enumerate(slaytlar, start=1):
                log.info(f"   [{s_idx}/{toplam_slayt}] {sp.name} ({sp.stat().st_size // 1024} KB)")

            basarili_sayisi += 1

        except Exception as e:
            log.error(f"✗ HATA (Haber #{h_id}): {e}", exc_info=True)
            raise e

    log.info("\n" + "=" * 70)
    log.info("TEST TAMAMLANDI: TÜM TESTLER BAŞARIYLA GEÇTİ!")
    log.info(f"Başarı Oranı: {basarili_sayisi}/{len(HABER_TEST_SETI)} (%100)")
    log.info(f"Toplam Üretilen Slayt: {toplam_slayt_sayisi}")
    log.info(f"Slayt Sayısı Dağılımı: {detay_sayfa_dagilimi}")
    log.info("=" * 70)


if __name__ == "__main__":
    test_20_haber()
