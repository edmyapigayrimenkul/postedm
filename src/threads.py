"""
threads.py — Meta Threads API Yayın Modülü
Instabot / Daily Brief mimarisinden uyarlanmıştır.

Metin, tekil görsel ve çoklu slayt (Carousel) paylaşımları yapar.

ÖNEMLİ SAHA TECRÜBELERİ (instabot bulguları):
1. 2207052 / 2207003 ("An unknown error occurred"): Meta'nın medya işleme hattı görseli
   hemen indiremediğinde HTTP 400 altında bu kodları döner. 15 saniye bekleyip tekrar
   denendiğinde kendiliğinden geçer.
2. CONTAINER_ARASI_SANIYE: Threads art arda gelen medya isteklerini reddeder; carousel
   öğeleri arasında 12-15 sn aralık bırakmak zorunludur.
3. 4279009 ("Media Not Found"): Konteyner FINISHED olduktan hemen sonra publish çağrıldığında
   oluşan yarış durumu. Publish öncesi 2 sn bekleme bunu önler.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from . import config, filtre

log = logging.getLogger(__name__)

THREADS_TABAN = "https://graph.threads.net/v1.0"
GECICI_HATALAR = {429, 500, 502, 503, 504}
GECICI_ALT_KODLAR = {2207003, 2207032, 2207052}
MEDYA_BEKLEME_SANIYE = 15
CONTAINER_ARASI_SANIYE = 12
PUBLISH_ONCESI_SANIYE = 2
MEDYA_YOK_ALT_KODU = 4279009
AZAMI_DENEME = 5


def _hesap_bilgileri() -> Tuple[str, str]:
    token = config.env_al("THREADS_ACCESS_TOKEN")
    kullanici_id = config.env_al("THREADS_USER_ID")
    return kullanici_id, token


def kullanilabilir_mi() -> bool:
    kid, tok = _hesap_bilgileri()
    return bool(kid and tok)


def _konteyner_olustur(url: str, payload: Dict[str, Any]) -> Optional[str]:
    """
    Threads konteynerini geçici hatalara ve Meta medya indirme gecikmelerine
    (2207003 / 2207052) karşı dayanıklı biçimde oluşturur.
    """
    for deneme in range(1, AZAMI_DENEME + 1):
        try:
            resp = requests.post(url, data=payload, timeout=30)
            if resp.status_code == 200:
                return resp.json().get("id")

            # Hata kodlarını çözümle
            alt_kod = None
            try:
                hata_detay = resp.json().get("error", {})
                alt_kod = hata_detay.get("error_subcode")
            except Exception:
                pass

            if alt_kod in GECICI_ALT_KODLAR:
                log.warning(
                    "Threads geçici medya gecikmesi (subcode %s, %d sn bekleniyor, deneme %d/%d)",
                    alt_kod,
                    MEDYA_BEKLEME_SANIYE,
                    deneme,
                    AZAMI_DENEME,
                )
                time.sleep(MEDYA_BEKLEME_SANIYE)
                continue

            if resp.status_code in GECICI_HATALAR:
                bekle = 3 * deneme
                log.warning("Threads geçici HTTP %d hatası, %d sn sonra tekrar", resp.status_code, bekle)
                time.sleep(bekle)
                continue

            log.warning("Threads konteyner oluşturma başarısız [%d]: %s", resp.status_code, resp.text[:200])
            break
        except requests.RequestException as e:
            log.warning("Threads ağ hatası (deneme %d/%d): %s", deneme, AZAMI_DENEME, e)
            time.sleep(3 * deneme)

    return None


def _konteyner_bekle(creation_id: str, access_token: str, max_bekleme: int = 60) -> bool:
    url = f"{THREADS_TABAN}/{creation_id}"
    params = {"fields": "status", "access_token": access_token}

    baslangic = time.time()
    while time.time() - baslangic < max_bekleme:
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                durum = resp.json().get("status")
                if durum == "FINISHED":
                    # FINISHED ile yayın anı arasındaki küçük yarış durumunu önle (instabot 4279009 dersi)
                    time.sleep(PUBLISH_ONCESI_SANIYE)
                    return True
                elif durum == "ERROR":
                    log.error("Threads konteyner hatası: %s", resp.text)
                    return False
        except Exception as e:
            log.warning("Threads durum sorgulama hatası: %s", e)
        time.sleep(3)
    return False


def _yayina_al(creation_id: str, kullanici_id: str, access_token: str) -> Optional[str]:
    url = f"{THREADS_TABAN}/{kullanici_id}/threads_publish"
    payload = {"creation_id": creation_id, "access_token": access_token}

    for deneme in range(1, 4):
        try:
            resp = requests.post(url, data=payload, timeout=25)
            if resp.status_code == 200:
                post_id = resp.json().get("id")
                log.info("Threads yayını başarılı! ID: %s", post_id)
                return post_id

            # Media Not Found (4279009) geçici işleme gecikmesi olabilir
            alt_kod = None
            try:
                alt_kod = resp.json().get("error", {}).get("error_subcode")
            except Exception:
                pass

            if alt_kod == MEDYA_YOK_ALT_KODU:
                log.warning("Threads 4279009 Media Not Found, 4 sn bekleniyor (deneme %d/3)", deneme)
                time.sleep(4)
                continue

            if resp.status_code in GECICI_HATALAR:
                time.sleep(3 * deneme)
                continue

            log.warning("Threads yayınlama denemesi %d başarısız: %s", deneme, resp.text[:200])
            break
        except Exception as e:
            log.error("Threads yayınlama hatası (deneme %d): %s", deneme, e)
            time.sleep(3 * deneme)
    return None


def paylas(metin: str, gorsel_urlleri: Optional[List[str]] = None) -> Optional[str]:
    """Threads'te paylaşım yapar (Salt metin, tek görsel veya çoklu slayt)."""
    kullanici_id, token = _hesap_bilgileri()
    if not kullanici_id or not token:
        log.warning("Threads kimlik bilgileri eksik (.env kontrol edin).")
        return None

    # Markdown yıldızlarını ve literal kaçış dizilerini temizle
    temiz_metin = filtre.markdown_temizle(metin)
    if len(temiz_metin) > 500:
        # Threads API katı 500 karakter sınırına sahiptir; kelime sınırından güvenli kırp
        kirpilmis = temiz_metin[:496]
        son_bosluk = kirpilmis.rfind(" ")
        if son_bosluk > 400:
            temiz_metin = kirpilmis[:son_bosluk] + "..."
        else:
            temiz_metin = kirpilmis + "..."
    url = f"{THREADS_TABAN}/{kullanici_id}/threads"

    # 1. Salt Metin Paylaşımı
    if not gorsel_urlleri:
        payload = {"media_type": "TEXT", "text": temiz_metin, "access_token": token}
        creation_id = _konteyner_olustur(url, payload)
        if creation_id:
            return _yayina_al(creation_id, kullanici_id, token)
        return None

    # 2. Tek Görsel
    if len(gorsel_urlleri) == 1:
        payload = {
            "media_type": "IMAGE",
            "image_url": gorsel_urlleri[0],
            "text": temiz_metin,
            "access_token": token,
        }
        creation_id = _konteyner_olustur(url, payload)
        if creation_id and _konteyner_bekle(creation_id, token):
            return _yayina_al(creation_id, kullanici_id, token)
        return None

    # 3. Carousel (Çoklu Slayt)
    cocuk_idler = []
    for idx, g_url in enumerate(gorsel_urlleri[:10]):
        payload = {
            "media_type": "IMAGE",
            "image_url": g_url,
            "is_carousel_item": "true",
            "access_token": token,
        }
        cid = _konteyner_olustur(url, payload)
        if cid:
            cocuk_idler.append(cid)
        else:
            log.warning("Threads carousel slaytı oluşturulamadı: %s", g_url)

        # Meta'nın ardışık istek sınırlamasına karşı güvenli bekleme
        if idx < len(gorsel_urlleri[:10]) - 1:
            time.sleep(CONTAINER_ARASI_SANIYE)

    if len(cocuk_idler) < 2:
        log.error("Threads carousel için en az 2 geçerli görsel gerekli, %d adet elde edildi.", len(cocuk_idler))
        return None

    payload = {
        "media_type": "CAROUSEL",
        "children": ",".join(cocuk_idler),
        "text": temiz_metin,
        "access_token": token,
    }
    creation_id = _konteyner_olustur(url, payload)
    if creation_id and _konteyner_bekle(creation_id, token):
        return _yayina_al(creation_id, kullanici_id, token)

    return None


