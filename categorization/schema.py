"""
schema.py — Kanonik Veri Kontratı (Kişi 1 — Veri & Ekstre İşleme)
================================================================

Bu dosya, tüm ekibin (Kişi 2/3/4/5) üzerinde anlaşacağı TEK kaynak (single
source of truth) veri sözleşmesidir. CSV, Excel ve PDF kaynaklarından gelen
her işlem (transaction) buradaki `TransactionRecord` şemasına map edilir.

Orijinal kontrat (yzta_bootcamp_2026/column_description.md) 7 alan tanımlıyordu:
    Date, Description, Amount, Transaction Type, Category, Account Name, Month

Biz bu 7 alanı JSON-dostu snake_case anahtarlarla koruyor + downstream ekibin
(anomali tespiti, dashboard, AI agent) işini kolaylaştıracak birkaç kritik
genişletme alanı ekliyoruz (currency, source, category_original, transaction_id).

Alan eşleştirmesi (kontrat -> bu şema):
    Date              -> date
    Description        -> description
    Amount            -> amount
    Transaction Type  -> transaction_type
    Category          -> category
    Account Name      -> account_name
    Month             -> month
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# 1) KANONİK ALANLAR (JSON kayıt anahtarları)
# --------------------------------------------------------------------------- #

# Orijinal kontrattaki çekirdek 7 alan (snake_case karşılıkları)
CORE_FIELDS = [
    "date",              # "YYYY-MM-DD"
    "description",       # str
    "amount",            # float, her zaman pozitif
    "transaction_type",  # "debit" | "credit"
    "category",          # kanonik kategori (aşağıdaki CANONICAL_CATEGORIES)
    "account_name",      # str
    "month",             # "YYYY-MM"
]

# Kişi 1'in eklediği, downstream için hayati genişletme alanları
EXTENSION_FIELDS = [
    "transaction_id",     # str, kaynak+alanlardan üretilen kararlı (stable) hash
    "currency",           # "INR" | "USD" | ...  (kaynaklar farklı para birimi!)
    "category_original",  # str, kaynaktaki ham kategori (Kişi 2 yeniden gruplayabilsin)
    "source",             # "india_csv" | "us_xlsx" | "pdf_<banka>"
]

ALL_FIELDS = CORE_FIELDS + EXTENSION_FIELDS


# --------------------------------------------------------------------------- #
# 2) İZİN VERİLEN DEĞERLER
# --------------------------------------------------------------------------- #

TRANSACTION_TYPES = {"debit", "credit"}

# Birleşik (unified) kategori taksonomisi.
# İki dataset farklı kategori isimleri kullanıyor; hepsini bu ~13 kanonik
# kovaya map ediyoruz. Kişi 2 dilerse bunları 6-8 üst kategoriye indirger,
# ham kategori `category_original` alanında korunduğu için bilgi kaybı olmaz.
CANONICAL_CATEGORIES = [
    "Groceries",
    "Food & Dining",
    "Shopping",
    "Electronics",
    "Transport",
    "Travel",
    "Bills & Utilities",
    "Entertainment",
    "Healthcare",
    "Housing",
    "Personal Care",
    "Income",
    "Transfers & Payments",
    "Other",  # eşleşmeyen her şey buraya (asla sessizce kaybolmasın)
]

# Ham kategori (küçük harfe indirgenmiş) -> kanonik kategori
# Sol taraftaki tüm anahtarlar iki datasette gerçekten görülen kategorilerdir.
CATEGORY_MAP = {
    # --- Hindistan CSV kategorileri (10 adet) ---
    "grocery": "Groceries",
    "food": "Food & Dining",
    "online shopping": "Shopping",
    "clothing": "Shopping",
    "electronics": "Electronics",
    "transport": "Transport",
    "travel": "Travel",
    "bills": "Bills & Utilities",
    "entertainment": "Entertainment",
    "healthcare": "Healthcare",
    # --- ABD Excel kategorileri (22 adet) ---
    "groceries": "Groceries",
    "restaurants": "Food & Dining",
    "fast food": "Food & Dining",
    "coffee shops": "Food & Dining",
    "alcohol & bars": "Food & Dining",
    "food & dining": "Food & Dining",
    "shopping": "Shopping",
    "electronics & software": "Electronics",
    "gas & fuel": "Transport",
    "auto insurance": "Transport",
    "utilities": "Bills & Utilities",
    "mobile phone": "Bills & Utilities",
    "internet": "Bills & Utilities",
    "television": "Bills & Utilities",
    "music": "Entertainment",
    "movies & dvds": "Entertainment",
    "home improvement": "Housing",
    "mortgage & rent": "Housing",
    "haircut": "Personal Care",
    "paycheck": "Income",
    "credit card payment": "Transfers & Payments",
}


def normalize_category(raw: str) -> str:
    """Ham kategori metnini kanonik kategoriye çevirir. Eşleşme yoksa 'Other'."""
    if raw is None:
        return "Other"
    return CATEGORY_MAP.get(str(raw).strip().lower(), "Other")


# --------------------------------------------------------------------------- #
# 3) JSON SCHEMA (Draft-07) — makine-okur veri kontratı
#    Kişi 2/4 mock veriyi bu şemaya göre doğrulayabilir.
# --------------------------------------------------------------------------- #

JSON_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "SmartFinance Transaction",
    "description": "YZTA Bootcamp 2026 — birleşik işlem (transaction) kaydı sözleşmesi",
    "type": "object",
    "additionalProperties": False,
    "required": CORE_FIELDS,  # çekirdek 7 alan zorunlu; genişletmeler önerilir
    "properties": {
        "transaction_id": {
            "type": "string",
            "description": "Kaynak + alanlardan üretilen kararlı hash (dedupe/join anahtarı).",
        },
        "date": {
            "type": "string",
            "pattern": r"^\d{4}-\d{2}-\d{2}$",
            "description": "İşlem tarihi, YYYY-MM-DD.",
        },
        "description": {
            "type": "string",
            "minLength": 1,
            "description": "İşlem açıklaması / satıcı adı.",
        },
        "amount": {
            "type": "number",
            "exclusiveMinimum": 0,
            "description": "İşlem tutarı, her zaman POZİTİF. Yön için transaction_type'a bak.",
        },
        "currency": {
            "type": "string",
            "enum": ["INR", "USD", "EUR", "TRY", "GBP"],
            "description": "ISO para birimi kodu. Kaynaklar farklı para birimi kullanır!",
        },
        "transaction_type": {
            "type": "string",
            "enum": sorted(TRANSACTION_TYPES),
            "description": "debit = gider, credit = gelir/iade.",
        },
        "category": {
            "type": "string",
            "enum": CANONICAL_CATEGORIES,
            "description": "Birleşik kanonik kategori.",
        },
        "category_original": {
            "type": "string",
            "description": "Kaynaktaki ham kategori (bilgi kaybını önlemek için).",
        },
        "account_name": {
            "type": "string",
            "description": "Hesap / ödeme yöntemi adı.",
        },
        "month": {
            "type": "string",
            "pattern": r"^\d{4}-\d{2}$",
            "description": "Tarihten türetilen ay, YYYY-MM (aylık trend analizi için).",
        },
        "source": {
            "type": "string",
            "description": "Kaydın geldiği kaynak: india_csv | us_xlsx | pdf_<banka>.",
        },
    },
}
