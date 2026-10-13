"""
tests/test_telegram_paketi.py — src/telegram/ paketinin yapı kuralları (Faz 2, 2026-10-13).

Davranışın bütünü tests/test_telegram_altin.py'de donduruldu; burada paketin mimari sözleşmeleri sınanır
(bkz. ARCHITECTURE.md §2): dosya boyutu, yukarı bağımlılık yok, kardeş işlevler modül üzerinden çağrılır.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import ast
import sys
import unittest
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

PAKET = KOK / "src" / "telegram"


def _moduller():
    return sorted(p for p in PAKET.rglob("*.py") if p.name != "__init__.py")


class TestTelegramPaketYapisi(unittest.TestCase):
    def test_hicbir_modul_dev_degil(self):
        buyuk = [f"{y.relative_to(KOK)}: {y.read_text(encoding='utf-8').count(chr(10))} satır"
                 for y in _moduller() if y.read_text(encoding="utf-8").count("\n") > 250]
        self.assertFalse(buyuk, f"Bölünmesi gereken modüller: {buyuk}")

    def test_paket_telegram_bot_a_bagimli_degil(self):
        """Bağımlılık yalnız aşağı akar: telegram_bot paketi içeri alır, paket telegram_bot'u bilmez."""
        ihlal = []
        for y in _moduller():
            for n in ast.walk(ast.parse(y.read_text(encoding="utf-8"))):
                adlar = []
                if isinstance(n, ast.ImportFrom):
                    adlar = [n.module or ""] + [a.name for a in n.names]
                elif isinstance(n, ast.Import):
                    adlar = [a.name for a in n.names]
                if any(a.split(".")[-1] == "telegram_bot" for a in adlar):
                    ihlal.append(f"{y.relative_to(KOK)}:{n.lineno}")
        self.assertFalse(ihlal, f"src/telegram telegram_bot'u içe aktarıyor: {ihlal}")

    def test_kardes_islevler_modul_uzerinden_cagrilir(self):
        """`from .istemci import mesaji_sil` yok, `from . import istemci` var: testlerin yaması her yerde geçsin (ARCHITECTURE.md §2 kural 4)."""
        ihlal = []
        for y in _moduller():
            for n in ast.walk(ast.parse(y.read_text(encoding="utf-8"))):
                if isinstance(n, ast.ImportFrom) and n.level == 1 and n.module:
                    ihlal.append(f"{y.relative_to(KOK)}:{n.lineno} from .{n.module} import ...")
        self.assertFalse(ihlal, f"Kardeş modülden ad alma yasak: {ihlal}")

    def test_eski_adlar_telegram_bot_tan_erisilebilir(self):
        """22 kaynak, 31 test dosyası ve workflow'lardaki `python -c` satırları bu adlarla çağırıyor; taşınınca kaybolmamalı."""
        from src import telegram_bot
        for ad in ("mesaj_gonder", "mesaji_sil", "mesaji_guncelle", "menuyu_degistir", "aciklama_metni_kutusu",
                   "fotograf_gonder", "video_gonder", "medya_grubu_gonder", "slaytlari_gonder",
                   "son_medya_grubu_mesaj_idleri", "icerik_onceki_mesajlarini_temizle", "son_mesajlari_sil",
                   "_bot_bilgileri", "_istek", "TELEGRAM_API_URL", "haber_onayina_sun", "yayin_kapisi", "sozluk_karti_hazirla_ve_sun",
                   "slot_icerigi_hazirla_ve_sun", "finans_icerigi_hazirla_ve_yayinla", "ilan_postunu_hazirla_ve_sor",
                   "bot_duraklatildi_mi", "yayindan_kaldir", "komut_menusu_kaydet", "kota_gonder", "sonucu_yaz"):
            self.assertTrue(hasattr(telegram_bot, ad), ad)

    def test_cephe_tablosu_paketle_ayni(self):
        """telegram_bot._EV (ad → modül) paketin gerçek içeriğiyle birebir; yeni işlev eklenince tabloya da eklenir
        (hata mesajı eksik / fazla / yanlış adları listeler)."""
        from src import telegram_bot
        gercek, cift = {}, []
        for y in _moduller():
            modul = ".".join(y.relative_to(PAKET).with_suffix("").parts)
            for n in ast.parse(y.read_text(encoding="utf-8")).body:
                adlar = ([n.name] if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                         else [t.id for t in n.targets if isinstance(t, ast.Name)] if isinstance(n, ast.Assign) else [])
                for a in adlar:
                    if a in ("log", "KOK", "_son_medya_grubu_mesaj_idleri"):
                        continue
                    if a in gercek:
                        cift.append(f"{a}: {gercek[a]} ve {modul}")
                    gercek[a] = modul
        self.assertFalse(cift, f"Aynı ad iki modülde (cephe hangisini göstereceğini bilemez): {cift}")
        eksik = sorted(set(gercek) - set(telegram_bot._EV))
        fazla = sorted(set(telegram_bot._EV) - set(gercek))
        yanlis = sorted(a for a in gercek if a in telegram_bot._EV and telegram_bot._EV[a] != gercek[a])
        self.assertEqual((eksik, fazla, yanlis), ([], [], []), "src/telegram_bot.py _EV tablosu paketle uyuşmuyor")

    def test_cephe_kod_barindirmaz(self):
        """telegram_bot.py yalnızca ad tablosu ve `__getattr__`/`__dir__`: iş mantığı geri sızmasın."""
        agac = ast.parse((KOK / "src" / "telegram_bot.py").read_text(encoding="utf-8"))
        islevler = sorted(n.name for n in agac.body if isinstance(n, ast.FunctionDef))
        self.assertEqual(islevler, ["__dir__", "__getattr__"])

    def test_cephe_adi_gercek_evinden_o_an_okur(self):
        """Gerçek evdeki yama cepheden çağıranı da kapsar (canlı takma ad)."""
        from unittest.mock import patch
        from src import telegram_bot
        with patch("src.telegram.istemci.mesaj_gonder", return_value={"message_id": 7}) as m:
            self.assertEqual(telegram_bot.mesaj_gonder("x"), {"message_id": 7})
        m.assert_called_once_with("x")
        self.assertIsNot(telegram_bot.mesaj_gonder, m)  # yama bitti: gerçek işlev geri geldi


if __name__ == "__main__":
    unittest.main(verbosity=2)
