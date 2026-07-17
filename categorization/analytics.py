import re
import numpy as np
import pandas as pd
from typing import List, Dict, Any
import yfinance as yf  
from pathlib import Path
from datetime import datetime
import json
# =====================================================================
# ANALİTİK VE BÜTÇE MOTORU 
# =====================================================================


class CurrencyStandardizer:
    """
    1. GÖREV: Canlı Kur Destekli Para Birimi Standardizasyonu
    Yahoo Finance kullanarak USD ve INR kurlarını internetten anlık çeker,
    tüm harcamaları kuruşu kuruşuna güncel TRY karşılığına eşitler.
    """
    def __init__(self, base_currency: str = "TRY"):
        self.base_currency = base_currency
        
        # İnternet kesilirse veya API o an yanıt vermezse kod çökmesin diye 
        # yedek (fallback) kurlarımızı buraya tanımlıyoruz.
        self.exchange_rates = {"TRY": 1.0, "USD": 34.50, "INR": 0.41}
        
        # Sınıf ayağa kalkar kalkmaz canlı kurları internetten çekmesi için fonksiyonu çağırıyoruz
        self._fetch_live_rates()
        
    
    def _fetch_live_rates(self):
            """Yahoo Finance üzerinden USD ve INR (Çapraz Kur) kurlarını çeker."""
            try:
                # USD/TRY kurunu çekiyoruz
                usd_ticker = yf.Ticker("USDTRY=X")
                live_usd = usd_ticker.info.get("regularMarketPreviousClose")
                
                if live_usd:
                    self.exchange_rates["USD"] = float(live_usd)
                    
                # INR/USD çapraz kurunu çekiyoruz (Çünkü INRTRY doğrudan yok)
                inr_usd_ticker = yf.Ticker("INRUSD=X")
                live_inr_usd = inr_usd_ticker.info.get("regularMarketPreviousClose")
                
                if live_inr_usd and live_usd:
                    # 1 Rupi kaç TL eder? (INR/USD * USD/TRY)
                    self.exchange_rates["INR"] = float(live_inr_usd) * self.exchange_rates["USD"]
                    
                print(f"🌍 Canlı Kurlar (Çapraz Hesaplama) -> USD: {self.exchange_rates['USD']:.4f} TRY | INR: {self.exchange_rates['INR']:.4f} TRY")
                
            except Exception as e:
                print(f"⚠️ Canlı kurlar çekilemedi, yedek kurlar kullanılıyor. Hata: {e}")

  
    def detect_currency(self, description: str, amount_str: str, source: str) -> str:
        """Metin içinden para birimini (USD/INR/TRY) tahmin eder."""
        text_to_search = str(description) + str(amount_str)
        
        # 'Rs.' veya 'INR' görürsen bu Hindistan Rupisidir
        if re.search(r"(\$|USD)", text_to_search, re.IGNORECASE): return "USD"
        if re.search(r"(₹|Rs\.|Rs|INR)", text_to_search, re.IGNORECASE): return "INR"
        if re.search(r"(₺|TL|TRY)", text_to_search, re.IGNORECASE): return "TRY"
        
        if "us" in str(source).lower(): return "USD"
        if "india" in str(source).lower(): return "INR"
        return self.base_currency

 
    def clean_amount(self, amount_val, transaction_type: str) -> float:
        """Metindeki para sembollerini (Rs., $, TL) güvenle temizler."""
        if pd.isna(amount_val): return 0.0
        if not isinstance(amount_val, str):
            amount_float = float(amount_val)
        else:
            # 1. Adım: 'Rs.' veya 'Rs' ifadesini ve peşindeki noktayı/boşluğu doğrudan kazıyalım
            cleaned = re.sub(r'(?i)rs\.?\s*', '', amount_val)
            
            # 2. Adım: Diğer bilinen para birimi harflerini ve sembollerini uçuralım
            cleaned = re.sub(r"[a-zA-Z\s\$\u2022\u203A\u20aa\u20a8₹]", "", cleaned)
            
            # 3. Adım: Eğer temizlik sonrası en başta serseri bir nokta kaldıysa onu da silelim
            # (Örn: "Rs.500" -> ".500" kalmasın diye)
            if cleaned.startswith('.'):
                cleaned = cleaned[1:]
                
            if not cleaned: return 0.0
            
            # Nokta virgül karmaşasını çözen standart mantığın:
            if "," in cleaned and "." in cleaned:
                if cleaned.rfind(",") > cleaned.rfind("."):
                    cleaned = cleaned.replace(".", "").replace(",", ".")
                else:
                    cleaned = cleaned.replace(",", "")
            elif "," in cleaned and "." not in cleaned:
                if cleaned.rfind(",") >= len(cleaned) - 3:
                    cleaned = cleaned.replace(",", ".")
                else:
                    cleaned = cleaned.replace(",", "")
            try:
                amount_float = float(cleaned)
            except ValueError:
                amount_float = 0.0

        if "debit" in str(transaction_type).lower() and amount_float > 0:
            amount_float = -amount_float
        return amount_float


    def standardize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """DataFrame'deki tüm satırları canlı kurlarla çarparak standardize eder."""
        result_df = df.copy()
        
        currencies = result_df.apply(
            lambda r: self.detect_currency(r.get("description", ""), r.get("amount", ""), r.get("source", "")), axis=1
        )
        cleaned_amounts = result_df.apply(
            lambda r: self.clean_amount(r.get("amount", 0.0), r.get("transaction_type", "")), axis=1
        )
        
        # Artık buradaki '.get(c)' kodu internetten çektiğimiz en taze kurları kullanıyor!
        rates = currencies.map(lambda c: self.exchange_rates.get(c, 1.0))
        base_rate = self.exchange_rates.get(self.base_currency, 1.0)
        
        result_df["standardized_amount"] = (cleaned_amounts * (rates / base_rate)).round(2)
        return result_df

