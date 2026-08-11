"""
Module 1 - Voice of Customer (Nike)
App Store + Google Maps reviews - themes, category performance, anomalies, exec summary.
"""
import os, sys
import pandas as pd
import plotly.express as px
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD_DIR  = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, MOD_DIR)

from config import REVIEWS_CSV, PRIMARY_BRAND_ID, PRODUCT_CATEGORIES, GROQ_MODEL
from voc_analyzer import get_groq_client, cluster_themes, detect_anomalies, write_exec_summary


def classify_category(text: str) -> str:
    text_lower = str(text).lower()
    for cat, keywords in PRODUCT_CATEGORIES.items():
        if any(k in text_lower for k in keywords):
            return cat
    return "General"


@st.cache_data(show_spinner=False)
def load_data():
    if not os.path.exists(REVIEWS_CSV):
        return pd.DataFrame()
    df = pd.read_csv(REVIEWS_CSV, parse_dates=["date"])
    df["stars"] = pd.to_numeric(df["stars"], errors="coerce")
    if "brand_id" in df.columns:
        df = df[df["brand_id"] == PRIMARY_BRAND_ID]
    return df.dropna(subset=["stars"])


def show():
    st.markdown("## 🎤 Voice of Customer - Nike")

    with st.spinner("Loading Nike reviews..."):
        df_raw = load_data()

    if df_raw.empty:
        st.error("No Nike data. Run scraper: GitHub Actions → Scrape Reviews.")
        return

    df = df_raw.copy()
    df["category"] = df["text"].fillna("").apply(classify_category)
    df_all = df.copy()

    # ── Sidebar filters ───────────────────────────────────────────────────────
    st.sidebar.markdown("### 🎤 VoC Filters")

    sources = df["source"].dropna().unique().tolist()
    sel_source = st.sidebar.multiselect("Source", sources, default=sources)

    categories = sorted(df["category"].unique().tolist())
    sel_cat = st.sidebar.multiselect("Product Category", categories, default=categories)

    stars_range = st.sidebar.slider("Stars", 1, 5, (1, 5))

    if "state" in df.columns:
        states = sorted(df["state"].dropna()[df["state"].str.strip() != ""].unique().tolist())
        sel_states = st.sidebar.multiselect("State (Google Maps only)", states, default=states)
        has_state = df["state"].fillna("").str.strip() != ""
        df = df[(~has_state) | df["state"].isin(sel_states)]

    if sel_source: df = df[df["source"].isin(sel_source)]
    if sel_cat:    df = df[df["category"].isin(sel_cat)]
    df = df[df["stars"].between(stars_range[0], stars_range[1])]

    if df.empty:
        st.warning("No reviews match current filters.")
        return

    total = len(df)
    avg   = df["stars"].mean()
    pos   = (df["stars"] >= 4).mean() * 100
    neg   = (df["stars"] <= 2).mean() * 100

    # ── KPIs ──────────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Reviews",           f"{total:,}")
    c2.metric("Avg Rating",        f"{avg:.2f} ⭐")
    c3.metric("Positive (4-5⭐)",  f"{pos:.1f}%")
    c4.metric("Negative (1-2⭐)",  f"{neg:.1f}%")

    st.markdown("---")

    # ── Rating by product category ────────────────────────────────────────────
    st.markdown("### 📦 Rating by Product Category")
    cat_stats = (df.groupby("category")["stars"]
                 .agg(avg="mean", count="count")
                 .reset_index()
                 .sort_values("avg"))

    fig = px.bar(
        cat_stats, x="avg", y="category", orientation="h",
        color="avg",
        color_continuous_scale=["#ef4444", "#f59e0b", "#22c55e"],
        text=cat_stats.apply(lambda r: f"{r['avg']:.2f}⭐ ({r['count']})", axis=1),
        labels={"avg": "Avg Rating", "category": "Category"},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=300, coloraxis_showscale=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=120, t=10, b=0),
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown("---")

    # ── Rating trend ──────────────────────────────────────────────────────────
    st.markdown("### 📈 Rating Trend")
    df_dated = df.dropna(subset=["date"])
    if not df_dated.empty:
        df_dated = df_dated.copy()
        df_dated["month"] = df_dated["date"].dt.to_period("M").dt.to_timestamp()
        trend = df_dated.groupby("month")["stars"].mean().reset_index()
        fig2 = px.line(trend, x="month", y="stars", markers=
