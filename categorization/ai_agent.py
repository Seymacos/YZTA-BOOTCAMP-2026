"""
ai_agent.py — AI Agent & Veri Servisleri (Kişi 4)
==================================================
Bu modül, Kişi 2'nin kategorilendirme (categorizer.py) ve canlı piyasa verileri
(market_data.py) modüllerini birleştirerek kullanıcıya kişiselleştirilmiş finansal
ve yatırım tavsiyeleri üreten "AI Agent" zincirini oluşturur.

Özellikler:
    1. Canlı piyasa verilerini (Döviz, Altın, Hisse) market_data.py'den çeker.
    2. Kullanıcı açıklamalarını (description) categorizer.py ile kategorize eder.
    3. DİKKAT (INR/USD Uyarı): Veri setindeki INR ve USD para birimlerini ayrıştırır,
       doğrudan toplayıp hatalı rakamlar oluşmasını engeller.
    4. LangChain / LLM (Gemini/OpenAI veya Akıllı Mock Fallback) ile çalışır.
    5. Streamlit dashboard'unda doğrudan kullanılabilecek TEMİZ JSON formatında dönüş verir.

Kullanım:
    python ai_agent.py
"""

import os
import json
from datetime import datetime
from collections import defaultdict

# Yerel modülleri içe aktar
try:
    from market_data import get_all_market_data
    from categorizer import predict_category
except ImportError:
    # Modüller aynı dizinde değilse yollarını ayarla
    import sys
    sys.path.append(os.path.dirname(__file__))
    from market_data import get_all_market_data
    from categorizer import predict_category


def get_currency_aware_summary(transactions_file: str = "transactions_merged.json") -> dict:
    """
    INR ve USD para birimlerini KARIŞTIRMADAN, her para birimi için ayrı
    kategori bazlı harcama özetleri hesaplar.
    Şeyma'nın bıraktığı INR/USD uyarı notunu çözen analitik fonksiyondur.
    """
    file_path = os.path.join(os.path.dirname(__file__), transactions_file)
    if not os.path.exists(file_path):
        file_path = transactions_file
        
    with open(file_path, "r", encoding="utf-8") as f:
        transactions = json.load(f)

    # Sadece giderleri (debit) al
    expenses = [t for t in transactions if t.get("transaction_type", "debit") == "debit"]

    # Para birimine göre grupla
    summary_by_curr = defaultdict(lambda: defaultdict(lambda: {"count": 0, "total": 0.0}))
    total_by_curr = defaultdict(float)

    for t in expenses:
        curr = t.get("currency", "USD")
        cat = t.get("category") or predict_category(t.get("description", ""))
        amount = float(t.get("amount", 0.0))

        summary_by_curr[curr][cat]["count"] += 1
        summary_by_curr[curr][cat]["total"] += amount
        total_by_curr[curr] += amount

    # Temiz sözlük formatına çevir
    result = {
        "summary_by_currency": {},
        "totals": dict(total_by_curr),
        "total_transactions_analyzed": len(expenses)
    }

    for curr, cats in summary_by_curr.items():
        sorted_cats = sorted(cats.items(), key=lambda x: -x[1]["total"])
        result["summary_by_currency"][curr] = {
            cat: {
                "count": data["count"],
                "total": round(data["total"], 2),
                "percentage": round((data["total"] / total_by_curr[curr]) * 100, 2) if total_by_curr[curr] > 0 else 0
            }
            for cat, data in sorted_cats
        }

    return result


def build_agent_context(user_custom_description: str = None) -> dict:
    """
    LLM/Agent için gerekli tüm bağlamı (Context) toplar:
    - Canlı piyasa verileri
    - Para birimi ayrıştırılmış harcama özeti
    - Opsiyonel: Kullanıcının anlık girdiği yeni bir harcamanın kategorisi
    """
    # 1. Canlı Piyasa Verisi
    try:
        market_data = get_all_market_data()
    except Exception as e:
        # İnternet sorunu vs olursa statik fallback
        market_data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "exchange_rates": {"USD/TRY": 36.20, "EUR/TRY": 38.10, "GBP/TRY": 45.80},
            "gold": {"Gold (USD/oz)": 2850.50},
            "stocks": {"THYAO": 310.25, "GARAN": 120.50, "AKBNK": 65.40},
            "note": "Offline/Cached data fallback used."
        }

    # 2. Harcama Özeti (INR/USD ayrıştırılmış)
    spending_summary = get_currency_aware_summary()

    # 3. Özel Harcama Kategorisi (Eğer kullanıcı arayüzden yeni harcama girdiyse)
    custom_category = None
    if user_custom_description:
        custom_category = predict_category(user_custom_description)

    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "market_data": market_data,
        "spending_summary": spending_summary,
        "custom_analysis": {
            "description": user_custom_description,
            "predicted_category": custom_category
        } if user_custom_description else None
    }


