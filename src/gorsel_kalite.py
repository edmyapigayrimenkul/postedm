"""
gorsel_kalite.py — Görsel Kalite, Netlik ve Çözünürlük Denetim Motoru.
Instabot / Daily Brief mimarisinden uyarlanmıştır.

Bu modül, Instagram Feed (1080x1350, 4:5) ve Story/Reels (1080x1920, 9:16) formatlarında
kullanılacak tüm fotoğrafların piksel yoğunluğunu, netliğini ve kalitesini denetler.

Temel Kurallar:
  1. Asla dikey kırpmada dijital büyütme (upscale) ile piksellenen fotoğraf kullanılmaz.
  2. Sahte büyütülmüş (yapay 1080p), bulanık veya düşük bitrate'li TV ekran görüntüleri
     Laplacian varyans filtresi ile elenir.
  3. Minimum dosya ve piksel yoğunluğu karşılanmayan görseller reddedilerek bir sonraki
     katmana (HD Web Basın Fotoğrafı, Wikimedia 4K, Pexels 4K veya AI) geçilir.
  4. Belge / Tablo / Taranmış İlan Formu Filtresi: Emlak/arsa/imar haberlerinde resmi kurum
     sitelerinin verdiği taranmış beyaz PDF, tablo veya ilan formları (Doygunluk <= 15 &
     Parlaklık >= 175) otomatik elenir.
"""

from __future__ import annotations

import logging
from typing import Any, Tuple
from PIL import Image, ImageFilter, ImageStat

log = logging.getLogger(__name__)

# Minimum kabul edilebilir netlik (Laplacian varyansı)
ASGARI_NETLIK_PUANI = 35.0

# 4:5 ve 9:16 için asgari hedef ölçüler
HEDEF_GENISLIK = 1080
HEDEF_YUKSEKLIK_FEED = 1350
HEDEF_YUKSEKLIK_STORY = 1920


def kirpma_olcegi_hesapla(
    genislik: int,
    yukseklik: int,
    hedef_g: int = HEDEF_GENISLIK,
    hedef_y: int = HEDEF_YUKSEKLIK_FEED,
) -> float:
    """
    Fotoğraf hedef dikey orana (örn. 4:5 veya 9:16) merkezden kırpıldığında,
    kırpılan alanın hedef tuvale göre gerçek piksel ölçeğini (yoğunluğunu) hesaplar.
    """
    if genislik <= 0 or yukseklik <= 0:
        return 0.0

    hedef_oran = hedef_g / hedef_y
    foto_oran = genislik / yukseklik

    if foto_oran > hedef_oran:
        kirpilan_genislik = yukseklik * hedef_oran
        kirpilan_yukseklik = yukseklik
    else:
        kirpilan_genislik = genislik
        kirpilan_yukseklik = genislik / hedef_oran

    olcek = min(kirpilan_genislik / hedef_g, kirpilan_yukseklik / hedef_y)
    return round(olcek, 3)


def netlik_puani(img: Image.Image) -> float:
    """
    Pillow tabanlı Laplacian kenar varyansı ile görselin gerçek netlik ve keskinliğini ölçer.
    Yapay olarak büyütülmüş, bulanık veya aşırı sıkıştırılmış görseller düşük puan alır.
    """
    try:
        w, h = img.size
        if max(w, h) > 1000:
            oran = 1000.0 / max(w, h)
            test_img = img.resize((int(w * oran), int(h * oran)), Image.BILINEAR)
        else:
            test_img = img

        gray = test_img.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        stat = ImageStat.Stat(edges)
        varyans = stat.var[0] if stat.var else 0.0
        return float(varyans)
    except Exception as e:
        log.debug("Netlik puanı hesaplanamadı: %s", e)
        return 100.0


