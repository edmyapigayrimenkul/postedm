"""
yayin/kanallar — Her kanal için BİR işçi: `yayinla(baglam, ilerleme) -> KanalSonucu`.

İşçiler birbirinden habersizdir; ortak durum yok (eski yayinla.py'de `nonlocal` ile paylaşılan değişkenlerdi). Yeni kanal eklemek =
yeni bir modül yazıp aşağıdaki sözlüğe eklemek + `yayin.hedef.kanal_listesi`nde seçim kuralını belirlemek.
"""

from . import fb, ig, li, reels, story, th, tt, tw, yt

KANALLAR = {
    "tiktok": tt.yayinla,
    "instagram": ig.yayinla,
    "reels": reels.yayinla,
    "story": story.yayinla,
    "threads": th.yayinla,
    "facebook": fb.yayinla,
    "facebook_reels": fb.yayinla,
    "youtube": yt.yayinla,
    "linkedin": li.yayinla,
    "twitter": tw.yayinla,
    "x": tw.yayinla,
}
