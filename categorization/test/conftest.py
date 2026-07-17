"""
conftest.py — Test kurulumu (Kişi 1)

categorization/ klasörünü import yoluna ekler; böylece testler
`from cleaning import ...` şeklinde, üretim kodunun kendi import
stiliyle aynı biçimde yazılabilir.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
