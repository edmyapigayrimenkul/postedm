"""
tests/test_is_akisi_guvenligi.py — GitHub Actions iş akışlarında kabuk enjeksiyonu.

Gerçek açık (2026-09-23): yayinla.yml Telegram'dan gelen metni doğrudan betiğe
gömüyordu:   METIN="${{ github.event.client_payload.metin }}"
${{ }} ifadesi kabuk çalışmadan ÖNCE metne yerleşir; tırnak ve $(...) içeren bir
yanıt ya da Telegram görünen adı, runner'da gizli anahtarlarla komut çalıştırır.
Worker'da gönderen kontrolü olmadığından bota yazabilen herkes buna ulaşabiliyordu.

Kural: dış girdi (client_payload, inputs) yalnızca `env:` üzerinden geçer.
"""

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import re
import unittest
from pathlib import Path

import yaml

KOK = Path(__file__).resolve().parent.parent
DIS_GIRDI = re.compile(r"client_payload|inputs\.|github\.event\.(comment|issue|head_commit|pull_request|review)")

# Yalnızca sabit bir bayrak üreten, kullanıcı metni taşımayan ifadeler
IZINLI = {
    "inputs.sadece_kontrol && '--sadece-kontrol' || ''",
}


class TestIsAkisiEnjeksiyonu(unittest.TestCase):
    def test_dis_girdi_run_bloguna_gomulmez(self):
        ihlaller = []
        for yol in sorted((KOK / ".github" / "workflows").glob("*.yml")):
            is_akisi = yaml.safe_load(yol.read_text(encoding="utf-8"))
            for is_adi, is_ in (is_akisi.get("jobs") or {}).items():
                for adim in is_.get("steps", []):
                    for ifade in re.findall(r"\$\{\{\s*(.*?)\s*\}\}", adim.get("run") or ""):
                        if DIS_GIRDI.search(ifade) and ifade not in IZINLI:
                            ihlaller.append(f"{yol.name} · {adim.get('name')} · ${{{{ {ifade} }}}}")
        self.assertEqual(ihlaller, [], "Dış girdi run bloğuna gömülmüş; env: ile geçirin:\n" + "\n".join(ihlaller))


if __name__ == "__main__":
    unittest.main(verbosity=2)
