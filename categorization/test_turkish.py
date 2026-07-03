"""
test_turkish.py — Türkçe Veri ile Model Testi (Kişi 2)
=======================================================
Modelin Türkçe mağaza isimleri ve açıklamalarla ne kadar iyi çalıştığını test eder.
"""

from categorizer import predict_category

turkish_tests = [
    # (description, beklenen kategori)
    ("Migros", "Groceries"),
    ("BIM", "Groceries"),
    ("Getir", "Food & Dining"),
    ("Yemeksepeti", "Food & Dining"),
    ("Turkcell faturası", "Bills & Utilities"),
    ("Elektrik faturası", "Bills & Utilities"),
    ("Pegasus", "Travel"),
    ("Türk Hava Yolları", "Travel"),
    ("Trendyol", "Shopping"),
    ("Hepsiburada", "Shopping"),
    ("Teknosa", "Electronics"),
    ("MediaMarkt", "Electronics"),
    ("Uber", "Transport"),
    ("Metro", "Transport"),
    ("Netflix", "Entertainment"),
    ("Spotify", "Entertainment"),
]

print("=== Türkçe Veri Testi ===\n")
correct = 0
for desc, expected in turkish_tests:
    predicted = predict_category(desc)
    status = "✓" if predicted == expected else "✗"
    if predicted == expected:
        correct += 1
    print(f"{status} {desc:25} | Beklenen: {expected:20} | Tahmin: {predicted}")

print(f"\nDoğruluk: {correct}/{len(turkish_tests)} ({round(correct/len(turkish_tests)*100, 2)}%)")