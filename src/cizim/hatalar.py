"""
src/cizim/hatalar.py — Çizim motoru istisnaları.
"""

from __future__ import annotations


class EksikIcerik(ValueError):
    """Formatın zorunlu alanı modelden gelmedi.

    Eskiden boş alan koddaki genel bir cümleyle doldurulurdu; #157'de ekspertiz
    konusuna "Yargıtay yerleşik içtihatları uyarınca…" diye sabit bir hüküm
    basıldı. Uydurmak yerine üretim durur.
    """


class TasmaHatasi(EksikIcerik):
    """Metin, okunabilir en küçük puntoda bile ayrılan alana sığmadı.

    Eskiden sığmayan metin kutunun altına girer (#243 sözlük: tanımın son iki
    satırı "Yatırımcı için önemi" kutusunun arkasında kaldı), tuvalden taşar
    (kapak manşeti) ya da sessizce kırpılırdı (kapak spotu 4 satırda kesiliyordu).
    Artık üretim durur; metin bütçesi (generate_text.BUTCE) bunu önlemeye çalışır.
    """
