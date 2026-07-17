"""
cleaning.py — Veri Temizleme Katmanı (Kişi 1 — Veri & Ekstre İşleme)
=====================================================================

schema.py kanonik kontratı tanımlar; bu dosya ham veriyi (CSV / Excel / PDF)
o kontrata GÜVENLİ şekilde çeviren temizleme primitiflerini içerir.

Sprint 1 retrospektifinde "veri temizleme tahmin edilenden fazla efor
gerektirdi" ve "para birimi karışıklığı geç fark edildi" notları alınmıştı.
Bu modül temizleme mantığını TEK yerde toplar; ingest.py ve pdf_statement.py
buradaki fonksiyonları çağırır, kendi kopyalarını yazmaz.

Çözülen başlıca problemler:
    1) Tutar ayrıştırma       — "1.234,56" (TR) vs "1,234.56" (US) belirsizliği
    2) Tarih ayrıştırma       — 03/04/2024 -> 3 Nisan mı, 4 Mart mı?
                                Dosyanın TAMAMINA bakarak karar verilir.
    3) Açıklama normalizasyonu — kart maskesi, referans no, POS öneki temizliği
    4) Kararlı transaction_id  — Sprint 1'deki reçeteyle birebir uyumlu
    5) Doğrulama + kalite raporu — bozuk satır sessizce kaybolmaz

NOT (kapsam sınırı): Bu modül para birimini yalnızca KAYNAKTA TESPİT eder
(ör. ekstredeki "₺" sembolü -> "TRY"). Para birimleri arası dönüşüm /
standardizasyon Kişi 2'nin görevidir; burada bilinçli olarak yapılmaz.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable

from schema import ALL_FIELDS, CORE_FIELDS, TRANSACTION_TYPES, normalize_category

# --------------------------------------------------------------------------- #
# 1) TÜRKÇE METİN YARDIMCILARI
# --------------------------------------------------------------------------- #
# Python'un str.lower() metodu "İ" harfini "i̇" (i + birleşen nokta) yapar.
# Bu, keyword eşleşmelerini sessizce bozar: "İSTANBUL".lower() != "istanbul".
# Aşağıdaki eşleme Türkçe'ye özgü harfleri önce düzeltir.

_TR_LOWER_MAP = str.maketrans({"İ": "i", "I": "ı", "Ş": "ş", "Ğ": "ğ", "Ü": "ü", "Ö": "ö", "Ç": "ç"})


def tr_lower(text: str) -> str:
    """Türkçe-güvenli küçük harfe çevirme (İ -> i, I -> ı)."""
    return str(text).translate(_TR_LOWER_MAP).lower()


# NFKD'nin ÇÖZEMEDİĞİ harfler. "ş" -> s + çengel, "ğ" -> g + kısa işareti
# şeklinde ayrışır ve birleşen işaret atılınca ASCII'ye iner. Ama "ı"
# (noktasız i) bir aksanlı harf DEĞİL, bağımsız bir Unicode harfidir ve
# ayrışmaz. Elle eşlenmezse fold("Açıklama") -> "acıklama" olur ve
# bank_profiles.COLUMN_SYNONYMS'teki "aciklama" ile EŞLEŞMEZ; gerçek Türkçe
# ekstrelerde sütun tespiti sessizce başarısız olur.
_FOLD_EXTRA_MAP = str.maketrans({"ı": "i", "İ": "i", "ﬁ": "fi", "ﬂ": "fl"})


def fold(text: str) -> str:
    """
    Aksan/şapka işaretlerini kaldırıp ASCII küçük harfe indirger.
    Yalnızca EŞLEŞTİRME için kullanılır (banka tespiti, sütun başlığı, keyword);
    kullanıcıya gösterilecek metinde kullanılmaz.

        fold("GARANTİ BBVA")  -> "garanti bbva"
        fold("Şok Marketler") -> "sok marketler"
        fold("Açıklama")      -> "aciklama"   (ı -> i)
    """
    lowered = tr_lower(text).translate(_FOLD_EXTRA_MAP)
    decomposed = unicodedata.normalize("NFKD", lowered)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


# --------------------------------------------------------------------------- #
# 2) TUTAR (AMOUNT) AYRIŞTIRMA
# --------------------------------------------------------------------------- #
# Ekstrelerde tutar biçimi bankaya/ülkeye göre değişir:
#     Türk bankası : 1.234,56  TL     (nokta = binlik, virgül = ondalık)
#     ABD/Hindistan: 1,234.56  USD    (virgül = binlik, nokta = ondalık)
#     Negatif       : -1.234,56 | 1.234,56- | (1.234,56)
# Yanlış yorum 1.234,56 TL'yi 1.23 TL yapar — sessiz ve tehlikeli bir hata.

# Tutar gövdesi: rakamlar + . ve , ayırıcıları
_AMOUNT_BODY_RE = re.compile(r"\d[\d.,]*")
# Parantezli negatif: (1.234,56)
_PAREN_NEG_RE = re.compile(r"^\(.*\)$")

# Sembol/kod -> ISO. detect_currency() ve dominant_currency() paylaşır.
_SYMBOL_PAIRS = (("₺", "TRY"), ("$", "USD"), ("€", "EUR"), ("£", "GBP"), ("₹", "INR"))
_CODE_PAIRS = (
    ("try", "TRY"), ("usd", "USD"), ("eur", "EUR"), ("gbp", "GBP"),
    ("inr", "INR"), ("tl", "TRY"), ("rs", "INR"),
)


def detect_currency(text: str, default: str | None = None) -> str | None:
    """
    TEK bir metin parçasındaki (hücre, tutar) para birimini ISO koduna çevirir.
    İLK eşleşme kazanır. Bulamazsa `default` döner.

        detect_currency("1.234,56 TL")  -> "TRY"
        detect_currency("$1,234.56")    -> "USD"

    Belgenin TAMAMI için bunu değil, dominant_currency() kullanın.
    """
    if text is None:
        return default
    raw = str(text)
    # Sembolleri ham metinde ara (fold sembolleri bozmaz ama kodları normalize eder)
    for symbol, code in _SYMBOL_PAIRS:
        if symbol in raw:
            return code
    folded = fold(raw)
    # Kod arama kelime sınırıyla: "tl" -> "atlas" içinde eşleşmesin
    for token, code in _CODE_PAIRS:
        if re.search(rf"\b{re.escape(token)}\b", folded):
            return code
    return default


def dominant_currency(text: str, default: str | None = None) -> str | None:
    """
    BELGE GENELİNDE en çok geçen para birimini döner.

    detect_currency() İLK eşleşmeyi alır; bu tek bir hücre için doğrudur ama
    ekstrenin TAMAMI için kırılgandır: Türk bankası ekstresinde geçen tek bir
    "$" (ör. bir döviz hesabı bakiyesi ya da dipnot) tüm ekstreyi USD yapardı.
    Saymak bu tek-örnek gürültüsüne dayanıklıdır.

    Eşitlik durumunda `_SYMBOL_PAIRS` sırası belirleyicidir (deterministik olsun
    diye); hiç eşleşme yoksa `default` döner.
    """
    if not text:
        return default

    counts: dict[str, int] = {}
    for symbol, code in _SYMBOL_PAIRS:
        found = text.count(symbol)
        if found:
            counts[code] = counts.get(code, 0) + found

    folded = fold(text)
    for token, code in _CODE_PAIRS:
        found = len(re.findall(rf"\b{re.escape(token)}\b", folded))
        if found:
            counts[code] = counts.get(code, 0) + found

    if not counts:
        return default
    return max(counts, key=lambda code: counts[code])


def parse_amount(raw: Any, locale_hint: str = "auto") -> float | None:
    """
    Ham tutar metnini float'a çevirir. İşareti KORUR (negatif olabilir);
    kanonik kayıtta amount her zaman pozitiftir, yönü çağıran belirler.

    locale_hint:
        "tr"   -> nokta binlik, virgül ondalık   (1.234,56 -> 1234.56)
        "us"   -> virgül binlik, nokta ondalık   (1,234.56 -> 1234.56)
        "auto" -> biçimden çıkarım yapar (aşağıdaki kurallar)

    Belirsizlik kuralları ("auto"):
        - Hem "." hem "," varsa: SONDAKİ ayırıcı ondalıktır.
          ("1.234,56" -> virgül sonda -> ondalık -> 1234.56)
        - Tek tür ayırıcı birden fazla kez geçiyorsa: binliktir.
          ("1.234.567" -> 1234567)
        - Tek ayırıcı ve ardından tam 3 hane varsa: binliktir.
          ("1,500" -> 1500 — parada 3 ondalık hane kullanılmaz)
        - Tek ayırıcı ve ardından 1-2 hane varsa: ondalıktır.
          ("1,5" -> 1.5 | "12.34" -> 12.34)

    Ayrıştıramazsa None döner (çağıran satırı rapora düşürür).
    """
    if raw is None:
        return None
    if isinstance(raw, bool):  # bool int'in alt sınıfı — kazara kabul etmeyelim
        return None
    if isinstance(raw, (int, float)):
        return float(raw)

    text = str(raw).strip()
    if not text:
        return None

    negative = False
    if _PAREN_NEG_RE.match(text):        # (1.234,56) -> muhasebe negatifi
        negative = True
        text = text[1:-1]
    if text.endswith("-"):               # 1.234,56-  -> bazı TR bankaları
        negative = True
        text = text[:-1]
    if text.lstrip().startswith("-"):    # -1.234,56
        negative = True

    match = _AMOUNT_BODY_RE.search(text)
    if not match:
        return None
    body = match.group(0)

    has_dot, has_comma = "." in body, "," in body

    if has_dot and has_comma:
        # Sondaki ayırıcı ondalıktır.
        decimal_sep = "." if body.rfind(".") > body.rfind(",") else ","
    elif has_dot or has_comma:
        sep = "." if has_dot else ","
        if body.count(sep) > 1:
            decimal_sep = None                      # birden fazla -> binlik
        else:
            digits_after = len(body.split(sep)[1])
            if locale_hint == "tr":
                decimal_sep = "," if sep == "," else None
            elif locale_hint == "us":
                decimal_sep = "." if sep == "." else None
            else:
                # auto: 3 hane -> binlik, 1-2 hane -> ondalık, 4+ -> ondalık
                decimal_sep = None if digits_after == 3 else sep
    else:
        decimal_sep = None

    if decimal_sep is None:
        cleaned = body.replace(".", "").replace(",", "")
    else:
        thousands_sep = "," if decimal_sep == "." else "."
        cleaned = body.replace(thousands_sep, "").replace(decimal_sep, ".")

    try:
        value = float(cleaned)
    except ValueError:
        return None
    return -value if negative else value


# --------------------------------------------------------------------------- #
# 3) TARİH AYRIŞTIRMA
# --------------------------------------------------------------------------- #
# 03/04/2024 -> 3 Nisan (TR, gün önce) mi, 4 Mart (US, ay önce) mi?
# Tek satıra bakarak KARAR VERİLEMEZ. Doğru yaklaşım: dosyadaki TÜM tarihlere
# bakıp ilk bileşende 12'den büyük bir değer var mı diye kontrol etmek.

_DATE_SPLIT_RE = re.compile(r"^\s*(\d{1,4})[./\-](\d{1,2})[./\-](\d{2,4})\s*$")

# Türkçe ay isimleri (bazı ekstreler "12 Oca 2024" biçimi kullanır)
_TR_MONTHS = {
    "oca": 1, "ocak": 1, "sub": 2, "subat": 2, "mar": 3, "mart": 3,
    "nis": 4, "nisan": 4, "may": 5, "mayis": 5, "haz": 6, "haziran": 6,
    "tem": 7, "temmuz": 7, "agu": 8, "agustos": 8, "eyl": 9, "eylul": 9,
    "eki": 10, "ekim": 10, "kas": 11, "kasim": 11, "ara": 12, "aralik": 12,
}
_TEXT_DATE_RE = re.compile(r"^\s*(\d{1,2})\s+([^\W\d_]+)\s+(\d{4})\s*$", re.UNICODE)


def _two_digit_year(year: int) -> int:
    """2 haneli yılı 4 haneye tamamlar (00-68 -> 20xx, 69-99 -> 19xx)."""
    if year >= 100:
        return year
    return 2000 + year if year <= 68 else 1900 + year


def infer_dayfirst(samples: Iterable[Any]) -> bool | None:
    """
    Tarih ÖRNEKLERİNİN TAMAMINA bakarak gün-önce mi ay-önce mi olduğunu bulur.

        - İlk bileşende 12'den büyük değer varsa  -> gün önce (True)
        - İkinci bileşende 12'den büyük değer varsa -> ay önce (False)
        - İkisi de yoksa (hepsi <= 12)            -> BELİRSİZ (None)

    None dönerse çağıran, banka profilinin varsayılanını kullanmalıdır.
    Çelişki varsa (ikisi de 12'yi aşıyorsa) None döner — veri tutarsızdır.
    """
    first_over, second_over = False, False
    for sample in samples:
        if sample is None:
            continue
        match = _DATE_SPLIT_RE.match(str(sample))
        if not match:
            continue
        a, b, c = (int(g) for g in match.groups())
        if len(match.group(1)) == 4:  # 2024-03-04 -> ISO, belirsizlik yok
            continue
        if a > 12:
            first_over = True
        if b > 12:
            second_over = True
    if first_over and second_over:
        return None  # çelişki — veri karışık
    if first_over:
        return True
    if second_over:
        return False
    return None


def parse_date(raw: Any, dayfirst: bool = True) -> date | None:
    """
    Ham tarihi `datetime.date` nesnesine çevirir. Ayrıştıramazsa None.

    Desteklenen biçimler:
        2024-03-04        (ISO — dayfirst yok sayılır)
        04/03/2024, 04.03.2024, 04-03-2024
        04/03/24          (2 haneli yıl)
        12 Oca 2024       (Türkçe ay adı)

    `dayfirst` yalnızca BELİRSİZ durumda kullanılır; ilk bileşen 12'den
    büyükse zaten gün olduğu kesindir ve `dayfirst` yok sayılır.
    """
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw

    text = str(raw).strip()
    if not text:
        return None

    # Türkçe ay adlı biçim: "12 Oca 2024"
    text_match = _TEXT_DATE_RE.match(text)
    if text_match:
        day_s, month_s, year_s = text_match.groups()
        month = _TR_MONTHS.get(fold(month_s)[:3])
        if month:
            try:
                return date(int(year_s), month, int(day_s))
            except ValueError:
                return None

    match = _DATE_SPLIT_RE.match(text)
    if not match:
        return None
    a, b, c = (int(g) for g in match.groups())

    if len(match.group(1)) == 4:            # ISO: 2024-03-04
        year, month, day = a, b, c
    else:
        year = _two_digit_year(c)
        if a > 12:                          # ilk bileşen gün olmak zorunda
            day, month = a, b
        elif b > 12:                        # ikinci bileşen gün olmak zorunda
            day, month = b, a
        else:                               # belirsiz -> çağıranın kararı
            day, month = (a, b) if dayfirst else (b, a)

    try:
        return date(year, month, day)
    except ValueError:
        return None


# --------------------------------------------------------------------------- #
# 4) AÇIKLAMA (DESCRIPTION) NORMALİZASYONU
# --------------------------------------------------------------------------- #
# PDF ekstre açıklamaları gürültülüdür:
#     "POS 5218 12** **** 3456 MIGROS TIC.A.S. REF:009182734 12/03"
# Kişi 2'nin TF-IDF modeli bu gürültüde boğulur. Amaç: mağaza adını korumak,
# gerisini atmak. DİKKAT: agresif temizlik mağaza adını yer ile birlikte
# yok edebilir — bu yüzden kurallar dar tutulmuştur ve ham metin
# `description_raw` alanında saklanır.

_NOISE_PATTERNS = [
    # Kart maskeleri: 5218 12** **** 3456 | ****1234 | XXXX-XXXX-XXXX-1234
    re.compile(r"\b(?:\d{4}[\s-]?)?[\dxX*]{2,4}[\s-]?[*xX]{2,4}[\s-]?[*xX]{2,4}[\s-]?\d{4}\b"),
    re.compile(r"[*xX]{4,}[\s-]?\d{2,4}\b"),
    # Referans/işlem numaraları
    re.compile(r"\b(?:ref|referans|islem|işlem|dekont|makbuz|txn|trn|auth)[\s.:#no]*\d{4,}\b", re.IGNORECASE),
    # Terminal / üye işyeri numarası
    re.compile(r"\b(?:term|terminal|uye|üye)[\s.:#]*\d{4,}\b", re.IGNORECASE),
    # Satır sonundaki gün/ay artığı: "... 12/03" veya "... 12.03.2024"
    re.compile(r"\s+\d{1,2}[./]\d{1,2}(?:[./]\d{2,4})?\s*$"),
]

# Baştaki kanal önekleri — mağaza adını değil, kanalı anlatır
_PREFIX_RE = re.compile(
    r"^\s*(?:pos|atm|otomatik[\s-]?odeme|otomatik[\s-]?ödeme|internet|mobil|"
    r"kredi[\s-]?karti|kredi[\s-]?kartı|harcama|alisveris|alışveriş|transaction\s+at)"
    r"[\s:.\-]+",
    re.IGNORECASE,
)

_WS_RE = re.compile(r"\s+")


def normalize_description(raw: Any) -> str:
    """
    Ekstre açıklamasını mağaza adına indirger.

        "POS 5218 12** **** 3456 MIGROS TIC.A.S. REF:009182734"
            -> "MIGROS TIC.A.S."
        "Transaction at Amazon" -> "Amazon"

    Büyük/küçük harf KORUNUR (dashboard'da okunaklı olsun diye);
    Kişi 2'nin TfidfVectorizer'ı zaten lowercase=True kullanıyor.

    Temizlik sonucu boş kalırsa ham metne geri döner — bilgi kaybetmektense
    gürültülü metin yeğdir.
    """
    if raw is None:
        return ""
    text = str(raw)
    text = _WS_RE.sub(" ", text).strip()
    if not text:
        return ""

    original = text
    for pattern in _NOISE_PATTERNS:
        text = pattern.sub(" ", text)
    # Önek birden fazla katmanlı olabilir: "POS INTERNET MIGROS"
    for _ in range(3):
        new_text = _PREFIX_RE.sub("", text)
        if new_text == text:
            break
        text = new_text

    # Sondaki nokta KORUNUR: "MIGROS TIC.A.S." gibi kısaltmaların parçasıdır.
    text = _WS_RE.sub(" ", text).strip(" -:,/")
    return text if text else original


# --------------------------------------------------------------------------- #
# 5) KARARLI transaction_id
# --------------------------------------------------------------------------- #

def make_transaction_id(
    source: str, date_str: str, description: str, amount: float, account_name: str
) -> str:
    """
    Sprint 1'de üretilen transactions_merged.json ile BİREBİR UYUMLU kimlik.

    Reçete:  md5("source|date|description|amount|account_name")[:16]
    Doğrulama: mevcut 8806 kaydın 8806'sında birebir eşleşir.

    DİKKAT — `amount` Python'un `str(float)` çıktısıyla katılır (ör. "11.11").
    Bu reçete float gösterimine bağlıdır ve kırılgandır; ancak mevcut veriyle
    join uyumluluğunu korumak için bilinçli olarak aynen tekrarlanmıştır.
    Değiştirilirse mevcut tüm kimlikler değişir.
    """
    key = f"{source}|{date_str}|{description}|{amount}|{account_name}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# 6) KAYIT KURMA + DOĞRULAMA
# --------------------------------------------------------------------------- #

@dataclass
class CleanReport:
    """
    Temizleme sürecinin şeffaf özeti.

    Kişi 3 bunu yükleme arayüzünde kullanıcıya gösterebilir ("42 satırın 40'ı
    alındı, 2'si tarihsiz olduğu için atlandı"). Hiçbir satır SESSİZCE
    kaybolmaz — bu, Sprint 1'de yaşanan güven sorununun çözümüdür.
    """

    total_rows: int = 0
    accepted: int = 0
    dropped: int = 0
    duplicates: int = 0
    drop_reasons: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    samples: list[dict] = field(default_factory=list)  # atlanan ilk birkaç satır

    def _drop(self, reason: str, row: Any = None) -> None:
        self.dropped += 1
        self.drop_reasons[reason] = self.drop_reasons.get(reason, 0) + 1
        if row is not None and len(self.samples) < 5:
            self.samples.append({"reason": reason, "row": str(row)[:200]})

    def to_dict(self) -> dict:
        return {
            "total_rows": self.total_rows,
            "accepted": self.accepted,
            "dropped": self.dropped,
            "duplicates": self.duplicates,
            "drop_reasons": dict(self.drop_reasons),
            "warnings": list(self.warnings),
            "dropped_samples": list(self.samples),
        }

    def summary_tr(self) -> str:
        """Kullanıcıya gösterilebilir tek satırlık Türkçe özet."""
        parts = [f"{self.total_rows} satır okundu", f"{self.accepted} işlem alındı"]
        if self.duplicates:
            parts.append(f"{self.duplicates} tekrar eden kayıt atlandı")
        if self.dropped:
            reasons = ", ".join(f"{k}: {v}" for k, v in self.drop_reasons.items())
            parts.append(f"{self.dropped} satır alınamadı ({reasons})")
        return " · ".join(parts)


def build_record(
    *,
    date_value: date,
    description: str,
    amount: float,
    transaction_type: str,
    account_name: str,
    source: str,
    currency: str,
    category_original: str | None = None,
    category: str | None = None,
    description_raw: str | None = None,
) -> dict:
    """
    Doğrulanmış alanlardan kanonik `TransactionRecord` sözlüğü kurar.
    Alan sırası schema.ALL_FIELDS ile aynıdır (JSON çıktısı okunaklı olsun diye).
    """
    date_str = date_value.isoformat()
    description = description.strip()
    amount = abs(float(amount))

    record = {
        "transaction_id": make_transaction_id(source, date_str, description, amount, account_name),
        "date": date_str,
        "description": description,
        "amount": amount,
        "currency": currency,
        "transaction_type": transaction_type,
        "category": category or normalize_category(category_original),
        "category_original": category_original if category_original is not None else "",
        "account_name": account_name,
        "month": date_str[:7],
        "source": source,
    }
    if description_raw is not None and description_raw.strip() != description:
        record["description_raw"] = description_raw.strip()
    return record


def validate_record(record: dict) -> list[str]:
    """
    Kaydı schema.py kontratına göre denetler; ihlal listesi döner (boşsa geçerli).
    jsonschema bağımlılığı eklemeden, kontratın kritik kurallarını kontrol eder.
    """
    errors: list[str] = []

    for f in CORE_FIELDS:
        if f not in record:
            errors.append(f"zorunlu alan eksik: {f}")

    unknown = set(record) - set(ALL_FIELDS)
    if unknown:
        errors.append(f"şemada tanımsız alan: {', '.join(sorted(unknown))}")

    if "date" in record and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(record["date"])):
        errors.append("date YYYY-MM-DD biçiminde değil")
    if "month" in record and not re.match(r"^\d{4}-\d{2}$", str(record["month"])):
        errors.append("month YYYY-MM biçiminde değil")
    if "date" in record and "month" in record and str(record["date"])[:7] != record["month"]:
        errors.append("month, date ile tutarsız")

    amount = record.get("amount")
    if not isinstance(amount, (int, float)) or isinstance(amount, bool):
        errors.append("amount sayı değil")
    elif amount <= 0:
        errors.append("amount pozitif değil (yön transaction_type'ta taşınır)")

    if record.get("transaction_type") not in TRANSACTION_TYPES:
        errors.append("transaction_type 'debit' veya 'credit' olmalı")
    if not str(record.get("description", "")).strip():
        errors.append("description boş")

    return errors


def dedupe(records: list[dict], report: CleanReport | None = None) -> list[dict]:
    """
    transaction_id'ye göre tekrar eden kayıtları eler; İLK görüleni korur.

    Kullanıcı aynı ekstreyi iki kez yüklediğinde veya ekstreler tarih aralığı
    olarak çakıştığında harcamalar iki katına çıkmasın diye gereklidir.
    """
    seen: set[str] = set()
    unique: list[dict] = []
    for record in records:
        tid = record.get("transaction_id")
        if tid in seen:
            if report is not None:
                report.duplicates += 1
            continue
        seen.add(tid)
        unique.append(record)
    return unique
