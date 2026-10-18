# Sözlük kart üretimi: 34 → 365 (iki günde bir kartla en az 2 yıl tekrarsız; ilk plan 730'du)

Bu dosya, sözlük kart arşivini alt ajanlarla büyütme işinin planıdır. Oturum kapansa ya da bağlam dolsa bile iş
buradan kaldığı yerden devam eder. Kart kuralları ve neden: `ICERIK-SISTEMI.md` §5.5.2, arşiv: `data/sozluk_kartlari.yaml`.

## Sahiplik: bu iş GEMİNİ ile yürür (kullanıcı kararı, 2026-10-13)

**Claude bu işi sürdürmez.** Kullanıcı Claude'dan yalnız **paylaşım (yayın) altyapısı** ve **Telegram altyapısı** geliştirmesini istedi (bkz. MEMORY.md §11, ARCHITECTURE.md §4 "Claude'un önceliği");
sözlük kartlarının geri kalanı (dalga 2 ve sonrası) Gemini ile yazılacak. Bu belge o yüzden iki işe yarar: (1) Gemini'ye verilecek devir notu, (2) Claude'un dalga 1'e kadar yaptığı işin kaydı.
Aşağıdaki "Claude alt ajan" ve `mcp__ccd_session_mgmt__get_usage` anlatımları geçmiş dönemdir; Gemini için karşılıkları:

- **Araçlar model bağımsızdır** ve olduğu gibi kullanılır: `scripts/kanun_oku.py` (kanun metni), `scripts/sozluk_kart_dogrula.py` (taslak doğrulayıcı), `scripts/sozluk_kart_birlestir.py` (`--kuru` ile deneme),
  kapıda tam test (`python -m unittest discover tests`) ve `scripts/gorsel_denetim.py`. Kanun metinleri `mevzuat-onbellek` dalındandır (bkz. "Pilot sonucu").
- **Değişmeyen kural:** yazan model kendi kartını incelemez. Taslak → doğrulayıcı → **ayrı bir inceleme turu** (ayrı oturum/ayrı istem; kartı yazmayan, kanun metnine iddia iddia bakan) → birleştirme. Doğrulayıcı yeşili doğruluk değildir;
  dalga 1'de yazar çıktısının ancak %62'si, o da çoğunlukla yeniden yazılarak girdi. Modelin yazdığı sözlükte ince yanlışlar çıktığı için (ICERIK-SISTEMI §5.5.2) taslaklar hiçbir koşulda incelemesiz arşive girmez.
- Yazar ve inceleme talimatları (aşağıdaki "Yazar ajan talimatı", "İnceleme ajanı talimatı" ve "Pilot/Dalga 1 sonucu"ndaki dersler, kural 8–12) model adından bağımsız metindir; Gemini'ye olduğu gibi verilebilir.
- **Gemini'nin ilk işi (Claude'dan devir):** A12 (TBK sözleşme kurulması) hiç yazılmadı; reddedilen ama içeriği iyi kira/fesih konuları (KONUT KİRASI KAPSAMI, BELİRSİZ SÜRELİ KİRA, KİRA SÖZLEŞMESİ, ÖNEMLİ SEBEP FESHİ, KİRACININ ÖLÜMÜ)
  md. 347–349, 353, 356 birlikte düşünülerek yeniden yazılacak; SZ-007'ye md. 353 istisnası; md. 339/2 (altı ay ve kısa geçici kiralar) hiçbir kartta yok.
- Gemini ücretsiz kotası ayrıdır; Claude kullanım limiti (aşağıda "Dalga 1" derslerindeki 4 ajan sınırı) onu bağlamaz.
- **Güncel durum (2026-10-18):** arşivde **103 kart**; zamanlanmış sözlük **iki günde bir** onaysız otomatik yayınlanır (94 kart hiç yayınlanmadı ≈188 gün stok), hedef **365 kart**; elle `/sozluk` onay kartıyla düşer;
  sözlük kartı onaylanmazsa havuza girmez, arşive alınır ve konusu iade edilir (yeniden kurmak ucuz; MEMORY.md §10 madde 23). Çalışma düzeni: GEMINI.md.

## Durum (2026-10-18; güncel arşiv sayısı 103 kart, hedef 365)