def metinleri_slaytlara_dagit(
    haber_veya_detay: Dict[str, Any],
    gorsel_urlleri: List[str],
) -> List[Dict[str, str]]:
    """
    Her slayt görseli için Threads karakter limitine (<= 500) tam uygun,
    parça parça zincir metinleri üretir.
    """
    detay = haber_veya_detay
    if "detay_metni" in detay and isinstance(detay["detay_metni"], str):
        try:
            detay = json.loads(detay["detay_metni"])
        except Exception:
            detay = haber_veya_detay

    toplam_slayt = len(gorsel_urlleri)
    if toplam_slayt == 0:
        return []

    manset_p1 = detay.get("manset_parca_1") or detay.get("manset", "")
    manset_v = detay.get("manset_vurgu", "")
    manset_p2 = detay.get("manset_parca_2", "")
    tam_manset = f"{manset_p1} {manset_v} {manset_p2}".strip()
    spot = detay.get("spot") or detay.get("orijinal_ozet", "")

    parcalar: List[str] = []

    # 1. Kapak Metni
    kapak_metin = f"📌 {tam_manset}\n\n{spot}".strip()
    parcalar.append(kapak_metin)

    # 2. Detay Kartları (slayt_2_detay)
    s2 = detay.get("slayt_2_detay", {})
    if isinstance(s2, dict):
        if "kart_1" in s2:
            k1 = s2["kart_1"]
            txt = f"⚠️ {k1.get('baslik', '')}\n\n{k1.get('aciklama', '')}".strip()
            parcalar.append(txt)
        if "kart_2" in s2:
            k2 = s2["kart_2"]
            txt = f"⚖️ {k2.get('baslik', '')}\n\n{k2.get('aciklama', '')}".strip()
            parcalar.append(txt)
        elif "kartlar" in s2 and isinstance(s2["kartlar"], list):
            for k in s2["kartlar"]:
                txt = f"🔹 {k.get('baslik', '')}\n\n{k.get('aciklama', '')}".strip()
                parcalar.append(txt)

    # 3. Çözüm Adımları (slayt_3_cozum)
    s3 = detay.get("slayt_3_cozum", {})
    if isinstance(s3, dict):
        maddeler = s3.get("maddeler", [])
        for idx, m in enumerate(maddeler, start=1):
            if isinstance(m, dict):
                txt = f"✅ Adım {idx}: {m.get('baslik', '')}\n\n{m.get('aciklama', '')}".strip()
            else:
                txt = f"✅ Adım {idx}: {str(m)}".strip()
            parcalar.append(txt)

    # 4. Kapanış / CTA
    cta = (detay.get("slayt_4_cta") or {}).get("cagri_metni") if isinstance(detay.get("slayt_4_cta"), dict) else ""
    if not cta:
        cta = (detay.get("slayt_4_cta") or {}).get("kaydet_metni") or "Bu bilgiyi daha sonra kullanmak üzere kaydedebilirsiniz."
    kapanis_metin = (
        f"🤝 {cta}\n\n"
        "Siz bu konuda ne düşünüyorsunuz? Yorumlarda buluşalım.\n\n"
        "EDM Yapı & Gayrimenkul · 0536 343 41 97 · Silivri\n"
        "#EDMYapıGayrimenkul #Silivri #Gayrimenkul #Yatırım"
    ).strip()
    parcalar.append(kapanis_metin)

    sayfalar: List[Dict[str, str]] = []
    for i, g_url in enumerate(gorsel_urlleri):
        metin = parcalar[i] if i < len(parcalar) else kapanis_metin
        temiz = filtre.markdown_temizle(metin)
        if len(temiz) > 480:
            temiz = temiz[:475].rsplit(" ", 1)[0] + "..."
        sayfalar.append({"gorsel_url": g_url, "metin": temiz})

    return sayfalar


