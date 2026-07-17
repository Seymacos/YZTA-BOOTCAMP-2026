"""
test_cleaning.py — Veri Temizleme Testleri (Kişi 1)

Odak: sessiz veri bozulmasına yol açan durumlar.
"1.234,56 TL"yi 1.23 TL okumak hata vermez — sadece yanlış olur. Bu testler
tam olarak o tür hataları yakalamak için vardır.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from cleaning import (
    build_record,
    dedupe,
    detect_currency,
    dominant_currency,
    fold,
    infer_dayfirst,
    make_transaction_id,
    normalize_description,
    parse_amount,
    parse_date,
    tr_lower,
    validate_record,
)


# --------------------------------------------------------------------------- #
# Türkçe metin
# --------------------------------------------------------------------------- #

def test_tr_lower_handles_dotted_capital_i():
    """Python'un str.lower() metodu "İ" -> "i̇" (i + birleşen nokta) yapar."""
    assert tr_lower("İSTANBUL") == "istanbul"
    assert tr_lower("İŞ BANKASI") == "iş bankası"
    assert "İSTANBUL".lower() != "istanbul"  # standart lower() BOZUK


def test_tr_lower_maps_dotless_i():
    assert tr_lower("IŞIK") == "ışık"


def test_fold_strips_accents_for_matching():
    assert fold("GARANTİ BBVA") == "garanti bbva"
    assert fold("Şok Marketler") == "sok marketler"
    assert fold("Açıklama") == "aciklama"


# --------------------------------------------------------------------------- #
# Tutar ayrıştırma — en kritik alan
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("raw,expected", [
    # Türk biçimi: nokta binlik, virgül ondalık
    ("1.234,56", 1234.56),
    ("18.500,00", 18500.00),
    ("1.234.567,89", 1234567.89),
    ("0,50", 0.50),
    # ABD/Hindistan biçimi: virgül binlik, nokta ondalık
    ("1,234.56", 1234.56),
    ("3,500.00", 3500.00),
    ("1,234,567.89", 1234567.89),
    ("12.40", 12.40),
    # Ayırıcısız
    ("450", 450.0),
    ("450.25", 450.25),
])
def test_parse_amount_auto_detects_locale(raw, expected):
    assert parse_amount(raw) == pytest.approx(expected)


def test_parse_amount_thousands_only_is_not_decimal():
    """
    "1.500" -> 1500 olmalı, 1.5 DEĞİL.
    Parada 3 ondalık hane kullanılmaz; 3 hane binlik ayırıcısıdır.
    """
    assert parse_amount("1.500") == 1500.0
    assert parse_amount("1,500") == 1500.0


def test_parse_amount_locale_hint_resolves_ambiguity():
    """Belirsiz "1.234" profil ipucuyla netleşir."""
    assert parse_amount("1.234", "tr") == 1234.0   # TR: nokta binlik
    assert parse_amount("1.234", "us") == 1.234    # US: nokta ondalık


