# SmartFinance — Dashboard (Kişi 3)

Kişisel Finans & Yatırım Asistanı'nın Streamlit arayüzü.
Kişi 1 (veri), Kişi 2 (kategorilendirme + piyasa) çıktıları entegre edilmiştir.

## Çalıştırma (lokal)
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy (Streamlit Cloud)
1. Bu klasörü GitHub repo'ya push et.
2. https://share.streamlit.io → GitHub ile giriş.
3. Repo + app.py seç → Deploy → canlı link hazır.

## Veri dosyaları (data/)
- transactions_sample.json / _merged.json → Kişi 1 (ham işlemler)
- dashboard_data.json → Kişi 2 (kategori özeti + aylık trend)
- market_data.json → Kişi 2 (canlı döviz/altın/hisse)
- ai_advice.json → Kişi 4 (AI agent önerileri)

## Dashboard bölümleri
- Canlı piyasa şeridi (USD/TRY, EUR/TRY, GBP/TRY, altın, THYAO/GARAN/AKBNK)
- Kategori dağılımı + aylık trend grafikleri
- Kategori detay tablosu (yüzdelerle)
- Aylık kategori kırılımı (açılır)
- Kişi 4 (AI agent) için hazır bağlantı noktası

## Bilinen not (Sprint 2'ye taşındı)
- Özet tutarlar farklı para birimlerini (USD+INR) birlikte topluyor.
  Para birimi bazında ayrıştırma Sprint 2'de yapılacak (Kişi 2 uyarısı).

## Kişi 4 için
"Akıllı Öneriler" bölümündeki placeholder'ı agent çıktısıyla değiştir.
