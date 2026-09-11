"""
tests/test_butunluk.py — Bütünlük Testleri (ÖNCE BUNU ÇALIŞTIR)

Kodu ÇALIŞTIRMADAN ayrıştırır. Ağa çıkmaz, veritabanına dokunmaz, para
harcamaz, saniyeler sürer.

NİYE VAR — iki gerçek olay:

1. LXML OLAYI (8-11 Eylül 2026). `fetch_news` BeautifulSoup(..., "xml")
   kullanıyor ve bu lxml gerektiriyor. lxml requirements.txt'te yoktu.
   Yerel venv'de kurulu olduğu için geliştirmede fark edilmedi; GitHub
   Actions'ta ÜÇ GÜN boyunca her RSS kaynağı sessizce düştü. Haber akışı
   üretimde hiç çalışmamıştı.

2. ÇAĞRI/İMZA HATALARI (instabot'ta üç kez). `fetch_news.hepsini_cek`
   (öyle bir fonksiyon yok), `metinleri_uret(con, ...)` (yanlış imza).
   Hepsi sözdizimsel geçerliydi, diğer testler geçiyordu, ilk gerçek
   çalıştırmada patladılar. Python modül çağrısını ancak o satır çalışınca
   çözümlüyor — gözetimsiz bir botta bu "gece cron patlar, sabah fark
   edilir" demektir.

⚠️ YANLIŞ POZİTİF DİSİPLİNİ: yanlış alarm veren test, hiç olmayan testten
kötüdür — insan onu görmezden gelmeye başlar. Şüpheli her durumda test
sessiz kalır; yalnızca KESİN hatalar raporlanır.
"""

from __future__ import annotations

import ast
import inspect
import sys
import sysconfig
import unittest
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))


def _python_dosyalari() -> list[Path]:
    dosyalar: list[Path] = []
    for klasor in ("src", "scripts", "tests"):
        dosyalar.extend(sorted((KOK / klasor).glob("*.py")))
    return [d for d in dosyalar if d.name != "__init__.py"]


# ---------------------------------------------------------------------------
# 1) BAĞIMLILIK BÜTÜNLÜĞÜ
# ---------------------------------------------------------------------------

# Import adı ile PyPI paket adı çoğu zaman farklı.
IMPORT_PAKET = {
    "yaml": "PyYAML",
    "bs4": "beautifulsoup4",
    "PIL": "Pillow",
    "dotenv": "python-dotenv",
    "dateutil": "python-dateutil",
    "imageio_ffmpeg": "imageio-ffmpeg",
    "google": "google-api-python-client",
    "googleapiclient": "google-api-python-client",
    "fontTools": "fonttools",       # import adı büyük T taşıyor
    "brotli": "Brotli",
}

# Doğrudan import edilmese de gereken paketler (ayrıştırıcı eklentileri gibi).
# lxml tam olarak bu sınıfta: kod "lxml" yazmıyor, BeautifulSoup(..., "xml")
# diyor ve bs4 arka planda lxml arıyor.
ORTULU_BAGIMLILIKLAR = {
    "lxml": 'BeautifulSoup(..., "xml") bu paketi gerektirir',
}


def _yerel_modul_mu(ad: str) -> bool:
    kok = ad.split(".")[0]
    return kok in {"src", "scripts", "tests"} or (KOK / kok).exists()


def _stdlib_mi(ad: str) -> bool:
    kok = ad.split(".")[0]
    if kok in sys.stdlib_module_names:
        return True
    # Yerleşik olmayan ama kurulu paketleri ayırt etmek için yol kontrolü
    yol = sysconfig.get_paths().get("stdlib", "")
    return bool(yol) and (Path(yol) / f"{kok}.py").exists()


class TestBagimlilik(unittest.TestCase):
    """Import edilen her üçüncü parti paket requirements.txt'te olmalı."""

    def setUp(self) -> None:
        ham = (KOK / "requirements.txt").read_text(encoding="utf-8")
        self.paketler = set()
        for satir in ham.splitlines():
            satir = satir.split("#")[0].strip()
            if not satir:
                continue
            ad = satir.split(">=")[0].split("==")[0].split("[")[0].strip()
            self.paketler.add(ad.lower().replace("_", "-"))

    def _kayitli_mi(self, paket: str) -> bool:
        return paket.lower().replace("_", "-") in self.paketler

    def test_ucuncu_parti_importlar_requirements_icinde(self) -> None:
        eksik: dict[str, set[str]] = {}
        for dosya in _python_dosyalari():
            agac = ast.parse(dosya.read_text(encoding="utf-8"), filename=str(dosya))
            for dugum in ast.walk(agac):
                adlar: list[str] = []
                if isinstance(dugum, ast.Import):
                    adlar = [a.name for a in dugum.names]
                elif isinstance(dugum, ast.ImportFrom) and dugum.level == 0 and dugum.module:
                    adlar = [dugum.module]
                for ad in adlar:
                    kok = ad.split(".")[0]
                    if _stdlib_mi(kok) or _yerel_modul_mu(kok):
                        continue
                    paket = IMPORT_PAKET.get(kok, kok)
                    if not self._kayitli_mi(paket):
                        eksik.setdefault(paket, set()).add(
                            f"{dosya.relative_to(KOK)} (import {kok})"
                        )

        self.assertFalse(
            eksik,
            "requirements.txt'te olmayan paketler import ediliyor.\n"
            "Yerelde kurulu olduğu için çalışıyor gibi görünür, runner'da patlar:\n"
            + "\n".join(f"  {p}: {', '.join(sorted(y))}" for p, y in sorted(eksik.items())),
        )

    def test_ortulu_bagimliliklar_requirements_icinde(self) -> None:
        """Kodda adı geçmeyen ama gereken paketler.

        lxml bu testin var oluş sebebi: kimse `import lxml` yazmıyor, ama
        onsuz RSS taramasının tamamı sessizce düşüyor.
        """
        eksik = [
            f"{p} — {sebep}"
            for p, sebep in ORTULU_BAGIMLILIKLAR.items()
            if not self._kayitli_mi(p)
        ]
        self.assertFalse(eksik, "Örtülü bağımlılık eksik:\n  " + "\n  ".join(eksik))

    def test_requirements_gercekten_kurulabilir(self) -> None:
        """requirements.txt'teki her paket bu ortamda import edilebiliyor mu."""
        # Ters harita küçük harfle kurulur: requirements'taki "Pillow" ile
        # haritadaki "Pillow" karşılaştırması aksi halde tutmuyor ve test
        # "pillow import edilemiyor" diye YANLIŞ ALARM veriyordu.
        PAKET_IMPORT = {v.lower().replace("_", "-"): k for k, v in IMPORT_PAKET.items()}
        kurulamayan = []
        for paket in sorted(self.paketler):
            modul = PAKET_IMPORT.get(paket, paket.replace("-", "_"))
            try:
                __import__(modul)
            except ImportError:
                kurulamayan.append(f"{paket} (import {modul})")
            except Exception:
                pass  # import sırasında başka hata: paket var, sorun bizim değil
        self.assertFalse(
            kurulamayan,
            "requirements.txt'te yazan ama import edilemeyen paketler:\n  "
            + "\n  ".join(kurulamayan),
        )


