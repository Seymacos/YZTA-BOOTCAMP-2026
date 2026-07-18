# SmartFinance — Dashboard (Kişi 3)

Kişisel Finans & Yatırım Asistanı'nın Streamlit arayüzü.
Kişi 1 (veri), Kişi 2 (kategorilendirme + anomali + piyasa) ve Kişi 4 (AI agent) çıktıları entegre edilmiştir.

## Canlı Demo

[SmartFinance Dashboard](https://RENDER-LINKINI-BURAYA-YAPISTIR.onrender.com)

## Çalıştırma (lokal)

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (Render)

1. Render → New Web Service → GitHub repo bağla
2. Root Directory: `dashboard`
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`

## Sekmeler (Sprint 2)

- **Genel Bakış** — özet kartlar, kategori dağılımı, aylık trend, AI önerileri
- **Anomaliler** — Z-Score / IQR ile olağandışı harcama tespiti, ayarlanabilir eşikler
- **Bütçe** — kategori bazlı önerilen limitler, gerçekleşen ile karşılaştırma, aşım uyarıları
- **Soru Sor** — doğal dil sorgu (agent varsa canlı, yoksa yerel cevap motoru)
- **Piyasa** — canlı döviz, altın, hisse

## Veri kaynakları (data/)

- transactions_sample.json / _merged.json → Kişi 1 (ham işlemler)
- dashboard_data.json → Kişi 2 (kategori özeti)
- market_data.json → Kişi 2 (canlı piyasa)
- ai_advice.json → Kişi 4 (AI agent önerileri)

## Agent entegrasyonu (opsiyonel)

Doğal dil sorgu için ana dizinde `agent/agent_engine.py` bulunmalı ve
`.env` içinde `GEMINI_API_KEY` tanımlı olmalıdır. Agent bulunamazsa
dashboard yerel cevap motoruyla çalışmaya devam eder.

## Kullanıcı dosya yükleme

Kenar çubuğundan "Kendi dosyamı yükle" seçilerek CSV veya JSON yüklenebilir.
Beklenen kolonlar: `date, description, amount, currency, transaction_type, category`
