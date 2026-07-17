"""
fixtures_builder.py — Sentetik Banka Ekstresi Üretici (Kişi 1)
==============================================================

Testler için sahte ama GERÇEKÇİ banka ekstresi PDF'leri üretir.

Neden sentetik?
    Gerçek banka ekstreleri kişisel finansal veridir; repoya koymak gizlilik
    ihlalidir. Bu üretici, farklı bankaların DÜZEN farklılıklarını (sütun
    isimleri, sayı biçimi, tarih sırası, borç/alacak ayrımı) taklit eder;
    ayrıştırıcı bu farklılıklara karşı test edilir.

    Sınır: bu fixture'lar gerçek PDF'lerin YAZI TİPİ / KOLON HİZALAMA
    tuhaflıklarını taklit etmez. Profillerin gerçek ekstrelerle doğrulanması
    hâlâ gereklidir (bkz. bank_profiles.py DÜRÜSTLÜK NOTU).

Üretilen düzenler:
    build_garanti_pdf()  — çizgili tablo, ayrı Borç/Alacak, TR sayı (1.234,56)
    build_isbank_pdf()   — çizgili tablo, tek işaretli Tutar sütunu, TR sayı
    build_chase_pdf()    — tablosuz düz metin, US sayı (1,234.56), ay/gün/yıl
    build_unknown_pdf()  — tanınmayan banka -> genel ayrıştırıcı yolu
    build_scanned_pdf()  — metinsiz (taranmış) PDF -> hata yolu
"""

from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# --------------------------------------------------------------------------- #
# Türkçe karakter desteği
# --------------------------------------------------------------------------- #
# reportlab'in yerleşik Helvetica'sı WinAnsi kodlamasıdır: ğ, ş, ı harfleri
# yoktur. Gerçekçi Türkçe ekstre üretebilmek için bir TTF kaydetmeye çalışırız.

_FONT = "Helvetica"
_FONT_BOLD = "Helvetica-Bold"

for _regular, _bold, _name in (
    (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf", "ArialTR"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuTR"),
):
    try:
        pdfmetrics.registerFont(TTFont(_name, _regular))
        pdfmetrics.registerFont(TTFont(f"{_name}-Bold", _bold))
        _FONT, _FONT_BOLD = _name, f"{_name}-Bold"
        break
    except Exception:  # font yok — ASCII'ye yakın metinle devam
        continue


def turkish_fonts_available() -> bool:
    """Testler tam Türkçe metin bekleyip beklemeyeceğini bilsin diye."""
    return _FONT != "Helvetica"


def _tr_safe(text: str) -> str:
    """TTF yoksa Helvetica'da basılamayan harfleri ASCII'ye indirger."""
    if turkish_fonts_available():
        return text
    return text.translate(str.maketrans({
        "ğ": "g", "Ğ": "G", "ş": "s", "Ş": "S", "ı": "i", "İ": "I",
        "ü": "u", "Ü": "U", "ö": "o", "Ö": "O", "ç": "c", "Ç": "C",
    }))


# --------------------------------------------------------------------------- #
# Ortak tablo çizici
# --------------------------------------------------------------------------- #

