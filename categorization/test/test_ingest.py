"""
test_ingest.py — Dosya Yükleme Akışı / Veri Tarafı Testleri (Kişi 1)

Kişi 3'ün arayüzünün dayandığı sözleşmeyi korur:
    - ingest_upload(bytes, filename) -> IngestResult
    - hatalar IngestError, mesajları Türkçe ve gösterilebilir
    - hiçbir satır sessizce kaybolmaz (report sayıları tutar)
"""

import io

import pytest

from cleaning import fold
from ingest import (
    MAX_FILE_MB,
    SUPPORTED_EXTENSIONS,
    IngestError,
    ingest_upload,
    merge_into_dataset,
)
from fixtures_builder import build_garanti_pdf, build_scanned_pdf


def _find(records, fragment):
    for record in records:
        if fold(fragment) in fold(record["description"]):
            return record
    raise AssertionError(
        f"'{fragment}' yok. Bulunanlar: {[r['description'] for r in records]}"
    )


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #

TR_CSV = (
    "Tarih;Açıklama;Tutar;Bakiye\n"
    "15/01/2024;POS MIGROS TIC.A.S. REF:8821;-567,80;12.432,20\n"
    "20/01/2024;IADE TRENDYOL;150,00;12.582,20\n"
    "25/01/2024;KIRA ODEMESI;-18.500,00;-5.917,80\n"
).encode("utf-8")

US_CSV = (
    "Date,Description,Amount,Transaction Type,Category,Account Name\n"
    "02/03/2024,Transaction at Amazon,1234.56,debit,Shopping,Platinum Card\n"
    "02/14/2024,Paycheck,3500.00,credit,Paycheck,Platinum Card\n"
    "02/28/2024,Starbucks,12.40,debit,Coffee Shops,Platinum Card\n"
).encode("utf-8")


def test_csv_semicolon_delimiter_is_detected():
    """Türkçe Excel CSV dışa aktarımı ';' kullanır — otomatik sezilmeli."""
    result = ingest_upload(TR_CSV, "ekstre.csv")
    assert len(result.records) == 3


def test_csv_turkish_headers_are_mapped():
    result = ingest_upload(TR_CSV, "ekstre.csv")
    assert _find(result.records, "MIGROS")["amount"] == pytest.approx(567.80)


def test_csv_turkish_number_format():
    """-18.500,00 -> 18500.0 (yön debit); 18.5 OLMAMALI."""
    record = _find(ingest_upload(TR_CSV, "e.csv").records, "KIRA")
    assert record["amount"] == pytest.approx(18500.00)
    assert record["transaction_type"] == "debit"


def test_csv_direction_from_sign():
    records = ingest_upload(TR_CSV, "e.csv").records
    assert _find(records, "MIGROS")["transaction_type"] == "debit"
    assert _find(records, "IADE")["transaction_type"] == "credit"


def test_csv_dayfirst_inferred_from_file():
    """25/01 -> gün/ay/yıl kesin."""
    assert _find(ingest_upload(TR_CSV, "e.csv").records, "KIRA")["date"] == "2024-01-25"


def test_csv_source_is_upload_csv():
    assert ingest_upload(TR_CSV, "e.csv").records[0]["source"] == "upload_csv"


def test_us_csv_explicit_type_column_wins():
    """Tutarlar işaretsiz; yön "Transaction Type" sütunundan okunmalı."""
    records = ingest_upload(US_CSV, "us.csv").records
    assert _find(records, "Amazon")["transaction_type"] == "debit"
    assert _find(records, "Paycheck")["transaction_type"] == "credit"


def test_us_csv_month_first_dates():
    """02/28 -> ay/gün/yıl kesin -> 02/03 = 3 Şubat."""
    assert _find(ingest_upload(US_CSV, "us.csv").records, "Amazon")["date"] == "2024-02-03"


def test_us_csv_category_is_mapped_and_original_kept():
    """Ham kategori korunur (Kişi 2 yeniden gruplayabilsin)."""
    record = _find(ingest_upload(US_CSV, "us.csv").records, "Starbucks")
    assert record["category"] == "Food & Dining"     # kanonik
    assert record["category_original"] == "Coffee Shops"  # ham


def test_us_csv_strips_transaction_at_prefix():
    """Sprint 1 Hindistan veri setindeki "Transaction at X" öneki temizlenir."""
    assert _find(ingest_upload(US_CSV, "us.csv").records, "Amazon")["description"] == "Amazon"


