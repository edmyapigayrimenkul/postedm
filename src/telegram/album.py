"""
src/telegram/album.py — Albüm (sendMediaGroup) gönderimi: yerel → URL → indir-yükle → tek tek düşme sırası.

Katman 3 (etki). Son başarılı albümün mesaj kimlikleri bu modülün durumudur (`son_medya_grubu_mesaj_idleri()`); kimliklerin
yeniden atandığı yer burası olduğu için yama/okuma da burada yapılmalıdır.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from .. import db, upload_image
from . import istemci, medya_istek

log = logging.getLogger(__name__)


_son_medya_grubu_mesaj_idleri: List[int] = []


def son_medya_grubu_mesaj_idleri() -> List[int]:
    """Son BAŞARILI sendMediaGroup çağrısında dönen telegram message_id listesi (her çağrının başında sıfırlanır)."""
    return list(_son_medya_grubu_mesaj_idleri)


def _ayikla_medya_mesaj_idleri(resp: requests.Response) -> List[int]:
    global _son_medya_grubu_mesaj_idleri
    try:
        data = resp.json()
        if data.get("ok") and isinstance(data.get("result"), list):
            mids = [m["message_id"] for m in data["result"] if isinstance(m, dict) and "message_id" in m]
            if mids:
                _son_medya_grubu_mesaj_idleri = mids
                return mids
    except Exception:
        pass
    return []


def _yerel_dosya_bul(f_yol: Path | str) -> Optional[Path]:
    """Görselin bu makinedeki dosyası: doğrudan yol, yüklenen URL'nin yerel karşılığı ya da çıktı klasörlerinde ad eşleşmesi."""
    p = Path(str(f_yol))
    if p.exists() and p.is_file():
        return p
    try:
        yerel = upload_image.yerel_karsiligi(str(f_yol))
        if yerel and yerel.exists() and yerel.is_file():
            return yerel
    except Exception:  # noqa: BLE001
        pass
    temiz_ad = Path(str(f_yol).split("?")[0]).name
    for klasor in [Path("data/output"), Path("output")]:
        olasi = klasor / temiz_ad
        if olasi.exists() and olasi.is_file():
            return olasi
    return None


def _indir(url: str) -> Optional[bytes]:
    try:
        r = requests.get(url, headers=medya_istek._MEDYA_UA, timeout=(10, 25))
        if r.status_code == 200 and r.content:
            return r.content
    except Exception as e:  # noqa: BLE001
        log.warning("Görsel indirilemedi (%s): %s", url[:60], e)
    return None


def _album_istegi(url: str, chat_id: str, ogeler: List[Tuple[str, Any]], caption: str, *,
                  etiket: str, bitis: float, deneme: int = medya_istek.MEDYA_DENEME) -> Tuple[Optional[Any], str]:
    """Bir sendMediaGroup isteği. `ogeler`: ('dosya', Path) | ('bayt', bytes) | ('url', str) çiftleri.
    Dosya ve bayt öğeleri multipart ile yüklenir (attach://), URL öğeleri Telegram'a çektirilir; ikisi karışabilir."""
    import io

    def hazirla(duz: bool) -> Tuple[Dict[str, Any], Any]:
        media: List[Dict[str, Any]] = []
        files: Dict[str, Any] = {}
        tutamaclar: List[Any] = []

        def kapat() -> None:
            for fh in tutamaclar:
                try:
                    fh.close()
                except Exception:  # noqa: BLE001
                    pass

        try:
            for idx, (tur, deger) in enumerate(ogeler):
                oge: Dict[str, Any] = {"type": "photo"}
                if tur == "url":
                    oge["media"] = str(deger)
                else:
                    ad = f"photo_{idx}"
                    oge["media"] = f"attach://{ad}"
                    if tur == "dosya":
                        fh = open(deger, "rb")
                        tutamaclar.append(fh)
                        files[ad] = (Path(deger).name, fh, "image/jpeg")
                    else:
                        files[ad] = (f"foto_{idx}.jpg", io.BytesIO(deger), "image/jpeg")
                if idx == 0 and caption:
                    oge["caption"] = medya_istek._duz_metin(caption)[:1024] if duz else caption[:1024]
                    if not duz:
                        oge["parse_mode"] = "HTML"
                media.append(oge)
        except OSError:
            kapat()
            raise
        if files:
            return {"data": {"chat_id": chat_id, "media": json.dumps(media)}, "files": files}, kapat
        return {"json": {"chat_id": chat_id, "media": media}}, kapat

    return medya_istek._medya_post(url, hazirla, etiket=etiket, bitis=bitis, deneme=deneme)


