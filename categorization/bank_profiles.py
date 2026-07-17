"""
bank_profiles.py — Banka Ekstre Profilleri (Kişi 1 — Veri & Ekstre İşleme)
==========================================================================

Her banka ekstresini farklı biçimde basar: sütun adları, tarih sırası,
ondalık ayırıcı, negatif gösterimi... Bu dosya bu farklılıkları TEK yerde,
veri olarak toplar. Yeni banka eklemek = yeni bir `BankProfile` yazmak;
pdf_statement.py'ye dokunmak gerekmez.

Tasarım kararı — neden profil + genel (generic) geri dönüş birlikte?
    Profil tespit edilemezse ekstre REDDEDİLMEZ; GENERIC_PROFILE ile
    ayrıştırılmaya çalışılır. Tanımadığımız bir banka yüzünden kullanıcının
    dosyası çöpe gitmesin. Tespit edilen profil rapora yazılır ki kullanıcı
    hangi varsayımların kullanıldığını görebilsin.

DÜRÜSTLÜK NOTU (ekip için önemli):
    Aşağıdaki profiller, bankaların yayımladığı ekstre düzenlerine dayanarak
    yazılmış ve tests/fixtures altındaki SENTETİK PDF'lerle doğrulanmıştır.
    GERÇEK ekstrelerle henüz test EDİLMEMİŞTİR. Her arkadaşımızın kendi
    bankasından aldığı gerçek bir PDF ile denemesi ve `number_locale`,
    `dayfirst`, sütun adları uyuşmuyorsa profili güncellemesi gerekir.
    Profil eklemek/düzeltmek bu dosyada birkaç satırlık iştir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# --------------------------------------------------------------------------- #
# 1) SÜTUN ADI EŞ ANLAMLILARI
# --------------------------------------------------------------------------- #
# Tablo başlıklarını kanonik role eşler. Metinler `cleaning.fold()` ile
# normalize edilmiş halde karşılaştırılır (aksan/büyük harf duyarsız).
#
# Sıra ÖNEMLİDİR: daha uzun/özgül ifadeler önce gelir ki "islem tarihi"
# başlığı "tarih" ile değil, doğru anahtarla eşleşsin.

COLUMN_SYNONYMS: dict[str, list[str]] = {
    # İşlem tarihi — valör (value date) tarihinden AYRI tutulur
    "date": [
        "islem tarihi", "transaction date", "posting date", "process date",
        "tarih", "date", "tarihi",
    ],
    # Valör tarihi — yalnızca işlem tarihi yoksa kullanılır
    "value_date": ["valor", "valor tarihi", "value date"],
    "description": [
        "islem aciklamasi", "aciklama / detay", "transaction details",
        "aciklama", "description", "detay", "details", "narration",
        "particulars", "islem", "aciklamasi",
    ],
    # Tek sütunda işaretli tutar
    "amount": [
        "islem tutari", "transaction amount", "tutar", "amount", "miktar",
    ],
    # Ayrı borç/alacak sütunları (çok yaygın)
    "debit": [
        "borc", "cikan", "cikan tutar", "para cikisi", "debit",
        "withdrawal", "withdrawals", "harcama",
    ],
    "credit": [
        "alacak", "gelen", "gelen tutar", "para girisi", "credit",
        "deposit", "deposits",
    ],
    "balance": ["bakiye", "kalan", "balance", "running balance"],
    "currency": ["para birimi", "doviz", "doviz cinsi", "currency"],
}


def match_column_role(header_text: str) -> str | None:
    """
    Tablo başlık hücresini kanonik role çevirir. Eşleşme yoksa None.
    `header_text` fold() edilmiş olarak beklenir.

        match_column_role("islem tarihi") -> "date"
        match_column_role("borc")         -> "debit"
        match_column_role("sube")         -> None
    """
    text = header_text.strip()
    if not text:
        return None
    # Önce tam eşleşme — en güvenilir
    for role, synonyms in COLUMN_SYNONYMS.items():
        if text in synonyms:
            return role
    # Sonra içerme — "islem tarihi (valor)" gibi başlıklar için
    for role, synonyms in COLUMN_SYNONYMS.items():
        for synonym in synonyms:
            if re.search(rf"\b{re.escape(synonym)}\b", text):
                return role
    return None


# --------------------------------------------------------------------------- #
# 2) PROFİL TANIMI
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class BankProfile:
    """
    Tek bir bankanın ekstre düzeni.

    key            : kayıt kaynağı eki -> source = "pdf_<key>"
    display_name   : kullanıcıya gösterilecek ad
    detect         : PDF metninde aranacak imzalar (fold() edilmiş)
    number_locale  : "tr" (1.234,56) | "us" (1,234.56) — cleaning.parse_amount'a geçer
    dayfirst       : tarih BELİRSİZ ise (her iki bileşen de <= 12) varsayılan
    currency_default: ekstrede sembol bulunamazsa varsayılan para birimi
    account_patterns: hesap/kart adını çekmek için regex'ler (ilk eşleşen kazanır)
    debit_keywords : tek tutar sütunlu ekstrede satırı gider sayan ipuçları
    credit_keywords: aynısının gelir karşılığı
    """

    key: str
    display_name: str
    detect: tuple[str, ...] = ()
    number_locale: str = "tr"
    dayfirst: bool = True
    currency_default: str = "TRY"
    account_patterns: tuple[str, ...] = ()
    debit_keywords: tuple[str, ...] = ()
    credit_keywords: tuple[str, ...] = ()
    notes: str = ""

    @property
    def source(self) -> str:
        """schema.py'deki `source` alanının değeri: pdf_garanti, pdf_generic..."""
        return f"pdf_{self.key}"