def generate_financial_advice_json(user_custom_description: str = None) -> str:
    """
    AI Agent Ana Zinciri:
    Toplanan context'i alır, bir sistem promptu ile finansal danışman kimliği atar,
    ve Streamlit arayüzünde kullanılabilecek TEMİZ JSON formatında öneriler döndürür.
    
    API anahtarı (GEMINI_API_KEY veya OPENAI_API_KEY) tanımlıysa gerçek LLM kullanır,
    aksi halde arayüzün her zaman çalışmasını sağlayan akıllı sentetik zeka motorunu devreye sokar.
    """
    context = build_agent_context(user_custom_description)
    
    # Gerçek LLM API desteği (LangChain / Google GenAI)
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if api_key:
        try:
            return _call_real_llm_agent(context, api_key)
        except Exception as e:
            print(f"LLM API çağrısında hata/rate-limit oluştu, akıllı sentetik fallback devreye giriyor: {e}")

    # Akıllı Sentetik Zeka Motoru (API Anahtarı yoksa veya hata verirse kesintisiz çalışır)
    return _generate_intelligent_mock_advice(context)


def _call_real_llm_agent(context: dict, api_key: str) -> str:
    """LangChain / OpenAI / Gemini ile gerçek AI çıkarımı yapar."""
    import json
    # Prompt hazırlama
    prompt_text = f"""
    Sen profesyonel ve stratejik bir Kişisel Finans ve Yatırım Danışmanısın.
    Aşağıda kullanıcının harcama verileri (INR ve USD olarak ayrıştırılmış) ve güncel canlı piyasa verileri bulunuyor:
    
    {json.dumps(context, ensure_ascii=False, indent=2)}
    
    GÖREVİN:
    1. Kullanıcının en çok harcama yaptığı kategorileri belirle. DİKKAT: INR (Hindistan Rupisi) ile USD birbirine karıştırılmamalı! (1 USD ~ 86 INR).
    2. Güncel canlı piyasa verilerini (altın, döviz, hisse) dikkate alarak kişiye özel, uygulanabilir ve akıllı yatırım/tasarruf tavsiyeleri ver.
    3. Çıktını SADECE aşağıdaki JSON formatında döndür, başka hiçbir açıklama metni ekleme:
    
    {{
      "analiz_ozeti": "Genel harcama durumu özeti ve INR/USD ayrımı hakkında kısa bilgi...",
      "kur_uyarisi": "Harcamalarda hem USD hem INR para birimi bulunduğu dikkate alınmıştır.",
      "oneriler": [
        {{
          "kategori": "Kategori Adı",
          "harcama_durumu": "Kısa durum tespiti",
          "yatirim_tavsiyesi": "Canlı piyasa verisiyle desteklenmiş net tavsiye...",
          "aksiyon": "Altın Yatırımı / Bütçe Kısma / Hisse Alımı vb."
        }}
      ]
    }}
    """
    
    # Gemini veya OpenAI çağrısı (Basit ve bağımlılıksız HTTP/SDK veya LangChain)
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-pro-latest')
        response = model.generate_content(prompt_text)
        text = response.text.strip()
        # Markdown kod bloğu varsa temizle
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        # JSON geçerliliğini test et
        json.loads(text.strip())
        return text.strip()
    except Exception:
        raise


