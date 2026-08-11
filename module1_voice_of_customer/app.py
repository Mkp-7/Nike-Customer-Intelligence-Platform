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

from config import REVIEWS_CSV, PRIMARY_BRAND_ID, PRODUCT_CATEGORIES
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

    if sel_source:
        df = df[df["source"].isin(sel_source)]
    if sel_cat:
        df = df[df["category"].isin(sel_cat)]
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
    c1.metric("Reviews",          f"{total:,}")
    c2.metric("Avg Rating",       f"{avg:.2f} ⭐")
    c3.metric("Positive (4-5⭐)", f"{pos:.1f}%")
    c4.metric("Negative (1-2⭐)", f"{neg:.1f}%")

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
    df_dated = df.dropna(subset=["date"]).copy()
    if not df_dated.empty:
        df_dated["month"] = df_dated["date"].dt.to_period("M").dt.to_timestamp()
        trend = df_dated.groupby("month")["stars"].mean().reset_index()
        fig2 = px.line(trend, x="month", y="stars", markers=True,
                       labels={"month": "Month", "stars": "Avg Rating"})
        fig2.add_hline(y=avg, line_dash="dot",
                       annotation_text=f"Overall avg: {avg:.2f}⭐")
        fig2.update_layout(
            height=280, yaxis=dict(range=[1, 5.5]),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig2, width="stretch")

    st.markdown("---")

    # ── Locations Needing Attention ───────────────────────────────────────────
    st.markdown("### 🚨 Locations Needing Attention")
    anomalies = detect_anomalies(df_all)
    if anomalies.empty:
        st.success("✅ No locations significantly below brand average.")
    else:
        st.dataframe(
            anomalies[["business_id", "avg_rating", "total_reviews", "rating_drop"]].head(10),
            column_config={
                "business_id":   st.column_config.TextColumn("Location"),
                "avg_rating":    st.column_config.NumberColumn("Avg Rating", format="%.2f⭐"),
                "total_reviews": st.column_config.NumberColumn("Reviews"),
                "rating_drop":   st.column_config.NumberColumn("Below Brand Avg", format="-%.2f"),
            },
            hide_index=True, width="stretch",
        )

    st.markdown("---")

    # ── AI Theme Analysis ─────────────────────────────────────────────────────
    st.markdown("### 🧠 AI Theme Analysis")
    col1, col2 = st.columns([1, 3])
    run_ai  = col1.button("Run AI Analysis", type="primary")
    max_rev = col2.slider("Reviews to analyze", 50, 300, 150, 50)

    if run_ai:
        try:
            client = get_groq_client()
        except ValueError as e:
            st.error(str(e))
            return

        sample = []
        for s in [1, 2, 3, 4, 5]:
            bucket = df[df["stars"] == s]["text"].dropna().tolist()
            sample.extend(bucket[:max_rev // 5])
        sample = sample[:max_rev]

        with st.spinner("AI clustering themes..."):
            result = cluster_themes(sample, client, industry="athletic footwear")

        themes = result.get("themes", [])
        if themes:
            scol = {"positive": "#22c55e", "negative": "#ef4444", "mixed": "#f59e0b"}
            for t in themes:
                c = scol.get(t.get("sentiment", "mixed"), "#888")
                st.markdown(
                    f"<div style='border-left:4px solid {c};padding:8px 16px;margin:8px 0'>"
                    f"<strong>{t['name']}</strong> - {t['percent']}% - <em>{t['sentiment']}</em><br>"
                    f"{t['description']}<br>"
                    f"<small>💬 \"{t.get('example_quote','')}\"</small></div>",
                    unsafe_allow_html=True,
                )

            d_min = df["date"].min()
            d_max = df["date"].max()
            date_range = (
                f"{d_min.strftime('%b %Y') if pd.notna(d_min) else 'N/A'} – "
                f"{d_max.strftime('%b %Y') if pd.notna(d_max) else 'N/A'}"
            )
            st.markdown("#### Executive Summary")
            with st.spinner("Generating summary..."):
                summary = write_exec_summary(
                    themes, anomalies, total, avg, date_range, client, "Nike"
                )
            st.info(summary)

    st.markdown("---")
    with st.expander("📋 Raw Reviews"):
        show_cols = [c for c in ["stars","date","category","source","title","text"]
                     if c in df.columns]
        disp = df[show_cols].head(200).copy()
        disp["date"] = disp["date"].astype(str).str[:10]
        st.dataframe(disp, hide_index=True, width="stretch", height=400)
