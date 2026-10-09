# Sözlük kart üretimi: 34 → 730 (en az 2 yıl tekrarsız)

Bu dosya, sözlük kart arşivini alt ajanlarla büyütme işinin planıdır. Oturum kapansa ya da bağlam dolsa bile iş
buradan kaldığı yerden devam eder. Kart kuralları ve neden: `ICERIK-SISTEMI.md` §5.5.2, arşiv: `data/sozluk_kartlari.yaml`.

## Durum (2026-10-09)

- Arşivde 34 kart var; günde bir kartla 34 gün yeter (12 Kasım'da biter). Hedef 730 (2 yıl × günde 1): **696 eksik**.
- `sozluk_arsivi.BEKLEME_GUN = 730` (aynı kart 2 yıl dolmadan tekrar gelmez), `HEDEF_KART = 730`; hiç yayınlanmamış kart 14'e
  inince Telegram'a hatırlatma gider. Kart bitince sözlük modelle üretilip onaya düşer (otomatik yayın YOK).
- Kullanıcı kararı (2026-10-09): kartları **Claude alt ajanlarla** üretmek.
- **ENGEL:** hesap planı Pro; haftalık limit %99 doluydu (sıfırlanma 13 Ekim 2026 06:00 UTC = 09:00 TR). Ajanları başlatmadan
  önce `mcp__ccd_session_mgmt__get_usage` ile bak: haftalık ve 5 saatlik pencerede en az %50 boşluk yoksa BAŞLATMA; yarıda
  kalan dalga hem kartları hem oturumu kilitler. 12 Kasım'a kadar vakit var, sıfırlanmayı beklemek güvenli.

## Süreç: yazar → bağımsız inceleme → birleştirme

1. **Pilot:** tek yazar ajan, küçük bir alan (ör. A07 Kadastro, 6 kart). Araçlar ve talimat uçtan uca doğrulanır.
2. **Dalga:** aynı anda en çok 10 yazar. Her yazar yalnız kendi `data/sozluk_taslak/<alan>.yaml` dosyasına yazar.
3. **İnceleme:** her taslağı, onu yazmayan ayrı bir inceleme ajanı (opus) kanun metnine karşı iddia iddia sınar; düzeltir ya da reddeder.
4. **Birleştirme:** yalnız `inceleme: onay` kartlar, doğrulayıcıdan geçenler arşive kod (SZ-035…) alarak eklenir; tekrarlar atılır.
5. **Kapı:** `python -m unittest discover -s tests -t .`, `scripts/gorsel_denetim.py`, commit, push, CI yeşil. Her dalga ayrı commit.
6. Dalga sonunda `scripts/hazirla.py --durum` kalan stoğu yazar.

Hakem (Gemini) geçişi yalnız orkestratörde, ücretsiz kotayı gözeterek; yazarlar `--hakem` kullanmaz.

## Yazılacak araçlar (henüz YOK; pilottan önce yapılır)

1. `scripts/kanun_oku.py`: `madde "<atıf>"` (atıftaki maddelerin TAM metni; aralık sınırı yok), `ara <kanun no> "<kelime>"…`
   (madde no + bağlam), `kanunlar`. Madde metninin sonundaki bir sonraki maddenin başlığı ayrıca işaretlenir.
2. `scripts/sozluk_kart_dogrula.py <taslak.yaml>…`: yapı (`kart_yapisal_sorunlari`), tekrar (arşiv + diğer taslaklar +
   dosya içi, aksan/boşluk gözetmeden), kanun metni (`kart_kanun_durumu` taze olmalı, atıf eksiksiz çözülmeli), kapı
   (`dogrula.denetle` UYARISIZ), iki ölçüde çizim (TasmaHatasi yok), cümle başına sözcük kökü örtüşmesi (yalnız ipucu).
   Çıkış kodu 1 = sorun var. `--json`, `--hakem` (yalnız orkestratör).
3. `scripts/sozluk_kart_birlestir.py`: onaylı taslak kartları arşive ekler (kod ataması, sıra, tekrar atma, `--kuru`).
4. `src/mevzuat.py`: yeni kanunlar (`KANUNLAR` + `_ADLAR`; tertip adayları denenir) ve önbelleğe atomik yazma
   (paralel ajanlar aynı dosyayı yazarken yarım okuma olmasın). Dalgadan önce önbellek ısıtılır (ajanlar yalnız okur).
   Eklenecek: 2942 Kamulaştırma, 3621 Kıyı, 4342 Mera, 6831 Orman, 4708 Yapı Denetimi, 488 Damga, 193 GVK, 3065 KDV,
   6100 HMK, 6325 Arabuluculuk, 2985 Toplu Konut, 1163 Kooperatifler, 2886 Devlet İhale, 5393 Belediye.
5. Testler 730 kartta patlamasın: render/geometri/süpürme testleri tüm arşiv yerine `sozluk_arsivi.temsilci_kartlar()`
   (en uzun tanım/madde/terim + her 25. kart, ~60 kart) üzerinde koşar; tam arşiv taraması doğrulayıcıda yapılır.

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

Çıktı: taslak dosyası ve kısa rapor (yazılan/atılan sayı, değiştirilen terimler, kuşkulu kartlar).

## İnceleme ajanı talimatı (ajana verilecek, opus)

Taslak dosyasındaki her kart için atıf yapılan maddelerin tam metnini oku ve tanım ile her maddeyi tek tek sına: (1) doğrudan metinden mi çıkıyor,
(2) eksik bırakarak yanıltıyor mu (koşul, istisna, süre başlangıcı), (3) gündelik okur için anlaşılır ve Türkçesi doğru mu, (4) terim ile tanım
tutarlı mı, kategori uygun mu, (5) iki madde aynı şeyi mi söylüyor. Düzeltilebiliyorsa kartı yerinde düzelt, doğrulayıcıyı yeniden koş,
`inceleme: duzeltildi` yaz; kusursuzsa `inceleme: onay`; kurtarılamazsa `inceleme: red` ve `inceleme_notu`. Şüphede red. Başka dosyaya dokunma.

## Not: ücretsiz alternatif

Gemini ücretsiz kotası ayrıdır (Claude limitini harcamaz). Taslak üretimi Gemini'ye, yalnız bağımsız inceleme Claude'a bırakılabilir; ama
modelin yazdığı sözlük incelemesinde 12 konunun en az 4'ünde ince yanlış çıktı (bkz. §5.5.2): taslaklar hiçbir koşulda incelemesiz arşive girmez.
