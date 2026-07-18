"""
SmartFinance — Kişisel Finans & Yatırım Asistanı
Dashboard (Kişi 3 — Sprint 2)

Sprint 2 eklentileri:
  - Kullanıcı dosya yükleme arayüzü (CSV / JSON)
  - Anomali tespiti sonuçlarının gösterimi (z-score / IQR)
  - Bütçe hedefi arayüzü (kategori bazlı limit + takip)
  - Doğal dil sorgu kutusu (agent entegrasyonu, API yoksa fallback)

Veri kaynakları:
  - data/transactions_*.json  → Kişi 1 (ham işlemler)
  - data/dashboard_data.json  → Kişi 2 (kategori özeti + aylık trend)
  - data/market_data.json     → Kişi 2 (canlı döviz/altın/hisse)
  - data/ai_advice.json       → Kişi 4 (AI agent önerileri)
  - agent.agent_engine        → Kişi 4 (doğal dil sorgu motoru, opsiyonel)
"""

import json
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="SmartFinance", page_icon="◆", layout="wide")

DATA_DIR = Path(__file__).parent / "data"
ROOT_DIR = Path(__file__).parent.parent

# Agent modülünü opsiyonel olarak yükle (yoksa dashboard yine çalışsın)
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
try:
    from agent.agent_engine import ask_financial_agent
    AGENT_AVAILABLE = True
except Exception:
    AGENT_AVAILABLE = False

# ----------------------------------------------------------------------
# TASARIM
# ----------------------------------------------------------------------
INK = "#0F2A43"
EMERALD = "#0F9D8C"
CORAL = "#E5674E"
GOLD = "#D4A24E"
SLATE = "#5B7085"
MIST = "#EEF3F7"

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
    .answer-box {{
        background: white; border: 1px solid #E3EAF0; border-left: 4px solid {EMERALD};
        border-radius: 8px; padding: 1.1rem 1.3rem; margin-top: 0.8rem;
    }}
    .answer-label {{
        font-size: 0.72rem; font-weight: 700; color: {EMERALD};
        text-transform: uppercase; letter-spacing: 0.05em;
    }}
    .answer-text {{ color: {INK}; font-size: 0.95rem; line-height: 1.5; margin-top: 0.2rem; }}
</style>
""", unsafe_allow_html=True)


# ----------------------------------------------------------------------
# VERİ YÜKLEYİCİLER
# ----------------------------------------------------------------------
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
    if not records:
        return pd.DataFrame()
    return _prepare_df(pd.DataFrame(records))


def _prepare_df(df: pd.DataFrame) -> pd.DataFrame:
    """Kontrata uygun hale getir: tarih/tutar tipleri, month kolonu."""
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    if "month" not in df.columns and "date" in df.columns:
        df["month"] = df["date"].dt.strftime("%Y-%m")
    for col in ["category", "transaction_type", "description", "currency"]:
        if col not in df.columns:
            df[col] = "—"
    return df


def parse_uploaded(file) -> pd.DataFrame:
    """Kullanıcının yüklediği CSV/JSON dosyasını DataFrame'e çevirir."""
    if file.name.lower().endswith(".json"):
        records = json.load(file)
        df = pd.DataFrame(records)
    else:
        df = pd.read_csv(file)
    return _prepare_df(df)