def zincir_paylas(sayfalar: List[Dict[str, str]]) -> Optional[str]:
    """Zinciri yayınlar, kök gönderi kimliğini döner (geriye uyumlu arayüz)."""
    return zincir_paylas_sonuc(sayfalar)["kok_id"]


def zincir_paylas_sonuc(sayfalar: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Threads'te 4:5 görselleri ve her sayfanın metnini parça parça
    birbirine bağlı bir yanıt zinciri (Thread Chain) olarak yayınlar.

    Kaç parçanın GERÇEKTEN yayınlandığını da döner: {"kok_id", "yayinlanan",
    "toplam", "eksik"}. Önceki arayüz yalnızca kök kimliği dönüyordu ve rapor
    planlanan sayıyı basıyordu — #241'de 6 parçanın 4'ü yayınlandığı halde
    "6 parçalı zincir paylaşıldı ✓" yazdı; eksik olanlar kapanış slaytlarıydı.
    """
    sonuc: Dict[str, Any] = {"kok_id": None, "yayinlanan": 0, "toplam": len(sayfalar or []), "eksik": []}
    kullanici_id, token = _hesap_bilgileri()
    if not kullanici_id or not token:
        log.warning("Threads kimlik bilgileri eksik (.env kontrol edin).")
        return sonuc

    if not sayfalar:
        log.warning("Zincir için sayfa verisi bulunamadı.")
        return sonuc

    url = f"{THREADS_TABAN}/{kullanici_id}/threads"
    kok_id: Optional[str] = None
    onceki_id: Optional[str] = None

    for idx, sayfa in enumerate(sayfalar):
        g_url = sayfa.get("gorsel_url")
        metin = filtre.markdown_temizle(sayfa.get("metin", ""))
        if len(metin) > 500:
            metin = metin[:495].rsplit(" ", 1)[0] + "..."

        payload: Dict[str, Any] = {
            "media_type": "IMAGE",
            "image_url": g_url,
            "text": metin,
            "access_token": token,
        }
        if onceki_id:
            payload["reply_to_id"] = onceki_id

        log.info("Threads zincir parçası %d/%d oluşturuluyor...", idx + 1, len(sayfalar))
        cid = _konteyner_olustur(url, payload)
        if not cid or not _konteyner_bekle(cid, token):
            log.warning("Threads zincir parçası %d hazırlanamadı.", idx + 1)
            sonuc["eksik"].append(idx + 1)
            continue

        yeni_id = _yayina_al(cid, kullanici_id, token)
        if yeni_id:
            if not kok_id:
                kok_id = yeni_id
            onceki_id = yeni_id
            sonuc["yayinlanan"] += 1
            log.info("Threads zincir parçası %d yayınlandı: ID=%s", idx + 1, yeni_id)
        else:
            log.warning("Threads zincir parçası %d yayına alınamadı.", idx + 1)
            sonuc["eksik"].append(idx + 1)

        if idx < len(sayfalar) - 1:
            time.sleep(CONTAINER_ARASI_SANIYE)

    sonuc["kok_id"] = kok_id
    return sonuc


def post_baglantisi(post_id: str) -> str:
    """Threads post bağlantısı — Telegram sonucunda göstermek için."""
    if not post_id:
        return ""
    try:
        token = config.env_al("THREADS_ACCESS_TOKEN")
        if token:
            url = f"https://graph.threads.net/v1.0/{post_id}?fields=permalink&access_token={token}"
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                p = r.json().get("permalink")
                if p:
                    return p
    except Exception:
        pass
    return f"https://www.threads.net/@edmyapigayrimenkul/post/{post_id}"


def zinciri_sil(ana_id: str) -> Tuple[int, int]:
    """Bir Threads zincirini veya tekil gönderiyi tamamen siler (Instabot standardı).

    (silinen, toplam) döner.
    Önce yanıtlar, en sonda ana gönderi silinir.
    """
    _, token = _hesap_bilgileri()
    if not token or not ana_id:
        return 0, 0

    yanitlar: List[str] = []
    try:
        url = f"{THREADS_TABAN}/{ana_id}/conversation"
        r = requests.get(url, params={"access_token": token, "fields": "id"}, timeout=15)
        if r.status_code == 200:
            yanitlar = [x["id"] for x in r.json().get("data", [])]
    except Exception as e:
        log.warning("Threads zinciri okunamadı (%s): %s", ana_id, e)

    hedefler = yanitlar + [ana_id]
    silinen = 0
    for h in hedefler:
        try:
            res = requests.delete(f"{THREADS_TABAN}/{h}", params={"access_token": token}, timeout=15)
            if res.status_code in (200, 204) or (res.json() if res.content else {}).get("success"):
                silinen += 1
                log.info("Threads gönderisi silindi: %s", h)
            else:
                log.warning("Threads gönderisi silinemedi (%s): %s", h, res.text[:120])
        except Exception as e:
            log.warning("Threads silme hatası (%s): %s", h, e)

    return silinen, len(hedefler)


def postu_sil(post_id: str) -> bool:
    """Tekil Threads gönderisini siler."""
    silinen, _ = zinciri_sil(post_id)
    return silinen > 0