def _generate_intelligent_mock_advice(context: dict) -> str:
    """
    API anahtarı olmadığında da canlı verileri ve gerçek harcama oranlarını
    kullanarak dinamik ve tamamen kişiselleştirilmiş JSON tavsiyeleri üretir.
    """
    market = context["market_data"]
    spending = context["spending_summary"]["summary_by_currency"]
    
    gold_price = market.get("gold", {}).get("Gold (USD/oz)", "2850.00")
    usd_try = market.get("exchange_rates", {}).get("USD/TRY", "36.20")
    thyao = market.get("stocks", {}).get("THYAO", "310.00")
    garan = market.get("stocks", {}).get("GARAN", "120.00")

    # USD için en yüksek harcama
    top_usd_cat = "Shopping"
    top_usd_amount = 0
    if "USD" in spending and spending["USD"]:
        top_usd_cat = list(spending["USD"].keys())[0]
        top_usd_amount = spending["USD"][top_usd_cat]["total"]

    # INR için en yüksek harcama
    top_inr_cat = "Electronics"
    top_inr_amount = 0
    if "INR" in spending and spending["INR"]:
        top_inr_cat = list(spending["INR"].keys())[0]
        top_inr_amount = spending["INR"][top_inr_cat]["total"]

    custom_text = ""
    if context.get("custom_analysis"):
        c_desc = context["custom_analysis"]["description"]
        c_cat = context["custom_analysis"]["predicted_category"]
        custom_text = f" Son eklediğiniz '{c_desc}' harcaması yapay zeka tarafından '{c_cat}' olarak kategorize edilmiştir."

    response_dict = {
        "analiz_ozeti": f"Yapay zeka analizimiz, harcama verilerinizdeki USD ve INR (Hindistan Rupisi) kaynaklarını başarılı bir şekilde ayrıştırmıştır.{custom_text} USD bazında en çok harcama '{top_usd_cat}' ({top_usd_amount:,.2f} $), INR bazında ise '{top_inr_cat}' ({top_inr_amount:,.2f} ₹) kategorisinde gerçekleşmiştir.",
        "kur_uyarisi": "⚠️ Veri setinde farklı para birimleri tespit edilmiştir. 1 USD ≈ 86 INR kur farkı nedeniyle rakamlar doğrudan toplanmamış, para birimi bazlı analitik ayrıştırma uygulanmıştır.",
        "oneriler": [
            {
                "kategori": f"{top_usd_cat} (Amerikan Doları Harcamaları)",
                "harcama_durumu": f"Aylık toplam {top_usd_amount:,.2f} USD harcama ile bütçenizin en büyük kısmını oluşturuyor.",
                "yatirim_tavsiyesi": f"Bu kategorideki harcamalarınızı %15 optimize ederek elde edeceğiniz dolar bazlı tasarrufu, canlı piyasada ons fiyatı {gold_price} USD olan Altın (GC=F) yatırımında değerlendirerek enflasyona karşı korunabilirsiniz.",
                "aksiyon": "Altın (Gold) Yatırımı"
            },
            {
                "kategori": f"{top_inr_cat} & Teknolojik Alışverişler (INR)",
                "harcama_durumu": f"Toplam {top_inr_amount:,.2f} ₹ tutarında yüksek harcama hacmi tespit edildi.",
                "yatirim_tavsiyesi": f"Rupi bazlı büyük harcamalarınızı daha planlı hale getirip, Türk Lirası varlıklarınızda BIST 30 hisselerine yönelebilirsiniz. Güncel piyasada THYAO ({thyao} TL) ve GARAN ({garan} TL) güçlü birer portföy çeşitlendirme seçeneğidir.",
                "aksiyon": "Hisse Senedi Çeşitlendirmesi"
            },
            {
                "kategori": "Canlı Döviz Kuru Stratejisi",
                "harcama_durumu": f"Güncel Dolar/TL Kuru: {usd_try}",
                "yatirim_tavsiyesi": "Sabit harcamalarınız dışındaki serbest nakit akışınızı kur dalgalanmalarından korumak için likit para piyasası fonlarında veya kısa vadeli döviz mevduatında tutmanız önerilir.",
                "aksiyon": "Nakit & Kur Yönetimi"
            }
        ]
    }

    return json.dumps(response_dict, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    print("=== AI Agent Finansal Danışman Testi ===\n")
    print("1. Standart Analiz Çıktısı:")
    json_output = generate_financial_advice_json()
    print(json_output)
    
    print("\n\n2. Kullanıcı Özel Açıklama Girişi Testi ('Getir den gece siparişi'):")
    custom_output = generate_financial_advice_json("Getir den gece siparişi")
    print(custom_output)
    
    # Sonucu bir dosyaya da yazalım
    output_path = os.path.join(os.path.dirname(__file__), "ai_agent_output.json")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json_output)
    print(f"\nSonuçlar '{output_path}' dosyasına başarıyla kaydedildi.")
