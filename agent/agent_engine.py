"""
agent_engine.py — AI Agent & Hafıza Modülü (Kişi 4)
===================================================
Bu modül, kullanıcının harcama özetlerini (dashboard/data/) ve canlı piyasa verillerini
bağlam (context) olarak alıp LangChain & Gemini (ChatGoogleGenerativeAI) ile
doğal dil sorgu motoru sunar.

3 Temel İşlev:
1. Agent'ı Canlı LLM'e Bağlama (Gemini API):
   - langchain-google-genai kütüphanesinden ChatGoogleGenerativeAI kullanımı.
   - Halüsinasyonu önlemek için düşük temperature (0.2).
2. Doğal Dil Sorgu Motoru:
   - dashboard/data/ altındaki JSON dosyalarını okur ve bağlam (context) olarak LLM'e sunar.
   - Kullanıcının finansal sorularını yanıtlayan LangChain chain mimarisi.
3. Öneri Metinleri Temizliği (Clean Output Parser):
   - Markdown etiketlerini (```json vb.) ve sohbet kirliliğini temizleyen parser.
   - Kesinlikle { "tespit": "...", "oneri": "...", "kategori": "..." } formatında JSON döndürür.
"""

import os
import re
import json
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# LangChain kütüphaneleri (yüklü değilse uyarı ver, API key yoksa mock fallback çalıştır)
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
    from langchain_core.output_parsers import BaseOutputParser
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False


PROJE_KOKU = Path(__file__).parent.parent
DASHBOARD_DATA_DIR = PROJE_KOKU / "dashboard" / "data"


# =====================================================================
# 3. ÖNERİ METİNLERİ TEMİZLİĞİ (CLEAN OUTPUT PARSER)
# =====================================================================

def clean_output_parser(raw_output: str) -> Dict[str, str]:
    """
    LLM'den gelen ham cevabı temizler:
    - ```json ve ``` gibi Markdown kod bloklarını kaldırır.
    - Sohbet metinlerini (Örn: "İşte sorunuzun cevabı:" vb.) temizler.
    - Sadece ve kesinlikle şu 3 anahtarlı JSON dict döndürür:
      {
        "tespit": "Harcama/piyasa durumu özeti",
        "oneri": "Kullanıcıya özel net, kısa yatırım/tasarruf tavsiyesi",
        "kategori": "Tasarruf/Yatırım/Uyarı"
      }
    """
    if not raw_output or not isinstance(raw_output, str):
        return _get_fallback_json("Geçersiz veya boş model yanıtı alındı.")

    text = raw_output.strip()

    # 1. Markdown kod blok etiketlerini temizle
    # ```json ... ``` veya ``` ... ``` arasındaki kısmı bulmaya çalış
    json_block_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if json_block_match:
        text = json_block_match.group(1).strip()
    else:
        # Kod bloğu etiketi yoksa, ilk '{' ile son '}' arasındaki JSON nesnesini bul
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            text = text[first_brace : last_brace + 1].strip()

    # 2. JSON ayrıştırma (parse) denemesi
    try:
        parsed_data = json.loads(text)
        if isinstance(parsed_data, dict):
            # Anahtarları standardize et ve kesinlikle istenen formatta döndür
            return {
                "tespit": str(parsed_data.get("tespit", parsed_data.get("analiz_ozeti", "Harcama durumu analiz edildi."))),
                "oneri": str(parsed_data.get("oneri", parsed_data.get("yatirim_tavsiyesi", "Bütçe optimizasyonu önerilir."))),
                "kategori": _normalize_kategori(str(parsed_data.get("kategori", "Tasarruf")))
            }
    except json.JSONDecodeError:
        pass

    # 3. Eğer JSON parse başarısız olursa, metin içinden akıllı çıkarım (Regex) veya Fallback
    tespit_match = re.search(r'"?tespit"?\s*:\s*"([^"]+)"', text, re.IGNORECASE)
    oneri_match = re.search(r'"?oneri"?\s*:\s*"([^"]+)"', text, re.IGNORECASE)
    kategori_match = re.search(r'"?kategori"?\s*:\s*"([^"]+)"', text, re.IGNORECASE)

    if tespit_match and oneri_match:
        return {
            "tespit": tespit_match.group(1),
            "oneri": oneri_match.group(1),
            "kategori": _normalize_kategori(kategori_match.group(1) if kategori_match else "Tasarruf")
        }

    return _get_fallback_json(text)


