"""
categorizer.py — TF-IDF + Random Forest Kategorilendirme (Kişi 2)
===================================================================
Kişi 1'in schema.py'sindeki kanonik kategorileri kullanır.
description alanına bakarak ML modeli ile kategori tahmin eder.
Türkçe mağaza isimleri için keyword fallback mekanizması eklenmiştir.

Görevler:
    - transactions_merged.json ile model eğitilir
    - TF-IDF ile metin vektörleştirilir
    - Random Forest ile sınıflandırma yapılır
    - Düşük güvenilirlikli tahminlerde keyword fallback devreye girer

Mevcut Durum:
    - Test doğruluğu: %99.66 (İngilizce/Hindistan verisi)
    - Türkçe veri testi: %25 doğruluk (model Türkçe bilmiyor)
    - Model 8806 satır veri ile eğitildi (Hindistan + ABD kaynaklı)

TODO — Sprint 2 toplantısında gündeme getirilecek:
    - Housing (57 satır), Personal Care (13 satır), Income (46 satır)
      kategorilerinde veri yetersiz, model bu kategorilerde zayıf kalıyor.
    - Veri seti genişletilmeli, bu kategoriler için ek veri bulunmalı
      veya sentetik veri üretilmeli.
    - Türkçe mağaza isimleri (Migros, Getir, Turkcell vb.) için
      Türkçe veri seti eklenmeli VEYA keyword fallback genişletilmeli.

Kullanım:
    python categorizer.py
"""

import json
from schema import CANONICAL_CATEGORIES
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

# ------------------------------------------------------------------ #
# Veriyi yükle
# ------------------------------------------------------------------ #
with open("transactions_merged.json", encoding="utf-8") as f:
    transactions = json.load(f)

# Tüm işlemleri al, sadece Other kategorisini çıkar
data = [
    t for t in transactions
    if t["category"] != "Other"
]

descriptions = [t["description"] for t in data]
categories = [t["category"] for t in data]

# ------------------------------------------------------------------ #
# TF-IDF vektörleştirme
# ------------------------------------------------------------------ #
vectorizer = TfidfVectorizer(
    lowercase=True,
    ngram_range=(1, 2),  # tek kelime + ikili kelime grupları
    max_features=5000
)
X = vectorizer.fit_transform(descriptions)
y = categories

# ------------------------------------------------------------------ #
# Eğitim / test ayrımı
# ------------------------------------------------------------------ #
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# ------------------------------------------------------------------ #
# Model eğitimi
# ------------------------------------------------------------------ #
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# ------------------------------------------------------------------ #
# Keyword fallback — model düşük güvenle tahmin yaparsa devreye girer
# Özellikle Türkçe mağaza isimleri için kullanılır
# ------------------------------------------------------------------ #
KEYWORD_MAP = {
    "Groceries": [
        "migros", "bim", "a101", "şok", "carrefour", "walmart",
        "grocery store", "bigbazaar", "jiomart", "supermarket"
    ],
    "Food & Dining": [
        "getir", "yemeksepeti", "trendyol yemek",
        "taco bell", "pizza place", "american tavern", "thai restaurant",
        "restaurant", "cafe", "coffee", "burger", "pizza"
    ],
    "Shopping": [
        "trendyol", "hepsiburada", "n11",
        "amazon", "flipkart", "ajio", "mall", "outlet"
    ],
    "Electronics": [
        "teknosa", "mediamarkt", "vatan",
        "best buy", "sony center", "samsung store", "dell exclusive"
    ],
    "Transport": [
        "shell", "uber", "rapido", "tsrtc",
        "taksi", "otobüs", "akbil", "petrol", "fuel"
    ],
    "Travel": [
        "pegasus", "türk hava yolları", "thy",
        "air india", "vistara", "airline", "hotel", "booking"
    ],
    "Bills & Utilities": [
        "turkcell", "türk telekom", "vodafone",
        "elektrik", "doğalgaz", "fatura", "internet",
        "phone company", "city water charges", "gas company"
    ],
    "Entertainment": [
        "netflix", "spotify", "gaana", "aha",
        "sinema", "bluutv", "exxen", "cinema"
    ],
    "Healthcare": [
        "hastane", "eczane", "doktor",
        "medplus", "aster", "cloudnine", "pharmacy", "hospital"
    ],
    "Housing": [
        "kira", "aidat", "konut",
        "mortgage payment", "hardware store", "rent"
    ],
    "Personal Care": [
        "kuaför", "berber", "kozmetik",
        "barbershop", "salon", "spa", "haircut"
    ],
    "Income": [
        "maaş", "gelir",
        "biweekly paycheck", "paycheck", "salary"
    ],
    "Transfers & Payments": [
        "havale", "eft",
        "credit card payment", "transfer"
    ],
}


def keyword_fallback(description: str) -> str:
    """
    Keyword eşleşmesiyle kategori tahmin eder.
    ML modeli düşük güvenle tahmin yaparsa bu fonksiyon devreye girer.
    """
    desc = description.lower().strip()
    # "Transaction at X" formatından mağaza adını soy
    if desc.startswith("transaction at "):
        desc = desc.replace("transaction at ", "")
    for category, keywords in KEYWORD_MAP.items():
        for keyword in keywords:
            if keyword in desc:
                return category
    return "Other"


def predict_category(description: str) -> str:
    """
    Verilen description için kategori tahmin eder.
    1. Önce ML modeli tahmin yapar
    2. Model %50'den düşük güvenle tahmin yaparsa keyword fallback devreye girer
    3. Keyword de bulamazsa Other döner
    """
    vec = vectorizer.transform([description])
    proba = model.predict_proba(vec)[0]
    max_proba = max(proba)
    prediction = model.predict(vec)[0]

    # Güven düşükse keyword fallback dene
    if max_proba < 0.5:
        keyword_result = keyword_fallback(description)
        if keyword_result != "Other":
            return keyword_result

    return prediction


# ------------------------------------------------------------------ #
# Değerlendirme ve sonuçları kaydet
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    accuracy = model.score(X_test, y_test)
    y_pred = model.predict(X_test)

    print(f"Test Doğruluğu: {round(accuracy * 100, 2)}%")
    print("\nDetaylı Rapor:")
    print(classification_report(y_test, y_pred))

    # Sonuçları JSON dosyasına kaydet
    report = classification_report(y_test, y_pred, output_dict=True)
    output = {
        "accuracy": round(accuracy * 100, 2),
        "report": report
    }
    with open("categorization_results.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("Sonuçlar categorization_results.json dosyasına kaydedildi.")