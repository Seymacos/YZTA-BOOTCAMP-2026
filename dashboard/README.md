# SmartFinance — Dashboard (Kişi 3)

Kişisel Finans & Yatırım Asistanı'nın Streamlit arayüzü.
Kişi 1 (veri), Kişi 2 (kategorilendirme + piyasa) ve Kişi 4 (AI agent) çıktıları entegre edilmiştir.

## 🚀 Canlı Demo

[SmartFinance Dashboard](https://yzta-bootcamp-2026.onrender.com)

## Çalıştırma (lokal)

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (Render)

1. Render'da "New Web Service" → GitHub repo bağlanır.
2. Root Directory: `dashboard`
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
5. Deploy → canlı link hazır.

## Veri dosyaları (data/)

- transactions_sample.json / _merged.json → Kişi 1 (ham işlemler)
- dashboard_data.json → Kişi 2 (kategori özeti + aylık trend)
- market_data.json → Kişi 2 (canlı döviz/altın/hisse)
- ai_advice.json → Kişi 4 (AI agent önerileri)

## Dashboard bölümleri

- Canlı piyasa şeridi (USD/TRY, EUR/TRY, GBP/TRY, altın, THYAO/GARAN/AKBNK)
- Kategori dağılımı + aylık trend grafikleri (Plotly)
- Kategori detay tablosu (yüzdelerle)
- Aylık kategori kırılımı (açılır)
- Akıllı Öneriler (AI agent — Kişi 4 entegre)

## Bilinen not (Sprint 2'ye taşındı)

- Özet tutarlar farklı para birimlerini (USD+INR) birlikte topluyor.
  Para birimi bazında ayrıştırma Sprint 2'de yapılacak.
