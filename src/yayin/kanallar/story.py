"""Instagram + Facebook Story: her zaman NATIVE 9:16 (1080x1920) kapak; üretilemezse onaylı 4:5 kapak çerçevelenir (yedek yol)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from ... import config, facebook, instagram, upload_image, video
from ..baglam import YayinBaglami
from ..ilerleme import Ilerleme
from ..sonuc import HATA, YAYINDA, KanalSonucu

log = logging.getLogger(__name__)

KANAL = "story"
_HABER_BICIMLERI = ("dailybrief", "haber", "haber_dailybrief")
_YENI_FORMATLAR = ("sozluk", "sozluk_uret", "nedir_dogrusu", "net_cevap", "vaka")


def story_kapagi_uret(detay: dict | None, haber: dict | None, ref_id: object, tur: str,
                      ilan: dict | None = None) -> Path | None:
    """Story için NATIVE 9:16 (1080x1920) kapak; üretilemezse None.

    Eskiden Story, onaylanan 4:5 besleme kapağını alıp `video._cercevele_9_16` ile 9:16'ya
    yerleştiriyordu: haberde fotoğraf kutunun üstünde/altında bulanık bir dolguyla bitiyordu ve
    tam boy fotoğraflı ana kare hiç gitmiyordu (2026-10-07 kullanıcı bildirimi: "story de 4:5'in
    üstü kesik hali gidiyor"). Reels/Shorts videosu zaten native 9:16 çiziliyor; Story de aynı
    kaynaktan çizilir. İçerik (4:5 kutunun içi) besleme ile aynıdır, fark kutunun dışındaki fotoğraftır.

    Onaylanan fotoğraf: `haberler.gorsel_url`. Onay anında `foto_yolu` olarak veriliyordu
    (`telegram_bot.haber_onayina_sun`); yayın anında detay_metni'nde yok, burada aynısı yapılır.
    """
    from ... import make_image, yeni_formatlar
    try:
        if tur == "ilan" and ilan:
            with make_image.tuval("story"):
                yol = make_image.ilan_kapak_slayti_ciz(ilan)
            return Path(yol) if yol and Path(yol).exists() else None
        if not isinstance(detay, dict) or not detay:
            return None
        veri = dict(detay)
        veri.setdefault("id", ref_id)  # sabitlenen fotoğraf adı: haber_foto_<id>.jpg (başka haberin dosyası karışmasın)
        if not (veri.get("foto_yolu") or veri.get("gorsel_yolu")) and isinstance(haber, dict) and haber.get("gorsel_url"):
            veri["foto_yolu"] = haber["gorsel_url"]
        fmt = str(veri.get("format_turu") or "").lower()
        bicim = veri.get("bicim")
        if fmt in ("", "reels", "otorite"):
            fmt = ""  # asıl biçim `bicim` alanında
        onek = f"story_{ref_id}"
        if fmt in _HABER_BICIMLERI or (not fmt and bicim in ("haber", "B5")):
            slaytlar = yeni_formatlar.slaytlari_uret(veri, format_turu="dailybrief", cikti_onek=onek, olcu="story")
            return Path(slaytlar[0]) if slaytlar and Path(slaytlar[0]).exists() else None
        elif fmt in _YENI_FORMATLAR:
            slaytlar = yeni_formatlar.slaytlari_uret(veri, format_turu=fmt, cikti_onek=onek, olcu="story")
            return Path(slaytlar[0]) if slaytlar and Path(slaytlar[0]).exists() else None
        elif not fmt and bicim in ("B1", "B2", "B3", "B4", None, ""):
            cikti_kapak = config.yol_al(f"data/output/{onek}_01_kapak.jpg")
            with make_image.tuval("story"):
                slayt_yolu = make_image.otorite_slayt_1_kapak(veri, cikti_kapak)
            return Path(slayt_yolu) if Path(slayt_yolu).exists() else None
        else:
            return None
    except Exception as e:  # noqa: BLE001 — Story üretilemezse onaylı kapak çerçevelenir (yedek yol)
        log.warning("Native 9:16 Story kapağı üretilemedi: %s", e)
        return None


def _story_gorseli_hazirla(b: YayinBaglami) -> str | None:
    """Story görselini hazırlayıp CDN'e yükler; adres ya da None."""
    from PIL import Image
    kok = Path(__file__).resolve().parents[3]
    story_dosya = kok / f"data/output/story_{b.ref_id}.jpg"
    story_dosya.parent.mkdir(parents=True, exist_ok=True)
    hazir_yol = None

    # 1. Öncelik: Video için üretilmiş native 9:16 dikey kapak varsa doğrudan kullan
    if b.dikey_slaytlar and Path(b.dikey_slaytlar[0]).exists():
        try:
            with Image.open(b.dikey_slaytlar[0]) as d_im:
                if d_im.size == (1080, 1920):
                    hazir_yol = Path(b.dikey_slaytlar[0])
        except Exception as de:  # noqa: BLE001
            log.debug("Dikey slayt öncelik kontrolü: %s", de)

    # 2. Öncelik: Native 9:16 Story kapağı üret (1080x1920)
    if not hazir_yol or not hazir_yol.exists():
        hazir_yol = story_kapagi_uret(b.detay, b.haber, b.ref_id, b.tur, b.ilan if b.tur == "ilan" else None)

    # 3. Son Çare Yedek: Yalnızca native 9:16 hiçbir şekilde üretilemezse onaylanan 4:5 kapak çerçevelenir
    if not hazir_yol or not hazir_yol.exists():
        if b.public_urller and len(b.public_urller) > 0:
            try:
                import requests
                resp = requests.get(b.public_urller[0], timeout=15)
                if resp.status_code == 200:
                    with open(story_dosya, "wb") as f:
                        f.write(resp.content)
                    hazir_yol = story_dosya
            except Exception as ue:  # noqa: BLE001
                log.warning("Story public URL indirme hatası: %s", ue)
        elif b.haber and b.haber.get("slayt_urlleri"):
            try:
                import requests
                db_urller = json.loads(b.haber["slayt_urlleri"])
                if isinstance(db_urller, list) and len(db_urller) > 0:
                    resp = requests.get(db_urller[0], timeout=15)
                    if resp.status_code == 200:
                        with open(story_dosya, "wb") as f:
                            f.write(resp.content)
                        hazir_yol = story_dosya
            except Exception as ue:  # noqa: BLE001
                log.warning("Story db URL indirme hatası: %s", ue)
        elif b.slayt_yollari and Path(b.slayt_yollari[0]).exists():
            hazir_yol = Path(b.slayt_yollari[0])

    if hazir_yol and hazir_yol.exists():
        with Image.open(hazir_yol) as im:
            if im.size == (1080, 1920):
                im.save(story_dosya, "JPEG", quality=95, optimize=True)
            else:
                s_img = video._cercevele_9_16(im)
                s_img.save(story_dosya, "JPEG", quality=95, optimize=True)
        return upload_image.gorsel_yukle(story_dosya)
    return None


def yayinla(b: YayinBaglami, ilerleme: Ilerleme) -> KanalSonucu:
    ilerleme.bildir(KANAL, "⏳ Yükleniyor...")
    s = KanalSonucu(KANAL, etiket="❌ Hata")
    story_url = None
    try:
        story_url = _story_gorseli_hazirla(b)
    except Exception as se:  # noqa: BLE001
        log.warning("Story görseli hazırlanamadı: %s", se)

    st_basarili = False
    if story_url:
        try:
            ig_story_id = instagram.story_yayinla(story_url)
            if ig_story_id:
                st_basarili = True
                s.ekle("📱 <b>Instagram Story:</b> Paylaşıldı ✓", YAYINDA)
            else:
                s.ekle("📱 <b>Instagram Story:</b> Hata oluştu ✗", HATA)
        except Exception as ise:  # noqa: BLE001
            log.warning("Instagram Story hatası: %s", ise)
            s.ekle(f"📱 <b>Instagram Story:</b> Hata ({ise}) ✗", HATA)

        try:
            fb_story_id = facebook.story_yayinla(story_url)
            if fb_story_id:
                st_basarili = True
                s.ekle("📘 <b>Facebook Story:</b> Paylaşıldı ✓", YAYINDA)
            else:
                s.ekle("📘 <b>Facebook Story:</b> Hata oluştu ✗", HATA)
        except Exception as fse:  # noqa: BLE001
            log.warning("Facebook Story hatası: %s", fse)
            s.ekle(f"📘 <b>Facebook Story:</b> Hata ({fse}) ✗", HATA)
    else:
        s.ekle("📱 <b>Story:</b> Görsel hazırlanamadı ✗", HATA)
    if st_basarili:
        s.etiket = "✅ Yayında"
    ilerleme.bildir(KANAL, s.etiket, increment=True)
    return s