def medya_grubu_gonder(foto_yollari: List[Path | str], caption: str = "",
                       yedek_urller: Optional[List[str]] = None) -> List[int] | bool:
    """Carousel önizlemesi için albüm (medya grubu) gönderir. Döner: mesaj kimlikleri (başarı) ya da False.

    `yedek_urller`: aynı görsellerin herkese açık adresleri (ImgBB/R2), `foto_yollari` ile aynı sırada. Yerel yükleme
    tutmazsa Telegram bu adreslerden çeker; sayı eşleşmiyorsa (kısmi yükleme) güvenilmez, kullanılmaz.

    Sırayla denenir, biri tutunca durulur:
      1. Yerel dosyalar multipart ile (yeniden denemeli)
      2. URL albümü (Telegram görselleri kendisi çeker)
      3. URL'lerden indirip multipart yükleme (WEBPAGE_CURL_FAILED kurtarma)
      4. Fotoğrafları TEK TEK gönderme (başlık ilk giden fotoğrafta). Hepsi gitmezse gidenlerin kimlikleri döner;
         çağıran `len(sonuc) < len(foto_yollari)` ile eksik teslimi anlar.
    Zaman aşımı belirsizdir (Telegram isteği işlemiş ama cevap gelmemiş olabilir), bu yüzden nadiren aynı albüm iki kez
    düşebilir; albüm kaybolmasından iyidir. Hiçbiri tutmazsa hata günlüğüne yazılır ve False döner.
    """
    global _son_medya_grubu_mesaj_idleri
    _son_medya_grubu_mesaj_idleri = []  # eski çağrının kimlikleri bu içeriğe karışmasın
    token, chat_id = istemci._bot_bilgileri()
    if not token or not chat_id or not foto_yollari:
        return False
    foto_yollari = list(foto_yollari)[:10]
    yedek = [str(u) for u in (yedek_urller or [])][:10]
    if len(yedek) != len(foto_yollari):
        yedek = []

    # Telegram sendMediaGroup minimum 2 medya gerektirir; tekil görsel (ör. sözlük kartı) sendPhoto ile gider.
    if len(foto_yollari) == 1:
        res = medya_istek.fotograf_gonder(foto_yollari[0], caption=caption)
        if not res and yedek:
            res = medya_istek.fotograf_gonder(yedek[0], caption=caption)
        if res and isinstance(res, dict) and "message_id" in res:
            _son_medya_grubu_mesaj_idleri = [res["message_id"]]
            return [res["message_id"]]
        if not res:
            _medya_hatasi_kaydet("tekil fotoğraf gönderilemedi")
        return bool(res)

    url = istemci.TELEGRAM_API_URL.format(token=token, method="sendMediaGroup")
    bitis = time.monotonic() + medya_istek.MEDYA_TOPLAM_SURE
    yereller = [_yerel_dosya_bul(fy) for fy in foto_yollari]
    hepsi_yerel = all(y is not None for y in yereller)
    hatalar: List[str] = []

    def basari(r: Any) -> List[int] | bool:
        mids = _ayikla_medya_mesaj_idleri(r)
        return mids if mids else True

    # 1. Yerel dosyalar. Yedek adres varsa tek deneme yeter: yükleme zaman aşımı çoğunlukla çıkış hattının yavaşlığıdır,
    # ikinci deneme de aynı hatta takılır; Telegram'ın görselleri kendi çekeceği URL yolu (2.) çoğu zaman anında tutar.
    if hepsi_yerel:
        r, hata = _album_istegi(url, chat_id, [("dosya", y) for y in yereller], caption, etiket="albüm(yerel)", bitis=bitis,
                                deneme=1 if yedek else medya_istek.MEDYA_DENEME)
        if r is not None:
            return basari(r)
        hatalar.append(f"yerel albüm: {hata}")

    # 2. URL albümü: girdinin kendisi URL ise o, değilse yedek adresler
    girdi_url_mi = all(str(f).startswith(("http://", "https://")) for f in foto_yollari)
    urller = [str(f) for f in foto_yollari] if girdi_url_mi else yedek
    if urller and time.monotonic() < bitis:
        r, hata = _album_istegi(url, chat_id, [("url", u) for u in urller], caption, etiket="albüm(url)", bitis=bitis)
        if r is not None:
            return basari(r)
        hatalar.append(f"url albümü: {hata}")

    # 3. URL'lerden indirip yükle (yerel dosya eksikse; hepsi yerelse 1. adım zaten aynı şeyi denedi)
    if urller and not hepsi_yerel and time.monotonic() < bitis:
        ogeler: List[Tuple[str, Any]] = []
        for yerel, u in zip(yereller, urller):
            if yerel is not None:
                ogeler.append(("dosya", yerel))
                continue
            bayt = _indir(u)
            if bayt is None:
                break
            ogeler.append(("bayt", bayt))
        if len(ogeler) == len(urller):
            r, hata = _album_istegi(url, chat_id, ogeler, caption, etiket="albüm(indir-yükle)", bitis=bitis)
            if r is not None:
                log.info("Albüm URL yerine indirilip yüklenerek iletildi.")
                return basari(r)
            hatalar.append(f"indir-yükle: {hata}")
        else:
            hatalar.append("indir-yükle: görseller indirilemedi")

    # 4. Tek tek
    teslim: List[int] = []
    ilk_basliksiz = True
    for i, yerel in enumerate(yereller):
        if time.monotonic() > bitis + 120:
            hatalar.append("tek tek: süre bütçesi doldu")
            break
        kaynak = yerel if yerel is not None else (urller[i] if urller else None)
        if kaynak is None:
            continue
        res = medya_istek.fotograf_gonder(kaynak, caption=caption if ilk_basliksiz else "")
        if res and isinstance(res, dict) and "message_id" in res:
            teslim.append(res["message_id"])
            ilk_basliksiz = False
    if teslim:
        _son_medya_grubu_mesaj_idleri = teslim
        if len(teslim) < len(foto_yollari):
            _medya_hatasi_kaydet(f"albüm eksik iletildi ({len(teslim)}/{len(foto_yollari)} fotoğraf): " + " | ".join(hatalar))
        else:
            log.warning("Albüm toplu gönderilemedi; fotoğraflar tek tek iletildi (%s)", " | ".join(hatalar))
        return teslim

    _medya_hatasi_kaydet("albüm hiçbir yolla iletilemedi: " + " | ".join(hatalar))
    return False


def _medya_hatasi_kaydet(ayrinti: str) -> None:
    """Teslim edilemeyen/eksik görseli kalıcı hata günlüğüne yazar (günlük rapor ve 'Ham Hata' düğmesi görsün)."""
    log.error("Telegram medya teslimi: %s", ayrinti)
    try:
        db.hata_kaydi_ekle("telegram.medya", "Görseller Telegram'a iletilemedi", "Slayt görselleri Telegram'a ulaşmadı.",
                           "Telegram yükleme/URL isteği zaman aşımı ya da reddedilme.", "yeniden_yayinla", False, ayrinti)
    except Exception as e:  # noqa: BLE001 — günlük yazılamasa da gönderim akışı sürsün
        log.warning("Medya hatası DB'ye yazılamadı: %s", e)


def slaytlari_gonder(foto_yollari: List[Path | str], basliklar: Optional[List[str]] = None) -> bool:
    """Instabot uyumluluk yardımcısı: Fotoğraf albümü (medya grubu) gönderir."""
    caption = basliklar[0] if basliklar else ""
    return medya_grubu_gonder(foto_yollari, caption=caption)
