"""
tests/test_hazirla_yml_elle_tetik.py — elle tetiklenen sözlük ONAYSIZ yayınlanmaz, onay kartıyla (yayın düğmeleriyle) düşer (2026-10-13)

Kullanıcı kararı: günde bir sözlük kesin çıkar (12:30 zamanlanmış koşu, onaysız yayın, acil fren SOZLUK_OTO_YAYIN=0), ama
Telegram'dan elle (/sozluk, paneldeki düğme) ya da Actions'tan elle tetiklenen her içerik "görsel + açıklama + Yayınla düğmeleri" olarak
gruba düşer; yayınlamak insana kalır. Eskiden elle tetiklenen sözlük de `--oto-yayin` ile doğrudan yayına çıkıyordu.

Test hazirla.yml'in "Günlük İçerik Hazırla ve Paylaş" adımındaki GERÇEK kabuk betiğini bash ile çalıştırır; `python` yerine argümanları
yazan bir kukla koyar. Yani sınanan şey workflow'un kendisidir, bir kopyası değil.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

KOK = Path(__file__).resolve().parent.parent
ADIM = "Günlük İçerik Hazırla ve Paylaş"


def _betik() -> str:
    w = yaml.safe_load((KOK / ".github/workflows/hazirla.yml").read_text(encoding="utf-8"))
    adim = next(a for a in w["jobs"]["hazirla"]["steps"] if a.get("name") == ADIM)
    return adim["run"]


def _calistir(**ortam: str) -> str:
    """Betiği verilen ortam değişkenleriyle çalıştırır; `python` çağrısının argümanlarını döner."""
    with tempfile.TemporaryDirectory() as d:
        kukla = Path(d) / "python"
        kukla.write_text('#!/bin/bash\necho "python $*"\n', encoding="utf-8")
        kukla.chmod(kukla.stat().st_mode | stat.S_IEXEC)
        env = {"PATH": f"{d}:{os.environ['PATH']}", "FORMAT": "", "SLOT": "", "HEDEF": "", "ZAMANLAMA": "", "ZAMANLANMIS": "false"}
        env.update(ortam)
        sonuc = subprocess.run(["bash", "-eo", "pipefail", "-c", _betik()], env=env, capture_output=True, text=True, check=True)
    cikti = [s for s in sonuc.stdout.splitlines() if s.strip()]
    assert len(cikti) == 1, f"tam bir python çağrısı bekleniyordu: {cikti}"
    return cikti[0].strip()


class TestElleTetikSozluk(unittest.TestCase):
    def test_telegram_sozluk_komutu_ve_paneli_onaysiz_yayinlamaz(self):
        """/sozluk ve panel düğmesi → sabah_hazirla {format_turu: sozluk} (zamanli yok)."""
        self.assertEqual(_calistir(FORMAT="sozluk"), "python scripts/hazirla.py --slot sozluk")

    def test_actions_elle_calistirma_sozluk_onaysiz_yayinlamaz(self):
        self.assertEqual(_calistir(HEDEF="slot_sozluk"), "python scripts/hazirla.py --slot sozluk")

    def test_zamanli_slot_hazirla_elle_gonderilirse_de_onaysiz_yayinlamaz(self):
        """slot_hazirla yüküne `zamanli: true` konmadıysa zamanlanmış koşu sayılmaz."""
        self.assertEqual(_calistir(SLOT="sozluk", ZAMANLANMIS="false"), "python scripts/hazirla.py --slot sozluk")

    def test_cloudflare_12_30_sozlugu_onaysiz_yayinlar(self):
        self.assertEqual(_calistir(SLOT="sozluk", ZAMANLANMIS="true"), "python scripts/hazirla.py --slot sozluk --oto-yayin")

    def test_github_yedek_cron_12_30_sozlugu_onaysiz_yayinlar(self):
        self.assertEqual(_calistir(ZAMANLAMA="30 9 * * *", ZAMANLANMIS="true"), "python scripts/hazirla.py --slot sozluk --oto-yayin")


class TestDigerFormatlarDegismedi(unittest.TestCase):
    def test_10_00_bilgilendirici_hicbir_zaman_onaysiz_yayinlanmaz(self):
        for env in (dict(SLOT="bilgilendirici", ZAMANLANMIS="true"), dict(ZAMANLAMA="0 7 * * *", ZAMANLANMIS="true"),
                    dict(HEDEF="slot_bilgilendirici"), dict(SLOT="bilgilendirici")):
            with self.subTest(env=env):
                self.assertEqual(_calistir(**env), "python scripts/hazirla.py --slot bilgilendirici")

    def test_elle_format_istekleri_onay_kartina_gider(self):
        for format_turu in ("nedir_dogrusu", "net_cevap", "vaka", "b1"):
            with self.subTest(format_turu=format_turu):
                self.assertEqual(_calistir(FORMAT=format_turu), f"python scripts/hazirla.py --format {format_turu}")

    def test_reels_onay_kartina_gider(self):
        self.assertEqual(_calistir(FORMAT="reels"), "python scripts/hazirla.py --reels")

    def test_finans_degismedi_bilinen_istisna(self):
        """Finans bülteni bu kararın dışında: bilinçli olarak `--oto-yayin` (MEMORY.md §10 madde 5, ICERIK-SISTEMI §5.5.2)."""
        self.assertEqual(_calistir(FORMAT="finans"), "python scripts/hazirla.py --finans --oto-yayin")

    def test_haber_oneri_slotu(self):
        self.assertEqual(_calistir(HEDEF="slot_haber"), "python scripts/hazirla.py --slot haber")


if __name__ == "__main__":
    unittest.main(verbosity=2)
