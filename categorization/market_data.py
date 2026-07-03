"""
market_data.py — Canlı Piyasa Verisi (Kişi 2)
==============================================
yfinance kütüphanesi ile canlı döviz, altın ve hisse verisi çeker.
Kişi 4'ün AI agent'ı bu veriyi kullanarak yatırım önerileri üretir.

Kullanım:
    python market_data.py
"""

import yfinance as yf
import json
from datetime import datetime


def get_exchange_rates() -> dict:
    """
    Canlı döviz kurlarını çeker.
    USD/TRY, EUR/TRY, GBP/TRY
    """
    tickers = {
        "USD/TRY": "USDTRY=X",
        "EUR/TRY": "EURTRY=X",
        "GBP/TRY": "GBPTRY=X",
    }
    rates = {}
    for name, ticker in tickers.items():
        data = yf.Ticker(ticker)
        price = data.fast_info.last_price
        rates[name] = round(price, 2) if price else None
    return rates


def get_gold_price() -> dict:
    """
    Canlı altın fiyatını çeker (USD/ons).
    """
    gold = yf.Ticker("GC=F")
    price = gold.fast_info.last_price
    return {
        "Gold (USD/oz)": round(price, 2) if price else None
    }


def get_stock_prices() -> dict:
    """
    Türk hisselerinin canlı fiyatlarını çeker.
    """
    tickers = {
        "THYAO": "THYAO.IS",
        "GARAN": "GARAN.IS",
        "AKBNK": "AKBNK.IS",
    }
    stocks = {}
    for name, ticker in tickers.items():
        data = yf.Ticker(ticker)
        price = data.fast_info.last_price
        stocks[name] = round(price, 2) if price else None
    return stocks


def get_all_market_data() -> dict:
    """
    Tüm piyasa verilerini birleştirir ve döner.
    """
    return {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "exchange_rates": get_exchange_rates(),
        "gold": get_gold_price(),
        "stocks": get_stock_prices(),
    }


if __name__ == "__main__":
    print("Piyasa verileri çekiliyor...")
    data = get_all_market_data()
    print(json.dumps(data, ensure_ascii=False, indent=2))

    # Sonuçları dosyaya kaydet
    with open("market_data_output.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("\nSonuçlar market_data_output.json dosyasına kaydedildi.")