def fmt(n):
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
# ANOMALİ TESPİTİ (z-score + IQR)
# ----------------------------------------------------------------------
@st.cache_data
def detect_anomalies(df: pd.DataFrame, z_threshold: float = 3.0,
                     iqr_multiplier: float = 1.5) -> pd.DataFrame:
    """Gider işlemlerinde olağandışı tutarları tespit eder."""
    if df.empty or "amount" not in df.columns:
        return pd.DataFrame()

    work = df[df["transaction_type"] == "debit"].copy() if "transaction_type" in df.columns else df.copy()
    if work.empty:
        work = df.copy()
    amounts = work["amount"].abs()

    flags = pd.Series(False, index=work.index)
    types = pd.Series("", index=work.index)
    scores = pd.Series(pd.NA, index=work.index, dtype="object")

    # Z-score
    mean, std = amounts.mean(), amounts.std(ddof=1)
    if std and not pd.isna(std) and std > 0:
        z = (amounts - mean) / std
        z_flag = z.abs() > z_threshold
        flags |= z_flag
        types[z_flag] = "Z-Score"
        scores[z_flag] = z[z_flag].round(2)

    # IQR
    q1, q3 = amounts.quantile(0.25), amounts.quantile(0.75)
    iqr = q3 - q1
    if iqr and iqr > 0:
        upper = q3 + iqr_multiplier * iqr
        iqr_flag = amounts > upper
        newly = iqr_flag & ~flags
        flags |= iqr_flag
        types[newly] = "IQR"
        types[iqr_flag & (types == "Z-Score")] = "Z-Score + IQR"

    result = work[flags].copy()
    if result.empty:
        return pd.DataFrame()
    result["anomaly_type"] = types[flags]
    result["z_score"] = scores[flags]
    return result.sort_values("amount", ascending=False)


# ----------------------------------------------------------------------
# BÜTÇE HESAPLAMA
# ----------------------------------------------------------------------
@st.cache_data
def calculate_budgets(df: pd.DataFrame, buffer: float = 0.10) -> pd.DataFrame:
    """Kategori bazlı aylık ortalama harcamadan önerilen bütçe hedefi üretir."""
    if df.empty:
        return pd.DataFrame()
    spend = df[df["transaction_type"] == "debit"].copy() if "transaction_type" in df.columns else df.copy()
    if spend.empty or "month" not in spend.columns:
        return pd.DataFrame()
    spend["abs_amount"] = spend["amount"].abs()

    monthly = spend.groupby(["category", "month"])["abs_amount"].sum().reset_index()
    summary = monthly.groupby("category")["abs_amount"].agg(
        ortalama_aylik="mean", en_yuksek_ay="max", takip_edilen_ay="count"
    ).reset_index()
    summary["onerilen_butce"] = (summary["ortalama_aylik"] * (1 + buffer)).round(2)
    summary["ortalama_aylik"] = summary["ortalama_aylik"].round(2)
    summary["en_yuksek_ay"] = summary["en_yuksek_ay"].round(2)
    return summary.sort_values("onerilen_butce", ascending=False)


# ----------------------------------------------------------------------
# BAŞLIK
# ----------------------------------------------------------------------
st.markdown(
    '<div class="brand">Smart<span class="brand-accent">Finance</span></div>'
    '<div class="tagline">Harcamalarını anla, piyasayı takip et, ne yapman gerektiğini gör.</div>',
    unsafe_allow_html=True,
)
st.write("")

# ----------------------------------------------------------------------
# KENAR ÇUBUĞU — VERİ KAYNAĞI
# ----------------------------------------------------------------------
with st.sidebar:
    st.header("Veri Kaynağı")
    source = st.radio(
        "Hangi veriyle çalışmak istersin?",
        ["Örnek veri", "Tam veri", "Kendi dosyamı yükle"],
        help="Kendi banka ekstreni CSV veya JSON olarak yükleyebilirsin.",
    )

    uploaded_df = None
    if source == "Kendi dosyamı yükle":
        up = st.file_uploader("Banka ekstresi / işlem dosyası", type=["csv", "json"])
        if up is not None:
            try:
                uploaded_df = parse_uploaded(up)
                st.success(f"{len(uploaded_df):,} işlem yüklendi.")
            except Exception as e:
                st.error(f"Dosya okunamadı: {e}")

# Aktif veri setini belirle
if source == "Kendi dosyamı yükle":
    if uploaded_df is None or uploaded_df.empty:
        st.info("Başlamak için kenar çubuğundan bir CSV veya JSON dosyası yükle. "
                "Beklenen kolonlar: date, description, amount, currency, transaction_type, category")
        st.stop()
    tx = uploaded_df
    data_label = "Yüklenen dosya"
elif source == "Tam veri":
    tx = load_transactions("transactions_merged.json")
    data_label = "Tam veri seti"