def test_csv_account_name_from_column():
    assert _find(ingest_upload(US_CSV, "us.csv").records, "Amazon")["account_name"] == "Platinum Card"


def test_csv_account_name_override():
    result = ingest_upload(TR_CSV, "e.csv", account_name="Benim Hesabım")
    assert all(r["account_name"] == "Benim Hesabım" for r in result.records)


def test_unsigned_file_without_type_column_assumes_debit_and_warns():
    """
    Yön bilgisi hiç yoksa (tip sütunu yok + hiç negatif yok) tümü gider
    sayılır AMA kullanıcı bu varsayımdan haberdar edilir.
    """
    csv = "Tarih;Açıklama;Tutar\n15/01/2024;MIGROS;567,80\n20/01/2024;A101;99,90\n".encode("utf-8")
    result = ingest_upload(csv, "e.csv")
    assert all(r["transaction_type"] == "debit" for r in result.records)
    assert any("GİDER sayıldı" in w for w in result.report.warnings)


def test_signed_file_does_not_emit_direction_warning():
    """TR_CSV negatif tutar içeriyor -> işaret yön taşıyor -> uyarı olmamalı."""
    result = ingest_upload(TR_CSV, "e.csv")
    assert not any("GİDER sayıldı" in w for w in result.report.warnings)


def test_csv_missing_required_column_raises_helpful_error():
    bad = b"Tarih;Sube;Musteri\n15/01/2024;Kadikoy;Ahmet\n"
    with pytest.raises(IngestError) as exc:
        ingest_upload(bad, "e.csv")
    message = str(exc.value)
    assert "açıklama" in message and "tutar" in message   # eksikleri sayar
    assert "Sube" in message                              # bulunanları gösterir


def test_csv_bad_rows_are_reported_not_silently_dropped():
    """Bozuk satır sessizce kaybolmaz; rapora yazılır."""
    csv = (
        "Tarih;Açıklama;Tutar\n"
        "15/01/2024;MIGROS;-567,80\n"
        "GECERSIZ;BOZUK SATIR;-100,00\n"
        "20/01/2024;A101;abc\n"
    ).encode("utf-8")
    result = ingest_upload(csv, "e.csv")
    assert len(result.records) == 1
    assert result.report.dropped == 2
    assert "tarih okunamadı" in result.report.drop_reasons
    assert "tutar okunamadı" in result.report.drop_reasons


def test_report_counts_always_add_up():
    result = ingest_upload(TR_CSV, "e.csv")
    report = result.report
    assert report.accepted + report.dropped + report.duplicates == report.total_rows


def test_report_summary_is_turkish_and_readable():
    summary = ingest_upload(TR_CSV, "e.csv").report.summary_tr()
    assert "satır okundu" in summary and "işlem alındı" in summary


def test_csv_cp1254_encoding_is_handled():
    """Türkçe Windows Excel bazen cp1254 (Latin-5) yazar."""
    data = "Tarih;Açıklama;Tutar\n15/01/2024;ŞOK MARKET;-99,90\n".encode("cp1254")
    result = ingest_upload(data, "e.csv")
    assert len(result.records) == 1
    assert "MARKET" in result.records[0]["description"].upper()


def test_duplicate_rows_within_file_are_deduped():
    csv = (
        "Tarih;Açıklama;Tutar\n"
        "15/01/2024;MIGROS;-567,80\n"
        "15/01/2024;MIGROS;-567,80\n"
    ).encode("utf-8")
    result = ingest_upload(csv, "e.csv")
    assert len(result.records) == 1
    assert result.report.duplicates == 1


# --------------------------------------------------------------------------- #
# Excel
# --------------------------------------------------------------------------- #

def _xlsx_bytes():
    pd = pytest.importorskip("pandas")
    pytest.importorskip("openpyxl")
    frame = pd.DataFrame([
        {"Date": "2024-01-15", "Description": "Amazon", "Amount": 1234.56,
         "Transaction Type": "debit", "Category": "Shopping", "Account Name": "Platinum Card"},
        {"Date": "2024-01-20", "Description": "Paycheck", "Amount": 3500.00,
         "Transaction Type": "credit", "Category": "Paycheck", "Account Name": "Platinum Card"},
    ])
    buffer = io.BytesIO()
    frame.to_excel(buffer, index=False)
    return buffer.getvalue()


