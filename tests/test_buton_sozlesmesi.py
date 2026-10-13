"""
tests/test_buton_sozlesmesi.py — Telegram buton sözleşmesi: Python'ın ve Worker'ın ürettiği her butonun Worker'da karşılığı var (2026-10-13)

NİYE: Butona basınca Telegram `callback_data` metnini Cloudflare Worker'a yollar (`worker/index.js`, callback bloğu); Worker tanımadığı bir adı SESSİZCE
yok sayar (cevap yok, bekleme simgesi döner, hata günlüğüne bir şey düşmez). Buton adları iki dilde ve iki yerde ayrı yazılıyor: Python mesajı kurar,
JavaScript tıklamayı işler. Biri yeniden adlandırılınca öbürü kırılır ve bunu hiçbir mevcut test görmezdi. Bu testle bulunan ilk iki ölü buton:
kota raporundaki "🎛 Kontrol Paneli" (`yonetim_panel`) ve kapak adaylarındaki "🔄 Başka adaylar" (`foto_degistir:<id>`).

Üç sözleşme:
  1. Python'ın ürettiği her `callback_data` Worker'da işleniyor.
  2. Worker'ın kendi menülerinin ürettiği her `callback_data` yine Worker'da işleniyor.
  3. Worker'ın GitHub'a yolladığı her `repository_dispatch` olayını bir workflow dinliyor.
Ayrıca statik buton adları Telegram'ın 64 bayt sınırını aşmaz.

Ayrıştırıcı kırılırsa (Worker yeniden yazıldı, kalıplar değişti) test sessizce boşa geçmesin diye "yeterince şey bulundu" denetimleri var.
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import ast
import re
import unittest
from collections import defaultdict
from pathlib import Path

import yaml

KOK = Path(__file__).resolve().parent.parent

# Bilinçli olarak işlenmeyen butonlar: ad → neden. Girdi artık ölü değilse ya da hiç üretilmiyorsa test KIRILIR (liste çürümesin).
BILINEN_OLU = {
    "piyasa_yayinla": "Piyasa verisi özelliği KAPALI (kullanıcı kararı, MEMORY.md §10 madde 8); scripts/piyasa_otomatik.py çalıştırılmıyor.",
}


# ---------------------------------------------------------------------------
# Python tarafı: `callback_data` üreten her yer (AST)
# ---------------------------------------------------------------------------

def _onekler(dugum: ast.AST, atamalar: dict[str, list[ast.AST]], derinlik: int = 0) -> list[tuple[str, bool]]:
    """Bir ifadenin alabileceği (önek, tam_mi) değerleri. Çözülemeyen ifade [] döner. `tam_mi`: değer tamamen sabit mi."""
    if derinlik > 4:
        return []
    if isinstance(dugum, ast.Constant) and isinstance(dugum.value, str):
        return [(dugum.value, True)]
    if isinstance(dugum, ast.JoinedStr):
        onek = ""
        for parca in dugum.values:
            if isinstance(parca, ast.Constant):
                onek += str(parca.value)
            else:
                break
        return [(onek, all(isinstance(p, ast.Constant) for p in dugum.values))]
    if isinstance(dugum, ast.IfExp):
        return _onekler(dugum.body, atamalar, derinlik + 1) + _onekler(dugum.orelse, atamalar, derinlik + 1)
    if isinstance(dugum, ast.Name) and dugum.id in atamalar:
        sonuc: list[tuple[str, bool]] = []
        for deger in atamalar[dugum.id]:
            sonuc += _onekler(deger, atamalar, derinlik + 1)
        return sonuc
    return []


def python_butonlari() -> tuple[dict[str, list[tuple[str, int, bool]]], list[tuple[str, int, str]]]:
    """({önek: [(dosya, satır, tam_mi)]}, [(dosya, satır, çözülemeyen ifade)])"""
    bulunan: dict[str, list[tuple[str, int, bool]]] = defaultdict(list)
    cozulemeyen: list[tuple[str, int, str]] = []
    dosyalar = sorted(list((KOK / "src").rglob("*.py")) + list((KOK / "scripts").glob("*.py")))
    for dosya in dosyalar:
        agac = ast.parse(dosya.read_text(encoding="utf-8"))
        atamalar: dict[str, list[ast.AST]] = defaultdict(list)
        for n in ast.walk(agac):
            if isinstance(n, ast.Assign):
                for h in n.targets:
                    if isinstance(h, ast.Name):
                        atamalar[h.id].append(n.value)
        adaylar: list[ast.AST] = []
        for n in ast.walk(agac):
            if isinstance(n, ast.Dict):
                adaylar += [v for k, v in zip(n.keys, n.values) if isinstance(k, ast.Constant) and k.value == "callback_data"]
            elif isinstance(n, ast.keyword) and n.arg == "callback_data":
                adaylar.append(n.value)
        for deger in adaylar:
            sonuc = _onekler(deger, atamalar)
            goreli = str(dosya.relative_to(KOK))
            if not sonuc:
                cozulemeyen.append((goreli, deger.lineno, ast.unparse(deger)[:70]))
            for onek, tam in sonuc:
                bulunan[onek].append((goreli, deger.lineno, tam))
    return dict(bulunan), cozulemeyen


# ---------------------------------------------------------------------------
# Worker tarafı: callback bloğu (işlenenler) ve her yerdeki menüler (üretilenler)
# ---------------------------------------------------------------------------

def _worker() -> str:
    return (KOK / "worker/index.js").read_text(encoding="utf-8")


def _callback_blogu(js: str) -> str:
    bas = js.index("if (update.callback_query) {")
    i = js.index("{", bas)
    derinlik = 0
    for j in range(i, len(js)):
        if js[j] == "{":
            derinlik += 1
        elif js[j] == "}":
            derinlik -= 1
            if derinlik == 0:
                return js[bas:j]
    raise AssertionError("Worker callback bloğunun sonu bulunamadı")


def worker_islenenler() -> tuple[set[str], set[str]]:
    """(tam eşleşmeler, önek eşleşmeleri) — callback bloğunda `data` ile karşılaştırılanlar."""
    blok = _callback_blogu(_worker())
    tam = set(re.findall(r'\bdata === "([^"]+)"', blok))
    onek = set(re.findall(r'\bdata\.startsWith\("([^"]+)"\)', blok))
    # Düzenli ifadeyle karşılaştırma: `/^sec:\d+$/.test(data)` ve `const kalip = /^yayinla_(?:ses_)?sonra:.../` (sonra `kalip.test(data)`)
    for m in re.finditer(r'/\^([a-z_]+)[^/\n]*/[a-z]*\.test\(data\)', blok):
        onek.add(m.group(1) + ":")
    for m in re.finditer(r'const kalip = /\^([^/\n]+)/', blok):
        gövde = m.group(1)
        for ad in re.findall(r'[a-z_]+(?=:)', gövde):
            onek.add(ad + ":")
        if gövde.startswith("yayinla_"):   # `yayinla_(?:ses_)?sonra:` gibi gruplu yazılış
            onek.update({"yayinla_sonra:", "yayinla_ses_sonra:"})
    return tam, onek


def worker_uretilenler() -> dict[str, list[int]]:
    """Worker kaynağındaki her `callback_data: "..."` / şablon dizesi → {önek: [satır]}."""
    js = _worker()
    bulunan: dict[str, list[int]] = defaultdict(list)
    for m in re.finditer(r'callback_data:\s*(?:"([^"\n]*)"|`([^`\n]*)`)', js):
        ham = m.group(1) if m.group(1) is not None else m.group(2)
        onek = ham.split("${", 1)[0]
        bulunan[onek].append(js.count("\n", 0, m.start()) + 1)
    return dict(bulunan)


def islenir(ad: str, tam: set[str], onek: set[str]) -> bool:
    return ad in tam or any(ad.startswith(o) for o in onek) or any(ad == o.rstrip(":") for o in onek)


# ---------------------------------------------------------------------------
# Testler
# ---------------------------------------------------------------------------

class TestAyristiriciCurumedi(unittest.TestCase):
    """Ayrıştırıcılar boş döner de testler sessizce geçmesin."""

    def test_python_tarafi_yeterince_dugme_buluyor(self):
        butonlar, cozulemeyen = python_butonlari()
        self.assertGreater(len(butonlar), 100, "Python tarafında beklenenden çok az callback_data bulundu: ayrıştırıcı bozuk olabilir")
        self.assertLessEqual(len(cozulemeyen), 3, f"Çözülemeyen callback_data ifadeleri çoğaldı, ayrıştırıcıyı genişletin: {cozulemeyen}")

    def test_worker_callback_blogu_dogru_kesildi(self):
        blok = _callback_blogu(_worker())
        self.assertIn("kanal:", blok.split("\n", 60)[-1] if False else blok)
        self.assertIn('data.startsWith("kota_kat:")', blok, "Bloğun sonundaki kota işleyicisi yok: blok eksik kesilmiş")
        self.assertGreater(blok.count("\n"), 600)

    def test_worker_islenenleri_ve_urettikleri_yeterli(self):
        tam, onek = worker_islenenler()
        self.assertGreater(len(tam) + len(onek), 70)
        self.assertTrue({"panel", "durum", "iptal"} <= tam, f"temel düğmeler işlenenlerde yok: {sorted(tam)[:20]}")
        self.assertTrue({"kanal:", "yayinla_sonra:", "sec:", "ayarsec:"} <= onek, f"önek kalıpları eksik: {sorted(onek)}")
        self.assertGreater(len(worker_uretilenler()), 60)


class TestPythonButonlariWorkerdaIslenir(unittest.TestCase):
    def test_python_in_urettigi_her_buton_worker_da_islenir(self):
        butonlar, _ = python_butonlari()
        tam, onek = worker_islenenler()
        olu = {ad: yerler[:2] for ad, yerler in sorted(butonlar.items())
               if ad and ad not in BILINEN_OLU and not islenir(ad, tam, onek)}
        self.assertEqual(
            olu, {},
            "Python bu butonları üretiyor ama Worker callback bloğu işlemiyor (butona basınca HİÇBİR ŞEY olmaz). "
            "Python'daki adı Worker'ın işlediği adla eşleyin ya da worker/index.js'e işleyici ekleyin: "
            + "; ".join(f"{ad!r} ← {yerler}" for ad, yerler in olu.items()),
        )

    def test_bilinen_olu_liste_cürümedi(self):
        butonlar, _ = python_butonlari()
        tam, onek = worker_islenenler()
        for ad, neden in BILINEN_OLU.items():
            with self.subTest(ad=ad):
                self.assertIn(ad, butonlar, f"BILINEN_OLU'daki '{ad}' artık hiçbir yerde üretilmiyor: listeden silin ({neden})")
                self.assertFalse(islenir(ad, tam, onek), f"'{ad}' artık Worker'da işleniyor: listeden silin")

    def test_bos_onekli_butonlar_yok(self):
        """`callback_data` tümüyle değişkenden geliyorsa (önek yok) sözleşme doğrulanamaz; yenisi eklenirse haber ver."""
        butonlar, _ = python_butonlari()
        self.assertEqual(butonlar.get("", []), [], f"Öneksiz callback_data: {butonlar.get('', [])}")


class TestWorkerKendiMenuleri(unittest.TestCase):
    def test_worker_in_urettigi_her_buton_yine_worker_da_islenir(self):
        tam, onek = worker_islenenler()
        olu = {ad: satirlar[:3] for ad, satirlar in sorted(worker_uretilenler().items())
               if ad and not islenir(ad, tam, onek)}
        self.assertEqual(
            olu, {},
            "Worker kendi menülerinde bu butonları üretiyor ama callback bloğunda işleyicisi yok (worker/index.js satırları): "
            + "; ".join(f"{ad!r} ← {s}" for ad, s in olu.items()),
        )


class TestOlayVeBoyutSozlesmesi(unittest.TestCase):
    def test_worker_in_yolladigi_her_olayi_bir_workflow_dinliyor(self):
        js = _worker()
        olaylar = (set(re.findall(r'\btetikle\(env, [A-Za-z]+, "([a-z_]+)"', js))
                   | set(re.findall(r'\btetikleGitHub\(env, "([a-z_]+)"', js))
                   | set(re.findall(r'\bolay: "([a-z_]+)"', js)))
        self.assertGreaterEqual(len(olaylar), 10, f"Worker olayları az bulundu: {sorted(olaylar)}")
        dinlenen: set[str] = set()
        for dosya in (KOK / ".github/workflows").glob("*.yml"):
            w = yaml.safe_load(dosya.read_text(encoding="utf-8"))
            dinlenen |= set(((w.get(True) or {}).get("repository_dispatch") or {}).get("types", []))
        self.assertEqual(sorted(olaylar - dinlenen), [],
                         "Worker bu olayları GitHub'a yolluyor ama hiçbir workflow dinlemiyor (tetik boşa gider)")

    def test_statik_buton_adlari_64_bayti_asmaz(self):
        """Telegram `callback_data` en çok 64 bayt kabul eder; fazlası mesajın TAMAMINI reddettirir (düğmeli kart hiç gitmez)."""
        butonlar, _ = python_butonlari()
        uzun = {ad: len(ad.encode("utf-8")) for ad in butonlar if len(ad.encode("utf-8")) > 64}
        for ad, satirlar in worker_uretilenler().items():
            if len(ad.encode("utf-8")) > 64:
                uzun[ad] = len(ad.encode("utf-8"))
        self.assertEqual(uzun, {}, f"64 baytı aşan callback_data önekleri: {uzun}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