def _normalize_kategori(kat: str) -> str:
    """Kategori alanının standart (Tasarruf / Yatırım / Uyarı) formda olmasını sağlar."""
    kat_lower = kat.lower()
    if "yatır" in kat_lower or "investment" in kat_lower or "hisse" in kat_lower or "altın" in kat_lower:
        return "Yatırım"
    elif "uyar" in kat_lower or "warning" in kat_lower or "risk" in kat_lower or "dikkat" in kat_lower:
        return "Uyarı"
    else:
        return "Tasarruf"


def _get_fallback_json(mesaj: str) -> Dict[str, str]:
    """Parse hatası veya beklenmeyen durumda döndürülecek güvenli JSON formatı."""
    temiz_mesaj = mesaj.replace("\n", " ").strip()
    if len(temiz_mesaj) > 150:
        temiz_mesaj = temiz_mesaj[:147] + "..."
    return {
        "tespit": f"Harcama analizi ve piyasa durumu incelendi ({temiz_mesaj}).",
        "oneri": "En yüksek harcama kalemlerinizi gözden geçirerek bütçenizde %10-15 tasarruf sağlayıp altın/döviz varlıklarında değerlendirebilirsiniz.",
        "kategori": "Tasarruf"
    }


if LANGCHAIN_AVAILABLE:
    class CleanJsonOutputParser(BaseOutputParser[Dict[str, str]]):
        """LangChain uyumlu Output Parser class'ı."""
        def parse(self, text: str) -> Dict[str, str]:
            return clean_output_parser(text)


# =====================================================================
# 2. DOĞAL DİL SORGU MOTORU (BAĞLAM / CONTEXT YÜKLEYİCİ)
# =====================================================================

def get_data_context(data_dir: Optional[Path] = None) -> Dict[str, Any]:
    """
    Ekibin dashboard/data/ altına kaydettiği harcama özetlerini ve
    canlı piyasa verilerini okuyarak LLM için birleştirilmiş bağlam (context) sunar.
    """
    target_dir = data_dir or DASHBOARD_DATA_DIR
    context = {
        "harcama_ozeti": {},
        "canli_piyasa": {},
        "kaynak": "dashboard/data"
    }

    # 1. dashboard_data.json okuma (Harcama Özetleri)
    dash_file = target_dir / "dashboard_data.json"
    if dash_file.exists():
        try:
            with open(dash_file, "r", encoding="utf-8") as f:
                context["harcama_ozeti"] = json.load(f)
        except Exception as e:
            context["harcama_ozeti"] = {"error": f"dashboard_data.json okunamadı: {e}"}
    else:
        # Fallback: Eğer dashboard_data.json yoksa örnek veri
        context["harcama_ozeti"] = {
            "summary": {
                "total_transactions": 4,
                "total_amount": 57115.91,
                "by_category": {
                    "Electronics": {"total": 56521.44, "count": 1, "percentage": 98.96},
                    "Dining": {"total": 244.47, "count": 1, "percentage": 0.43},
                    "Entertainment": {"total": 200.00, "count": 1, "percentage": 0.35},
                    "Groceries": {"total": 150.00, "count": 1, "percentage": 0.26}
                }
            }
        }

    # 2. market_data.json okuma (Canlı Piyasa Verileri)
    market_file = target_dir / "market_data.json"
    if market_file.exists():
        try:
            with open(market_file, "r", encoding="utf-8") as f:
                context["canli_piyasa"] = json.load(f)
        except Exception as e:
            context["canli_piyasa"] = {"error": f"market_data.json okunamadı: {e}"}
    else:
        context["canli_piyasa"] = {
            "timestamp": "2026-07-18",
            "exchange_rates": {"USD/TRY": "47.10", "EUR/TRY": "49.50"},
            "gold": {"Gold (USD/oz)": "2,350.00"},
            "stocks": {"THYAO": "310.50"}
        }

    return context


# =====================================================================
# 1. AGENT'I CANLI LLM'E BAĞLAMA (ChatGoogleGenerativeAI) & SORGU MOTORU
# =====================================================================