@pytest.mark.parametrize("raw,expected", [
    ("-1.234,56", -1234.56),      # baştaki eksi
    ("1.234,56-", -1234.56),      # sondaki eksi (bazı TR bankaları)
    ("(1.234,56)", -1234.56),     # parantezli muhasebe negatifi
])
def test_parse_amount_preserves_negative_conventions(raw, expected):
    assert parse_amount(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw,expected", [
    ("1.234,56 TL", 1234.56),
    ("₺1.234,56", 1234.56),
    ("$1,234.56", 1234.56),
    ("USD 1,234.56", 1234.56),
    ("1.234,56 TRY", 1234.56),
])
def test_parse_amount_strips_currency(raw, expected):
    assert parse_amount(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", [None, "", "   ", "abc", "-", "N/A", True, False])
def test_parse_amount_returns_none_for_garbage(raw):
    """Ayrıştırılamayan değer None döner; 0.0 DÖNMEZ (0 gerçek tutar olabilir)."""
    assert parse_amount(raw) is None


def test_parse_amount_passes_through_numbers():
    assert parse_amount(1234.56) == 1234.56
    assert parse_amount(42) == 42.0


# --------------------------------------------------------------------------- #
# Para birimi tespiti
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("text,expected", [
    ("1.234,56 TL", "TRY"),
    ("₺1.234,56", "TRY"),
    ("$1,234.56", "USD"),
    ("1,234.56 USD", "USD"),
    ("€99,90", "EUR"),
    ("₹5,000.00", "INR"),
    ("Rs. 5,000.00", "INR"),
])
def test_detect_currency(text, expected):
    assert detect_currency(text) == expected


def test_detect_currency_falls_back_to_default():
    assert detect_currency("1234.56", "TRY") == "TRY"
    assert detect_currency("", None) is None


def test_detect_currency_does_not_match_tl_inside_word():
    """"tl" kelime içinde geçince (ATLAS) para birimi sanılmamalı."""
    assert detect_currency("ATLAS TURIZM", None) is None


# --------------------------------------------------------------------------- #
# Belge geneli para birimi (baskın)
# --------------------------------------------------------------------------- #

def test_dominant_currency_ignores_single_stray_symbol():
    """
    Türk ekstresinde geçen TEK bir "$" (dipnot/döviz bakiyesi) tüm ekstreyi
    USD yapmamalı. detect_currency() ilk eşleşmeyi alır ve burada yanılır;
    dominant_currency() sayar ve doğruyu bulur.
    """
    text = (
        "GARANTİ BBVA Hesap Ekstresi\n"
        "Not: USD hesabınız için ayrı ekstre düzenlenir.\n"   # tek USD geçişi
        "04/03/2024 MIGROS 1.234,56 TL\n"
        "11/03/2024 TURKCELL 389,90 TL\n"
        "14/03/2024 GETIR 245,75 TL\n"
    )
    assert dominant_currency(text, "TRY") == "TRY"
    assert detect_currency(text, "TRY") == "USD"   # ilk-eşleşme yaklaşımı yanılıyor


def test_dominant_currency_picks_majority():
    assert dominant_currency("$100 $200 $300 ₺50", "TRY") == "USD"
    assert dominant_currency("₺100 ₺200 ₺300 $50", "USD") == "TRY"


def test_dominant_currency_falls_back_to_default():
    assert dominant_currency("hicbir para birimi yok", "TRY") == "TRY"
    assert dominant_currency("", "TRY") == "TRY"
    assert dominant_currency(None, "TRY") == "TRY"


# --------------------------------------------------------------------------- #
# Tarih ayrıştırma
# --------------------------------------------------------------------------- #

def test_infer_dayfirst_detects_day_first_from_file():
    """25 > 12 olduğu için ilk bileşen gün olmak ZORUNDA."""
    assert infer_dayfirst(["15/01/2024", "20/01/2024", "25/01/2024"]) is True


def test_infer_dayfirst_detects_month_first_from_file():
    """28 > 12 ikinci bileşende -> ay/gün/yıl."""
    assert infer_dayfirst(["02/03/2024", "02/14/2024", "02/28/2024"]) is False


def test_infer_dayfirst_returns_none_when_ambiguous():
    """Tüm bileşenler <= 12 -> karar verilemez, çağıran varsayılana düşer."""
    assert infer_dayfirst(["04/03/2024", "05/03/2024"]) is None


def test_infer_dayfirst_returns_none_on_contradiction():
    """Hem 25/01 hem 02/28 varsa veri tutarsız -> None."""
    assert infer_dayfirst(["25/01/2024", "02/28/2024"]) is None


def test_infer_dayfirst_ignores_iso_dates():
    assert infer_dayfirst(["2024-03-04", "2024-03-05"]) is None


@pytest.mark.parametrize("raw,dayfirst,expected", [
    ("2024-03-04", True, date(2024, 3, 4)),      # ISO — dayfirst yok sayılır
    ("2024-03-04", False, date(2024, 3, 4)),
    ("04/03/2024", True, date(2024, 3, 4)),      # gün/ay
    ("04/03/2024", False, date(2024, 4, 3)),     # ay/gün
    ("25/01/2024", False, date(2024, 1, 25)),    # 25 gün olmak zorunda
    ("04.03.2024", True, date(2024, 3, 4)),
    ("04-03-2024", True, date(2024, 3, 4)),
    ("04/03/24", True, date(2024, 3, 4)),        # 2 haneli yıl
])
def test_parse_date_formats(raw, dayfirst, expected):
    assert parse_date(raw, dayfirst=dayfirst) == expected


def test_parse_date_turkish_month_names():
    assert parse_date("12 Oca 2024") == date(2024, 1, 12)
    assert parse_date("3 Mart 2024") == date(2024, 3, 3)
    assert parse_date("15 Aralık 2023") == date(2023, 12, 15)


def test_parse_date_two_digit_year_pivot():
    assert parse_date("01/01/68").year == 2068
    assert parse_date("01/01/69").year == 1969


@pytest.mark.parametrize("raw", [None, "", "abc", "32/13/2024", "00/00/0000"])
def test_parse_date_returns_none_for_invalid(raw):
    assert parse_date(raw) is None


def test_parse_date_accepts_date_objects():
    assert parse_date(date(2024, 3, 4)) == date(2024, 3, 4)


# --------------------------------------------------------------------------- #
# Açıklama normalizasyonu
# --------------------------------------------------------------------------- #

def test_normalize_description_strips_card_mask_and_ref():
    raw = "POS 5218 12** **** 3456 MIGROS TIC.A.S. REF:009182734"
    assert normalize_description(raw) == "MIGROS TIC.A.S."


def test_normalize_description_strips_transaction_at_prefix():
    """Sprint 1 Hindistan veri setinde her satır bu önekle geliyordu."""
    assert normalize_description("Transaction at Amazon") == "Amazon"


def test_normalize_description_strips_channel_prefix():
    assert normalize_description("POS GETIR PERAKENDE") == "GETIR PERAKENDE"
    assert normalize_description("ATM PARA CEKME") == "PARA CEKME"


def test_normalize_description_preserves_case():
    """Dashboard'da okunaklı olsun; TF-IDF zaten lowercase=True kullanıyor."""
    assert normalize_description("MIGROS") == "MIGROS"


def test_normalize_description_collapses_whitespace():
    assert normalize_description("  MIGROS    TIC   ") == "MIGROS TIC"


def test_normalize_description_falls_back_to_raw_when_fully_stripped():
    """Temizlik her şeyi yerse ham metne dön — bilgi kaybetme."""
    assert normalize_description("REF:123456") == "REF:123456"


def test_normalize_description_keeps_digits_inside_merchant_name():
    """"A101" mağaza adıdır, referans numarası değil."""
    assert "A101" in normalize_description("A101 YENI MAGAZA")


@pytest.mark.parametrize("raw", [None, ""])
def test_normalize_description_handles_empty(raw):
    assert normalize_description(raw) == ""


# --------------------------------------------------------------------------- #
# transaction_id — Sprint 1 verisiyle uyumluluk
# --------------------------------------------------------------------------- #

def test_transaction_id_matches_sprint1_recipe():
    """Sprint 1'de üretilmiş gerçek bir kaydın kimliği birebir tutmalı."""
    assert make_transaction_id(
        "us_xlsx", "2018-01-01", "Amazon", 11.11, "Platinum Card"
    ) == "58d3b735352a15de"


def test_transaction_id_matches_every_existing_record():
    """
    Mevcut 8806 kaydın TAMAMINDA reçete doğrulanır.
    Bu test kırılırsa transactions_merged.json ile join uyumluluğu bozulmuş
    demektir — Kişi 2/3/4'ün verisi sessizce eşleşmez hale gelir.
    """
    dataset = Path(__file__).resolve().parents[1] / "transactions_merged.json"
    if not dataset.exists():
        pytest.skip("transactions_merged.json bulunamadı")

    records = json.loads(dataset.read_text(encoding="utf-8"))
    for record in records:
        expected = make_transaction_id(
            record["source"], record["date"], record["description"],
            record["amount"], record["account_name"],
        )
        assert record["transaction_id"] == expected, f"uyuşmayan kayıt: {record}"


def test_transaction_id_is_stable_and_distinct():
    first = make_transaction_id("pdf_garanti", "2024-03-04", "MIGROS", 1234.56, "Vadesiz")
    assert first == make_transaction_id("pdf_garanti", "2024-03-04", "MIGROS", 1234.56, "Vadesiz")
    assert first != make_transaction_id("pdf_garanti", "2024-03-04", "MIGROS", 1234.57, "Vadesiz")


# --------------------------------------------------------------------------- #
# Kayıt kurma + doğrulama
# --------------------------------------------------------------------------- #

def _record(**overrides):
    defaults = dict(
        date_value=date(2024, 3, 4), description="MIGROS", amount=1234.56,
        transaction_type="debit", account_name="Vadesiz", source="pdf_garanti",
        currency="TRY", category_original="",
    )
    defaults.update(overrides)
    return build_record(**defaults)


def test_build_record_derives_month_from_date():
    assert _record()["month"] == "2024-03"


def test_build_record_forces_amount_positive():
    """Şema kuralı: amount her zaman pozitif, yön transaction_type'ta."""
    record = _record(amount=-1234.56, transaction_type="debit")
    assert record["amount"] == 1234.56
    assert record["transaction_type"] == "debit"


def test_build_record_defaults_unmapped_category_to_other():
    assert _record(category_original="Bilinmeyen Kategori")["category"] == "Other"


def test_build_record_maps_known_category():
    assert _record(category_original="Grocery")["category"] == "Groceries"


def test_build_record_includes_raw_description_only_when_changed():
    changed = _record(description="MIGROS", description_raw="POS **** 1234 MIGROS REF:99")
    assert changed["description_raw"] == "POS **** 1234 MIGROS REF:99"

    unchanged = _record(description="MIGROS", description_raw="MIGROS")
    assert "description_raw" not in unchanged


def test_valid_record_passes_validation():
    assert validate_record(_record()) == []


@pytest.mark.parametrize("mutation,fragment", [
    ({"amount": 0}, "pozitif"),
    ({"amount": -5}, "pozitif"),
    ({"amount": "1234"}, "sayı değil"),
    ({"transaction_type": "expense"}, "debit"),
    ({"date": "04/03/2024"}, "YYYY-MM-DD"),
    ({"month": "2024-04"}, "tutarsız"),
    ({"description": "   "}, "boş"),
])
def test_validate_record_catches_contract_violations(mutation, fragment):
    record = _record()
    record.update(mutation)
    errors = validate_record(record)
    assert any(fragment in e for e in errors), f"beklenen hata yakalanmadı: {errors}"


def test_validate_record_rejects_unknown_field():
    record = _record()
    record["sneaky_field"] = 1
    assert any("tanımsız alan" in e for e in validate_record(record))


def test_validate_record_catches_missing_core_field():
    record = _record()
    del record["category"]
    assert any("zorunlu alan eksik" in e for e in validate_record(record))


# --------------------------------------------------------------------------- #
# Tekrar eleme
# --------------------------------------------------------------------------- #

def test_dedupe_removes_identical_records():
    """Aynı ekstre iki kez yüklenirse harcamalar ikiye katlanmamalı."""
    records = [_record(), _record(), _record(description="A101")]
    unique = dedupe(records)
    assert len(unique) == 2


def test_dedupe_keeps_first_occurrence_and_counts():
    from cleaning import CleanReport

    report = CleanReport()
    dedupe([_record(), _record()], report)
    assert report.duplicates == 1
