"""
tests/test_zamanli_isler.py — Faz 5: zamanlanmış işler Cloudflare cron'undan tetiklenir, GitHub cron'u yedektir (2026-10-13)

Günlük rapor, haber önerisi ve onay hatırlatıcı eskiden yalnız GitHub `schedule` ile çalışıyordu ve 6-10 saat gecikiyordu. Artık
Worker aynı saatlerde `repository_dispatch` {slot, zamanli: true} yollar; workflow'lardaki GitHub cron'ları YEDEK kalır.
İkisi birden çalışabildiği için aynı slot aynı Türkiye gününde bir kez çalışmalı (scripts/zamanli_koruma.py).

Burada iki şey sınanır:
  1. Üç yerin uyumu: Worker tablosu (index.js › ZAMANLI_ISLER) ↔ wrangler.toml crons ↔ workflow cron/slot/olay adları ↔ dağıtım doğrulaması.
     Biri değişip diğeri unutulursa iş sessizce hiç çalışmaz ya da günde iki kez çalışır.
  2. Koruma betiğinin davranışı (ilk koşu çalışır ve işaretlenir, yedek atlanır, elle istek korumaya takılmaz, başarısız tur işaretlenmez).
"""

from __future__ import annotations

import os
os.environ.setdefault("POSTEDM_TEST_MODU", "1")  # üretim .env/DB'sine dokunma — bkz. src/config.py

import importlib.util
import re
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

import yaml

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from src import telegram_bot as tb

# workflow dosyası → (repository_dispatch olayı, iş adı) — Worker tablosundaki `olay` ile aynı olmalı
ISLER = {
    "hatirlat.yml": "hatirlat",
    "haber-oneri.yml": "haber_oneri",
    "gunluk-rapor.yml": "rapor",
    "hazirla.yml": "slot_hazirla",
}


def _workflow(ad: str) -> dict:
    return yaml.safe_load((KOK / ".github/workflows" / ad).read_text(encoding="utf-8"))


def _worker_tablosu() -> dict[str, tuple[str, str]]:
    """index.js › ZAMANLI_ISLER: {cron: (olay, slot)}."""
    kaynak = (KOK / "worker/index.js").read_text(encoding="utf-8")
    govde = kaynak[kaynak.index("const ZAMANLI_ISLER = {"):]
    govde = govde[:govde.index("\n};")]
    bulunan = re.findall(r'"([^"]+)":\s*\{\s*olay:\s*"([^"]+)",\s*slot:\s*"([^"]+)"', govde)
    return {cron: (olay, slot) for cron, olay, slot in bulunan}


def _wrangler_cronlari() -> list[str]:
    return tomllib.loads((KOK / "worker/wrangler.toml").read_text(encoding="utf-8"))["triggers"]["crons"]


def _github_cronlari(ad: str) -> set[str]:
    return {c["cron"] for c in (_workflow(ad).get(True) or {}).get("schedule", [])}