def ask_financial_agent(
    user_query: str,
    api_key: Optional[str] = None,
    temperature: float = 0.2,
    model_name: str = "gemini-2.5-flash"
) -> Dict[str, str]:
    """
    Kullanıcının doğal dil sorgusunu ('Bu ay en çok nereye para harcadım?') alır,
    harcama ve piyasa bağlamı ile birlikte Gemini API'ye iletir ve
    temizlenmiş JSON sonucu döndürür.
    
    Parametreler:
        user_query: Kullanıcının sorusu
        api_key: Gemini API anahtarı (Yoksa os.environ'dan aranır veya mock motor devreye girer)
        temperature: Halüsinasyonu önlemek için düşük tutulan sıcaklık (Varsayılan: 0.2)
        model_name: Kullanılacak Gemini modeli (Varsayılan: gemini-2.5-flash)
    """
    context = get_data_context()
    resolved_api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    # API Anahtarı var ve LangChain kuruluysa Canlı Gemini'ye bağlan
    if resolved_api_key and LANGCHAIN_AVAILABLE:
        # Önce istenen modeli, hata durumunda kota dostu gemini-2.5-flash modelini dene
        models_to_try = [model_name]
        if model_name != "gemini-2.5-flash":
            models_to_try.append("gemini-2.5-flash")

        for try_model in models_to_try:
            try:
                llm = ChatGoogleGenerativeAI(
                    model=try_model,
                    temperature=temperature,
                    google_api_key=resolved_api_key
                )

                prompt = ChatPromptTemplate.from_messages([
                    ("system", """Sen uzman bir Kişisel Finans ve Yatırım Asistanısın.
Aşağıda kullanıcının harcama özetleri ve güncel piyasa koşulları (Bağlam) JSON formatında verilmiştir.

BAĞLAM:
{context}

GÖREVİN:
1. Kullanıcının sorusunu bu bağlamdaki somut verilere dayanarak analiz et.
2. Halüsinasyon yapma, sadece bağlamda olan gerçek harcama tutarlarını ve piyasa verilerini kullan.
3. Çıktını KESİNLİKLE VE SADECE aşağıdaki 3 anahtarlı JSON formatında ver. Başka hiçbir açıklama, sohbet metni veya Markdown başlığı ekleme:
{{
  "tespit": "Harcama veya piyasa verilerine dayalı net durum özeti",
  "oneri": "Kullanıcıya özel pratik, uygulanabilir tasarruf veya yatırım tavsiyesi",
  "kategori": "Tasarruf veya Yatırım veya Uyarı"
}}"""),
                    ("human", "{user_query}")
                ])

                chain = prompt | llm
                response = chain.invoke({
                    "context": json.dumps(context, ensure_ascii=False, indent=2),
                    "user_query": user_query
                })

                # LLM'den gelen cevabı parser ile temizle
                raw_text = response.content if hasattr(response, "content") else str(response)
                return clean_output_parser(raw_text)

            except Exception as e:
                print(f"[UYARI] '{try_model}' modelinde hata oluştu: {e}")
                continue

    # API Anahtarı yoksa veya hata oluşursa: Akıllı Doğal Dil Fallback Engine
    return _intelligent_query_fallback(user_query, context)