def gorsel_kalite_denetle(
    img: Image.Image,
    dosya_boyutu_kb: float = 0.0,
    hedef_g: int = HEDEF_GENISLIK,
    hedef_y: int = HEDEF_YUKSEKLIK_FEED,
    asgari_olcek: float = 0.45,
    asgari_netlik: float = ASGARI_NETLIK_PUANI,
) -> Tuple[bool, str]:
    """
    Görselin yayın kalitesi standartlarını karşılayıp karşılamadığını denetler.
    Döner: `(uygun_mu, aciklama)`
    """
    w, h = img.size

    # 1. Asgari Mutlak Boyut Denetimi (16:9 HD 1200x675 / 1280x720 / 1920x1080 ve dikey portreleri kapsar)
    if (w < 800 or h < 450) and not (w >= 600 and h >= 600):
        return False, f"Mutlak çözünürlük çok düşük: {w}x{h} px (asgari 800x450 px gerekli)"

    # 2. Dikey Kırpma Piksel Yoğunluğu (Crop Density)
    olcek = kirpma_olcegi_hesapla(w, h, hedef_g, hedef_y)
    if olcek < asgari_olcek:
        return (
            False,
            f"Dikey kırpmada aşırı piksel kaybı ({olcek}x < {asgari_olcek}x, {w}x{h} px)",
        )

    # 3. Dosya Boyutu ve Bitrate Denetimi
    piksel_mp = (w * h) / 1_000_000.0
    if dosya_boyutu_kb > 0:
        if piksel_mp >= 1.5 and dosya_boyutu_kb < 70:
            return False, f"Aşırı JPEG sıkıştırma artefaktı ({dosya_boyutu_kb:.1f} KB / {piksel_mp:.1f} MP)"

    # 4. Laplacian Netlik ve Keskinlik Denetimi
    puan = netlik_puani(img)
    if puan < asgari_netlik:
        return False, f"Görsel bulanık veya yapay büyütülmüş (Netlik puanı: {puan:.1f} < {asgari_netlik})"

    # 5. Belge / Tablo / Taranmış İlan Formu Denetimi (Scanned Document Filter)
    try:
        stat_hsv = ImageStat.Stat(img.convert("HSV"))
        stat_l = ImageStat.Stat(img.convert("L"))
        sat_mean = stat_hsv.mean[1] if len(stat_hsv.mean) > 1 else 100.0
        lum_mean = stat_l.mean[0] if stat_l.mean else 100.0
        if sat_mean < 15.0 and lum_mean > 175.0:
            return (
                False,
                f"Görsel bir belge/tablo taraması veya düz beyaz zeminli metin belgesi (Doygunluk: {sat_mean:.1f}, Parlaklık: {lum_mean:.1f})",
            )
    except Exception as e:
        log.debug("Belge denetiminde hata: %s", e)

    # 6. Haber Sitesi / TV Kanalı Şerit ve Ticker Bandı Filtresi
    bant_var, bant_aciklama = haber_banti_var_mi(img)
    if bant_var:
        return False, bant_aciklama

    return True, f"Kalite onaylandı (Ölçek: {olcek}x, Netlik: {puan:.1f}, {w}x{h} px)"


def dhash_hesapla(img: Image.Image, hash_boyutu: int = 8) -> str:
    """Pillow tabanlı 64-bit fark (difference) hash hesaplar."""
    try:
        resized = img.convert("L").resize((hash_boyutu + 1, hash_boyutu), Image.Resampling.LANCZOS)
        pixels = list(resized.get_flattened_data()) if hasattr(resized, "get_flattened_data") else list(resized.getdata())
        diff = []
        for row in range(hash_boyutu):
            for col in range(hash_boyutu):
                p_left = pixels[row * (hash_boyutu + 1) + col]
                p_right = pixels[row * (hash_boyutu + 1) + col + 1]
                diff.append(p_left > p_right)

        decimal_val = 0
        hex_parts = []
        for idx, bit in enumerate(diff):
            if bit:
                decimal_val += 1 << (idx % 4)
            if (idx % 4) == 3:
                hex_parts.append(hex(decimal_val)[2:])
                decimal_val = 0
        return "".join(hex_parts)
    except Exception as e:
        log.debug("dHash hesaplanamadı: %s", e)
        return ""