def _table_pdf(header_lines: list[str], columns: list[str], rows: list[list[str]]) -> bytes:
    """Başlık metni + ÇİZGİLİ tablo içeren PDF üretir (tablo modu testleri)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    style = styles["Normal"]
    style.fontName = _FONT

    story = []
    for line in header_lines:
        story.append(Paragraph(_tr_safe(line), style))
    story.append(Spacer(1, 14))

    data = [[_tr_safe(c) for c in columns]]
    data += [[_tr_safe(str(c)) for c in row] for row in rows]

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        # GRID şart: pdfplumber varsayılan olarak ÇİZGİLERDEN tablo bulur
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), _FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
    ]))
    story.append(table)
    doc.build(story)
    return buffer.getvalue()


def _text_pdf(lines: list[str]) -> bytes:
    """Tablosuz, düz metin PDF üretir (satır modu testleri)."""
    buffer = io.BytesIO()
    canvas = pdfcanvas.Canvas(buffer, pagesize=A4)
    canvas.setFont(_FONT, 9)
    y = A4[1] - 50
    for line in lines:
        canvas.drawString(40, y, _tr_safe(line))
        y -= 14
        if y < 50:
            canvas.showPage()
            canvas.setFont(_FONT, 9)
            y = A4[1] - 50
    canvas.save()
    return buffer.getvalue()


# --------------------------------------------------------------------------- #
# 1) Garanti BBVA — çizgili tablo, ayrı Borç/Alacak, TR sayı biçimi
# --------------------------------------------------------------------------- #

GARANTI_EXPECTED = [
    # (tarih, açıklama_parçası, tutar, yön)
    ("2024-03-04", "MIGROS", 1234.56, "debit"),
    ("2024-03-05", "MAAS ODEMESI", 42500.00, "credit"),
    ("2024-03-11", "TURKCELL", 389.90, "debit"),
    ("2024-03-14", "GETIR", 245.75, "debit"),
]


def build_garanti_pdf() -> bytes:
    """
    Garanti BBVA düzeni: Borç ve Alacak AYRI sütunlarda -> yön tahmin edilmez.
    Tarihler gün/ay/yıl; 04/03 ve 05/03 belirsiz ama 11/03 ve 14/03 gün>12
    OLMADIĞI için infer_dayfirst None döner -> profil varsayılanı devreye girer.
    """
    return _table_pdf(
        header_lines=[
            "GARANTİ BBVA — Hesap Ekstresi",
            "Hesap Adı: Vadesiz TL Hesabı",
            "IBAN: TR33 0006 2000 1234 5678 9012 34",
            "Dönem: 01/03/2024 - 31/03/2024",
        ],
        columns=["İşlem Tarihi", "Açıklama", "Borç", "Alacak", "Bakiye"],
        rows=[
            ["04/03/2024", "POS 5218 12** **** 3456 MIGROS TIC.A.S. REF:009182734", "1.234,56", "", "8.765,44"],
            ["05/03/2024", "MAAŞ ÖDEMESİ MEDRON A.S.", "", "42.500,00", "51.265,44"],
            ["11/03/2024", "TURKCELL FATURA ÖDEMESİ", "389,90", "", "50.875,54"],
            ["14/03/2024", "POS GETIR PERAKENDE", "245,75", "", "50.629,79"],
            ["", "TOPLAM", "1.870,21", "42.500,00", ""],
        ],
    )


# --------------------------------------------------------------------------- #
# 2) İş Bankası — tek işaretli Tutar sütunu + Bakiye
# --------------------------------------------------------------------------- #

ISBANK_EXPECTED = [
    ("2024-01-15", "A101", 567.80, "debit"),
    ("2024-01-20", "IADE", 150.00, "credit"),
    ("2024-01-25", "KIRA", 18500.00, "debit"),
]


def build_isbank_pdf() -> bytes:
    """
    İş Bankası düzeni: tek "Tutar" sütunu, negatifler eksi işaretli.
    25/01 -> gün 25 > 12 olduğu için infer_dayfirst KESİN olarak True döner.
    """
    return _table_pdf(
        header_lines=[
            "TÜRKİYE İŞ BANKASI A.Ş.",
            "Hesap Adı: Maximum Kart",
            "Ekstre Dönemi: 01.01.2024 - 31.01.2024",
        ],
        columns=["Tarih", "Açıklama", "Tutar", "Bakiye"],
        rows=[
            ["15/01/2024", "A101 YENI MAGAZA REF:88213", "-567,80", "12.432,20"],
            ["20/01/2024", "IADE TRENDYOL", "150,00", "12.582,20"],
            ["25/01/2024", "KIRA ODEMESI", "-18.500,00", "-5.917,80"],
        ],
    )


# --------------------------------------------------------------------------- #
# 3) Chase (ABD) — TABLOSUZ düz metin, US sayı biçimi, ay/gün/yıl
# --------------------------------------------------------------------------- #

CHASE_EXPECTED = [
    ("2024-02-03", "AMAZON", 1234.56, "debit"),
    ("2024-02-14", "PAYROLL", 3500.00, "credit"),
    ("2024-02-28", "STARBUCKS", 12.40, "debit"),
]


def build_chase_pdf() -> bytes:
    """
    Chase düzeni: çizgi YOK -> satır modu devreye girer.
    Tarihler ay/gün/yıl (02/28/2024 -> ikinci bileşen 28 > 12 -> dayfirst=False
    KESİN olarak çıkarılır). Sayılar 1,234.56 biçiminde.
    """
    return _text_pdf([
        "JPMORGAN CHASE BANK, N.A.",
        "Account Name: Total Checking",
        "Statement Period: 02/01/2024 - 02/29/2024",
        "",
        "Date        Description                                  Amount        Balance",
        "02/03/2024  AMAZON MARKETPLACE PURCHASE               -1,234.56      5,432.10",
        "02/14/2024  PAYROLL DIRECT DEPOSIT                     3,500.00      8,932.10",
        "02/28/2024  STARBUCKS STORE 12345                        -12.40      8,919.70",
        "",
        "Total withdrawals: 1,246.96",
    ])


# --------------------------------------------------------------------------- #
# 4) Tanınmayan banka — genel ayrıştırıcı yolu
# --------------------------------------------------------------------------- #

def build_unknown_pdf() -> bytes:
    """Hiçbir profile uymayan ekstre; GENERIC_PROFILE ile ayrıştırılmalı."""
    return _table_pdf(
        header_lines=[
            "KUZEY YILDIZI BANKASI",     # kayıtlı hiçbir profilde yok
            "Hesap Adı: Günlük Hesap",
        ],
        columns=["Tarih", "Açıklama", "Tutar"],
        rows=[
            ["17/05/2024", "MIGROS ALISVERIS", "-450,25"],
            ["18/05/2024", "MAAS", "35.000,00"],
        ],
    )


# --------------------------------------------------------------------------- #
# 5) Taranmış (metinsiz) PDF — hata yolu
# --------------------------------------------------------------------------- #

def build_scanned_pdf() -> bytes:
    """Metin katmanı olmayan PDF; StatementParseError beklenir."""
    buffer = io.BytesIO()
    canvas = pdfcanvas.Canvas(buffer, pagesize=A4)
    canvas.rect(100, 400, 300, 200, fill=0)  # yalnızca çizim, metin yok
    canvas.save()
    return buffer.getvalue()
