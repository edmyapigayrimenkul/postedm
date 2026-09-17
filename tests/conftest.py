"""
tests/conftest.py — Pytest ve test çalıştırma yapılandırması
Test ortamında hiçbir ağ çağrısının veya git commit işleminin canlıya sızmamasını garanti eder.
"""

import os

os.environ["POSTEDM_TEST_MODU"] = "1"