# ---------------------------------------------------------------------------
# 2) ÇAĞRI VE İMZA BÜTÜNLÜĞÜ
# ---------------------------------------------------------------------------

class TestCagriButunlugu(unittest.TestCase):
    """`modul.fonksiyon(...)` çağrılarının hepsi gerçekten var mı, imza uyuyor mu."""

    # Bu modüller içe aktarılıp fonksiyonları denetlenir.
    DENETLENEN = [
        "src.konu_bankasi", "src.generate_text", "src.make_image",
        "src.haber_puanlama", "src.haber_triyaj", "src.fetch_news",
        "src.telegram_bot", "src.db", "src.config",
    ]

    def setUp(self) -> None:
        self.moduller = {}
        for ad in self.DENETLENEN:
            try:
                self.moduller[ad.split(".")[-1]] = __import__(ad, fromlist=["x"])
            except Exception as e:  # pragma: no cover
                self.fail(f"{ad} içe aktarılamadı: {type(e).__name__}: {e}")

    def test_cagrilan_fonksiyonlar_var(self) -> None:
        eksik = []
        for dosya in _python_dosyalari():
            agac = ast.parse(dosya.read_text(encoding="utf-8"), filename=str(dosya))
            for dugum in ast.walk(agac):
                if not (isinstance(dugum, ast.Call) and isinstance(dugum.func, ast.Attribute)):
                    continue
                if not isinstance(dugum.func.value, ast.Name):
                    continue
                modul_adi = dugum.func.value.id
                modul = self.moduller.get(modul_adi)
                if modul is None:
                    continue
                if not hasattr(modul, dugum.func.attr):
                    eksik.append(
                        f"{dosya.relative_to(KOK)}:{dugum.lineno} → "
                        f"{modul_adi}.{dugum.func.attr}() yok"
                    )
        self.assertFalse(eksik, "Var olmayan fonksiyon çağrıları:\n  " + "\n  ".join(eksik))

    def test_cagri_argumanlari_imzaya_uyuyor(self) -> None:
        hatalar = []
        for dosya in _python_dosyalari():
            agac = ast.parse(dosya.read_text(encoding="utf-8"), filename=str(dosya))
            for dugum in ast.walk(agac):
                if not (isinstance(dugum, ast.Call) and isinstance(dugum.func, ast.Attribute)):
                    continue
                if not isinstance(dugum.func.value, ast.Name):
                    continue
                modul = self.moduller.get(dugum.func.value.id)
                if modul is None or not hasattr(modul, dugum.func.attr):
                    continue
                hedef = getattr(modul, dugum.func.attr)
                if not callable(hedef) or inspect.isclass(hedef):
                    continue
                try:
                    imza = inspect.signature(hedef)
                except (ValueError, TypeError):
                    continue

                # *args/**kwargs varsa imza esnektir, denetlemiyoruz
                if any(p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
                       for p in imza.parameters.values()):
                    continue
                # Çağrıda yıldızlı açılım varsa neyin geçtiğini bilemeyiz
                if any(isinstance(a, ast.Starred) for a in dugum.args) or \
                   any(k.arg is None for k in dugum.keywords):
                    continue

                yer = f"{dosya.relative_to(KOK)}:{dugum.lineno} {dugum.func.value.id}.{dugum.func.attr}()"

                gecerli = set(imza.parameters)
                for k in dugum.keywords:
                    if k.arg not in gecerli:
                        hatalar.append(f"{yer} → '{k.arg}' diye bir parametre yok")

                if len(dugum.args) > len(imza.parameters):
                    hatalar.append(
                        f"{yer} → {len(dugum.args)} konumsal argüman verildi, "
                        f"imza {len(imza.parameters)} alıyor"
                    )
        self.assertFalse(hatalar, "İmzaya uymayan çağrılar:\n  " + "\n  ".join(hatalar))


if __name__ == "__main__":
    unittest.main(verbosity=2)