- **2026-10-18 güncellemesi (Dalga 3 tamamlandı):** A01 (TMK mülkiyetin kapsamı ve kazanılması, 10 kart) ve A02 (TMK mülkiyet kısıtlamaları ve komşuluk, 9 kart) arşive eklendi (`SZ-085`..`SZ-103`). Arşivde **103 kart** var (94'ü hiç yayınlanmamış ≈ 188 gün stok). Hedef 365 (`HEDEF_KART`).
- **2026-10-15 güncellemesi (Dalga 2 tamamlandı):** A12 (TBK sözleşme kurulması, 15 kart) ve A16_revize (md. 339/2 geçici kiralar, md. 346 ek ödeme yasağı, md. 353 dava süresi uzaması, 3 kart) arşive eklendi (`SZ-067`..`SZ-084`). SZ-007'ye md. 353 istisnası işlendi. Arşiv 84 kart olmuştu.
- (Eski, 2026-10-09) Arşivde 34 kart var; günde bir kartla 34 gün yeter (12 Kasım'da biter). Hedef 730 (2 yıl × günde 1): **696 eksik**.
- `sozluk_arsivi.BEKLEME_GUN = 730` (aynı kart 2 yıl dolmadan tekrar gelmez), `HEDEF_KART = 365`; hiç yayınlanmamış kart 14'e
  inince Telegram'a hatırlatma gider. Kart bitince sözlük modelle üretilip onaya düşer (otomatik yayın YOK).
- Kullanıcı kararı (2026-10-09): kartları Claude alt ajanlarla üretmek. **2026-10-13'te değişti: Gemini ile** (yukarıdaki "Sahiplik" bölümü).
- Eski engel notu (geçmiş): Claude hesabının haftalık limiti dolmuştu; ajan başlatmadan önce kullanım boşluğuna bakmak gerekiyordu. Gemini ile çalışırken geçerli değil.

## Pilot sonucu (2026-10-13, A07 Kadastro 3402)

**Kanun metinleri:** Actions → Mevzuat Önbelleği ile 32 kanunun TAMAMI çekildi (14 yeni kanunun tahmini tertipleri de tuttu; hiçbir `KANUNLAR` düzeltmesi gerekmedi).
Dosyalar `mevzuat-onbellek` dalında; oturumda `git fetch origin mevzuat-onbellek` + `git archive FETCH_HEAD | tar -x -C data/mevzuat_onbellek` ile alınır (dizin .gitignore'da).
Her dosya başlığında kanun no geçiyor, boyutlar makul (6217: 5,7 KB … 2004: 418 KB).

**Kartlar:** 8 kart yazıldı (6 + reddedilen 2'nin yerine yeni 2), **4'ü arşive girdi (SZ-035…038)**. Doğrulayıcı ilk taslakta 6/6 yeşildi; bağımsız inceleme (opus) yine de 4 kartı düzeltti, 2'sini reddetti;
yerine yazılan 2 kart da ikinci bağımsız incelemede reddedildi. **Doğrulayıcının yeşili doğruluk değildir**: yapıyı, alıntının birebirliğini ve sayıları sınar; kapsamı, istisnayı ve anlamı yalnız inceleme yakalar.
Maliyet: iki inceleme ≈ 250 bin ajan tokeni (≈ 9 + 5 dk). Dalga planı bu orana göre kurulmalı: ~%50 ret/düzeltme payı + her dalgada ikinci inceleme turu.

| Arşive girdi | Kod | Not |
|---|---|---|
| ASKI İLANI (md. 11) | SZ-035 | düzeltildi: tanımdaki dava cümlesi puf'la aynıydı, "Kanuna göre" → "Kadastro Kanunu gereğince", gerçek + tüzel kişi |
| TESPİTE İTİRAZ (md. 9 ve 11) | SZ-036 | düzeltildi: dava hakkı her itiraz eden için ayrı madde; "askı ilanı" md. 11'den geldiği için atıfa md. 11 eklendi. Terim inceleme sırasında "KADASTRO TESPİTİNE İTİRAZ"dı; başlık tabanına sığmadığı için kısaltıldı (aşağıda) |
| KADASTRO KOMİSYONU (md. 10) | SZ-037 | düzeltildi: sürenin başlangıcı ("geldiği tarihten"), "kanunla mahkemeye bırakılan" kaydı, "intikal" (miras sanılır) kaldırıldı |
| KESİNLEŞME (md. 12) | SZ-038 | düzeltildi: "kesinleşmeden" çift anlamlıydı; on yıl kuralı tek maddede. Terim "KADASTRO KESİNLEŞMESİ"ydi (112 pt); kısaltıldı |

**Reddedilenler ve dersler** (bir sonraki yazar/inceleme talimatına işlendi, aşağıda 8–10):
- *TAPUSUZ TAŞINMAZ (md. 14)*: tapusuz her taşınmazın 20 yıllık zilyetlikle zilyet adına tespit edildiği izlenimini veriyordu; md. 16/17/18 (orta malları, hizmet malları, ormanlar, kamu hizmetine tahsisli yerler, imar planı alanı) bu yoldan çıkarılmış.
- *KAMU MALI VE ZAMANAŞIMI (md. 18)*: "gibi" kapalı listeyi örnek listesine çevirdi; puf'lar tanımı tekrarladı; terim kavram değil konu başlığıydı.
- *TAPU SINIRININ TESPİTİ (md. 20)*: terim kanundaki başlığa uymuyordu ("Kayıt ve belgelerin kapsamını tayin"); "haritasız kayıt" kısaltması kapsamı bozdu ("harita, plan ve krokiye dayanmayan"); D bendi ve sonundaki md. 14/17 yollaması eksikti.
- *İHYA EDİLEN TAŞINMAZ (md. 14 ve 17)*: md. 14'ün asıl şartları (tapusuzluk, 20 yıl zilyetlik, 40/100 dönüm sınırı, belge) kartta yoktu; "Devlet arazisi" gündelik dilde tapulu Hazine arazisini de kapsar; "bu hüküm" yanlış okunabiliyordu.
  → Başka maddelere yollama yapan, kapsam/istisna zinciri taşıyan maddeler (3402 md. 14, 16, 17, 18, 20 gibi) tek kartla doğru anlatılamıyor; bu alanlarda daha basit, tek kuralı olan maddeler seçilmeli.

**Başlık yerleşim tabanı (pilotta kaçan hata):** iki kart doğrulayıcıdan ve incelemeden geçti, ama tam testte düştü: başlık (terim) tek satırda 116-160 pt ya da iki satırda 112-144 pt aralığında yerleşip ≥114 pt olmalı
(`tests/test_sozluk_stres_sabotaj.py`); "KADASTRO TESPİTİNE İTİRAZ" iki satıra bile sığmadı, "KADASTRO KESİNLEŞMESİ" 112 pt'ye düştü. Sorun uzun TEK sözcüktür (KESİNLEŞMESİ 12 harf). Doğrulayıcıya `baslik_sigma_sorunu` eklendi;
artık çizim denetiminde bu da sınanır (testi: `TestBaslikYerlesimTabani`). Yazar kuralı: terim ≤ ~20 karakter, tek sözcük ≤ ~10 harf; sınır durumlarında doğrulayıcıyı çalıştırarak seç.
Kapıda **tam test paketi** şarttır (yalnız doğrulayıcı yetmez).

**Araç düzeltmesi (aynı gün):** `kanun_oku.py ara` ek maddelerdeki ("Ek Madde 6") geçişleri "md. 6" diye etiketliyordu ve `maddelere_bol`/`mevzuat.madde_metni` ek maddeyi normal madde sayıyordu: ek madde atıfı ("ek md. 6") yoktu, ve normal maddesi bulunmayan
numaralar sessizce Ek Madde'nin metnine çözülüyordu (2985 Toplu Konut Kanunu md. 11–17 gibi; mevcut hiçbir atıf etkilenmiyordu). Ayrıca 21 normal maddenin sonuna bir sonraki Ek Madde başlığının "Ek" sözcüğü sızıyordu. Artık ek maddeler ayrı tür:
etiket "ek md. 6", atıf `3402 sayılı Kanun ek md. 6`, anahtar `ek 6` (testler: `TestEkMaddeler`). Eski ve yeni `madde_metni`, 32 kanunun 4375 normal maddesinde karşılaştırıldı: yalnız bu iki fark.

## Dalga 1 sonucu (2026-10-13: A15 kira genel, A16 konut/çatılı işyeri kirası, A20 KMK md. 1–19)

**Arşiv 38 → 66 kart (≈61 günlük stok).** 4 yazar (sonnet) + 4 bağımsız inceleme (opus): 45 taslak karttan **28'i girdi (SZ-039…066), 17'si reddedildi** (%62 kabul). A12 (TBK sözleşme kurulması) hiç yazılamadı, yeniden verilecek.

| Dosya | Alan | Taslak | Onay | Düzeltildi | Red |
|---|---|---|---|---|---|
| A15a | TBK kira, genel (md. 299–321) | 11 | 1 | 7 | 3 |
| A15b | TBK kira, genel (md. 321–338) | 11 | 0 | 6 | 5 |
| A16 | TBK konut/çatılı işyeri kirası (md. 339–378) | 15 | 2 | 7 | 6 |
| A20 | KMK md. 1–19 | 8 | 0 | 5 | 3 |

**Ne yanlış gitti / dersler**
- **Kullanım sınırı:** dört yazar aynı anda çalışırken oturumun kullanım sınırı doldu (sıfırlanma 11:50 UTC) ve hepsi yarıda kesildi; taslaklar kendi doğrulama ve son kontrol adımına gelmeden kaldı (45 karttan 26'sı doğrulayıcıda kırmızı: puf >115 karakter, sığmayan başlık).
  Çözüm: bu taslaklar doğrudan incelemeye verildi (inceleyici biçimi de düzeltti; kararlarını kart kart dosyaya yazdığı için kesinti riski azaldı). **Bir dalgada aynı anda en çok 4 ajan; bir sonraki dalgayı limit sıfırlanınca başlat.**
  İnceleme maliyeti ≈ 700 bin ajan tokeni (4 inceleme: 143–211 bin). Kabul edilen 28 kartın 25'i inceleyici tarafından yeniden yazılarak kurtarıldı; yazar çıktısı tek başına yayına uygun değildi.
- **Doğrulayıcı hatası bulundu:** süre denetimi "md. 319 ayıp" → "319 ay" sayıp **ayıp kartlarını hep engelliyordu** (ayrıca "ayrı", "aynı", "ayrıca", "ayıbı"). `mevzuat._SURE` düzeltildi, testli.
- **Sık ret nedenleri:** (a) ürün kirası ya da konut/çatılı işyeri ayrımını söylemeden genel kural sunmak (ALT KİRA md. 322 ↔ md. 366; KİRACININ İFLASI md. 332 ↔ md. 370; KİRACININ ÖLÜMÜ md. 333 ↔ md. 356); (b) "gibi" ile kapalı liste açmak; (c) tanımı döngüsel yazmak ("…kütüğüne tescil edildiği sicildir"); (d) arşivdeki karta anlamca tekrar (KAT İRTİFAKI SAHİBİ, ÖNCELİKLE SATIN ALMA ↔ ÖNALIM HAKKI); (e) başlığın sığmaması (KAT MÜLKİYETİ KÜTÜĞÜ, KONUT KİRASI KAPSAMI, OLAĞANÜSTÜ KİRA İNDİRİMİ…).
- **Reddedilen ama içeriği iyi olanlar, yeniden yazılırken tüm fesih/bildirim kuralları (md. 347–349, 353, 356) birlikte düşünülmeli:** KONUT KİRASI KAPSAMI (md. 339), BELİRSİZ SÜRELİ KİRA, KİRA SÖZLEŞMESİ (md. 347 "ancak" zinciri), ÖNEMLİ SEBEP FESHİ, KİRACININ ÖLÜMÜ + md. 356.

**Arşivdeki mevcut kartlarla ilgili bulgu (Dalga 2'de tamamlandı):** SZ-007 İHTİYAÇTAN TAHLİYE kartında "dava, sürenin sonundan başlayarak bir ay içinde açılmalıdır" ifadesi vardı. Dalga 2'de puf[0]'a md. 353 uyarınca yazılı bildirimle dava süresinin bir yıl uzaması istisnası eklendi ve mevzuat atfına md. 353 dahil edildi.
**Eksik kapsam (Dalga 2'de tamamlandı):** md. 339/2 uyarınca geçici konut kirası (altı ay veya daha kısa) SZ-082 olarak arşive eklendi.

## Dalga 2 sonucu (2026-10-15: A12 TBK sözleşme kurulması, A16_revize kira tamamlama)

**Arşiv 66 → 84 kart (77'si hiç yayınlanmamış ≈ 154 günlük stok).** Gemini oturumu: 1 yazar + 1 bağımsız inceleme ajanı. 18 taslak karttan **18'i girdi (SZ-067…084), 0 ret** (%100 başarı; 12 doğrudan onay, 6 incelemede yerinde düzeltilerek girdi).

| Dosya | Alan | Taslak | Onay | Düzeltildi | Red | Kod Aralığı |
|---|---|---|---|---|---|---|
| A12 | TBK sözleşmenin kurulması, şekil, gabin, irade sakatlıkları, temsil (md. 1–40) | 15 | 11 | 4 | 0 | SZ-067…081 |
| A16_revize | TBK kira tamamlama (md. 339/2 geçici kira, md. 346 ek ödeme yasağı, md. 353 dava süresi uzaması) | 3 | 1 | 2 | 0 | SZ-082…084 |

**Kartlar ve Notlar:**
- **A12 (15 kart):** SÖZLEŞME KURULMASI (SZ-067), SÜRELİ ÖNERİ (SZ-068), SÜRESİZ ÖNERİ (SZ-069), ÖNERİ SAYILMA (SZ-070), ŞEKİL SERBESTİSİ (SZ-071), YAZILI ŞEKİL (SZ-072), İMZA KURALI (SZ-073), İRADİ ŞEKİL (SZ-074), AŞIRI YARARLANMA (SZ-075), ÖN SÖZLEŞME (SZ-076), ESASLI YANILMA (SZ-077), ALDATMA (SZ-078), KORKUTMA (SZ-079), İRADE BOZUKLUĞU (SZ-080), YETKİSİZ TEMSİL (SZ-081).
- **A16_revize (3 kart):** GEÇİCİ KONUT KİRASI (SZ-082, md. 339/2), EK ÖDEME YASAĞI (SZ-083, md. 346), DAVA SÜRESİ UZAMASI (SZ-084, md. 353).
- **SZ-007 Güncellemesi:** İHTİYAÇTAN TAHLİYE kartı puf[0]'a md. 353 bildirimiyle 1 yıl uzama istisnası eklendi; mevzuat `Türk Borçlar Kanunu md. 350, 353 ve 355` oldu.
- **İnceleme & Doğrulama:** Bağımsız inceleme alt ajanı kanun metinleriyle iddia iddia karşılaştırdı. 6 kartta yerinde hukuki hassasiyet düzeltmeleri yapıldı (Yazılı Şekil'de borç altına girenlerin imzası vurgusu; İmza Kuralı'nda el yazısı şartı; Ön Sözleşme'de asıl sözleşme şekli kuralı; Aldatma'da üçüncü kişi ayrımı; Geçici Konut Kirası'nda doğası gereği şartı; Dava Süresi Uzaması'nda 1 ay yerine davanın açılması için öngörülen süre ifadesi).
- **Tipografi & Denetim:** Başlık yerleşimi kontrol edildi (EK ÖDEME YASAĞI 15 karakter seçildi); `sozluk_kart_dogrula.py` 18/18 temiz; `gorsel_denetim.py` 226 vaka 0 hata; 1204 Python testi ve 73 Worker testi yeşil.

## Dalga 3 sonucu (2026-10-18: A01 TMK mülkiyet kapsamı/kazanılması, A02 TMK mülkiyet kısıtlamaları ve komşuluk)

**Arşiv 84 → 103 kart (94'ü hiç yayınlanmamış ≈ 188 günlük stok).** Gemini oturumu: 1 yazar + 1 bağımsız inceleme ajanı. 19 taslak karttan **19'u girdi (SZ-085…103), 0 ret** (%100 başarı; 19'u incelemede yerinde düzeltilerek girdi).

| Dosya | Alan | Taslak | Onay | Düzeltildi | Red | Kod Aralığı |
|---|---|---|---|---|---|---|
| A01 | TMK mülkiyetin kapsamı, kazanılması, sınırlanması (md. 683–717) | 10 | 0 | 10 | 0 | SZ-085…094 |
| A02 | TMK taşınmaz mülkiyetinin kısıtlamaları ve komşuluk (md. 718–761) | 9 | 0 | 9 | 0 | SZ-095…103 |

**Kartlar ve Notlar:**
- **A01 (10 kart):** MÜLKİYET HAKKI (SZ-085, md. 683), BÜTÜNLEYİCİ PARÇA (SZ-086, md. 684), DOĞAL ÜRÜNLER (SZ-087, md. 685), YARARLANMA ANLAŞMASI (SZ-088, md. 689), PAYLAŞMA İSTEMİ (SZ-089, md. 698), TAŞINMAZ MÜLKİYETİ (SZ-090, md. 704), TESCİL İLKESİ (SZ-091, md. 705), RESMÎ ŞEKİL ŞARTI (SZ-092, md. 706), HEYELAN BÖLGESİ (SZ-093, md. 710), OLAĞAN ZAMANAŞIMI (SZ-094, md. 712).
- **A02 (9 kart):** DİKEY KAPSAM (SZ-095, md. 718), HAKSIZ YAPI (SZ-096, md. 722), ARAZİ DEVRİ İSTEMİ (SZ-097, md. 724), TAŞKIN YAPI (SZ-098, md. 725), TAŞINIR YAPI (SZ-099, md. 728), KOMŞU HAKKI (SZ-100, md. 737), TAŞAN DAL VE KÖKLER (SZ-101, md. 740), MECRA HAKKI (SZ-102, md. 744), ZORUNLU SU HAKKI (SZ-103, md. 761).
- **İnceleme & Düzeltmeler:** Bağımsız inceleme ajanı tüm kartları kanun metinleriyle iddia iddia denetledi. Yapay "AĞAÇ VE DAL SINIRI" terimi kanun lafzındaki "TAŞAN DAL VE KÖKLER" ile değiştirildi ve orman istisnası eklendi. "MECRA GEÇİRME HAKKI" terimi iki satırda 112 pt tabanını aştığı için "MECRA HAKKI" olarak kısaltıldı ve kamulaştırma istisnası eklendi. Paylaşma isteminde "uygun olmayan zaman" yasağı, resmî şekil şartında ölüme bağlı tasarruf istisnası, tescil ilkesinde işgal ve kamulaştırma kapalı listesi tam metinle yazıldı.
- **Tipografi & Denetim:** `sozluk_kart_dogrula.py` 19/19 temiz; `gorsel_denetim.py` 226 vaka 0 hata; JS testleri 73/73 yeşil, sözlük unit testleri 106/106 yeşil.

## Süreç: yazar → bağımsız inceleme → birleştirme

1. **Pilot:** tek yazar ajan, küçük bir alan (ör. A07 Kadastro, 6 kart). Araçlar ve talimat uçtan uca doğrulanır.
2. **Dalga:** aynı anda en çok 10 yazar. Her yazar yalnız kendi `data/sozluk_taslak/<alan>.yaml` dosyasına yazar.
3. **İnceleme:** her taslağı, onu yazmayan ayrı bir inceleme ajanı (opus) kanun metnine karşı iddia iddia sınar; düzeltir ya da reddeder.
4. **Birleştirme:** yalnız `inceleme: onay` kartlar, doğrulayıcıdan geçenler arşive kod (SZ-035…) alarak eklenir; tekrarlar atılır.
5. **Kapı:** `python -m unittest discover -s tests -t .`, `scripts/gorsel_denetim.py`, commit, push, CI yeşil. Her dalga ayrı commit.
6. Dalga sonunda `scripts/hazirla.py --durum` kalan stoğu yazar.

Hakem (Gemini) geçişi yalnız orkestratörde, ücretsiz kotayı gözeterek; yazarlar `--hakem` kullanmaz.

## Araçlar (YAZILDI 2026-10-12; 2026-10-13'te canlı kanun metniyle uçtan uca DENENDİ — bkz. Pilot sonucu)

Yazıldıkları ortamda `www.mevzuat.gov.tr` ağ politikasıyla kapalıydı: tüm testler sahte kanun metniyle çalışıyor. **Pilottan önce, ağı açık
bir ortamda (yerel ya da ağ erişimi verilmiş bulut oturumu):**
1. `python scripts/kanun_oku.py kanunlar --dene` — her kanunu gerçekten çekmeyi dener. ÇEKİLEMEDİ çıkan kanunun tertip adayını
   `src/mevzuat.py › KANUNLAR`ta düzelt (14 yeni kanunun tertipleri tahmindir; yanlış tertip sitede 302 döner).
2. Pilot taslağı (A07, 6 kart) yazılıp aşağıdaki iki komutla denenir; çıktı beklenenden farklıysa araç düzeltilir, dalga başlatılmaz.

| Araç | Ne yapar |
|---|---|
| `python scripts/kanun_oku.py madde "<atıf>"` | atıftaki maddelerin TAM metni (aralık sınırı yok); her maddenin sonunda "BU MADDE BURADA BİTER ▶ sonraki madde: …" işareti |
| `python scripts/kanun_oku.py ara <kanun no> "<kelime>" …` | kelime geçişleri: madde no + bağlam (Türkçe İ/I duyarlı) |
| `python scripts/kanun_oku.py kanunlar [--dene]` | okunabilir kanunlar (14 yeni kanun dahil), önbellek durumu |
| `python scripts/sozluk_kart_dogrula.py <taslak.yaml>…` | yapı → tekrar (arşiv + diğer taslaklar + dosya içi) → kanun (atıf tam okunabilir, alıntı birebir, sayılar maddede) → yayın kapısı → iki ölçüde çizim; cümle başına sözcük kökü örtüşmesi İPUCU. Çıkış 0/1/2. `--json`, `--hakem` (YALNIZ orkestratör), `--kanunsuz`/`--cizimsiz` (hızlı, birleştirme için geçersiz) |
| `python scripts/sozluk_kart_birlestir.py <taslak.yaml>… [--kuru]` | yalnız `inceleme: onay`/`duzeltildi` olup denetimden YENİDEN temiz çıkan kartları arşivin sonuna ekler; kod SZ-035… arşivdeki en büyük numaradan devam eder (pasif/boşluk dahil, yeniden kullanılmaz); başlık yorumlarına dokunmaz; atomik yazar, ardından arşivi yeniden doğrular, tutmazsa eski haline döner |

Taslak biçimi arşivle aynıdır (`kartlar:` listesi) ama `kod` yazılmaz; inceleme ajanı `inceleme: onay|duzeltildi|red` ve `inceleme_notu` ekler.
Kitaplık: `src/kanun_okuma.py`, `src/sozluk_dogrulama.py` (testler: `tests/test_kanun_okuma.py`, `tests/test_sozluk_kart_araclari.py`).

**Güvenceler (testli):**
- Doğrulayıcı ve birleştirici `POSTEDM_TEST_MODU=1` ile başlar: `src.db` içe aktarılırken şemayı göç ettirir ve `data/edm.db`'yi DEĞİŞTİRİR
  (ölçüldü); paralel ajanların depo kopyasında DB'ye dokunmaması gerekir. `--hakem` bunun tek istisnası (`.env` anahtarı ister).
- `mevzuat.kanun_metni` önbelleğe artık atomik yazar: paralel ajanlar aynı kanunu aynı anda çekerken okuyucu yarım metin görmez.
- Çizim/geometri testleri arşivin tamamı yerine `sozluk_arsivi.temsilci_kartlar()` (en uzun tanım/madde/terim/sözcük + her 25. kart,
  ≤60 kartta hepsi) üzerinde koşar; her kartın çizimi zaten arşive girerken doğrulayıcıda sınanır. Yapı, tekrar ve kanun metni testleri
  TÜM kartı tarar (ucuz). `test_sozluk_stres_sabotaj.py` kod bazlı beklentiler içerir (SZ-009 …); 730 kartta gözden geçirilmeli.

## Alan planı (37 alan, ham hedef ~764 → tekrar ve ret sonrası ~700)

Kapsam konuya göredir (madde numaraları yaklaşıktır; yazar `kanun_oku.py ara` ile kesinleştirir). Mevcut 34 terim her alanda yasak.

| Alan | Kapsam | Hedef |
|---|---|---|
| A01 | TMK mülkiyetin kapsamı, kazanılması, sınırlanması (683–717) | 20 |
| A02 | TMK komşuluk, taşkınlık, ağaç/su/sınır, taşınmaz mülkiyetinin sınırlamaları (718–778) | 20 |
| A03 | TMK irtifak hakları, üst hakkı, sükna, taşınmaz yükü (779–850) | 22 |
| A04 | TMK rehin: ipotek ve türleri, ipotekli borç senedi, irat senedi, paraya çevirme (850–…) | 22 |
| A05 | TMK tapu sicili: kütük, şerh, beyan, tescil, yolsuz tescil, tapuya güven (998–1030) | 24 |
| A06 | Tapu Kanunu 2644: işlemler, resmî senet, vekâlet, yabancı, ifraz/tevhid, cins değişikliği | 22 |
| A07 | Kadastro Kanunu 3402: tespit, itiraz, askı, sınır, kesinleşme | 18 |
| A08 | TMK zilyetlik, zamanaşımıyla kazanma, ihya | 14 |
| A09 | TMK aile ve mal rejimleri (edinilmiş mallara katılma, kişisel mal, katkı alacağı) | 24 |
| A10 | TMK miras I: yasal mirasçılar, saklı pay oranları, vasiyet, miras sözleşmesi | 24 |
| A11 | TMK miras II: mirasçılık belgesi, ret, ortaklık, paylaşma, tereke | 22 |
| A12 | TBK genel I: sözleşmenin kurulması, şekil, irade sakatlığı, gabin | 22 |
| A13 | TBK genel II: ifa, temerrüt, imkânsızlık, cezai şart, zamanaşımı | 24 |
| A14 | TBK satış sözleşmesi: ayıp, teslim, ifa, cayma, geri alım | 24 |
| A15 | TBK kira I: kuruluş, bedel, ayıp, kiracı yükümlülükleri, alt kira | 24 |
| A16 | TBK kira II: sona erme, ihtar, fesih, uzama, konut/çatılı işyeri özel hükümleri | 20 |
| A17 | TBK eser sözleşmesi, arsa payı karşılığı, müteahhit, yapı sözleşmeleri | 20 |
| A18 | TBK vekâlet, komisyon, saklama, ödünç, bağışlama | 16 |
| A19 | TBK haksız fiil, sebepsiz zenginleşme, vekâletsiz iş görme | 14 |
| A20 | KMK I (1–19): bağımsız bölüm, ortak yerler, eklenti, arsa payı | 24 |
| A21 | KMK II (20–…): kat malikleri kurulu, aidat, yönetici, denetçi, yükümlülükler | 24 |
| A22 | İmar Kanunu I (1–29): planlar, yetkiler, ruhsat, sorumluluk | 24 |
| A23 | İmar Kanunu II (30–…): iskân, kaçak yapı, yıkım, para cezaları, geçici maddeler | 24 |
| A24 | Yapı Denetimi 4708, Belediye 5393 imar yetkileri | 20 |
| A25 | Afet Riski 6306: riskli yapı/alan, tespit, çoğunluk, kira yardımı | 22 |
| A26 | Kamulaştırma 2942 | 22 |
| A27 | Kıyı 3621, Mera 4342, Orman 6831 | 20 |
| A28 | Toprak Koruma 5403: tarım arazisi, toplulaştırma, tarım dışı kullanım | 14 |
| A29 | Kültür ve Tabiat Varlıkları 2863 | 14 |
| A30 | Emlak Vergisi 1319, Harçlar 492, Damga 488 | 24 |
| A31 | GVK 193 (gayrimenkul sermaye iradı, değer artış kazancı) ve KDV 3065 | 22 |
| A32 | Veraset 7338 ve VUK 213 (tarh, tahakkuk, ziyaı, zamanaşımı) | 22 |
| A33 | Tüketici 6502: konut finansmanı, taksitli satış, devre tatil, ayıp | 20 |
| A34 | İİK 2004: taşınmaz haczi/satışı/ihale, ipotek takibi, kira takibi, tahliye | 24 |
| A35 | HMK 6100 ve Arabuluculuk 6325 (gayrimenkul uyuşmazlıkları) | 18 |
| A36 | Kooperatifler 1163, Toplu Konut 2985, Devlet İhale 2886 | 16 |
| A37 | DASK 6305, yabancılara satış, özel durumlar | 14 |

Dalgalar: A01–A10, A11–A20, A21–A30, A31–A37 (her dalga: yazarlar → inceleme → birleştirme → test → push).

## Yazar ajan talimatı (ajana verilecek)

Amaç: EDM Yapı & Gayrimenkul'ün (Silivri) her gün 12:30'da onaysız yayınlanan "Emlak Sözlüğü" kartları. İnsan okumadan yayınlanır:
hukuki yanlışa sıfır tolerans. Dil Türkçe (ğ ş ı İ doğru), sade, ünlemsiz.

Alanında en az hedef kadar terim seç (anahtar kelime aramasıyla), en bilinen ve emlak/tapu/kira/imar/vergi/finans okuruna yararlı
olanları yaz. Kart alanları (örnek: `data/sozluk_kartlari.yaml`): `terim` (en çok 26 karakter, BÜYÜK HARF), `kategori_kodu`
(`yeni_formatlar.KATEGORI_HARITASI` anahtarlarından), `tanim` (40–260 karakter, tek tanım cümlesi), `puf` (2–3 madde, her biri
15–115 karakter, "bilinmesi gerekenler": koşul, süre, sonuç, istisna), `mevzuat` (atıf; "Türk Medeni Kanunu md. 826, 827 ve 828" ya da
"2942 sayılı Kanun md. 11"; aralık en çok 4 maddeye açılır, fazlasını tek tek yaz), `dayanak_alintisi` (atıf yapılan maddelerden BİREBİR
en az 40 karakterlik tam cümle), `kontrol` (bugünün tarihi). `kod` verme (birleştirmede atanır).

Kurallar:
1. Tanım ve maddeler YALNIZCA atıf yapılan maddelerde yazanı aktarır. Kartta geçen her sayı, süre, oran, çoğunluk ve para tutarı o maddelerde
   bulunmalı. Maddede olmayan istisnayı, usulü, belgeyi, kurumu EKLEME. Para tutarı yazma (yıllık yeniden değerleme ile değişir) ya da
   maddedeki tutarı "kanunda yazan tutar" diye belirt.
2. Eksik bırakarak yanıltma: maddede "ancak", "istisna", "saklıdır" gibi bir koşul varsa karta gir ya da cümleyi daralt.
3. Kanun metni değişmiş olabilir: kendi bilginle değil `scripts/kanun_oku.py` çıktısıyla yaz.
4. Aynı fikri iki maddede tekrarlama; maddeler birbirini tamamlasın. Tanım "X nedir?" sorusunu cevaplasın.
5. Terim tekrarı yok: arşivdeki 34 terim, diğer taslaklar ve kendi dosyan (doğrulayıcı kontrol eder).
6. Yalnız kendi taslak dosyana yaz. Başka dosyayı değiştirme, git kullanma, tüm test paketini koşma, `--hakem` kullanma.
7. `scripts/sozluk_kart_dogrula.py` tamamen yeşil olana kadar düzelt. Sonra her kartı kendin yeniden oku ve kanun metniyle iddia iddia karşılaştır.
   Emin olmadığın kartı at ve başka terim yaz.
8. Kapsam/istisna zinciri olan maddeyi kartlaştırma: madde "ancak", "saklıdır", "hükümleri dışında kalan" ile başka maddelere yolluyorsa ya da kuralın kapsamı başka bir maddede daralıyorsa (pilotta 3402 md. 14, 16, 17, 18, 20), kural tek kartla doğru anlatılamaz. Tek kuralı olan, kendi içinde tamam maddeler seç.
9. Terim kanundaki kavramın ya da madde başlığının kendisi olsun; kısaltma/özel ad uydurma ("haritasız kayıt"). Kanundaki kapalı listeyi "gibi" ile açma. "İntikal", "ihya", "tespit" gibi sözcük gündelik dilde başka anlama geliyorsa tanımda açıkça söyle ya da kullanma.
10. Puf maddesi tanımın bir yarısını tekrar etmez; iki puf aynı cümlenin iki yarısı olmaz. Her puf tek başına doğru ve kapsamı belli olmalı ("kesinleşmeden" gibi çift anlamlı sözcük yok).
11. Başlık (terim) yerleşim tabanına uymalı: en çok iki satır, ≥114 pt. Uzun tek sözcükten ("KESİNLEŞMESİ") ve ~22 karakteri aşan terimden kaçın; doğrulayıcı `çizim (başlık)` uyarısı verirse terimi kısalt.
12. Yoğunluk: tanım ≤ ~200 karakter, tanım + puf toplamı ≤ ~280 karakter olsun; uzun kartın tanım puntosu 40 pt'ye (en yoğun kartta 36 pt'ye) iner ve Instagram'da okunması zorlaşır (dalga 1'de 7 kart 40 pt'ydi).

Çıktı: taslak dosyası ve kısa rapor (yazılan/atılan sayı, değiştirilen terimler, kuşkulu kartlar).

## İnceleme ajanı talimatı (ajana verilecek, opus)

Taslak dosyasındaki her kart için atıf yapılan maddelerin tam metnini oku ve tanım ile her maddeyi tek tek sına: (1) doğrudan metinden mi çıkıyor,
(2) eksik bırakarak yanıltıyor mu (koşul, istisna, süre başlangıcı), (3) gündelik okur için anlaşılır ve Türkçesi doğru mu, (4) terim ile tanım
tutarlı mı, kategori uygun mu, (5) iki madde aynı şeyi mi söylüyor. Düzeltilebiliyorsa kartı yerinde düzelt, doğrulayıcıyı yeniden koş,
`inceleme: duzeltildi` yaz; kusursuzsa `inceleme: onay`; kurtarılamazsa `inceleme: red` ve `inceleme_notu`. Şüphede red. Başka dosyaya dokunma.

## Not: ücretsiz alternatif

Gemini ücretsiz kotası ayrıdır (Claude limitini harcamaz). 2026-10-13 kararıyla taslak üretimi Gemini'dedir; bağımsız inceleme turu da ayrı bir Gemini çalıştırması olmalıdır
(yazanın kendi kartını incelemesi geçerli sayılmaz). Claude'dan inceleme almak isterseniz kullanıcı ayrıca isteyebilir, ama iş akışı buna bağlı değildir. Ancak
modelin yazdığı sözlük incelemesinde 12 konunun en az 4'ünde ince yanlış çıktı (bkz. §5.5.2): taslaklar hiçbir koşulda incelemesiz arşive girmez.