class TestUcYerinUyumu(unittest.TestCase):
    def test_worker_tablosu_okunabiliyor(self):
        tablo = _worker_tablosu()
        self.assertEqual(len(tablo), 7, f"ZAMANLI_ISLER 7 iş içermeli (2 içerik turu, rapor, 2 haber önerisi, 2 hatırlatma): {tablo}")

    def test_wrangler_crons_worker_tablosu_ve_plan_cronu_ile_ayni(self):
        beklenen = set(_worker_tablosu()) | {"*/10 * * * *"}
        self.assertEqual(set(_wrangler_cronlari()), beklenen,
                         "wrangler.toml › triggers.crons ile index.js › ZAMANLI_ISLER (+ plan cron'u) birebir aynı olmalı: "
                         "tabloda olup toml'da olmayan iş hiç tetiklenmez, toml'da olup tabloda olmayan cron boşa çalışır.")
        self.assertEqual(len(_wrangler_cronlari()), len(set(_wrangler_cronlari())), "wrangler.toml'da yinelenen cron var")

    def test_dagitim_dogrulamasi_wrangler_ile_ayni_cronlari_bekliyor(self):
        metin = (KOK / ".github/workflows/worker-dagit.yml").read_text(encoding="utf-8")
        blok = metin[metin.index("beklenen = {"):]
        blok = blok[:blok.index("}")]
        beklenen = set(re.findall(r'"([^"]+)"', blok))
        self.assertEqual(beklenen, set(_wrangler_cronlari()),
                         "Worker Dağıt doğrulaması wrangler.toml'daki cron'ların hepsini (ve yalnız onları) beklemeli")

    def test_her_isin_olayi_workflow_tarafindan_dinleniyor(self):
        for cron, (olay, _slot) in _worker_tablosu().items():
            dinleyenler = [ad for ad in ISLER if olay in ((_workflow(ad).get(True) or {}).get("repository_dispatch") or {}).get("types", [])]
            self.assertTrue(dinleyenler, f"{cron}: Worker '{olay}' olayını yolluyor ama hiçbir workflow bu olayı dinlemiyor")

    def test_her_cloudflare_cronunun_github_yedegi_ayni_saatte(self):
        """Cloudflare ve GitHub cron'ları AYNI UTC saatinde: biri diğerinin yedeği (aynı slot, aynı gün)."""
        for cron, (olay, slot) in _worker_tablosu().items():
            dosya = next(ad for ad, o in ISLER.items() if o == olay)
            self.assertIn(cron, _github_cronlari(dosya), f"{slot}: {dosya} içinde yedek GitHub cron'u '{cron}' yok")

    def test_workflow_slotlari_korunan_slotlarla_ayni(self):
        """Workflow'daki ZAMANLI_SLOT ifadesinin ürettiği her ad, ZAMANLI_GUNLUK_SLOTLAR'da ve Worker tablosunda olmalı."""
        worker_slotlari = {slot for _o, slot in _worker_tablosu().values()}
        for ad in ("hatirlat.yml", "haber-oneri.yml", "gunluk-rapor.yml"):
            job = next(iter(_workflow(ad)["jobs"].values()))
            ifade = job["env"]["ZAMANLI_SLOT"]
            adlar = set(re.findall(r"'([a-z_]+)'", ifade)) or {ifade}
            adlar = {a for a in adlar if a not in ("cloudflare_cron",)}
            # `github.event.schedule == '17 15 * * *'` gibi cron karşılaştırmaları ad değildir
            adlar = {a for a in adlar if not re.search(r"\d", a)}
            self.assertTrue(adlar, f"{ad}: ZAMANLI_SLOT ifadesinden slot adı çıkarılamadı: {ifade}")
            for a in adlar:
                self.assertIn(a, tb.ZAMANLI_GUNLUK_SLOTLAR, f"{ad}: '{a}' korunan slotlar arasında değil → koruma uygulanmaz")
                self.assertIn(a, worker_slotlari, f"{ad}: '{a}' Worker tablosunda yok → Cloudflare bu slotu hiç yollamaz")

    def test_her_worker_slotu_korunuyor(self):
        for cron, (_olay, slot) in _worker_tablosu().items():
            self.assertIn(slot, tb.ZAMANLI_GUNLUK_SLOTLAR, f"{cron}: '{slot}' ZAMANLI_GUNLUK_SLOTLAR'da yok → ikinci tetik ikinci kez çalışır")

    def test_uc_workflow_koruma_adimina_sahip_ve_isi_ona_bagli(self):
        for ad in ("hatirlat.yml", "haber-oneri.yml", "gunluk-rapor.yml"):
            job = next(iter(_workflow(ad)["jobs"].values()))
            adimlar = job["steps"]
            adlar = [a.get("name") for a in adimlar]
            self.assertIn("Zamanlı koruma (günde bir kez)", adlar, ad)
            self.assertIn("Zamanlı işi işaretle", adlar, ad)
            self.assertLess(adlar.index("Zamanlı koruma (günde bir kez)"), adlar.index("Zamanlı işi işaretle"), ad)
            self.assertIn("client_payload.zamanli", str(job["env"]["ZAMANLANMIS"]),
                          f"{ad}: Worker'ın yolladığı iş 'zamanlanmış koşu' sayılmıyor, koruma atlanır")
            koruma = next(a for a in adimlar if a.get("name") == "Zamanlı koruma (günde bir kez)")
            self.assertEqual(koruma["id"], "koruma")
            isaret = next(a for a in adimlar if a.get("name") == "Zamanlı işi işaretle")
            self.assertIn("success()", isaret["if"], f"{ad}: başarısız tur işaretlenirse yedek tetik işi yeniden deneyemez")
            self.assertIn("steps.koruma.outputs.atla", isaret["if"])
            # Koruma ile işaret arasındaki her gerçek iş adımı atlanabilir olmalı
            for a in adimlar[adlar.index("Zamanlı koruma (günde bir kez)") + 1:adlar.index("Zamanlı işi işaretle")]:
                self.assertIn("steps.koruma.outputs.atla", str(a.get("if", "")), f"{ad} › {a.get('name')}: koruma atlasa da çalışır")

    def test_haber_onerisi_zamanli_yuk_elle_istek_sayilmaz(self):
        """Worker'ın haber_oneri yükü `--haber-oneri` yoluna gitmeli; Telegram düğmesi/komutu (zamanli yok) `--slot haber`e."""
        job = _workflow("haber-oneri.yml")["jobs"]["oneri"]
        adim = next(a for a in job["steps"] if a.get("name") == "Haberleri tara ve öner")
        elle = adim["env"]["ELLE"]
        self.assertIn("client_payload.zamanli != true", elle)
        self.assertIn("github.event_name != 'schedule'", elle)

    def test_hatirlat_zamanli_yuk_zorla_modunu_acmaz(self):
        adim = next(a for a in _workflow("hatirlat.yml")["jobs"]["hatirlat"]["steps"] if a.get("name", "").startswith("Kuyruk bakımını çalıştır"))
        self.assertNotIn("zamanli", adim["env"]["ZORLA"])