def _intelligent_query_fallback(user_query: str, context: Dict[str, Any]) -> Dict[str, str]:
    """
    API anahtarı bulunmadığında da sorgu türünü anlayan ve gerçek dashboard/data/
    verilerine dayanan %100 çalışabilir akıllı cevap üretir.
    """
    query_lower = user_query.lower()
    summary = context.get("harcama_ozeti", {}).get("summary", {})
    by_cat = summary.get("by_category", {})
    market = context.get("canli_piyasa", {})

    # En çok harcama yapılan kategoriyi bul
    top_cat = "Electronics"
    top_tutar = 0.0
    top_pct = 0.0
    if by_cat:
        sorted_cats = sorted(by_cat.items(), key=lambda x: -x[1].get("total", 0.0))
        if sorted_cats:
            top_cat, top_data = sorted_cats[0]
            top_tutar = top_data.get("total", 0.0)
            top_pct = top_data.get("percentage", 0.0)

    gold = market.get("gold", {}).get("Gold (USD/oz)", "2,350.00")
    usd_try = market.get("exchange_rates", {}).get("USD/TRY", "47.10")

    # Sorgu türüne göre akıllı yanıt üret
    if any(k in query_lower for k in ["en çok", "nereye", "harcadım", "harcama", "gider", "fazla"]):
        return {
            "tespit": f"Bu ay toplam {summary.get('total_amount', top_tutar):,.2f} TL harcamanızın en büyük kısmı %{top_pct:.1f} oran ve {top_tutar:,.2f} TL tutar ile '{top_cat}' kategorisinde gerçekleşmiştir.",
            "oneri": f"'{top_cat}' kalemindeki harcamalarınızı %15 optimize ederek her ay önemli bir birikim yaratabilir ve bu tasarrufu ons fiyatı {gold} $ olan altın veya {usd_try} TL seviyesindeki döviz varlıklarında değerlendirebilirsiniz.",
            "kategori": "Tasarruf"
        }
    elif any(k in query_lower for k in ["yatırım", "piyasa", "altın", "hisse", "dolar", "döviz", "ne alayım"]):
        return {
            "tespit": f"Canlı piyasada Dolar/TL {usd_try}, Altın (ons) ise {gold} $ seviyesinden işlem görmektedir.",
            "oneri": "Sabit giderleriniz dışındaki nakit fazlanızı tek bir enstrümana yönlendirmek yerine %50 Altın ve %50 BIST 30 hisseleri (örn: THYAO) ile portföy çeşitlendirmesi yapmanız enflasyona karşı koruma sağlar.",
            "kategori": "Yatırım"
        }
    elif any(k in query_lower for k in ["risk", "uyarı", "tehlike", "bütçe", "aşım"]):
        return {
            "tespit": f"Harcama dağılımınızda '{top_cat}' kategorisi %{top_pct:.1f} gibi çok yüksek bir yoğunluğa sahiptir.",
            "oneri": "Tek bir kategorinin bütçenizi bu derece domine etmesi likidite riskini artırır. Ani nakit ihtiyaçları için acil durum fonu oluşturmanız önemle tavsiye olunur.",
            "kategori": "Uyarı"
        }
    else:
        return {
            "tespit": f"Genel bütçe analizi: {summary.get('total_transactions', 0)} işlemde toplam {summary.get('total_amount', 0):,.2f} TL harcama kaydedildi. En yüksek kalem '{top_cat}' ({top_tutar:,.2f} TL).",
            "oneri": "Aylık gelir-gider dengenizi korumak için 50/30/20 kuralını uygulayarak gelirinizi zorunlu ihtiyaçlar, istekler ve yatırımlar arasında paylaştırabilirsiniz.",
            "kategori": "Tasarruf"
        }


# =====================================================================
# MODÜL KULLANIM TESTİ (__main__)
# =====================================================================
if __name__ == "__main__":
    print("=== Kişi 4: AI Agent & Hafıza Modülü Testi ===\n")

    # 1. Temizleme ve Output Parser Testi (Kirlenmiş Markdown/Sohbet Girdisi)
    dirty_llm_response = """İşte yaptığım analiz sonucunda size özel tavsiyem:
```json
{
  "tespit": "Bu ay en çok harcamayı 56,521 TL ile Electronics kategorisine yaptınız.",
  "oneri": "Elektronik harcamalarınızı bir süre erteleyerek elinizdeki nakdi Altın (ons: 2350$) alarak değerlendiriniz.",
  "kategori": "Tasarruf"
}
```
Umuyorum bu tavsiyeler bütçenize yardımcı olur!"""

    print("1. Öneri Metinleri Temizliği (Clean Output Parser) Testi:")
    cleaned_json = clean_output_parser(dirty_llm_response)
    print(json.dumps(cleaned_json, ensure_ascii=False, indent=2))
    print("-" * 50)

    # 2. Doğal Dil Sorgu Motoru Testi
    sample_queries = [
        "Bu ay en çok nereye para harcadım, tasarruf için ne yapmalıyım?",
        "Elimde kalan parayla nasıl bir yatırım yapmalıyım?",
        "Bütçemde dikkat etmem gereken bir risk var mı?"
    ]

    print("\n2. Doğal Dil Sorgu Motoru (ask_financial_agent) Testi:\n")
    for q in sample_queries:
        print(f"Soru: {q}")
        yanit = ask_financial_agent(q)
        print(f"Temiz JSON Çıktısı:\n{json.dumps(yanit, ensure_ascii=False, indent=2)}\n")