def test_xlsx_is_parsed():
    result = ingest_upload(_xlsx_bytes(), "ekstre.xlsx")
    assert len(result.records) == 2
    assert result.source == "upload_xlsx"


def test_xlsx_iso_dates_and_types():
    records = ingest_upload(_xlsx_bytes(), "e.xlsx").records
    assert _find(records, "Amazon")["date"] == "2024-01-15"
    assert _find(records, "Paycheck")["transaction_type"] == "credit"


def test_xlsx_records_are_schema_valid():
    from cleaning import validate_record
    for record in ingest_upload(_xlsx_bytes(), "e.xlsx").records:
        assert validate_record(record) == [], record


# --------------------------------------------------------------------------- #
# PDF yönlendirmesi
# --------------------------------------------------------------------------- #

def test_pdf_is_routed_to_statement_parser():
    result = ingest_upload(build_garanti_pdf(), "ekstre.pdf")
    assert result.file_type == "pdf"
    assert result.bank == "Garanti BBVA"
    assert result.source == "pdf_garanti"
    assert len(result.records) == 4


def test_pdf_parse_error_becomes_ingest_error():
    """Kişi 3 tek bir hata türü yakalasın yeter."""
    with pytest.raises(IngestError, match="taranmış"):
        ingest_upload(build_scanned_pdf(), "taranmis.pdf")


def test_file_like_object_is_accepted():
    """Streamlit UploadedFile dosya-benzeri nesnedir."""
    result = ingest_upload(io.BytesIO(TR_CSV), "e.csv")
    assert len(result.records) == 3


# --------------------------------------------------------------------------- #
# Doğrulama / sınırlar
# --------------------------------------------------------------------------- #

def test_unsupported_extension_rejected():
    with pytest.raises(IngestError, match="Desteklenmeyen"):
        ingest_upload(b"data", "resim.png")


def test_empty_file_rejected():
    with pytest.raises(IngestError, match="boş"):
        ingest_upload(b"", "e.csv")


def test_oversized_file_rejected():
    big = b"x" * int((MAX_FILE_MB + 1) * 1024 * 1024)
    with pytest.raises(IngestError, match="çok büyük"):
        ingest_upload(big, "e.csv")


def test_supported_extensions_cover_ui_needs():
    """Kişi 3 bunu st.file_uploader(type=...) içinde kullanır."""
    assert set(SUPPORTED_EXTENSIONS) >= {"csv", "xlsx", "pdf"}


def test_to_dict_is_json_serializable():
    """Rapor arayüze/JSON'a taşınabilmeli."""
    import json
    result = ingest_upload(TR_CSV, "e.csv")
    json.dumps(result.to_dict(), ensure_ascii=False)


# --------------------------------------------------------------------------- #
# Veri setine birleştirme
# --------------------------------------------------------------------------- #

def test_merge_appends_new_records():
    existing = ingest_upload(US_CSV, "us.csv").records
    new = ingest_upload(TR_CSV, "tr.csv").records
    merged, added = merge_into_dataset(new, existing)
    assert added == 3
    assert len(merged) == len(existing) + 3


def test_merge_is_idempotent():
    """Aynı ekstreyi iki kez yüklemek harcamaları ikiye katlamamalı."""
    records = ingest_upload(TR_CSV, "e.csv").records
    merged, added = merge_into_dataset(records, records)
    assert added == 0
    assert len(merged) == len(records)


def test_merge_sorts_by_date():
    records = ingest_upload(TR_CSV, "e.csv").records
    merged, _ = merge_into_dataset(records, [])
    assert [r["date"] for r in merged] == sorted(r["date"] for r in merged)


def test_merge_into_existing_dataset_keeps_sprint1_records():
    """
    Sprint 1'in gerçek veri setine yükleme yapmak mevcut kayıtları bozmamalı.
    transaction_id reçetesi uyumlu olduğu için çakışma olmaz.
    """
    import json
    from pathlib import Path

    dataset_path = Path(__file__).resolve().parents[1] / "transactions_merged.json"
    if not dataset_path.exists():
        pytest.skip("transactions_merged.json bulunamadı")

    existing = json.loads(dataset_path.read_text(encoding="utf-8"))
    new = ingest_upload(TR_CSV, "e.csv").records
    merged, added = merge_into_dataset(new, existing)

    assert added == 3
    assert len(merged) == len(existing) + 3
    existing_ids = {r["transaction_id"] for r in existing}
    assert existing_ids <= {r["transaction_id"] for r in merged}  # hiçbiri kaybolmadı
