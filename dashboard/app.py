"""
SmartFinance — Kişisel Finans & Yatırım Asistanı
Dashboard (Kişi 3 — Sprint 1)

Veri kaynakları:
  - data/transactions_sample.json  → Kişi 1 (ham işlemler)
  - data/dashboard_data.json       → Kişi 2 (kategori özeti + aylık trend)
  - data/market_data.json          → Kişi 2 (canlı döviz/altın/hisse)
"""

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="SmartFinance", page_icon="◆", layout="wide")

DATA_DIR = Path(__file__).parent / "data"

# ----------------------------------------------------------------------
# TASARIM — renk paleti (finans / güven teması)
# ----------------------------------------------------------------------
# Derin lacivert (güven) + zümrüt yeşil (gelir/pozitif) + mercan (gider/dikkat)
INK = "#0F2A43"        # koyu lacivert — ana metin/başlık
EMERALD = "#0F9D8C"    # zümrüt — gelir, pozitif
CORAL = "#E5674E"      # mercan — gider, dikkat
GOLD = "#D4A24E"       # altın — piyasa vurgusu
SLATE = "#5B7085"      # kül mavi — ikincil metin
MIST = "#EEF3F7"       # açık zemin

# Kategori paleti (tutarlı, sıcak-soğuk dengeli)
CAT_PALETTE = [
    "#0F9D8C", "#2E86AB", "#E5674E", "#D4A24E", "#7B6CA8",
    "#4FB286", "#E89B4C", "#5B7085", "#C0556F", "#3D8DAE",
    "#8AB17D", "#A4666F",
]

