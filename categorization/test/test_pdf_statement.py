"""
test_pdf_statement.py — PDF Ekstre Ayrıştırma Testleri (Kişi 1)

Sentetik ekstrelerle (fixtures_builder.py) uçtan uca ayrıştırma testi.
Her banka düzeni FARKLI bir zorluk sınar:

    Garanti   -> çizgili tablo + AYRI borç/alacak sütunları
    İş Bankası-> tek işaretli tutar sütunu + bakiye
    Chase     -> TABLOSUZ düz metin + ABD sayı/tarih biçimi
    Bilinmeyen-> profil yok -> genel ayrıştırıcı
    Taranmış  -> metin yok -> anlaşılır hata
"""

import pytest

from bank_profiles import GENERIC_PROFILE, detect_profile, supported_banks
from cleaning import fold
from pdf_statement import StatementParseError, parse_pdf
from fixtures_builder import (
    CHASE_EXPECTED,
    GARANTI_EXPECTED,
    ISBANK_EXPECTED,
    build_chase_pdf,
    build_garanti_pdf,
    build_isbank_pdf,
    build_scanned_pdf,
    build_unknown_pdf,
    turkish_fonts_available,
)


def _find(records, fragment):
    """
    Açıklamasında `fragment` geçen ilk kaydı bulur.

    Karşılaştırma fold() ile yapılır: fixture'lar TTF varsa gerçek Türkçe
    basar ("MAAŞ ÖDEMESİ"), yoksa ASCII'ye iner ("MAAS ODEMESI"). Beklentiler
    ASCII yazılıp fold ile eşleştirilince test iki durumda da çalışır.
    """
    for record in records:
        if fold(fragment) in fold(record["description"]):
            return record
    raise AssertionError(
        f"'{fragment}' içeren kayıt yok. Bulunanlar: "
        f"{[r['description'] for r in records]}"
    )


# --------------------------------------------------------------------------- #
# Garanti — tablo modu, ayrı borç/alacak
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def garanti():
    return parse_pdf(build_garanti_pdf())


def test_garanti_detects_bank(garanti):
    assert garanti.bank_key == "garanti"
    assert garanti.currency == "TRY"


def test_garanti_uses_table_mode(garanti):
    """Çizgili tablo varsa satır moduna düşmemeli — tablo modu daha güvenilir."""
    assert "table" in garanti.mode


def test_garanti_extracts_all_transactions(garanti):
    assert len(garanti.records) == len(GARANTI_EXPECTED)


def test_garanti_skips_total_row(garanti):
    """"TOPLAM" satırı işlem değildir; tarihi olmadığı için düşmeli."""
    assert not any("TOPLAM" in r["description"].upper() for r in garanti.records)


@pytest.mark.parametrize("expected_date,fragment,expected_amount,expected_type", GARANTI_EXPECTED)
def test_garanti_row_values(garanti, expected_date, fragment, expected_amount, expected_type):
    record = _find(garanti.records, fragment)
    assert record["date"] == expected_date
    assert record["amount"] == pytest.approx(expected_amount)
    assert record["transaction_type"] == expected_type
    assert record["currency"] == "TRY"


def test_garanti_reads_direction_from_debit_credit_columns(garanti):
    """
    Ayrı Borç/Alacak sütunları varken yön TAHMİN EDİLMEZ, OKUNUR.
    Maaş satırı Alacak sütunundadır -> credit olmalı.
    """
    assert _find(garanti.records, "MAAS")["transaction_type"] == "credit"
    assert _find(garanti.records, "MIGROS")["transaction_type"] == "debit"


def test_garanti_parses_turkish_number_format(garanti):
    """1.234,56 -> 1234.56 olmalı; 1.23 OLMAMALI (sessiz veri bozulması)."""
    assert _find(garanti.records, "MIGROS")["amount"] == pytest.approx(1234.56)
    assert _find(garanti.records, "MAAS")["amount"] == pytest.approx(42500.00)


def test_garanti_cleans_description_noise(garanti):
    """Kart maskesi ve referans no temizlenmeli, mağaza adı kalmalı."""
    record = _find(garanti.records, "MIGROS")
    assert "5218" not in record["description"]
    assert "REF" not in record["description"].upper()
    assert "009182734" not in record["description"]


def test_garanti_keeps_raw_description_for_audit(garanti):
    """Temizlik bir şeyi yanlış silerse aslına bakılabilmeli."""
    record = _find(garanti.records, "MIGROS")
    assert "REF:009182734" in record["description_raw"]


