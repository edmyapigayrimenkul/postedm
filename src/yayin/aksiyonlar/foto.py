"""Fotoğraf özelleştirme: değiştir / saf editoryal / stok / AI / gerçek / ilk / 3 aday sunma / aday seçimi.

2026-10-13: `foto_adaylar` ("Başka Fotoğraf Bul → 3 aday") eski yayinla.py'de HİÇ çalışmıyordu: main() içinde daha aşağıda yapılan
`from src import make_image` bu adı fonksiyon boyunca YEREL değişken yapıyor, aday dalı ona atanmadan önce erişince
`UnboundLocalError` veriyordu. Artık `make_image` modül düzeyinde içe aktarılır; altın çıktı testi bu senaryoyu bilinçli olarak güncellendi.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict

from ... import config, db, make_image, telegram_bot
from ..baglam import Istek
from ..icerik import haber_taze

log = logging.getLogger(__name__)


def _adaylari_sun(haber: Dict[str, Any], ref_id: str) -> bool:
    """3 farklı kapak adayı üretip Telegram'a sunar. Hiç aday üretilemezse False (çağıran mevcut akışa düşer)."""
    c_dir = config.yol_al("data/output/adaylar")
    c_dir.mkdir(parents=True, exist_ok=True)
    aday_slaytlari = []
    etiketler = []

    # 1. Aday: Gerçek / Kardeş Haber Fotoğrafı
    h1 = dict(haber)
    h1["foto_kaynak"] = "gercek"
    h1.pop("saf_editoryal", None)
    p1 = c_dir / f"aday_{ref_id}_1.jpg"
    make_image.haber_dailybrief_slayti_ciz(h1, cikti_yolu=p1, sayfa_no="1/3", olcu="story")
    if p1.exists():
        aday_slaytlari.append(p1)
        etiketler.append("1️⃣ Basın / Kardeş Haber Görseli")

    # 2. Aday: Mimari Stok Fotoğrafı (Pexels)
    h2 = dict(haber)
    h2["foto_kaynak"] = "stok"
    h2.pop("saf_editoryal", None)
    p2 = c_dir / f"aday_{ref_id}_2.jpg"
    make_image.haber_dailybrief_slayti_ciz(h2, cikti_yolu=p2, sayfa_no="2/3", olcu="story")
    if p2.exists():
        aday_slaytlari.append(p2)
        etiketler.append("2️⃣ Mimari Stok Fotoğraf")

    # 3. Aday: EDM Kurumsal Mimari Pafta Tasarımı
    h3 = dict(haber)
    h3["saf_editoryal"] = True
    h3.pop("foto_kaynak", None)
    p3 = c_dir / f"aday_{ref_id}_3.jpg"
    make_image.haber_dailybrief_slayti_ciz(h3, cikti_yolu=p3, sayfa_no="3/3", olcu="story")
    if p3.exists():
        aday_slaytlari.append(p3)
        etiketler.append("3️⃣ EDM Kurumsal Pafta Tasarımı")

    if not aday_slaytlari:
        return False

    telegram_bot.slaytlari_gonder(aday_slaytlari, etiketler)
    secim_butonlari = [
        [
            {"text": "1️⃣", "callback_data": f"gorsel_sec:1:{ref_id}"},
            {"text": "2️⃣", "callback_data": f"gorsel_sec:2:{ref_id}"},
            {"text": "3️⃣", "callback_data": f"gorsel_sec:3:{ref_id}"},
        ],
        [
            {"text": "🔄 Başka adaylar", "callback_data": f"foto_adaylar:{ref_id}"},   # Worker `foto_degistir:<id>` işlemez
            {"text": "↩️ Mevcut Görsel Kalsın", "callback_data": "kurtar_menu:2"},
        ],
    ]
    telegram_bot.mesaj_gonder(
        f"🎨 <b>3 Alternatif Kapak Görseli (#{ref_id})</b>\n\n"
        f"1️⃣ Basın / Kardeş Haber Görseli\n"
        f"2️⃣ Mimari Stok Fotoğraf (Pexels)\n"
        f"3️⃣ EDM Kurumsal Pafta Tasarımı\n\n"
        f"Beğendiğin numaraya basarak tek tıkla uygulayabilirsin.",
        butonlar=secim_butonlari,
    )
    return True


