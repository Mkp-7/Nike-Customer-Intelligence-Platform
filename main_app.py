"""
Nike Consumer Intelligence Platform - Main App
"""
import os, sys
import pandas as pd
import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from config import (
    PLATFORM_TITLE, PLATFORM_SUBTITLE, PLATFORM_ICON,
    BRANDS, PRIMARY_BRAND_ID, REVIEWS_CSV, BUSINESSES_CSV,
)

st.set_page_config(
    page_title=PLATFORM_TITLE,
    page_icon=PLATFORM_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.8rem; font-weight: 700; }
[data-testid="stMetricDelta"] { font-size: 0.85rem; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"## {PLATFORM_ICON} {PLATFORM_TITLE}")
    st.caption(PLATFORM_SUBTITLE)
    st.markdown("---")

    page = st.radio(
        "Navigate",
        [
            "🏠 Overview",
            "🎤 Voice of Customer",
            "⚔️ Competitive Intel",
            "🚨 Defection Radar",
            "🤖 Analyst Copilot",
            "📋 Merchandising",
        ],
        label_visibility="collapsed",
    )

    st.markdown("---")
    reviews_ok = os.path.exists(REVIEWS_CSV)
    biz_ok     = os.path.exists(BUSINESSES_CSV)
    st.caption("**Data Status**")
    st.markdown(f"{'✅' if reviews_ok else '❌'} Reviews")
    st.markdown(f"{'✅' if biz_ok else '❌'} Locations")

    if reviews_ok:
        try:
            _df = pd.read_csv(REVIEWS_CSV, usecols=["brand_id"])
            brands_n = _df["brand_id"].nunique()
            total_n  = len(_df)
            st.caption(f"{total_n:,} reviews · {brands_n} brands tracked")
        except Exception:
            pass

    st.markdown("---")
    st.caption("Refresh data:\nGitHub → Actions → **Scrape Reviews** → Run workflow")

# ── Pages ─────────────────────────────────────────────────────────────────────
if page == "🏠 Overview":
    import plotly.express as px

    st.markdown(f"# {PLATFORM_ICON} {PLATFORM_TITLE}")
    st.markdown(f"*{PLATFORM_SUBTITLE}*")
    st.markdown("---")

    if not os.path.exists(REVIEWS_CSV):
        st.warning("No data yet. GitHub Actions → **Scrape Reviews** → Run workflow.")
    else:
        df = pd.read_csv(REVIEWS_CSV, parse_dates=["date"])
        df["stars"] = pd.to_numeric(df["stars"], errors="coerce")

        nike_df = df[df["brand_id"] == PRIMARY_BRAND_ID] if "brand_id" in df.columns else df
        comp_df = df[df["brand_id"] != PRIMARY_BRAND_ID] if "brand_id" in df.columns else pd.DataFrame()

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Nike Reviews",       f"{len(nike_df):,}")
        c2.metric("Nike Avg Rating",    f"{nike_df['stars'].mean():.2f} ⭐" if len(nike_df) else "-")
        c3.metric("Competitors Tracked",f"{comp_df['brand_id'].nunique() if len(comp_df) else 0}")

        if len(comp_df) and len(nike_df):
            gap = nike_df["stars"].mean() - comp_df["stars"].mean()
            c4.metric("Nike vs Competitors", f"{gap:+.2f} ⭐",
                      delta_color="normal" if gap >= 0 else "inverse")
        else:
            c4.metric("Nike vs Competitors", "-")

        neg_pct = (nike_df["stars"] <= 2).mean() * 100 if len(nike_df) else 0
        c5.metric("Negative Reviews %", f"{neg_pct:.1f}%")

        st.markdown("---")

        if "brand_id" in df.columns and df["brand_id"].nunique() > 1:
            st.markdown("### Brand Ratings at a Glance")
            brand_map = {b["brand_id"]: b["name"]  for b in BRANDS}
            color_map = {b["name"]:     b["color"] for b in BRANDS}
            ba = (df.groupby("brand_id")["stars"]
                  .agg(avg="mean", count="count")
                  .reset_index())
            ba["name"] = ba["brand_id"].map(brand_map)
            ba = ba.dropna(subset=["name"]).sort_values("avg", ascending=False)

            fig = px.bar(
                ba, x="name", y="avg",
                color="name", color_discrete_map=color_map,
                text=ba["avg"].apply(lambda x: f"{x:.2f}⭐"),
                labels={"name": "Brand", "avg": "Avg Rating"},
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                height=320, showlegend=False,
                yaxis=dict(range=[0, 5.5]),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig, width="stretch")

        st.markdown("---")
        st.markdown("### Platform Modules")
        c1, c2, c3 = st.columns(3)
        c1.info("**🎤 Voice of Customer**\nNike review themes, rating trends, anomalous locations, exec summary")
        c2.info("**⚔️ Competitive Intel**\nBrand health scores · Rating benchmarks · AI theme comparison vs competitors")
        c3.info("**🚨 Defection Radar**\nNLP detection of consumers switching away · Category risk map · Recovery brief")

elif page == "🎤 Voice of Customer":
    import module1_voice_of_customer.app as m1
    m1.show()

elif page == "⚔️ Competitive Intel":
    import module2_competitive_intel.app as m2
    m2.show()

elif page == "🚨 Defection Radar":
    import module3_defection_radar.app as m3
    m3.show()

elif page == "🤖 Analyst Copilot":
    import module4_analyst_copilot.app as m4
    m4.show()

elif page == "📋 Merchandising":
    import module5_merchandising.app as m5
    m5.show()