def test_garanti_extracts_account_name(garanti):
    assert "Hesab" in garanti.account_name or "Vadesiz" in garanti.account_name


def test_garanti_records_are_schema_valid(garanti):
    from cleaning import validate_record
    for record in garanti.records:
        assert validate_record(record) == [], record


def test_garanti_report_counts_add_up(garanti):
    report = garanti.report
    assert report.accepted == len(garanti.records)
    assert report.accepted + report.dropped + report.duplicates == report.total_rows


# --------------------------------------------------------------------------- #
# İş Bankası — tek işaretli tutar sütunu
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def isbank():
    return parse_pdf(build_isbank_pdf())


def test_isbank_detects_bank(isbank):
    assert isbank.bank_key == "isbank"


def test_isbank_extracts_all_transactions(isbank):
    assert len(isbank.records) == len(ISBANK_EXPECTED)


@pytest.mark.parametrize("expected_date,fragment,expected_amount,expected_type", ISBANK_EXPECTED)
def test_isbank_row_values(isbank, expected_date, fragment, expected_amount, expected_type):
    record = _find(isbank.records, fragment)
    assert record["date"] == expected_date
    assert record["amount"] == pytest.approx(expected_amount)
    assert record["transaction_type"] == expected_type


def test_isbank_infers_direction_from_sign(isbank):
    """Tek tutar sütununda işaret yönü belirler: -567,80 gider, 150,00 gelir."""
    assert _find(isbank.records, "A101")["transaction_type"] == "debit"
    assert _find(isbank.records, "IADE")["transaction_type"] == "credit"


def test_isbank_amount_is_always_positive(isbank):
    """Şema kuralı: amount pozitif, yön transaction_type'ta taşınır."""
    assert all(r["amount"] > 0 for r in isbank.records)


def test_isbank_resolves_dayfirst_from_file(isbank):
    """25/01 -> 25 > 12 -> gün/ay/yıl KESİN. 15/01 doğru okunmalı."""
    assert _find(isbank.records, "A101")["date"] == "2024-01-15"
    assert _find(isbank.records, "KIRA")["date"] == "2024-01-25"


def test_isbank_large_amount_not_truncated(isbank):
    """18.500,00 -> 18500.0 olmalı; 18.5 OLMAMALI."""
    assert _find(isbank.records, "KIRA")["amount"] == pytest.approx(18500.00)


# --------------------------------------------------------------------------- #
# Chase — satır modu, ABD biçimi
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def chase():
    return parse_pdf(build_chase_pdf())


def test_chase_detects_bank_and_currency(chase):
    assert chase.bank_key == "chase"
    assert chase.currency == "USD"


def test_chase_falls_back_to_line_mode(chase):
    """Çizgi yok -> tablo bulunamaz -> satır modu devreye girmeli."""
    assert "line" in chase.mode


def test_chase_extracts_all_transactions(chase):
    assert len(chase.records) == len(CHASE_EXPECTED)


@pytest.mark.parametrize("expected_date,fragment,expected_amount,expected_type", CHASE_EXPECTED)
def test_chase_row_values(chase, expected_date, fragment, expected_amount, expected_type):
    record = _find(chase.records, fragment)
    assert record["date"] == expected_date
    assert record["amount"] == pytest.approx(expected_amount)
    assert record["transaction_type"] == expected_type


def test_chase_resolves_month_first_dates(chase):
    """
    02/28/2024 -> ikinci bileşen 28 > 12 -> ay/gün/yıl KESİN.
    Bu çıkarım olmasaydı 02/03/2024 -> 2 Mart okunurdu (yanlış).
    """
    assert _find(chase.records, "AMAZON")["date"] == "2024-02-03"   # 3 Şubat
    assert _find(chase.records, "STARBUCKS")["date"] == "2024-02-28"


def test_chase_parses_us_number_format(chase):
    """1,234.56 -> 1234.56 olmalı; 123456 OLMAMALI."""
    assert _find(chase.records, "AMAZON")["amount"] == pytest.approx(1234.56)
    assert _find(chase.records, "STARBUCKS")["amount"] == pytest.approx(12.40)


def test_chase_ignores_header_and_total_lines(chase):
    """"Date Description Amount" başlığı ve "Total withdrawals" işlem değildir."""
    descriptions = " ".join(r["description"].lower() for r in chase.records)
    assert "total withdrawals" not in descriptions
    assert "statement period" not in descriptions