class SahteAyarlar:
    def __init__(self):
        self.veri: dict[str, str] = {}

    def oku(self, anahtar, varsayilan=None):
        return self.veri.get(anahtar, varsayilan)

    def yaz(self, anahtar, deger):
        self.veri[anahtar] = str(deger)


def _koruma_modulu():
    spec = importlib.util.spec_from_file_location("zamanli_koruma_modul", KOK / "scripts" / "zamanli_koruma.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


class TestKorumaBetigi(unittest.TestCase):
    BUGUN, DUN = "2026-10-13", "2026-10-12"

    def setUp(self):
        self.koruma = _koruma_modulu()
        self.ayar = SahteAyarlar()
        self.bugun = self.BUGUN
        yamalar = [
            mock.patch("src.db.ayar_oku", side_effect=self.ayar.oku),
            mock.patch("src.db.ayar_yaz", side_effect=self.ayar.yaz),
            mock.patch("src.telegram.akislar.zamanli._tr_bugun", side_effect=lambda: self.bugun),
        ]
        for y in yamalar:
            y.start()
            self.addCleanup(y.stop)

    def env(self, slot="hatirlat_ogle", zamanlanmis="true", **ek):
        return {"ZAMANLANMIS": zamanlanmis, "ZAMANLI_SLOT": slot, **ek}

    def test_ilk_kosu_calisir_isaretlenir_yedek_atlanir(self):
        self.assertFalse(self.koruma.kontrol(self.env()))
        self.assertTrue(self.koruma.isaretle(self.env()))
        self.assertEqual(self.ayar.veri["zamanli_slot_son_gun:hatirlat_ogle"], self.BUGUN)
        self.assertTrue(self.koruma.kontrol(self.env()), "aynı gün ikinci tetik (GitHub yedeği) atlanmalı")

    def test_ertesi_gun_yeniden_calisir(self):
        self.ayar.veri["zamanli_slot_son_gun:rapor"] = self.DUN
        self.assertFalse(self.koruma.kontrol(self.env("rapor")))

    def test_slotlar_birbirinden_bagimsiz(self):
        """Öğle hatırlatması yapıldı diye akşam hatırlatması ya da haber önerisi atlanmaz."""
        self.koruma.isaretle(self.env("hatirlat_ogle"))
        for diger in ("hatirlat_aksam", "haber_oneri_sabah", "haber_oneri_aksam", "rapor", "bilgilendirici", "sozluk"):
            self.assertFalse(self.koruma.kontrol(self.env(diger)), diger)

    def test_elle_istek_korumaya_takilmaz_ve_onu_tuketmez(self):
        self.ayar.veri["zamanli_slot_son_gun:hatirlat_ogle"] = self.BUGUN
        self.assertFalse(self.koruma.kontrol(self.env(zamanlanmis="false")), "elle tetikleme bugün yapılmış olsa da çalışmalı")
        self.assertFalse(self.koruma.isaretle(self.env("rapor", zamanlanmis="false")))
        self.assertNotIn("zamanli_slot_son_gun:rapor", self.ayar.veri, "elle istek zamanlı slotu 'yapıldı' diye işaretlememeli")

    def test_zamanlanmis_degeri_buyuk_kucuk_harf_ve_bosluga_dayanikli(self):
        self.ayar.veri["zamanli_slot_son_gun:rapor"] = self.BUGUN
        self.assertTrue(self.koruma.kontrol(self.env("rapor", zamanlanmis=" True ")))

    def test_bilinmeyen_ya_da_bos_slot_korumasiz_calisir_isaret_yazmaz(self):
        """Yazım hatası işi sessizce İPTAL etmemeli (atla=false); ama rastgele anahtar da yazılmamalı."""
        for slot in ("", "hatirlat_ogel", "haber"):
            self.assertFalse(self.koruma.kontrol(self.env(slot)), repr(slot))
            self.assertFalse(self.koruma.isaretle(self.env(slot)), repr(slot))
        self.assertEqual(self.ayar.veri, {})

    def test_main_github_output_dosyasina_yazar(self):
        with tempfile.TemporaryDirectory() as d:
            cikti = Path(d) / "out.txt"
            env = self.env("rapor", GITHUB_OUTPUT=str(cikti))
            self.assertEqual(self.koruma.main(["kontrol"], env), 0)
            self.assertEqual(cikti.read_text(encoding="utf-8"), "atla=false\n")
            self.assertEqual(self.koruma.main(["isaretle"], env), 0)
            self.assertEqual(self.koruma.main(["kontrol"], env), 0)
            self.assertEqual(cikti.read_text(encoding="utf-8"), "atla=false\natla=true\n")

    def test_main_gecersiz_komutta_hata_kodu_doner(self):
        self.assertEqual(self.koruma.main([], {}), 2)
        self.assertEqual(self.koruma.main(["sil"], {}), 2)
        self.assertEqual(self.koruma.main(["kontrol", "fazla"], {}), 2)


class TestTurkiyeGunu(unittest.TestCase):
    """Koruma TÜRKİYE gününe bağlı: 13:30 hatırlatması ile 21:30 hatırlatması aynı gündür, gece yarısından sonrası yeni gündür."""

    def _bugun(self, utc_an):
        from datetime import datetime, timezone
        from src.telegram.akislar import zamanli

        class Sahte(datetime):
            @classmethod
            def now(cls, tz=None):
                return utc_an.astimezone(tz) if tz else utc_an

        with mock.patch.object(zamanli, "datetime", Sahte):
            return zamanli._tr_bugun()

    def test_utc_2130_ayni_turkiye_gunu_utc_2130_ertesi_gundur(self):
        from datetime import datetime, timezone
        self.assertEqual(self._bugun(datetime(2026, 10, 13, 18, 30, tzinfo=timezone.utc)), "2026-10-13")   # 21:30 TR
        self.assertEqual(self._bugun(datetime(2026, 10, 13, 21, 0, tzinfo=timezone.utc)), "2026-10-14")    # 00:00 TR
        self.assertEqual(self._bugun(datetime(2026, 10, 13, 5, 40, tzinfo=timezone.utc)), "2026-10-13")    # 08:40 TR


if __name__ == "__main__":
    unittest.main(verbosity=2)