st.markdown(f"""
<style>
    .main .block-container {{ padding-top: 2rem; max-width: 1300px; }}
    h1, h2, h3 {{ color: {INK}; font-weight: 700; letter-spacing: -0.02em; }}
    [data-testid="stMetricValue"] {{ color: {INK}; font-weight: 700; }}
    [data-testid="stMetricLabel"] {{ color: {SLATE}; }}
    .brand {{
        font-size: 2.2rem; font-weight: 800; color: {INK};
        letter-spacing: -0.03em; margin-bottom: 0;
    }}
    .brand-accent {{ color: {EMERALD}; }}
    .tagline {{ color: {SLATE}; font-size: 0.95rem; margin-top: 0.2rem; }}
    .insight-card {{
        background: {MIST}; border-left: 4px solid {EMERALD};
        padding: 0.9rem 1.1rem; border-radius: 6px; margin-bottom: 0.6rem;
        color: {INK}; font-size: 0.95rem;
    }}
    .insight-warn {{ border-left-color: {CORAL}; }}
    .insight-gold {{ border-left-color: {GOLD}; }}
    .advice-card {{
        background: white; border: 1px solid #E3EAF0; border-top: 3px solid {EMERALD};
        border-radius: 8px; padding: 1rem 1.1rem; height: 100%;
        box-shadow: 0 1px 3px rgba(15,42,67,0.05);
    }}
    .advice-action {{
        display: inline-block; background: {EMERALD}; color: white;
        font-size: 0.72rem; font-weight: 700; padding: 0.2rem 0.6rem;
        border-radius: 12px; margin-bottom: 0.6rem;
    }}
    .advice-cat {{ font-weight: 700; color: {INK}; font-size: 0.95rem; margin-bottom: 0.4rem; }}
    .advice-status {{ color: {SLATE}; font-size: 0.82rem; margin-bottom: 0.5rem; }}
    .advice-tip {{ color: {INK}; font-size: 0.85rem; line-height: 1.45; }}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_json(name: str):
    path = DATA_DIR / name
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_transactions(name: str) -> pd.DataFrame:
    records = load_json(name)
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    return df


def fmt(n):
    """Büyük sayıları okunaklı kısalt (1.2M, 340K)."""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return "—"
    if abs(n) >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"{n/1_000:.0f}K"
    return f"{n:,.0f}"


# ----------------------------------------------------------------------
# BAŞLIK
# ----------------------------------------------------------------------
st.markdown(
    '<div class="brand">Smart<span class="brand-accent">Finance</span></div>'
    '<div class="tagline">Harcamalarını anla, piyasayı takip et, ne yapman gerektiğini gör.</div>',
    unsafe_allow_html=True,
)
st.write("")

market = load_json("market_data.json")
dash = load_json("dashboard_data.json")

# ----------------------------------------------------------------------
# SEKMELER
# ----------------------------------------------------------------------
tab_ozet, tab_kategori, tab_piyasa = st.tabs(["  Genel Bakış  ", "  Kategoriler  ", "  Piyasa  "])

# ======================================================================
# TAB 1 — GENEL BAKIŞ
# ======================================================================
with tab_ozet:
    if dash:
        summary = dash["summary"]
        by_cat = summary["by_category"]
        cat_df = pd.DataFrame([
            {"Kategori": k, "Tutar": v["total"], "İşlem": v["count"], "Yüzde": v["percentage"]}
            for k, v in by_cat.items()
        ]).sort_values("Tutar", ascending=False)

        # --- Özet kartları ---
        k1, k2, k3 = st.columns(3)
        k1.metric("Toplam İşlem", f"{summary['total_transactions']:,}")
        k2.metric("Toplam Harcama", fmt(summary["total_amount"]))
        k3.metric("Kategori Sayısı", len(by_cat))

        # --- Otomatik içgörüler (kural tabanlı) ---
        st.markdown("#### Öne çıkanlar")
        top_cat = cat_df.iloc[0]
        top3_share = cat_df.head(3)["Yüzde"].sum()

        st.markdown(
            f'<div class="insight-card">En yüksek harcama kategorin '
            f'<b>{top_cat["Kategori"]}</b> — toplam harcamanın '
            f'<b>%{top_cat["Yüzde"]:.0f}</b>\'i ({top_cat["İşlem"]} işlem).</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div class="insight-card insight-gold">En büyük 3 kategori '
            f'(<b>{", ".join(cat_df.head(3)["Kategori"])}</b>) '
            f'harcamanın <b>%{top3_share:.0f}</b>\'ini oluşturuyor.</div>',
            unsafe_allow_html=True,
        )
        if top_cat["Yüzde"] > 40:
            st.markdown(
                f'<div class="insight-card insight-warn">⚠️ Harcamanın çok büyük kısmı tek '
                f'kategoride toplanmış ({top_cat["Kategori"]}). Bu kategoriyi gözden geçirmek '
                f'bütçende en hızlı etkiyi yaratır.</div>',
                unsafe_allow_html=True,
            )

        st.write("")
        c_left, c_right = st.columns([1, 1])

        # --- Donut: kategori dağılımı ---
        with c_left:
            st.markdown("##### Harcama Dağılımı")
            fig = go.Figure(data=[go.Pie(
                labels=cat_df["Kategori"], values=cat_df["Tutar"],
                hole=0.55, marker=dict(colors=CAT_PALETTE),
                textinfo="percent", textposition="inside",
                hovertemplate="<b>%{label}</b><br>%{percent}<extra></extra>",
            )])
            fig.update_layout(
                showlegend=True, height=340, margin=dict(t=10, b=10, l=10, r=10),
                legend=dict(font=dict(size=10), orientation="v", x=1, y=0.5),
                annotations=[dict(text="Gider", x=0.5, y=0.5, font_size=16, showarrow=False, font_color=INK)],
            )
            st.plotly_chart(fig, use_container_width=True)

        # --- Aylık trend ---
        with c_right:
            st.markdown("##### Aylık Harcama Trendi")
            monthly = dash["monthly_trends"]
            mt = {m: sum(c.values()) for m, c in sorted(monthly.items())}
            trend_df = pd.DataFrame({"Ay": list(mt.keys()), "Toplam": list(mt.values())})
            fig2 = px.area(trend_df, x="Ay", y="Toplam")
            fig2.update_traces(line_color=EMERALD, fillcolor="rgba(15,157,140,0.12)")
            fig2.update_layout(
                height=340, margin=dict(t=10, b=10, l=10, r=10),
                xaxis_title=None, yaxis_title=None, plot_bgcolor="white",
            )
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning("Kişi 2'nin dashboard_data.json dosyası data/ klasöründe bulunamadı.")

# ======================================================================
# TAB 2 — KATEGORİLER
# ======================================================================
with tab_kategori:
    if dash:
        st.markdown("#### Kategori Bazlı Harcama")
        st.caption("Otomatik kategorilendirme — model doğruluğu %99.66 (Kişi 2)")

        # Yatay bar (okunması kolay)
        bar_df = cat_df.sort_values("Tutar", ascending=True)
        fig3 = go.Figure(go.Bar(
            x=bar_df["Tutar"], y=bar_df["Kategori"], orientation="h",
            marker_color=EMERALD,
            hovertemplate="<b>%{y}</b><br>Tutar: %{x:,.0f}<extra></extra>",
        ))
        fig3.update_layout(
            height=420, margin=dict(t=10, b=10, l=10, r=10),
            xaxis_title=None, yaxis_title=None, plot_bgcolor="white",
        )
        st.plotly_chart(fig3, use_container_width=True)

        # Detay tablo
        st.markdown("##### Detay")
        show = cat_df.copy()
        show["Tutar"] = show["Tutar"].map(lambda x: f"{x:,.0f}")
        show["Yüzde"] = show["Yüzde"].map(lambda x: f"%{x:.2f}")
        st.dataframe(show, use_container_width=True, hide_index=True)

        # Aylık kırılım
        with st.expander("Belirli bir ayın dağılımını gör"):
            months = sorted(dash["monthly_trends"].keys())
            sel = st.selectbox("Ay", months, index=len(months) - 1)
            md = dash["monthly_trends"][sel]
            mdf = pd.DataFrame(
                [{"Kategori": k, "Tutar": v} for k, v in sorted(md.items(), key=lambda x: -x[1])]
            )
            figm = px.bar(mdf, x="Kategori", y="Tutar", color="Kategori",
                          color_discrete_sequence=CAT_PALETTE)
            figm.update_layout(height=320, showlegend=False, xaxis_title=None,
                               yaxis_title=None, plot_bgcolor="white",
                               margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(figm, use_container_width=True)
    else:
        st.warning("Kategori verisi bulunamadı.")

# ======================================================================
# TAB 3 — PİYASA
# ======================================================================
with tab_piyasa:
    if market:
        st.markdown("#### Canlı Piyasa")
        st.caption(f"Son güncelleme: {market.get('timestamp', '—')}")

        st.markdown("##### Döviz & Altın")
        m = st.columns(4)
        rates = market.get("exchange_rates", {})
        m[0].metric("USD/TRY", rates.get("USD/TRY", "—"))
        m[1].metric("EUR/TRY", rates.get("EUR/TRY", "—"))
        m[2].metric("GBP/TRY", rates.get("GBP/TRY", "—"))
        m[3].metric("Altın (USD/ons)", market.get("gold", {}).get("Gold (USD/oz)", "—"))

        st.markdown("##### BIST Hisseleri")
        stocks = market.get("stocks", {})
        s = st.columns(len(stocks) if stocks else 1)
        for i, (name, price) in enumerate(stocks.items()):
            s[i].metric(name, price)

        st.info("Yatırımcı modu (portföy analizi, sektör uyarıları) Sprint 3'te eklenecek.")
    else:
        st.warning("Piyasa verisi bulunamadı.")

# ----------------------------------------------------------------------
# AKILLI ÖNERİLER (Kişi 4 — AI agent)
# ----------------------------------------------------------------------
st.divider()
st.markdown("### 💡 Akıllı Öneriler")
st.caption("AI agent (Kişi 4) — harcamalarını ve canlı piyasayı birleştiren kişisel tavsiyeler")

advice = load_json("ai_advice.json")
if advice:
    # Analiz özeti + kur uyarısı
    st.markdown(
        f'<div class="insight-card">{advice.get("analiz_ozeti", "")}</div>',
        unsafe_allow_html=True,
    )
    if advice.get("kur_uyarisi"):
        st.markdown(
            f'<div class="insight-card insight-warn">{advice["kur_uyarisi"]}</div>',
            unsafe_allow_html=True,
        )

    st.write("")
    # Öneri kartları — yan yana kolonlar
    oneriler = advice.get("oneriler", [])
    if oneriler:
        cols = st.columns(len(oneriler))
        for col, o in zip(cols, oneriler):
            with col:
                st.markdown(
                    f'<div class="advice-card">'
                    f'<div class="advice-action">{o.get("aksiyon", "")}</div>'
                    f'<div class="advice-cat">{o.get("kategori", "")}</div>'
                    f'<div class="advice-status">{o.get("harcama_durumu", "")}</div>'
                    f'<div class="advice-tip">{o.get("yatirim_tavsiyesi", "")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
    st.caption("⚠️ Bu içerik bilgilendirme amaçlıdır, yatırım tavsiyesi değildir.")
else:
    st.info("AI agent önerileri (ai_advice.json) data/ klasöründe bulunamadı.")

st.caption("SmartFinance • YZTA Bootcamp 2026")