def test_chase_direction_from_sign(chase):
    assert _find(chase.records, "PAYROLL")["transaction_type"] == "credit"
    assert _find(chase.records, "AMAZON")["transaction_type"] == "debit"


# --------------------------------------------------------------------------- #
# Bilinmeyen banka — genel ayrıştırıcı
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def unknown():
    return parse_pdf(build_unknown_pdf())


def test_unknown_bank_uses_generic_profile(unknown):
    """Tanınmayan banka REDDEDİLMEZ; genel kurallarla ayrıştırılır."""
    assert unknown.bank_key == GENERIC_PROFILE.key


def test_unknown_bank_still_extracts_transactions(unknown):
    assert len(unknown.records) == 2


def test_unknown_bank_warns_user(unknown):
    """Kullanıcı hangi varsayımların kullanıldığını bilmeli."""
    assert any("tespit edilemedi" in w.lower() for w in unknown.report.warnings)


def test_unknown_bank_values_correct(unknown):
    assert _find(unknown.records, "MIGROS")["amount"] == pytest.approx(450.25)
    assert _find(unknown.records, "MIGROS")["transaction_type"] == "debit"
    assert _find(unknown.records, "MAAS")["transaction_type"] == "credit"


def test_unknown_bank_resolves_dayfirst(unknown):
    """17/05 -> 17 > 12 -> gün/ay/yıl."""
    assert _find(unknown.records, "MIGROS")["date"] == "2024-05-17"


# --------------------------------------------------------------------------- #
# Hata yolları
# --------------------------------------------------------------------------- #

def test_scanned_pdf_raises_actionable_error():
    """Taranmış PDF sessizce boş dönmemeli; ne yapılacağını söylemeli."""
    with pytest.raises(StatementParseError, match="taranmış"):
        parse_pdf(build_scanned_pdf())


def test_corrupt_file_raises_parse_error():
    with pytest.raises(StatementParseError):
        parse_pdf(b"bu bir PDF degil")


def test_error_messages_are_turkish():
    """Kişi 3 hata mesajını doğrudan st.error() ile basabilmeli."""
    with pytest.raises(StatementParseError) as exc:
        parse_pdf(build_scanned_pdf())
    assert any(w in str(exc.value).lower() for w in ("pdf", "ekstre", "yükleyin"))


# --------------------------------------------------------------------------- #
# Profil kayıt defteri
# --------------------------------------------------------------------------- #

def test_detect_profile_returns_generic_for_unknown_text():
    profile, score = detect_profile(fold("KUZEY YILDIZI BANKASI"))
    assert profile.key == GENERIC_PROFILE.key
    assert score == 0


def test_detect_profile_picks_highest_scoring_bank():
    profile, score = detect_profile(fold("GARANTİ BBVA A.Ş. — Garanti Bankası ekstresi"))
    assert profile.key == "garanti"
    assert score >= 2


def test_bank_key_override_skips_detection():
    """Kullanıcı arayüzde bankayı elle seçerse otomatik tespit atlanmalı."""
    result = parse_pdf(build_unknown_pdf(), bank_key="garanti")
    assert result.bank_key == "garanti"


def test_source_field_encodes_bank():
    """schema.py sözleşmesi: source = pdf_<banka>."""
    assert parse_pdf(build_garanti_pdf()).records[0]["source"] == "pdf_garanti"


def test_supported_banks_listed_for_ui():
    banks = supported_banks()
    assert "Garanti BBVA" in banks
    assert len(banks) >= 5


def test_profile_source_prefix():
    from bank_profiles import get_profile
    assert get_profile("akbank").source == "pdf_akbank"
    assert get_profile("bilinmeyen_banka").key == GENERIC_PROFILE.key


# --------------------------------------------------------------------------- #
# Türkçe karakterler (yalnızca TTF varsa anlamlı)
# --------------------------------------------------------------------------- #

@pytest.mark.skipif(
    not turkish_fonts_available(),
    reason="Türkçe TTF yok; fixture ASCII'ye indirgeniyor",
)
def test_turkish_column_headers_are_matched(garanti):
    """
    "İşlem Tarihi" / "Açıklama" başlıkları eşleşmeli.
    Bu test fold()'daki ı->i eşlemesini korur: kaldırılırsa
    fold("Açıklama") -> "acıklama" olur ve sütun bulunamaz.
    """
    assert len(garanti.records) == len(GARANTI_EXPECTED)