class TransactionAnomalyDetector:
    """
    2. GÖREV: Anomali Tespiti (Z-Score & IQR)
    Kullanıcının normal harcama limitlerini aşan, şüpheli veya ekstrem büyüklükteki harcamalarını yakalar.
    """
    def __init__(self, z_threshold: float = 3.0, iqr_multiplier: float = 1.5):
        self.z_threshold = z_threshold       # Z-Score için sınır (Ortalamadan 3 standart sapma uzaklık)
        self.iqr_multiplier = iqr_multiplier # IQR için çarpan katsayısı (Genelde standart olarak 1.5 alınır)

    def detect_z_score_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Z-SCORE YÖNTEMİ:
        Harcama tutarlarının ortalamasını ve standart sapmasını hesaplar.
        Ortalamadan çok uzakta kalan (Z-Score > 3) devasa harcamaları ayıklar.
        """
        # Eğer tabloda aradığımız sütun yoksa veya tablo boşsa işlem yapma
        if "standardized_amount" not in df.columns or df.empty:
            return pd.DataFrame()
            
        # Sadece harcamaların büyüklüğüyle ilgilendiğimiz için mutlak değer (.abs()) alıyoruz
        amounts = df["standardized_amount"].abs()
        mean = amounts.mean()          # Harcama ortalaması
        std_dev = amounts.std(ddof=1)  # Harcamaların standart sapması (ddof=1 örneklem istatistiğidir)
        
        # EMNİYET SİBOBU (Öz eleştiri çözümü): Eğer standart sapma 0 ise (tüm harcamalar aynıysa) çökmemek için boş dön
        if std_dev == 0 or pd.isna(std_dev):
            return pd.DataFrame()
            
        # Tüm satırların Z-Skorunu tek seferde hesaplıyoruz: (Değer - Ortalama) / Standart Sapma
        z_scores = (amounts - mean) / std_dev
        
        # Belirlediğimiz eşik değerini aşan satırları filtreliyoruz
        is_anomaly = z_scores.abs() > self.z_threshold
        if not is_anomaly.any():
            return pd.DataFrame() # Anomali yoksa boş tablo dön
            
        # Anomalileri yeni bir tabloya kopyalayıp etiket basıyoruz
        anomalies = df[is_anomaly].copy()
        anomalies["anomaly_type"] = "Z-Score"
        anomalies["z_score"] = z_scores[is_anomaly].round(2)
        return anomalies

    def detect_iqr_anomalies(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        IQR (ÇEYREKLİKLER ARASI MESAFE) YÖNTEMİ:
        Verileri küçükten büyüğe sıralar. %25'lik dilim (Q1) ile %75'lik dilim (Q3) arasındaki farkı bulur.
        Q3 + (1.5 * IQR) formülüyle bir üst sınır çizer ve bu sınırı aşan harcamaları yakalar.
        Veride çok fazla ekstrem uç değer olduğunda Z-Score'a göre çok daha kararlıdır.
        """
        if "standardized_amount" not in df.columns or df.empty:
            return pd.DataFrame()
            
        amounts = df["standardized_amount"].abs()
        
        # Pandas .quantile() fonksiyonu ile çeyreklikleri otomatik hesaplıyoruz
        q1 = amounts.quantile(0.25) # %25'lik sınır
        q3 = amounts.quantile(0.75) # %75'lik sınır
        iqr = q3 - q1               # Çeyreklikler arası mesafe
        
        # Matematiksel üst sınırımızı belirliyoruz
        upper_bound = q3 + (self.iqr_multiplier * iqr)
        
        # Bu üst sınırı aşan harcama satırlarını filtreliyoruz
        is_anomaly = amounts > upper_bound
        if not is_anomaly.any():
            return pd.DataFrame()
            
        anomalies = df[is_anomaly].copy()
        anomalies["anomaly_type"] = "IQR"
        anomalies["upper_bound_limit"] = round(upper_bound, 2)
        return anomalies