# Türk bankalarında yaygın gelir/gider ipuçları — profiller bunları paylaşır.
_TR_DEBIT_KEYWORDS = (
    "harcama", "odeme", "cekim", "para cekme", "pos", "alisveris",
    "fatura", "komisyon", "masraf", "ucret", "vergi", "eft gonderilen",
    "havale gonderilen", "gonderilen", "cikis", "borc",
)
_TR_CREDIT_KEYWORDS = (
    "maas", "gelen havale", "gelen eft", "iade", "faiz", "yatirma",
    "para yatirma", "alacak", "giris", "gelen", "iadesi",
)

_TR_ACCOUNT_PATTERNS = (
    r"(?:hesap\s*ad[ıi]|hesap\s*ismi)\s*[:\-]\s*(.+)",
    r"(?:kart\s*ad[ıi]|kart\s*ismi)\s*[:\-]\s*(.+)",
    r"(?:ürün|urun)\s*[:\-]\s*(.+)",
    r"(?:hesap\s*(?:no|numaras[ıi]))\s*[:\-]\s*([\w\s\-/]+)",
    r"(?:iban)\s*[:\-]\s*([A-Z]{2}[\d\s]{15,32})",
)


# --------------------------------------------------------------------------- #
# 3) PROFİL KAYIT DEFTERİ
# --------------------------------------------------------------------------- #
# Yeni banka eklemek için: aşağıya bir BankProfile ekleyin, `detect` alanına
# ekstrenin başlığında/altbilgisinde GEÇEN ve başka bankada geçmeyen bir
# ifade yazın. Sıra önemli değildir; en çok imza eşleşen profil seçilir.

