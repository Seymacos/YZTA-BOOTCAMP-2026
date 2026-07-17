"""
ingest.py — Kullanıcı Dosya Yükleme Akışı / VERİ TARAFI (Kişi 1)
================================================================

Kullanıcının yüklediği CSV / Excel / PDF dosyasını schema.py'deki kanonik
`TransactionRecord` listesine çeviren TEK giriş noktası.

Kapsam sınırı — bu dosya ARAYÜZ İÇERMEZ
----------------------------------------
Yükleme arayüzü (st.file_uploader, ilerleme çubuğu, önizleme tablosu)
Kişi 3'ün görevidir. Burada yalnızca "bytes gir -> temiz kayıt çık" mantığı
vardır; streamlit import EDİLMEZ. Böylece bu modül arayüzden bağımsız test
edilebilir ve Kişi 3 arayüzü istediği gibi tasarlayabilir.

Kişi 3 için sözleşme (arayüzün ihtiyacı olan her şey)
-----------------------------------------------------
    from ingest import ingest_upload, SUPPORTED_EXTENSIONS, IngestError

    # st.file_uploader(type=SUPPORTED_EXTENSIONS)
    try:
        result = ingest_upload(uploaded.getvalue(), uploaded.name)
    except IngestError as e:
        st.error(str(e))            # mesajlar Türkçe ve kullanıcıya gösterilebilir
    else:
        st.success(result.report.summary_tr())
        st.dataframe(result.records[:20])   # önizleme
        for w in result.report.warnings:
            st.warning(w)

Kişi 2 için not
---------------
Kayıtlar `category` alanında "Other" ile gelir (PDF'te kategori yoktur).
Kategori tahminini categorizer.predict_category() yapar; bu modül kasıtlı
olarak categorizer'ı import ETMEZ — veri katmanı ML katmanına bağımlı olmasın
(ve model yüklemesi dosya yüklemeyi yavaşlatmasın) diye.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO

from bank_profiles import COLUMN_SYNONYMS
from cleaning import (
    CleanReport,
    build_record,
    dedupe,
    detect_currency,
    fold,
    infer_dayfirst,
    normalize_description,
    parse_amount,
    parse_date,
    validate_record,
)
from pdf_statement import StatementParseError, parse_pdf

# --------------------------------------------------------------------------- #
# 1) SABİTLER — Kişi 3 arayüzde bunları kullanabilir
# --------------------------------------------------------------------------- #

SUPPORTED_EXTENSIONS = ["csv", "tsv", "xlsx", "xls", "pdf"]

# Yüklemede üst sınır. Bootcamp demosunda 10 MB fazlasıyla yeter; sınır,
# yanlışlıkla yüklenen dev dosyanın Streamlit sunucusunu şişirmesini önler.
MAX_FILE_MB = 10


class IngestError(Exception):
    """
    Dosya alınamadığında fırlatılır.
    Mesaj Türkçe ve doğrudan kullanıcıya gösterilebilir.
    """


@dataclass
class IngestResult:
    """ingest_upload() çıktısı."""

    records: list[dict] = field(default_factory=list)
    report: CleanReport = field(default_factory=CleanReport)
    file_type: str = ""       # "csv" | "xlsx" | "pdf"
    source: str = ""          # kayıtlardaki `source` değeri
    bank: str = ""            # yalnızca PDF için
    currency: str = ""
    account_name: str = ""

    def to_dict(self) -> dict:
        return {
            "file_type": self.file_type,
            "source": self.source,
            "bank": self.bank,
            "currency": self.currency,
            "account_name": self.account_name,
            "record_count": len(self.records),
            "report": self.report.to_dict(),
        }


# --------------------------------------------------------------------------- #
# 2) TABLO (CSV/EXCEL) SÜTUN EŞLEME
# --------------------------------------------------------------------------- #
# bank_profiles.COLUMN_SYNONYMS ekstre tabloları için yazılmıştı; kullanıcı
# CSV/Excel dışa aktarımlarında ek olarak kategori / hesap / işlem tipi
# sütunları da bulunur. Sprint 1'in iki veri seti de bu başlıkları kullanıyordu.

TABULAR_SYNONYMS: dict[str, list[str]] = {
    **COLUMN_SYNONYMS,
    "transaction_type": [
        "transaction type", "islem tipi", "islem turu", "tip", "tur",
        "type", "dr/cr", "borc/alacak",
    ],
    "category": ["category", "kategori", "harcama kategorisi"],
    "account_name": [
        "account name", "hesap adi", "hesap", "kart", "kart adi",
        "account", "hesap ismi",
    ],
}


def _match_tabular_role(header: str) -> str | None:
    """CSV/Excel başlığını kanonik role çevirir."""
    text = fold(str(header)).strip()
    if not text:
        return None
    for role, synonyms in TABULAR_SYNONYMS.items():
        if text in synonyms:
            return role
    for role, synonyms in TABULAR_SYNONYMS.items():
        for synonym in synonyms:
            if re.search(rf"\b{re.escape(synonym)}\b", text):
                return role
    return None


# İşlem tipi sütunundaki değerler bankadan bankaya değişir.
_DEBIT_TOKENS = {
    "debit", "dr", "d", "borc", "gider", "expense", "withdrawal",
    "payment", "cikis", "harcama", "-",
}
_CREDIT_TOKENS = {
    "credit", "cr", "c", "alacak", "gelir", "income", "deposit",
    "refund", "giris", "maas", "+",
}


def _parse_transaction_type(value: Any) -> str | None:
    """
    İşlem tipi sütununu "debit"/"credit"e çevirir. Tanınmazsa None
    (çağıran o zaman işarete/anahtar kelimeye bakar).
    """
    if value is None:
        return None
    token = fold(str(value)).strip(" .")
    if not token:
        return None
    if token in _DEBIT_TOKENS:
        return "debit"
    if token in _CREDIT_TOKENS:
        return "credit"
    # "Debit Card Purchase" gibi birleşik değerler
    if any(re.search(rf"\b{re.escape(t)}\b", token) for t in ("debit", "borc", "gider")):
        return "debit"
    if any(re.search(rf"\b{re.escape(t)}\b", token) for t in ("credit", "alacak", "gelir")):
        return "credit"
    return None


def _read_tabular(data: bytes, extension: str) -> tuple[list[str], list[list[Any]]]:
    """
    CSV/TSV/Excel'i (başlıklar, satırlar) olarak okur.
    Excel için pandas+openpyxl, CSV için ayırıcıyı otomatik sezen csv modülü.
    """
    if extension in ("xlsx", "xls"):
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover
            raise IngestError(
                "Excel okumak için pandas gerekli: pip install pandas openpyxl"
            ) from exc
        try:
            frame = pd.read_excel(io.BytesIO(data))
        except Exception as exc:
            raise IngestError(f"Excel dosyası okunamadı: {exc}") from exc
        headers = [str(c) for c in frame.columns]
        rows = frame.astype(object).where(frame.notna(), None).values.tolist()
        return headers, rows

    # --- CSV / TSV --- #
    text: str | None = None
    for encoding in ("utf-8-sig", "utf-8", "cp1254", "iso-8859-9", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise IngestError(
            "CSV dosyasının karakter kodlaması çözülemedi. "
            "Dosyayı UTF-8 olarak kaydedip tekrar deneyin."
        )

    sample = text[:8192]
    try:
        # Türkçe Excel CSV'leri genelde ';' kullanır — otomatik sez
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = "\t" if extension == "tsv" else ","

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    all_rows = [r for r in reader if any(str(c).strip() for c in r)]
    if not all_rows:
        raise IngestError("CSV dosyası boş.")
    return [str(c) for c in all_rows[0]], [list(r) for r in all_rows[1:]]


def _ingest_tabular(
    data: bytes,
    extension: str,
    *,
    source: str,
    account_name: str | None,
    default_currency: str | None,
) -> IngestResult:
    """CSV/Excel dosyasını kanonik kayıtlara çevirir."""
    headers, rows = _read_tabular(data, extension)
    report = CleanReport(total_rows=len(rows))

    role_map: dict[int, str] = {}
    for index, header in enumerate(headers):
        role = _match_tabular_role(header)
        if role and role not in role_map.values():
            role_map[index] = role

    roles = set(role_map.values())
    missing = [
        label
        for label, present in (
            ("tarih", "date" in roles or "value_date" in roles),
            ("açıklama", "description" in roles),
            ("tutar", "amount" in roles or "debit" in roles or "credit" in roles),
        )
        if not present
    ]
    if missing:
        raise IngestError(
            f"Dosyada zorunlu sütun(lar) bulunamadı: {', '.join(missing)}. "
            f"Bulunan sütunlar: {', '.join(headers[:12])}. "
            "Sütun başlıklarında 'Tarih', 'Açıklama' ve 'Tutar' (veya İngilizce "
            "karşılıkları) geçmelidir."
        )

    def cell(row: list[Any], role: str) -> Any:
        for index, mapped_role in role_map.items():
            if mapped_role == role and index < len(row):
                return row[index]
        return None

    # Tarih sırasını DOSYANIN TAMAMINDAN çıkar (03/04 belirsizliği)
    date_samples = [cell(r, "date") or cell(r, "value_date") for r in rows]
    dayfirst = infer_dayfirst(date_samples)
    if dayfirst is None:
        dayfirst = True
        report.warnings.append(
            "Tarihlerin gün/ay sırası dosyadan kesinleştirilemedi; "
            "gün/ay/yıl varsayıldı."
        )

    # Dosyada HİÇ negatif tutar yoksa, işaret yön bilgisi TAŞIMIYOR demektir;
    # o zaman pozitif olmak "gelir" anlamına gelmez. Bu, dosya genelinde bir
    # özelliktir; döngü içinde tekrar tekrar hesaplanmasın diye bir kez bakılır.
    has_explicit_type = "transaction_type" in roles or "debit" in roles or "credit" in roles
    file_uses_signs = any(
        (parse_amount(cell(r, "amount")) or 0) < 0 for r in rows
    )
    if not has_explicit_type and not file_uses_signs:
        report.warnings.append(
            "Dosyada işlem tipi sütunu yok ve tutarların hiçbiri negatif değil; "
            "gelir/gider ayrımı yapılamadığı için tüm işlemler GİDER sayıldı. "
            "Doğruysa sorun yok; değilse dosyaya 'İşlem Tipi' sütunu ekleyin."
        )

    records: list[dict] = []
    for row in rows:
        raw_date = cell(row, "date") or cell(row, "value_date")
        parsed_date = parse_date(raw_date, dayfirst=dayfirst)
        if parsed_date is None:
            report._drop("tarih okunamadı", row)
            continue

        raw_description = cell(row, "description")
        description = normalize_description(raw_description)
        if not description:
            report._drop("açıklama boş", row)
            continue

        raw_amount = cell(row, "amount")
        amount = parse_amount(raw_amount)
        direction = _parse_transaction_type(cell(row, "transaction_type"))

        if amount is None:  # ayrı borç/alacak sütunları
            debit_value = parse_amount(cell(row, "debit"))
            credit_value = parse_amount(cell(row, "credit"))
            if debit_value:
                amount, direction = debit_value, "debit"
            elif credit_value:
                amount, direction = credit_value, "credit"

        if amount is None:
            report._drop("tutar okunamadı", row)
            continue
        if amount == 0:
            report._drop("tutar sıfır", row)
            continue

        # Yön: 1) işlem tipi sütunu  2) tutarın işareti  3) gider varsayımı
        if direction is None:
            if amount < 0:
                direction = "debit"
            elif file_uses_signs:
                direction = "credit"   # dosya işaret kullanıyor + bu satır pozitif
            else:
                direction = "debit"    # işaret yön taşımıyor -> çoğunluk giderdir

        raw_currency = cell(row, "currency")
        currency = (
            detect_currency(str(raw_currency), None) if raw_currency else None
        ) or (detect_currency(str(raw_amount), None) if raw_amount else None) or (
            default_currency or "TRY"
        )

        account = (
            account_name
            or (str(cell(row, "account_name")).strip() if cell(row, "account_name") else "")
            or "Yüklenen Hesap"
        )

        raw_category = cell(row, "category")
        record = build_record(
            date_value=parsed_date,
            description=description,
            amount=amount,
            transaction_type=direction,
            account_name=account,
            source=source,
            currency=currency,
            category_original=str(raw_category).strip() if raw_category else "",
            description_raw=str(raw_description) if raw_description else None,
        )

        errors = validate_record(record)
        if errors:
            report._drop(f"şema ihlali: {errors[0]}", row)
            continue
        records.append(record)

    records = dedupe(records, report)
    report.accepted = len(records)

    return IngestResult(
        records=records,
        report=report,
        file_type=extension,
        source=source,
        currency=records[0]["currency"] if records else (default_currency or "TRY"),
        account_name=records[0]["account_name"] if records else (account_name or ""),
    )


# --------------------------------------------------------------------------- #
# 3) ANA GİRİŞ NOKTASI
# --------------------------------------------------------------------------- #

def ingest_upload(
    data: bytes | BinaryIO,
    filename: str,
    *,
    password: str | None = None,
    account_name: str | None = None,
    bank_key: str | None = None,
    default_currency: str | None = None,
) -> IngestResult:
    """
    Yüklenen dosyayı kanonik işlem kayıtlarına çevirir. Kişi 3'ün çağıracağı
    TEK fonksiyon budur.

    Parametreler
    ------------
    data            : dosya içeriği (Streamlit: `uploaded_file.getvalue()`)
    filename        : orijinal dosya adı — TÜRÜ BELİRLEMEK İÇİN kullanılır
    password        : şifreli PDF ekstreler için
    account_name    : dosyadan okunamazsa kullanılacak hesap adı
    bank_key        : PDF'te otomatik banka tespitini atlamak için
    default_currency: para birimi tespit edilemezse varsayılan

    Dönüş: IngestResult (.records + .report)
    Hata  : IngestError — mesajı kullanıcıya gösterilebilir Türkçe metindir.
    """
    if hasattr(data, "read"):
        data = data.read()
    if not isinstance(data, (bytes, bytearray)):
        raise IngestError("Dosya içeriği okunamadı.")
    data = bytes(data)

    if not data:
        raise IngestError("Dosya boş.")
    size_mb = len(data) / (1024 * 1024)
    if size_mb > MAX_FILE_MB:
        raise IngestError(
            f"Dosya çok büyük ({size_mb:.1f} MB). Üst sınır {MAX_FILE_MB} MB."
        )

    extension = Path(filename or "").suffix.lower().lstrip(".")
    if extension not in SUPPORTED_EXTENSIONS:
        raise IngestError(
            f"Desteklenmeyen dosya türü: '{extension or filename}'. "
            f"Desteklenenler: {', '.join(SUPPORTED_EXTENSIONS)}."
        )

    if extension == "pdf":
        try:
            parsed = parse_pdf(
                data, password=password, account_name=account_name, bank_key=bank_key
            )
        except StatementParseError as exc:
            raise IngestError(str(exc)) from exc
        return IngestResult(
            records=parsed.records,
            report=parsed.report,
            file_type="pdf",
            source=f"pdf_{parsed.bank_key}",
            bank=parsed.bank,
            currency=parsed.currency,
            account_name=parsed.account_name,
        )

    source = "upload_xlsx" if extension in ("xlsx", "xls") else "upload_csv"
    return _ingest_tabular(
        data,
        extension,
        source=source,
        account_name=account_name,
        default_currency=default_currency,
    )


# --------------------------------------------------------------------------- #
# 4) VERİ SETİNE BİRLEŞTİRME
# --------------------------------------------------------------------------- #

def merge_into_dataset(
    new_records: list[dict], existing: list[dict] | None = None
) -> tuple[list[dict], int]:
    """
    Yeni kayıtları mevcut veri setine ekler; transaction_id ile tekrarları eler.

    Dönüş: (birleşik_liste, gerçekten_eklenen_sayısı)

    Kullanıcının aynı ekstreyi iki kez yüklemesi harcamaları ikiye katlamasın
    diye gereklidir. Mevcut kayıtlar korunur, yeniler eklenir.
    """
    existing = existing or []
    seen = {r.get("transaction_id") for r in existing}
    merged = list(existing)
    added = 0
    for record in new_records:
        if record.get("transaction_id") in seen:
            continue
        seen.add(record.get("transaction_id"))
        merged.append(record)
        added += 1
    merged.sort(key=lambda r: (r.get("date", ""), r.get("description", "")))
    return merged, added


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Kullanım: python ingest.py <dosya> [--json cikti.json]")
        print(f"Desteklenen türler: {', '.join(SUPPORTED_EXTENSIONS)}")
        sys.exit(1)

    path = Path(sys.argv[1])
    try:
        result = ingest_upload(path.read_bytes(), path.name)
    except IngestError as exc:
        print(f"HATA: {exc}")
        sys.exit(1)

    print(f"Dosya      : {path.name}")
    print(f"Tür/Kaynak : {result.file_type} / {result.source}")
    if result.bank:
        print(f"Banka      : {result.bank}")
    print(f"Hesap      : {result.account_name}")
    print(f"Para birimi: {result.currency}")
    print(f"Özet       : {result.report.summary_tr()}")
    for warning in result.report.warnings:
        print(f"  UYARI: {warning}")

    print("\nİlk 5 kayıt:")
    for record in result.records[:5]:
        print(
            f"  {record['date']}  {record['description'][:38]:38}  "
            f"{record['amount']:>12,.2f} {record['currency']}  {record['transaction_type']}"
        )

    if "--json" in sys.argv:
        out_path = Path(sys.argv[sys.argv.index("--json") + 1])
        out_path.write_text(
            json.dumps(result.records, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n{len(result.records)} kayıt {out_path} dosyasına yazıldı.")