else:
    tx = load_transactions("transactions_sample.json")
    data_label = "Örnek veri"

market = load_json("market_data.json")
dash = load_json("dashboard_data.json")
advice = load_json("ai_advice.json")

# Kategori özetini aktif veriden hesapla (yüklenen dosya için de çalışsın)
def build_category_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    spend = df[df["transaction_type"] == "debit"] if "transaction_type" in df.columns else df
    if spend.empty:
        spend = df
    g = spend.groupby("category")["amount"].agg(Tutar=lambda s: s.abs().sum(), İşlem="count").reset_index()
    g = g.rename(columns={"category": "Kategori"})
    toplam = g["Tutar"].sum()
    g["Yüzde"] = (g["Tutar"] / toplam * 100) if toplam else 0
    return g.sort_values("Tutar", ascending=False)

cat_df = build_category_df(tx)

# ----------------------------------------------------------------------
# SEKMELER
# ----------------------------------------------------------------------
tab_ozet, tab_anomali, tab_butce, tab_sorgu, tab_piyasa = st.tabs(
    ["  Genel Bakış  ", "  Anomaliler  ", "  Bütçe  ", "  Soru Sor  ", "  Piyasa  "]
)

# ======================================================================
# TAB 1 — GENEL BAKIŞ
# ======================================================================
with tab_ozet:
    st.caption(f"Aktif veri: {data_label} · {len(tx):,} işlem")

    k1, k2, k3 = st.columns(3)
    spend_total = tx.loc[tx["transaction_type"] == "debit", "amount"].abs().sum() if "transaction_type" in tx.columns else tx["amount"].abs().sum()
    k1.metric("Toplam İşlem", f"{len(tx):,}")
    k2.metric("Toplam Harcama", fmt(spend_total))
    k3.metric("Kategori Sayısı", tx["category"].nunique())

    if not cat_df.empty:
        st.markdown("#### Öne çıkanlar")
        top = cat_df.iloc[0]
        top3 = cat_df.head(3)["Yüzde"].sum()
        st.markdown(
            f'<div class="insight-card">En yüksek harcama kategorin '
            f'<b>{top["Kategori"]}</b> — toplam harcamanın <b>%{top["Yüzde"]:.0f}</b>\'i '
            f'({int(top["İşlem"])} işlem).</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="insight-card insight-gold">En büyük 3 kategori '
            f'(<b>{", ".join(cat_df.head(3)["Kategori"].astype(str))}</b>) '
            f'harcamanın <b>%{top3:.0f}</b>\'ini oluşturuyor.</div>', unsafe_allow_html=True)

        st.write("")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("##### Harcama Dağılımı")
            fig = go.Figure(data=[go.Pie(
                labels=cat_df["Kategori"], values=cat_df["Tutar"], hole=0.55,
                marker=dict(colors=CAT_PALETTE), textinfo="percent", textposition="inside",
                hovertemplate="<b>%{label}</b><br>%{percent}<extra></extra>",
            )])
            fig.update_layout(height=340, margin=dict(t=10, b=10, l=10, r=10),
                              legend=dict(font=dict(size=10)),
                              annotations=[dict(text="Gider", x=0.5, y=0.5, font_size=16,
                                                showarrow=False, font_color=INK)])
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.markdown("##### Aylık Harcama Trendi")
            spend = tx[tx["transaction_type"] == "debit"] if "transaction_type" in tx.columns else tx
            monthly = spend.groupby("month")["amount"].apply(lambda s: s.abs().sum()).sort_index()
            if len(monthly) > 0:
                tdf = pd.DataFrame({"Ay": monthly.index, "Toplam": monthly.values})
                fig2 = px.area(tdf, x="Ay", y="Toplam")
                fig2.update_traces(line_color=EMERALD, fillcolor="rgba(15,157,140,0.12)")
                fig2.update_layout(height=340, margin=dict(t=10, b=10, l=10, r=10),
                                   xaxis_title=None, yaxis_title=None, plot_bgcolor="white")
                st.plotly_chart(fig2, use_container_width=True)

        st.markdown("##### Kategori Detayı")
        show = cat_df.copy()
        show["Tutar"] = show["Tutar"].map(lambda x: f"{x:,.0f}")
        show["Yüzde"] = show["Yüzde"].map(lambda x: f"%{x:.2f}")
        st.dataframe(show, use_container_width=True, hide_index=True)

    # AI önerileri (Kişi 4 — statik dosya)
    if advice:
        st.divider()
        st.markdown("##### Akıllı Öneriler")
        st.caption("AI agent — harcamalarını ve piyasayı birleştiren kişisel tavsiyeler")
        if advice.get("analiz_ozeti"):
            st.markdown(f'<div class="insight-card">{advice["analiz_ozeti"]}</div>',
                        unsafe_allow_html=True)
        if advice.get("kur_uyarisi"):
            st.markdown(f'<div class="insight-card insight-warn">{advice["kur_uyarisi"]}</div>',
                        unsafe_allow_html=True)
        oneriler = advice.get("oneriler", [])
        if oneriler:
            cols = st.columns(len(oneriler))
            for col, o in zip(cols, oneriler):
                with col:
                    st.markdown(
                        f'<div class="advice-card">'
                        f'<div class="advice-action">{o.get("aksiyon","")}</div>'
                        f'<div class="advice-cat">{o.get("kategori","")}</div>'
                        f'<div class="advice-status">{o.get("harcama_durumu","")}</div>'
                        f'<div class="advice-tip">{o.get("yatirim_tavsiyesi","")}</div>'
                        f'</div>', unsafe_allow_html=True)
        st.caption("Bu içerik bilgilendirme amaçlıdır, yatırım tavsiyesi değildir.")

