"""LinkedIn: görsel dosyalarıyla kurumsal metin (yalnız LINKEDIN_ACCESS_TOKEN tanımlıysa)."""

from __future__ import annotations

import logging
from pathlib import Path

from ... import linkedin
from ..baglam import YayinBaglami
from ..ilerleme import Ilerleme
from ..sonuc import HATA, YAYINDA, KanalSonucu

log = logging.getLogger(__name__)

KANAL = "linkedin"


def yayinla(b: YayinBaglami, ilerleme: Ilerleme) -> KanalSonucu:
    ilerleme.bildir(KANAL, "⏳ Yükleniyor...")
    s = KanalSonucu(KANAL, etiket="❌ Hata")
    if not linkedin.kullanilabilir_mi():
        s.ekle("💼 <b>LinkedIn:</b> Yapılandırılmamış (LINKEDIN_ACCESS_TOKEN eksik) ✗", HATA)
        ilerleme.bildir(KANAL, s.etiket, increment=True)
        return s

    try:
        li_veri = b.detay if (b.detay and isinstance(b.detay, dict)) else (b.haber if isinstance(b.haber, dict) else {})
        li_metin = linkedin.linkedin_metni_hazirla(li_veri, manset=b.baslik)
        gorseller_li = [str(p) for p in b.slayt_yollari if Path(p).exists()]
        lid = linkedin.paylas(li_metin, dosya_yollari=gorseller_li)
        s.kimlik = lid
        if lid:
            s.ekle("💼 <b>LinkedIn:</b> Paylaşıldı ✓", YAYINDA)
        else:
            s.ekle("💼 <b>LinkedIn:</b> Hata oluştu ✗", HATA)
    except Exception as le:  # noqa: BLE001
        log.warning("LinkedIn paylaşım hatası: %s", le)
        s.ekle(f"💼 <b>LinkedIn:</b> Hata ({le}) ✗", HATA)
    if s.kimlik:
        s.etiket = "✅ Yayında"
    ilerleme.bildir(KANAL, s.etiket, increment=True)
    return s