def dhash_mesafesi(h1: str, h2: str) -> int:
    """İki dHash arasındaki Hamming mesafesini (farklı bit sayısını) hesaplar."""
    if not h1 or not h2 or len(h1) != len(h2):
        return 64
    try:
        return bin(int(h1, 16) ^ int(h2, 16)).count("1")
    except (ValueError, TypeError):
        return 64


def haber_banti_var_mi(img: Image.Image) -> Tuple[bool, str]:
    """Haber siteleri veya TV kanallarının alt/üst 'SON DAKİKA' / 'FLAŞ' şeridini denetler."""
    w, h = img.size
    if w < 200 or h < 100:
        return False, ""

    try:
        # Orta gövde rengi (referans: tüm resim tek renkse bant değil düz zemin sayılır)
        orta = img.crop((0, int(h * 0.25), w, int(h * 0.75)))
        st_orta = ImageStat.Stat(orta)
        or_mean, og_mean, ob_mean = st_orta.mean[:3]

        # Alt %8'lik şerit analizi
        alt_serit = img.crop((0, int(h * 0.92), w, h))
        stat_rgb = ImageStat.Stat(alt_serit)
        stat_hsv = ImageStat.Stat(alt_serit.convert("HSV"))
        r_mean, g_mean, b_mean = stat_rgb.mean[:3]
        sat_mean = stat_hsv.mean[1] if len(stat_hsv.mean) > 1 else 0

        # Kırmızı haber bandı (AA/NTV/Habertürk/TRT): Gövdeden farklı, kırmızı baskın ve doygun
        if r_mean > 160 and g_mean < 80 and b_mean < 80 and sat_mean > 140:
            if abs(r_mean - or_mean) > 35 or abs(g_mean - og_mean) > 35:
                return True, "Alt kısımda kırmızı haber/ticker bandı tespit edildi"

        # Mavi haber bandı: Gövdeden farklı, mavi baskın ve doygun
        if b_mean > 160 and r_mean < 70 and sat_mean > 140:
            if abs(b_mean - ob_mean) > 35 or abs(r_mean - or_mean) > 35:
                return True, "Alt kısımda mavi haber/ticker bandı tespit edildi"

        # Üst %7'lik şerit analizi
        ust_serit = img.crop((0, 0, w, int(h * 0.07)))
        stat_u_rgb = ImageStat.Stat(ust_serit)
        stat_u_hsv = ImageStat.Stat(ust_serit.convert("HSV"))
        ur, ug, ub = stat_u_rgb.mean[:3]
        u_sat = stat_u_hsv.mean[1] if len(stat_u_hsv.mean) > 1 else 0
        if ur > 160 and ug < 80 and ub < 80 and u_sat > 140:
            if abs(ur - or_mean) > 35 or abs(ug - og_mean) > 35:
                return True, "Üst kısımda kırmızı haber bandı tespit edildi"
    except Exception as e:
        log.debug("Haber bandı denetiminde hata: %s", e)

    return False, ""


def kristal_netlestir(img: Image.Image) -> Image.Image:
    """Fotoğrafa ince, profesyonel editoryal keskinlik kazandırır."""
    return img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=110, threshold=2))


def akilli_odak_x(img: Image.Image) -> float:
    """Yatay fotoğraflarda kenar enerjisine göre yatay ağırlık merkezini hesaplar."""
    try:
        w, h = img.size
        if w <= h:
            return 0.5
        thumb = img.convert("L").resize((128, max(1, int(128 * h / w))))
        edges = thumb.filter(ImageFilter.FIND_EDGES)
        tw, th = thumb.size
        pix = edges.load()
        energies = [sum(pix[x, y] for y in range(th)) for x in range(tw)]
        toplam = sum(energies)
        if toplam <= 0:
            return 0.5
        mx = sum(x * e for x, e in enumerate(energies)) / (toplam * (tw - 1))
        return max(0.25, min(0.75, round(mx, 3)))
    except Exception:
        return 0.5