# ======================================================================
# TAB 2 — ANOMALİLER
# ======================================================================
with tab_anomali:
    st.markdown("#### Olağandışı Harcamalar")
    st.caption("Z-Score ve IQR yöntemleriyle normal harcama örüntünün dışına çıkan işlemler")

    col_a, col_b = st.columns([1, 1])
    with col_a:
        z_th = st.slider("Z-Score eşiği", 2.0, 5.0, 3.0, 0.5,
                         help="Düşük değer = daha hassas tespit")
    with col_b:
        iqr_mult = st.slider("IQR çarpanı", 1.0, 3.0, 1.5, 0.5,
                             help="Düşük değer = daha hassas tespit")

    anomalies = detect_anomalies(tx, z_th, iqr_mult)

    if anomalies.empty:
        st.success("Seçili eşiklerde olağandışı harcama tespit edilmedi.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("Tespit Edilen", f"{len(anomalies):,}")
        m2.metric("Toplam Tutar", fmt(anomalies["amount"].abs().sum()))
        m3.metric("Oran", f"%{len(anomalies)/len(tx)*100:.1f}")

        st.markdown(
            f'<div class="insight-card insight-warn">'
            f'<b>{len(anomalies)}</b> işlem olağandışı bulundu. '
            f'En yüksek: <b>{anomalies.iloc[0]["description"]}</b> '
            f'({anomalies.iloc[0]["amount"]:,.0f} {anomalies.iloc[0].get("currency","")}).'
            f'</div>', unsafe_allow_html=True)

        # Dağılım grafiği — anomaliler kırmızı
        spend = tx[tx["transaction_type"] == "debit"] if "transaction_type" in tx.columns else tx
        plot_df = spend.copy()
        plot_df["Durum"] = "Normal"
        plot_df.loc[plot_df.index.isin(anomalies.index), "Durum"] = "Anomali"
        fig = px.scatter(plot_df, x="date", y=plot_df["amount"].abs(), color="Durum",
                         color_discrete_map={"Normal": SLATE, "Anomali": CORAL},
                         hover_data=["description", "category"])
        fig.update_layout(height=360, plot_bgcolor="white", xaxis_title=None,
                          yaxis_title="Tutar", margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("##### Olağandışı İşlemler")
        cols_show = [c for c in ["date", "description", "amount", "currency",
                                 "category", "anomaly_type", "z_score"] if c in anomalies.columns]
        table = anomalies[cols_show].copy()
        if "date" in table.columns:
            table["date"] = table["date"].dt.strftime("%Y-%m-%d")
        st.dataframe(
            table.style.apply(lambda r: [f"background-color: #FDEDE9"] * len(r), axis=1),
            use_container_width=True, hide_index=True, height=340,
        )

# ======================================================================
# TAB 3 — BÜTÇE
# ======================================================================
with tab_butce:
    st.markdown("#### Bütçe Hedefleri")
    st.caption("Geçmiş harcamalarına göre önerilen aylık limitler — üzerinde oynayabilirsin")

    budgets = calculate_budgets(tx)

    if budgets.empty:
        st.info("Bütçe hesabı için aylık gider verisi gerekiyor.")
    else:
        buffer_pct = st.slider("Esneklik payı (%)", 0, 30, 10, 5,
                               help="Önerilen bütçe = aylık ortalama + esneklik payı")
        budgets = calculate_budgets(tx, buffer_pct / 100)

        # Son ayın gerçek harcaması ile karşılaştır
        spend = tx[tx["transaction_type"] == "debit"] if "transaction_type" in tx.columns else tx
        son_ay = spend["month"].max() if "month" in spend.columns and not spend.empty else None
        gerceklesen = (spend[spend["month"] == son_ay].groupby("category")["amount"]
                       .apply(lambda s: s.abs().sum()) if son_ay else pd.Series(dtype=float))

        st.markdown(f"##### Kategori Limitleri {f'· {son_ay} gerçekleşen ile karşılaştırma' if son_ay else ''}")

        limits = {}
        for _, row in budgets.head(8).iterrows():
            kat = row["category"]
            onerilen = float(row["onerilen_butce"])
            harcanan = float(gerceklesen.get(kat, 0))

            c1, c2 = st.columns([1, 2])
            with c1:
                limit = st.number_input(
                    f"{kat}", min_value=0.0, value=round(onerilen, 2), step=50.0,
                    key=f"limit_{kat}", label_visibility="visible",
                )
                limits[kat] = limit
            with c2:
                oran = (harcanan / limit * 100) if limit > 0 else 0
                renk = CORAL if oran > 100 else (GOLD if oran > 80 else EMERALD)
                st.markdown(f"<div style='padding-top:1.9rem'></div>", unsafe_allow_html=True)
                st.progress(min(oran / 100, 1.0))
                durum = "aşıldı" if oran > 100 else ("limite yakın" if oran > 80 else "uygun")
                st.markdown(
                    f"<span style='color:{renk}; font-size:0.82rem; font-weight:600'>"
                    f"{harcanan:,.0f} / {limit:,.0f} (%{oran:.0f}) — {durum}</span>",
                    unsafe_allow_html=True)

        # Aşım uyarıları
        asilanlar = [(k, gerceklesen.get(k, 0), v) for k, v in limits.items()
                     if v > 0 and gerceklesen.get(k, 0) > v]
        if asilanlar:
            st.divider()
            for kat, harcanan, limit in asilanlar:
                st.markdown(
                    f'<div class="insight-card insight-warn">'
                    f'<b>{kat}</b> kategorisinde bütçeni <b>{harcanan - limit:,.0f}</b> aştın '
                    f'({harcanan:,.0f} / {limit:,.0f}).</div>', unsafe_allow_html=True)

        with st.expander("Bütçe hesaplama detayları"):
            show_b = budgets.rename(columns={
                "category": "Kategori", "ortalama_aylik": "Aylık Ortalama",
                "en_yuksek_ay": "En Yüksek Ay", "takip_edilen_ay": "Takip Edilen Ay",
                "onerilen_butce": "Önerilen Bütçe",
            })
            st.dataframe(show_b, use_container_width=True, hide_index=True)

# ======================================================================
# TAB 4 — DOĞAL DİL SORGU
# ======================================================================
with tab_sorgu:
    st.markdown("#### Finans Asistanına Sor")
    st.caption("Harcamalarınla ilgili sorularını doğal dilde sorabilirsin")

    if not AGENT_AVAILABLE:
        st.info("Agent modülü bulunamadı — örnek cevap motoru kullanılıyor. "
                "Canlı yanıt için `agent/agent_engine.py` ve `GEMINI_API_KEY` gerekir.")

    ornekler = [
        "Bu ay en çok nereye harcadım?",
        "Hangi kategoride tasarruf edebilirim?",
        "Harcamalarımda dikkat etmem gereken bir şey var mı?",
    ]
    st.markdown("**Örnek sorular:**")
    ec = st.columns(len(ornekler))
    for i, (col, ornek) in enumerate(zip(ec, ornekler)):
        if col.button(ornek, key=f"ornek_{i}", use_container_width=True):
            st.session_state["soru"] = ornek

    soru = st.text_input(
        "Sorunu yaz",
        value=st.session_state.get("soru", ""),
        placeholder="Örn: Geçen aya göre harcamam nasıl değişti?",
    )
    sor = st.button("Sor", type="primary")

    if sor and soru.strip():
        with st.spinner("Analiz ediliyor..."):
            cevap = None
            if AGENT_AVAILABLE:
                try:
                    cevap = ask_financial_agent(soru)
                except Exception as e:
                    st.warning(f"Agent yanıt veremedi, örnek cevaba geçiliyor. ({e})")

            if not cevap:
                # Yerel fallback — veriden basit cevap üret
                if not cat_df.empty:
                    top = cat_df.iloc[0]
                    cevap = {
                        "tespit": (f"En yüksek harcaman {top['Kategori']} kategorisinde: "
                                   f"{top['Tutar']:,.0f} (toplamın %{top['Yüzde']:.0f}'i)."),
                        "oneri": (f"{top['Kategori']} harcamanı %10 azaltırsan aylık "
                                  f"yaklaşık {top['Tutar']*0.1:,.0f} tasarruf edebilirsin."),
                        "kategori": "Tasarruf",
                    }
                else:
                    cevap = {"tespit": "Analiz için yeterli veri bulunamadı.",
                             "oneri": "Daha fazla işlem verisi yükleyerek tekrar dene.",
                             "kategori": "Tasarruf"}

        rozet = {"Yatırım": EMERALD, "Uyarı": CORAL, "Tasarruf": GOLD}.get(
            cevap.get("kategori", "Tasarruf"), EMERALD)
        st.markdown(
            f'<div class="answer-box">'
            f'<span style="background:{rozet};color:white;font-size:0.72rem;font-weight:700;'
            f'padding:0.2rem 0.6rem;border-radius:12px">{cevap.get("kategori","")}</span>'
            f'<div class="answer-label" style="margin-top:0.8rem">Tespit</div>'
            f'<div class="answer-text">{cevap.get("tespit","")}</div>'
            f'<div class="answer-label" style="margin-top:0.8rem">Öneri</div>'
            f'<div class="answer-text">{cevap.get("oneri","")}</div>'
            f'</div>', unsafe_allow_html=True)
        st.caption("Bu içerik bilgilendirme amaçlıdır, yatırım tavsiyesi değildir.")

# ======================================================================
# TAB 5 — PİYASA
# ======================================================================
with tab_piyasa:
    if market:
        st.markdown("#### Canlı Piyasa")
        st.caption(f"Son güncelleme: {market.get('timestamp', '—')}")

        rates = market.get("exchange_rates", {})
        if rates:
            st.markdown("##### Döviz")
            cols = st.columns(len(rates))
            for col, (isim, deger) in zip(cols, rates.items()):
                col.metric(isim, deger)

        gold = market.get("gold", {})
        stocks = market.get("stocks", {})
        if gold or stocks:
            st.markdown("##### Altın & Hisse")
            items = list(gold.items()) + list(stocks.items())
            cols = st.columns(max(len(items), 1))
            for col, (isim, deger) in zip(cols, items):
                col.metric(isim, deger)
    else:
        st.warning("Piyasa verisi (market_data.json) bulunamadı.")

st.caption("SmartFinance • YZTA Bootcamp 2026")
