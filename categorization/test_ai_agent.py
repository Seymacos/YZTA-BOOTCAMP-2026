"""
test_ai_agent.py — AI Agent Adım Adım Test Dosyası
====================================================
Bu dosya, ai_agent.py içindeki 3 ana fonksiyonu sırasıyla test eder.
"""
import json
from ai_agent import get_currency_aware_summary, build_agent_context, generate_financial_advice_json

# =====================================================================
# ADIM 1: Para Birimi Ayrıştırma Testi (INR / USD)
# =====================================================================
print("=" * 60)
print("ADIM 1: Para Birimi Ayristirma (get_currency_aware_summary)")
print("=" * 60)

result = get_currency_aware_summary()

print(f"Toplam islenen harcama sayisi: {result['total_transactions_analyzed']}")
print(f"Bulunan para birimleri: {list(result['totals'].keys())}")
print()

for curr, total in result["totals"].items():
    if curr == "USD":
        print(f"  {curr} Toplam: ${total:,.2f}")
    else:
        print(f"  {curr} Toplam: {total:,.2f} Rupi")

print()
for curr in result["summary_by_currency"]:
    print(f"--- {curr} En Cok Harcama Yapilan 3 Kategori ---")
    cats = result["summary_by_currency"][curr]
    for i, (cat, data) in enumerate(list(cats.items())[:3]):
        symbol = "$" if curr == "USD" else "₹"
        print(f"  {i+1}. {cat}: {symbol}{data['total']:,.2f} (%{data['percentage']})")
    print()


# =====================================================================
# ADIM 2: Agent Context (Canli Piyasa + Harcama Ozeti)
# =====================================================================
print("=" * 60)
print("ADIM 2: Agent Context Olusturma (build_agent_context)")
print("=" * 60)

context = build_agent_context()
market = context["market_data"]

print(f"Zaman damgasi: {context['timestamp']}")
print(f"Doviz kurlari: {market.get('exchange_rates', {})}")
print(f"Altin fiyati: {market.get('gold', {})}")
print(f"Hisse fiyatlari: {market.get('stocks', {})}")
print()


# =====================================================================
# ADIM 3: Kullanici Harcama Giris Testi (predict_category)
# =====================================================================
print("=" * 60)
print("ADIM 3: Kullanici Harcama Kategori Tahmini")
print("=" * 60)

context2 = build_agent_context("Migros market alisverisi")
custom = context2.get("custom_analysis", {})
print(f"  Girilen: '{custom.get('description')}'")
print(f"  Tahmin edilen kategori: {custom.get('predicted_category')}")
print()

context3 = build_agent_context("Turkcell fatura odemesi")
custom3 = context3.get("custom_analysis", {})
print(f"  Girilen: '{custom3.get('description')}'")
print(f"  Tahmin edilen kategori: {custom3.get('predicted_category')}")
print()

context4 = build_agent_context("Netflix aylik abonelik")
custom4 = context4.get("custom_analysis", {})
print(f"  Girilen: '{custom4.get('description')}'")
print(f"  Tahmin edilen kategori: {custom4.get('predicted_category')}")
print()


# =====================================================================
# ADIM 4: AI Agent Tavsiye Uretimi (generate_financial_advice_json)
# =====================================================================
print("=" * 60)
print("ADIM 4: AI Agent Tavsiye Uretimi (JSON)")
print("=" * 60)

advice_json = generate_financial_advice_json()
advice = json.loads(advice_json)

print(f"Analiz Ozeti: {advice.get('analiz_ozeti', '')}")
print(f"Kur Uyarisi: {advice.get('kur_uyarisi', '')}")
print()
print(f"Toplam {len(advice.get('oneriler', []))} adet oneri uretildi:")
for i, oneri in enumerate(advice.get("oneriler", [])):
    print(f"  {i+1}. [{oneri.get('aksiyon')}] {oneri.get('kategori', oneri.get('category', ''))}")
    print(f"     Durum: {oneri.get('harcama_durumu', '')}")
    print(f"     Tavsiye: {oneri.get('yatirim_tavsiyesi', '')}")
    print()


print("=" * 60)
print("TAMAMLANDI! Tum 4 adim basariyla test edildi.")
print("=" * 60)