PROFILES: list[BankProfile] = [
    BankProfile(
        key="garanti",
        display_name="Garanti BBVA",
        detect=("garanti bbva", "garanti bankasi", "garantibank", "t. garanti"),
        number_locale="tr",
        dayfirst=True,
        currency_default="TRY",
        account_patterns=_TR_ACCOUNT_PATTERNS,
        debit_keywords=_TR_DEBIT_KEYWORDS,
        credit_keywords=_TR_CREDIT_KEYWORDS,
    ),
    BankProfile(
        key="isbank",
        display_name="Türkiye İş Bankası",
        detect=("is bankasi", "isbank", "turkiye is bankasi", "maximum"),
        number_locale="tr",
        dayfirst=True,
        currency_default="TRY",
        account_patterns=_TR_ACCOUNT_PATTERNS,
        debit_keywords=_TR_DEBIT_KEYWORDS,
        credit_keywords=_TR_CREDIT_KEYWORDS,
    ),
    BankProfile(
        key="yapikredi",
        display_name="Yapı Kredi",
        detect=("yapi kredi", "yapikredi", "yapi ve kredi bankasi", "worldcard"),
        number_locale="tr",
        dayfirst=True,
        currency_default="TRY",
        account_patterns=_TR_ACCOUNT_PATTERNS,
        debit_keywords=_TR_DEBIT_KEYWORDS,
        credit_keywords=_TR_CREDIT_KEYWORDS,
    ),
    BankProfile(
        key="akbank",
        display_name="Akbank",
        detect=("akbank", "axess", "wings kart"),
        number_locale="tr",
        dayfirst=True,
        currency_default="TRY",
        account_patterns=_TR_ACCOUNT_PATTERNS,
        debit_keywords=_TR_DEBIT_KEYWORDS,
        credit_keywords=_TR_CREDIT_KEYWORDS,
    ),
    BankProfile(
        key="ziraat",
        display_name="Ziraat Bankası",
        detect=("ziraat bankasi", "t.c. ziraat", "ziraat katilim", "bankkart"),
        number_locale="tr",
        dayfirst=True,
        currency_default="TRY",
        account_patterns=_TR_ACCOUNT_PATTERNS,
        debit_keywords=_TR_DEBIT_KEYWORDS,
        credit_keywords=_TR_CREDIT_KEYWORDS,
    ),
    BankProfile(
        key="finansbank",
        display_name="QNB Finansbank",
        detect=("finansbank", "qnb finansbank", "cardfinans"),
        number_locale="tr",
        dayfirst=True,
        currency_default="TRY",
        account_patterns=_TR_ACCOUNT_PATTERNS,
        debit_keywords=_TR_DEBIT_KEYWORDS,
        credit_keywords=_TR_CREDIT_KEYWORDS,
    ),
    BankProfile(
        key="denizbank",
        display_name="DenizBank",
        detect=("denizbank", "bonus kart", "deniz bank"),
        number_locale="tr",
        dayfirst=True,
        currency_default="TRY",
        account_patterns=_TR_ACCOUNT_PATTERNS,
        debit_keywords=_TR_DEBIT_KEYWORDS,
        credit_keywords=_TR_CREDIT_KEYWORDS,
    ),
    # --- Türkçe olmayan ekstreler -------------------------------------- #
    # Sprint 1 veri setleri Hindistan (INR) ve ABD (USD) kaynaklıydı;
    # kullanıcı benzer bir PDF yüklerse diye profilleri hazır tutuyoruz.
    BankProfile(
        key="hdfc",
        display_name="HDFC Bank (India)",
        detect=("hdfc bank", "hdfc"),
        number_locale="us",   # Hindistan da nokta-ondalık kullanır
        dayfirst=True,        # gün/ay/yıl
        currency_default="INR",
        account_patterns=(r"(?:account\s*name|a/c\s*name)\s*[:\-]\s*(.+)",),
        debit_keywords=("debit", "withdrawal", "purchase", "payment"),
        credit_keywords=("credit", "deposit", "salary", "refund", "interest"),
    ),
    BankProfile(
        key="chase",
        display_name="Chase (US)",
        detect=("jpmorgan chase", "chase bank", "chase.com"),
        number_locale="us",
        dayfirst=False,       # ABD: ay/gün/yıl
        currency_default="USD",
        account_patterns=(r"(?:account\s*name|account)\s*[:\-]\s*(.+)",),
        debit_keywords=("debit", "withdrawal", "purchase", "payment", "fee"),
        credit_keywords=("credit", "deposit", "payroll", "refund", "interest"),
    ),
]

# Hiçbir profil eşleşmediğinde kullanılır. Muhafazakâr varsayımlar:
# tutar biçimi "auto" (parse_amount kendi çıkarımını yapar), tarih sırası
# dosyanın tamamından çıkarılır, para birimi metinden tespit edilir.
GENERIC_PROFILE = BankProfile(
    key="generic",
    display_name="Bilinmeyen Banka (genel ayrıştırıcı)",
    detect=(),
    number_locale="auto",
    dayfirst=True,
    currency_default="TRY",
    account_patterns=_TR_ACCOUNT_PATTERNS + (
        r"(?:account\s*name)\s*[:\-]\s*(.+)",
    ),
    debit_keywords=_TR_DEBIT_KEYWORDS + ("debit", "withdrawal", "purchase"),
    credit_keywords=_TR_CREDIT_KEYWORDS + ("credit", "deposit", "salary"),
    notes="Profil tespit edilemedi; genel kurallarla ayrıştırıldı.",
)


def detect_profile(folded_text: str) -> tuple[BankProfile, int]:
    """
    PDF'in TAM METNİNDEN bankayı tespit eder.

    `folded_text` cleaning.fold() ile normalize edilmiş olmalıdır.
    Dönüş: (profil, eşleşen_imza_sayısı). Eşleşme yoksa (GENERIC_PROFILE, 0).

    En çok imza eşleşen profil kazanır; böylece "akbank" imzası taşıyan ama
    "axess" da geçen bir ekstre doğru profile gider.
    """
    best: BankProfile | None = None
    best_score = 0
    for profile in PROFILES:
        score = sum(1 for signature in profile.detect if signature in folded_text)
        if score > best_score:
            best, best_score = profile, score
    if best is None:
        return GENERIC_PROFILE, 0
    return best, best_score


def get_profile(key: str) -> BankProfile:
    """Profili anahtarıyla getirir; bulunamazsa GENERIC_PROFILE döner."""
    for profile in PROFILES:
        if profile.key == key:
            return profile
    return GENERIC_PROFILE


def supported_banks() -> list[str]:
    """Kişi 3'ün arayüzde 'desteklenen bankalar' listesi gösterebilmesi için."""
    return [p.display_name for p in PROFILES]
