"""
pdf_statement.py — PDF Banka Ekstresi Ayrıştırma (Kişi 1 — Veri & Ekstre İşleme)
===============================================================================

Bir PDF banka ekstresini schema.py'deki kanonik `TransactionRecord` listesine
çevirir. Banka farklılıkları bank_profiles.py'de veri olarak tutulur; temizleme
mantığı cleaning.py'dedir. Bu dosya yalnızca ÇIKARMA (extraction) işini yapar.

İki aşamalı strateji
--------------------
1) TABLO MODU (tercih edilen) — pdfplumber ile tablo çıkarılır, başlık satırı
   bank_profiles.COLUMN_SYNONYMS ile eşlenir. Çizgili tablosu olan ekstrelerde
   en güvenilir yöntem; "Borç/Alacak" sütunları net ayrıldığı için harcama/gelir
   yönü TAHMİN EDİLMEZ, okunur.

2) SATIR MODU (geri dönüş) — tablo bulunamazsa düz metin satırları regex ile
   ayrıştırılır: <tarih> <açıklama> <tutar> [<bakiye>]

Harcama/gelir yönü (debit/credit) hangi sırayla belirlenir
----------------------------------------------------------
    1. Ayrı Borç/Alacak sütunları        -> kesin bilgi, okunur
    2. Tutarın işareti (-1.234,56 / (1.234,56)) -> kesin bilgi
    3. BAKİYE FARKI                      -> bakiye düştüyse gider, arttıysa gelir
    4. Açıklamadaki anahtar kelimeler    -> "maaş" gelir, "harcama" gider
    5. Varsayılan: debit (gider)         -> ekstre satırlarının çoğu giderdir

3. adım (bakiye farkı) önemlidir: işaretsiz tek tutar sütunu basan bankalarda
   yönü tahmine bırakmak yerine matematikten okumayı sağlar.

Kullanım:
    from pdf_statement import parse_pdf
    result = parse_pdf("ekstre.pdf")
    print(result.report.summary_tr())
    records = result.records          # kanonik kayıtlar
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, BinaryIO

import pdfplumber

from bank_profiles import (
    GENERIC_PROFILE,
    BankProfile,
    detect_profile,
    get_profile,
    match_column_role,
)
from cleaning import (
    CleanReport,
    build_record,
    dedupe,
    detect_currency,
    dominant_currency,
    fold,
    infer_dayfirst,
    normalize_description,
    parse_amount,
    parse_date,
    validate_record,
)


class StatementParseError(Exception):
    """
    Ekstre okunamadığında fırlatılır.

    Mesaj KULLANICIYA GÖSTERİLEBİLİR Türkçe metindir — Kişi 3 bunu yükleme
    arayüzünde doğrudan st.error() ile basabilir.
    """


@dataclass
class ParsedStatement:
    """parse_pdf() çıktısı — kayıtlar + ne olduğunun şeffaf özeti."""

    records: list[dict] = field(default_factory=list)
    report: CleanReport = field(default_factory=CleanReport)
    bank: str = GENERIC_PROFILE.display_name
    bank_key: str = GENERIC_PROFILE.key
    currency: str = "TRY"
    account_name: str = ""
    pages: int = 0
    mode: str = ""  # "table" | "line" | "table+line"

    def to_dict(self) -> dict:
        return {
            "bank": self.bank,
            "bank_key": self.bank_key,
            "currency": self.currency,
            "account_name": self.account_name,
            "pages": self.pages,
            "mode": self.mode,
            "report": self.report.to_dict(),
        }


# --------------------------------------------------------------------------- #
# 1) DÜŞÜK SEVİYE METİN YARDIMCILARI
# --------------------------------------------------------------------------- #

# Satır başındaki tarih: 04/03/2024 | 4.3.24 | 2024-03-04
_LINE_DATE_RE = re.compile(r"^\s*(\d{1,4}[./\-]\d{1,2}[./\-]\d{2,4})\s+(.*)$")

# Satır sonundaki sayı belirteçleri: 1.234,56 | (1.234,56) | -1.234,56 | 1.234,56-
_TRAILING_NUM_RE = re.compile(r"(\(?-?\d[\d.,]*\)?-?)\s*$")

# Ekstrelerde tabloya benzeyen ama işlem OLMAYAN satırlar
_SKIP_LINE_PATTERNS = tuple(
    re.compile(p) for p in (
        r"\b(?:devreden|onceki|önceki)\s+bakiye\b",
        r"\b(?:toplam|ara\s*toplam|genel\s*toplam)\b",
        r"\b(?:opening|closing)\s+balance\b",
        r"\btotal\b",
        r"\bsayfa\s*\d+\b",
        r"\bpage\s*\d+\b",
    )
)


def _is_skippable(folded_line: str) -> bool:
    """Toplam/bakiye/sayfa satırlarını işlem sanmamak için."""
    return any(p.search(folded_line) for p in _SKIP_LINE_PATTERNS)


def _split_trailing_numbers(text: str, max_count: int = 2) -> tuple[str, list[str]]:
    """
    Satır sonundaki sayıları soyar; (kalan_metin, [sayılar_soldan_saga]) döner.

        "MIGROS ALISVERIS 1.234,56 5.678,90"
            -> ("MIGROS ALISVERIS", ["1.234,56", "5.678,90"])

    max_count neden 2?
        Satır modunda sütun sınırı yoktur; yalnızca "sondaki sayı" görülür.
        En fazla 2 soyarız çünkü beklenen düzen <tutar> [<bakiye>] şeklindedir.
        Daha fazlasını soymak mağaza adının İÇİNDEKİ sayıyı yutar:
            "STARBUCKS STORE 12345   -12.40   8,919.70"
        3 soyulsaydı "12345" tutar sanılırdı (12.40 yerine 12345.0 okunurdu).
        2 ile sınırlayınca "12345" açıklamada kalır ve tutar doğru okunur.

        Bedeli: borç/alacak/bakiye şeklinde 3 sayısal sütunu OLAN ve çizgisi
        OLMAYAN bir ekstre satır modunda tam çözülemez. Bu düzenler pratikte
        çizgili tablo ile gelir ve tablo modunda sütunlar zaten net okunur.
    """
    numbers: list[str] = []
    rest = text.rstrip()
    while len(numbers) < max_count:
        match = _TRAILING_NUM_RE.search(rest)
        if not match:
            break
        token = match.group(1)
        # En az bir rakam ve tek başına anlamlı olmalı
        if not re.search(r"\d", token):
            break
        numbers.append(token)
        rest = rest[: match.start()].rstrip()
    numbers.reverse()
    return rest, numbers


def _extract_account_name(text: str, profile: BankProfile) -> str:
    """
    Ekstre başlığından hesap/kart adını çeker. Bulamazsa boş string.
    İlk eşleşen desen kazanır (profildeki sıra = öncelik).
    """
    for pattern in profile.account_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            value = re.split(r"\s{2,}|\n", value)[0].strip(" :-")
            if value:
                return value[:80]
    return ""


# --------------------------------------------------------------------------- #
# 2) TABLO MODU
# --------------------------------------------------------------------------- #

def _map_header(row: list[Any]) -> dict[int, str] | None:
    """
    Tablo başlık satırını {sütun_indeksi: rol} sözlüğüne çevirir.

    Geçerli sayılması için en az bir tarih sütunu VE bir tutar kaynağı
    (amount ya da debit/credit) gerekir; aksi halde bu satır başlık değildir.
    """
    mapping: dict[int, str] = {}
    for index, cell in enumerate(row):
        if cell is None:
            continue
        role = match_column_role(fold(str(cell)))
        if role and role not in mapping.values():
            mapping[index] = role

    roles = set(mapping.values())
    has_date = "date" in roles or "value_date" in roles
    has_amount = "amount" in roles or "debit" in roles or "credit" in roles
    return mapping if (has_date and has_amount) else None


def _rows_from_table(table: list[list[Any]]) -> list[dict[str, str]]:
    """Tek bir tabloyu rol->değer sözlüklerine çevirir. Başlık yoksa boş liste."""
    header_map: dict[int, str] | None = None
    out: list[dict[str, str]] = []

    for row in table:
        if not row:
            continue
        if header_map is None:
            header_map = _map_header(row)
            continue  # başlık satırı veri değildir

        record: dict[str, str] = {}
        for index, role in header_map.items():
            if index < len(row) and row[index] is not None:
                value = str(row[index]).replace("\n", " ").strip()
                if value:
                    record[role] = value
        if record:
            out.append(record)
    return out


# --------------------------------------------------------------------------- #
# 3) SATIR MODU
# --------------------------------------------------------------------------- #

def _rows_from_lines(text: str) -> list[dict[str, str]]:
    """
    Düz metin satırlarını rol->değer sözlüklerine çevirir.
    Yalnızca TARİHLE BAŞLAYAN satırlar işlem adayıdır.
    """
    out: list[dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or _is_skippable(fold(line)):
            continue
        match = _LINE_DATE_RE.match(line)
        if not match:
            continue

        date_text, rest = match.group(1), match.group(2)
        description, numbers = _split_trailing_numbers(rest)
        if not numbers or not description.strip():
            continue

        row: dict[str, str] = {"date": date_text, "description": description}
        # 1 sayı -> yalnızca tutar | 2 sayı -> tutar + bakiye
        row["amount"] = numbers[0]
        if len(numbers) >= 2:
            row["balance"] = numbers[-1]
        out.append(row)
    return out


# --------------------------------------------------------------------------- #
# 4) YÖN (debit/credit) BELİRLEME
# --------------------------------------------------------------------------- #

def _direction_from_keywords(description: str, profile: BankProfile) -> str | None:
    """Açıklamadaki ipuçlarından yön çıkarır. Kararsızsa None."""
    folded = fold(description)
    if any(k in folded for k in profile.credit_keywords):
        return "credit"
    if any(k in folded for k in profile.debit_keywords):
        return "debit"
    return None


def _resolve_direction(
    row: dict[str, str],
    amount: float,
    profile: BankProfile,
    previous_balance: float | None,
    current_balance: float | None,
) -> tuple[str, float]:
    """
    Satırın yönünü ve MUTLAK tutarını belirler.
    Dönüş: ("debit"|"credit", pozitif_tutar)

    Öncelik sırası dosya başlığındaki açıklamadadır.
    """
    # 1) Ayrı Borç/Alacak sütunları — kesin bilgi
    debit_raw, credit_raw = row.get("debit"), row.get("credit")
    debit_value = parse_amount(debit_raw, profile.number_locale) if debit_raw else None
    credit_value = parse_amount(credit_raw, profile.number_locale) if credit_raw else None
    if debit_value and abs(debit_value) > 0:
        return "debit", abs(debit_value)
    if credit_value and abs(credit_value) > 0:
        return "credit", abs(credit_value)

    # 2) Tutarın işareti — kesin bilgi
    if amount < 0:
        return "debit", abs(amount)
    if "amount" in row and re.search(r"^\s*\+", str(row["amount"])):
        return "credit", abs(amount)

    # 3) Bakiye farkı — bakiye düştüyse para çıkmıştır
    if previous_balance is not None and current_balance is not None:
        delta = current_balance - previous_balance
        # Yuvarlama gürültüsüne karşı küçük tolerans
        if abs(abs(delta) - abs(amount)) < 0.02:
            return ("credit", abs(amount)) if delta > 0 else ("debit", abs(amount))

    # 4) Anahtar kelimeler
    guess = _direction_from_keywords(row.get("description", ""), profile)
    if guess:
        return guess, abs(amount)

    # 5) Varsayılan — ekstre satırlarının çoğunluğu giderdir
    return "debit", abs(amount)


# --------------------------------------------------------------------------- #
# 5) ANA GİRİŞ NOKTASI
# --------------------------------------------------------------------------- #

def _open_pdf(source: str | Path | bytes | BinaryIO, password: str | None):
    """pdfplumber nesnesi açar; şifreli/bozuk dosyada Türkçe hata verir."""
    if isinstance(source, bytes):
        source = io.BytesIO(source)
    try:
        return pdfplumber.open(source, password=password or "")
    except Exception as exc:  # pdfminer şifre hatasını genel exception olarak atar
        message = str(exc).lower()
        if "password" in message or "encrypt" in message:
            raise StatementParseError(
                "Bu PDF parola korumalı. Lütfen parolasız bir kopya yükleyin "
                "veya parolayı belirtin."
            ) from exc
        raise StatementParseError(
            f"PDF açılamadı — dosya bozuk veya geçerli bir PDF değil. ({exc})"
        ) from exc


def parse_pdf(
    source: str | Path | bytes | BinaryIO,
    *,
    password: str | None = None,
    account_name: str | None = None,
    bank_key: str | None = None,
) -> ParsedStatement:
    """
    PDF banka ekstresini kanonik işlem kayıtlarına çevirir.

    Parametreler
    ------------
    source       : dosya yolu, bytes ya da dosya-benzeri nesne
                   (Streamlit'in UploadedFile nesnesi doğrudan verilebilir)
    password     : şifreli PDF için parola
    account_name : ekstreden okunamazsa kullanılacak hesap adı
    bank_key     : otomatik tespiti atlayıp profili zorlamak için
                   (kullanıcı arayüzde bankayı elle seçerse)

    Dönüş
    -----
    ParsedStatement — .records (kanonik kayıtlar) + .report (kalite özeti)

    Hatalar
    -------
    StatementParseError — parola korumalı, taranmış (görüntü) veya işlem
                          bulunamayan PDF'lerde; mesaj kullanıcıya gösterilebilir.
    """
    report = CleanReport()

    with _open_pdf(source, password) as pdf:
        page_count = len(pdf.pages)
        page_texts: list[str] = []
        raw_rows: list[dict[str, str]] = []
        used_table, used_line = False, False

        for page in pdf.pages:
            page_text = page.extract_text() or ""
            page_texts.append(page_text)

            page_rows: list[dict[str, str]] = []
            for table in page.extract_tables() or []:
                page_rows.extend(_rows_from_table(table))

            if page_rows:
                used_table = True
            elif page_text:
                page_rows = _rows_from_lines(page_text)
                if page_rows:
                    used_line = True
            raw_rows.extend(page_rows)

    full_text = "\n".join(page_texts)

    # --- Taranmış (görüntü) PDF kontrolü -------------------------------- #
    if not full_text.strip():
        raise StatementParseError(
            "Bu PDF'te metin bulunamadı; büyük ihtimalle taranmış bir görüntü. "
            "Bankanızın internet şubesinden PDF olarak indirilmiş (taranmamış) "
            "bir ekstre yükleyin."
        )

    # --- Banka profili -------------------------------------------------- #
    folded_text = fold(full_text)
    if bank_key:
        # Kullanıcı bankayı elle seçti -> otomatik tespiti atla.
        # score = -1: "tespit çalıştırılmadı" (0 ile karıştırılmasın; 0
        # "çalıştı ama bulamadı" demektir ve uyarı üretir).
        profile, score = get_profile(bank_key), -1
    else:
        profile, score = detect_profile(folded_text)
    if score == 0:
        report.warnings.append(
            "Banka tespit edilemedi; genel ayrıştırıcı kullanıldı. "
            "Sonuçları kontrol edin."
        )

    # Belge geneli için dominant_currency: ekstrede geçen tek bir yabancı sembol
    # (dipnot, döviz bakiyesi) tüm ekstrenin para birimini kaydırmasın.
    currency = dominant_currency(full_text, profile.currency_default) or profile.currency_default
    account = (
        account_name
        or _extract_account_name(full_text, profile)
        or profile.display_name
    )

    if not raw_rows:
        raise StatementParseError(
            f"PDF okundu ({page_count} sayfa, {profile.display_name}) ancak hiç işlem "
            "satırı bulunamadı. Ekstre biçimi tanınmıyor olabilir — lütfen bu dosyayı "
            "Kişi 1'e iletin ki banka profili eklensin."
        )

    report.total_rows = len(raw_rows)

    # --- Tarih sırası: DOSYANIN TAMAMINDAN çıkarım ---------------------- #
    # Tek satırdan 03/04 belirsizliği çözülemez; tüm tarihlere bakılır.
    date_samples = [r.get("date") or r.get("value_date") for r in raw_rows]
    dayfirst = infer_dayfirst(date_samples)
    if dayfirst is None:
        dayfirst = profile.dayfirst
        report.warnings.append(
            f"Tarihlerin gün/ay sırası dosyadan kesinleştirilemedi; "
            f"{profile.display_name} varsayılanı kullanıldı "
            f"({'gün/ay/yıl' if dayfirst else 'ay/gün/yıl'})."
        )

    # --- Satırları kanonik kayda çevir ---------------------------------- #
    records: list[dict] = []
    previous_balance: float | None = None

    for row in raw_rows:
        raw_date = row.get("date") or row.get("value_date")
        parsed_date = parse_date(raw_date, dayfirst=dayfirst)
        if parsed_date is None:
            report._drop("tarih okunamadı", row)
            continue

        raw_description = row.get("description", "")
        description = normalize_description(raw_description)
        if not description:
            report._drop("açıklama boş", row)
            continue

        current_balance = (
            parse_amount(row.get("balance"), profile.number_locale)
            if row.get("balance")
            else None
        )

        amount = parse_amount(row.get("amount"), profile.number_locale)
        if amount is None:
            # Tutar sütunu yok; borç/alacak sütunlarından gelebilir
            amount = parse_amount(row.get("debit"), profile.number_locale) or parse_amount(
                row.get("credit"), profile.number_locale
            )
        if amount is None:
            report._drop("tutar okunamadı", row)
            continue
        if amount == 0:
            report._drop("tutar sıfır", row)
            continue

        direction, absolute = _resolve_direction(
            row, amount, profile, previous_balance, current_balance
        )
        if current_balance is not None:
            previous_balance = current_balance

        # Satır bazlı para birimi sütunu varsa onu tercih et
        row_currency = detect_currency(row.get("currency", ""), currency) or currency

        record = build_record(
            date_value=parsed_date,
            description=description,
            amount=absolute,
            transaction_type=direction,
            account_name=account,
            source=profile.source,
            currency=row_currency,
            category_original="",       # PDF'te kategori yok -> Kişi 2 tahmin eder
            description_raw=raw_description,
        )

        errors = validate_record(record)
        if errors:
            report._drop(f"şema ihlali: {errors[0]}", row)
            continue

        records.append(record)

    records = dedupe(records, report)
    report.accepted = len(records)

    mode = "+".join(m for m, used in (("table", used_table), ("line", used_line)) if used)

    return ParsedStatement(
        records=records,
        report=report,
        bank=profile.display_name,
        bank_key=profile.key,
        currency=currency,
        account_name=account,
        pages=page_count,
        mode=mode or "none",
    )