def foto(istek: Istek) -> None:
    tur, ref_id, hedef = istek.tur, istek.ref_id, istek.hedef
    if tur not in ("haber", "reels"):
        return
    haber = haber_taze(ref_id)
    if not haber:
        return
    detay = json.loads(haber["detay_metni"]) if haber.get("detay_metni") else {}

    # İlk görsel URL'sini yedekle (asla kaybolmasın)
    if not detay.get("ilk_gorsel_url") and haber.get("gorsel_url"):
        detay["ilk_gorsel_url"] = haber["gorsel_url"]

    # 3 Farklı Aday Sunma İstemi
    if hedef == "foto_adaylar" and _adaylari_sun(haber, ref_id):
        return

    # Aday Seçimi Yapıldıysa
    if hedef.startswith("gorsel_sec:"):
        secilen = hedef.split(":")[1]
        if secilen == "1":
            detay["foto_kaynak"] = "gercek"
            detay.pop("saf_editoryal", None)
        elif secilen == "2":
            detay["foto_kaynak"] = "stok"
            detay.pop("saf_editoryal", None)
        elif secilen == "3":
            detay["saf_editoryal"] = True
            detay.pop("foto_kaynak", None)
        detay["foto_degistir"] = True
    elif hedef == "foto_ilk":
        detay.pop("foto_kaynak", None)
        detay.pop("saf_editoryal", None)
        detay.pop("foto_degistir", None)
        detay.pop("odak_x_yuzde", None)
        detay.pop("foto_sira", None)
        if detay.get("ilk_gorsel_url"):
            detay["gorsel_url"] = detay["ilk_gorsel_url"]
        for p_dir in (config.yol_al("data/output/gonderiler"), config.yol_al("data/output")):
            cp = p_dir / f"haber_foto_{ref_id}.jpg"
            if cp.exists():
                try:
                    cp.unlink()
                except OSError:
                    pass
    elif hedef in ("foto_odak:sol", "foto_odak:orta", "foto_odak:sag"):
        if hedef == "foto_odak:sol":
            detay["odak_x_yuzde"] = 20
        elif hedef == "foto_odak:sag":
            detay["odak_x_yuzde"] = 80
        else:
            detay["odak_x_yuzde"] = 50
    elif hedef == "foto_editoryal":
        detay["saf_editoryal"] = True
        detay.pop("foto_kaynak", None)
    elif hedef in ("foto_stok", "foto_ai", "foto_gercek", "foto_degistir"):
        detay.pop("saf_editoryal", None)
        detay["foto_sira"] = int(detay.get("foto_sira") or 0) + 1
        if hedef == "foto_stok":
            detay["foto_kaynak"] = "stok"
        elif hedef == "foto_ai":
            detay["foto_kaynak"] = "ai"
        elif hedef == "foto_gercek":
            detay["foto_kaynak"] = "gercek"
        detay["foto_degistir"] = True
    else:
        detay["foto_degistir"] = True

    db.haber_guncelle(int(ref_id), detay_metni=json.dumps(detay, ensure_ascii=False), slayt_yollari=None, slayt_urlleri=None, video_yolu=None)
    if tur == "reels":
        telegram_bot.reels_hazirla_ve_sun()
    else:
        telegram_bot.haber_onayina_sun(int(ref_id))
    ad = "Reels Videosu" if tur == "reels" else "Haber"
    telegram_bot.mesaj_gonder(f"🖼️ <b>{ad} #{ref_id} görseli güncellendi ({hedef}) ve yeni önizleme sunuldu.</b>")
