"""
dashboard_output.py — Dashboard Formatında Çıktı (Kişi 2)
==========================================================
Kategorilendirme sonuçlarını Kişi 3'ün Streamlit dashboard'u için
hazır JSON formatında üretir.

Kullanım:
    python dashboard_output.py
"""

import json
from collections import defaultdict
from categorizer import predict_category

# Veriyi yükle
with open("transactions_merged.json", encoding="utf-8") as f:
    transactions = json.load(f)

# Sadece gider işlemleri
expenses = [t for t in transactions if t["transaction_type"] == "debit"]


def build_summary(transactions: list[dict]) -> dict:
    """Kategori bazlı özet istatistikler üretir."""
    by_category = defaultdict(lambda: {"count": 0, "total": 0.0})
    total_amount = 0.0

    for t in transactions:
        cat = t.get("category", predict_category(t["description"]))
        by_category[cat]["count"] += 1
        by_category[cat]["total"] += t["amount"]
        total_amount += t["amount"]

    return {
        "total_transactions": len(transactions),
        "total_amount": round(total_amount, 2),
        "by_category": {
            k: {
                "count": v["count"],
                "total": round(v["total"], 2),
                "percentage": round(v["total"] / total_amount * 100, 2)
            }
            for k, v in sorted(by_category.items(), key=lambda x: -x[1]["total"])
        }
    }


def build_monthly_trends(transactions: list[dict]) -> dict:
    """Aylık kategori bazlı harcama trendlerini üretir."""
    monthly = defaultdict(lambda: defaultdict(float))

    for t in transactions:
        month = t.get("month", t["date"][:7])
        cat = t.get("category", predict_category(t["description"]))
        monthly[month][cat] += t["amount"]

    return {
        month: {cat: round(amount, 2) for cat, amount in cats.items()}
        for month, cats in sorted(monthly.items())
    }


def build_dashboard_output() -> dict:
    """Tüm dashboard verilerini birleştirir."""
    return {
        "summary": build_summary(expenses),
        "monthly_trends": build_monthly_trends(expenses),
        "market_data_file": "market_data_output.json"
    }


if __name__ == "__main__":
    print("Dashboard verisi hazırlanıyor...")
    output = build_dashboard_output()

    with open("dashboard_output.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Toplam işlem: {output['summary']['total_transactions']}")
    print(f"Toplam tutar: {output['summary']['total_amount']}")
    print("\nKategori dağılımı:")
    for cat, data in output['summary']['by_category'].items():
        print(f"  {cat:25} | {data['count']:5} işlem | %{data['percentage']}")

    print("\nDashboard verisi dashboard_output.json dosyasına kaydedildi.")