class BudgetPlanner:
    """
    3. GÖREV: Bütçe Hedefi Hesaplama Mantığı
    Kullanıcının geçmiş harcamalarını kategorilerine göre gruplar ve gelecek ay için bütçe hedefleri belirler.
    """
    def __init__(self, buffer_percentage: float = 0.10):
        # Önerilen bütçeye eklenecek %10'luk esneklik/güvenlik marjı
        self.buffer_percentage = buffer_percentage

    def calculate_category_budgets(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Pandas .groupby() fonksiyonunu kullanarak harcamaları kategorilerine ve aylara göre 
        özetler, ortalama harcamayı bulur ve üzerine %10 esneklik payı koyarak bütçe önerir.
        """
        if "standardized_amount" not in df.columns or df.empty:
            return pd.DataFrame()
            
        # Sadece harcamaları (0'dan küçük olan eksi tutarları) filtreleyip alıyoruz
        spending_df = df[df["standardized_amount"] < 0].copy()
        spending_df["abs_amount"] = spending_df["standardized_amount"].abs() # Pozitif hale getiriyoruz
        
        # PANDAS GROUPBY: Verileri önce 'category' ve 'month' sütunlarına göre gruplayıp aylık toplam harcamaları buluyoruz
        monthly_grouped = spending_df.groupby(["category", "month"])["abs_amount"].sum().reset_index()
        
        # Bulduğumuz aylık toplamlar üzerinden, her kategorinin kendi ortalamasını ve maksimum harcamasını hesaplıyoruz
        category_summary = monthly_grouped.groupby("category")["abs_amount"].agg(
            average_monthly_spending='mean', # Kategorinin aylık ortalaması
            max_monthly_spending='max',      # Kategoride en çok harcanan ayın tutarı
            tracked_months_count='count'     # Bu kategorinin kaç ay boyunca takip edildiği
        ).reset_index()
        
        # Önerilen Yeni Bütçe = Aylık Ortalama Harcama * 1.10 (%10 Esneklik Eklenmiş Hali)
        category_summary["proposed_budget_target"] = (
            category_summary["average_monthly_spending"] * (1 + self.buffer_percentage)
        ).round(2)
        
        # Tablodaki tüm finansal değerleri daha okunabilir olması için virgülden sonra 2 basamağa yuvarlıyoruz
        category_summary["average_monthly_spending"] = category_summary["average_monthly_spending"].round(2)
        category_summary["max_monthly_spending"] = category_summary["max_monthly_spending"].round(2)
        return category_summary


def save_analytics_to_json(standardized_df, exchange_rates, output_dir="dashboard/data"):
    """
    Kişi 2 (Sen) tarafından üretilen analitik sonuçları, 
    Kişi 3'ün dashboard'da okuyabilmesi için JSON formatında kaydeder.
    """
    data_path = Path(output_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    
    # 1. MARKET DATA YAPISI
    market_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "exchange_rates": {
            "USD/TRY": f"{exchange_rates.get('USD', 0):.2f}",
            "INR/TRY": f"{exchange_rates.get('INR', 0):.4f}", # Rupi hassas olduğu için 4 basamak
            "EUR/TRY": "49.50", # Eğer yfinance'de yoksa mock/varsayılan değer
            "GBP/TRY": "56.20"
        },
        "gold": {"Gold (USD/oz)": "2,350.00"}, # Arayüzün patlamaması için sabit/mock eklemeler
        "stocks": {"THYAO": "310.50", "EREGL": "52.20"}
    }
    
    with open(data_path / "market_data.json", "w", encoding="utf-8") as f:
        json.dump(market_data, f, ensure_ascii=False, indent=2)
        
    # 2. DASHBOARD DATA YAPISI
    # DataFrame'den kategori özetlerini çıkaralım
    by_category = {}
    total_amount = float(abs(standardized_df['standardized_amount'].sum()))
    total_transactions = len(standardized_df)
    
    # Kategori bazlı gruplama
    grouped = standardized_df.groupby('category')
    for cat_name, group in grouped:
        cat_total = float(abs(group['standardized_amount'].sum()))
        cat_count = int(len(group))
        percentage = (cat_total / total_amount * 100) if total_amount > 0 else 0
        
        by_category[cat_name] = {
            "total": cat_total,
            "count": cat_count,
            "percentage": percentage
        }
    
    dashboard_data = {
        "summary": {
            "total_transactions": total_transactions,
            "total_amount": total_amount,
            "by_category": by_category
        },
        "monthly_trends": {
            "2026-07": {cat: info["total"] for cat, info in by_category.items()}
        }
    }
    
    with open(data_path / "dashboard_data.json", "w", encoding="utf-8") as f:
        json.dump(dashboard_data, f, ensure_ascii=False, indent=2)
        
    print("🚀 Kişi 3 için dashboard verileri 'dashboard/data/' klasörüne başarıyla kaydedildi!")

    
# =====================================================================
# ANLIK TEST ETME BLOKU (Geçici)
# =====================================================================
if __name__ == "__main__":
    print("🚀 Analitik motoru test ediliyor...\n")
    
    # 1. Adım: Sahte bir harcama tablosu oluşturuyoruz (Dolar, Rupi ve TL karışık)
    test_verisi = {
        "description": ["Migros Sanal Market", "Amazon US Electronics", "Mumbai Cafe Dinner", "Netflix Subscription"],
        "amount": ["150,00 TL", "$1,200.00", "Rs. 500", "200.00 TRY"],
        "transaction_type": ["debit", "debit", "debit", "debit"],
        "source": ["tr_pdf", "us_xlsx", "india_csv", "tr_pdf"],
        "category": ["Groceries", "Electronics", "Dining", "Entertainment"],
        "month": ["2026-07", "2026-07", "2026-07", "2026-07"]
    }
    df_test = pd.DataFrame(test_verisi)
    print("--- Ham Gelen Veri Tablosu ---")
    print(df_test[["description", "amount"]])
    print("-" * 30)

    # 2. Adım: Para birimi eşitleme motorunu test edelim
    standardizer = CurrencyStandardizer()
    df_standardize = standardizer.standardize_dataframe(df_test)
    print("\n✅ 1. GÖREV BAŞARILI: Para Birimleri TRY'ye Çevrildi:")
    print(df_standardize[["description", "standardized_amount"]])

    # 3. Adım: Anomali (Şüpheli Harcama) motorunu test edelim
    # Amazon harcaması ($1200 = ~41.400 TL) devasa olduğu için IQR bunu yakalamalı!
    detector = TransactionAnomalyDetector()
    anomaliler = detector.detect_iqr_anomalies(df_standardize)
    print("\n⚠️ 2. GÖREV BAŞARILI: Yakalanan Şüpheli Harcamalar (Anomali):")
    if not anomaliler.empty:
        print(anomaliler[["description", "standardized_amount", "anomaly_type"]])
    else:
        print("Anomali bulunamadı.")

    # 4. Adım: Bütçe planlayıcıyı test edelim
    planner = BudgetPlanner()
    butceler = planner.calculate_category_budgets(df_standardize)
    print("\n📊 3. GÖREV BAŞARILI: Kategorilere Göre Önerilen Gelecek Ay Bütçesi:")
    print(butceler)

    # 5. Adım: Sonuçları JSON olarak kaydetme fonksiyonunu çağırıyoruz
    save_analytics_to_json(df_standardize, standardizer.exchange_rates, output_dir="dashboard/data")