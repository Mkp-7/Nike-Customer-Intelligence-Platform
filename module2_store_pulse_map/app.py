"""
Module 2 - Competitive Intelligence
Nike vs On Running vs HOKA vs New Balance
Side-by-side brand health benchmarking on real App Store data.
"""
import os, sys
import pandas as pd
import plotly.express as px
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD_DIR  = os.path.join(BASE_DIR, "module1_voice_of_customer")
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, MOD_DIR)

from config import REVIEWS_CSV, BRANDS, PRIMARY_BRAND_ID, GROQ_MODEL
from voc_analyzer import get_groq_client

BRAND_MAP = {b["brand_id"]: b["name"]  for b in BRANDS}
COLOR_MAP = {b["name"]:     b["color"] for b in BRANDS}


@st.cache_data(show_spinner=False)
def load_comp_data() -> pd.DataFrame:
    if not os.path.exists(REVIEWS_CSV):
        return pd.DataFrame()
    df = pd.read_csv(REVIEWS_CSV, parse_dates=["date"])
    df["stars"]      = pd.to_numeric(df["stars"], errors="coerce")
    df["brand_name"] = df["brand_id"].map(BRAND_MAP)
    return df.dropna(subset=["stars", "brand_name"])


def brand_health_score(df: pd.DataFrame, brand_id: str) -> dict:
    bdf = df[df["brand_id"] == brand_id]
    if bdf.empty:
        return {"score": 0, "grade": "N/A", "components": {}}

    avg = bdf["stars"].mean()
    pos = (bdf["stars"] >= 4).mean()
    neg = (bdf["stars"] <= 2).mean()

    if "date" in bdf.columns and bdf["date"].notna().any():
        cutoff     = pd.Timestamp.now() - pd.DateOffset(months=12)
        recent_pct = (bdf["date"] >= cutoff).mean()
    else:
        recent_pct = 0.5

    score = (avg / 5.0) * 40 + pos * 30 + (1 - neg) * 20 + recent_pct * 10
    grade = "A" if score >= 80 else "B" if score >= 65 else "C" if score >= 50 else "D"

    return {
        "score": round(score, 1),
        "grade": grade,
        "components": {
            "avg_rating":    round(avg, 2),
            "positive_pct":  round(pos * 100, 1),
            "negative_pct":  round(neg * 100, 1),
            "recent_pct":    round(recent_pct * 100, 1),
        },
    }


def get_ai_themes(brand_id: str, sample_text: str, client) -> str:
    try:
        prompt = f"""Analyze these customer reviews for {BRAND_MAP.get(brand_id, brand_id)}.
Give exactly 3 top themes in this format:
1. [THEME NAME]: one sentence description (sentiment: positive/negative/mixed)
2. ...
3. ...

Reviews:
{sample_text[:3000]}"""
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"AI unavailable: {e}"


def show():
    st.markdown("## ⚔️ Competitive Intelligence")
    st.markdown(
        "Nike benchmarked against On Running, HOKA, and New Balance "
        "using real App Store review data."
    )

    df = load_comp_data()
    if df.empty:
        st.error("No data. Run scraper: GitHub Actions → Scrape Reviews.")
        return

    brands_in_data = [b for b in df["brand_id"].unique() if b in BRAND_MAP]

    # ── Brand Health Scorecards ───────────────────────────────────────────────
    st.markdown("### 🏆 Brand Health Scorecards")
    st.caption(
        "Composite score (0–100): avg rating (40%) + % positive (30%) "
        "+ % non-negative (20%) + review recency (10%)"
    )

    cols = st.columns(len(brands_in_data))
    grade_icon = {"A": "🟢", "B": "🟡", "C": "🟠", "D": "🔴", "N/A": "⚫"}

    for i, bid in enumerate(brands_in_data):
        h     = brand_health_score(df, bid)
        bname = BRAND_MAP[bid]
        icon  = "👟 " if bid == PRIMARY_BRAND_ID else ""
        gi    = grade_icon.get(h["grade"], "⚫")
        comp  = h["components"]

        with cols[i]:
            st.markdown(f"**{icon}{bname}**")
            st.metric("Health Score", f"{h['score']}/100")
            st.caption(
                f"{gi} Grade **{h['grade']}**  \n"
                f"⭐ Avg: {comp.get('avg_rating','-')}  \n"
                f"👍 Positive: {comp.get('positive_pct','-')}%  \n"
                f"👎 Negative: {comp.get('negative_pct','-')}%  \n"
                f"🕐 Recent: {comp.get('recent_pct','-')}%"
            )

    st.markdown("---")

    # ── Rating distribution ───────────────────────────────────────────────────
    st.markdown("### 📊 Rating Distribution by Brand")
    dist = (df.groupby(["brand_name", "stars"])
            .size()
            .reset_index(name="count"))
    dist["pct"] = dist.groupby("brand_name")["count"].transform(
        lambda x: x / x.sum() * 100
    )
    fig = px.bar(
        dist, x="stars", y="pct", color="brand_name", barmode="group",
        color_discrete_map=COLOR_MAP,
        labels={"stars": "Stars", "pct": "% of Reviews", "brand_name": "Brand"},
        text=dist["pct"].apply(lambda x: f"{x:.0f}%"),
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=350, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown("---")

    # ── Rating trend ──────────────────────────────────────────────────────────
    st.markdown("### 📈 Rating Trend - Last 18 Months")
    df_dated = df.dropna(subset=["date"]).copy()
    if not df_dated.empty:
        df_dated["month"] = df_dated["date"].dt.to_period("M").dt.to_timestamp()
        cutoff = pd.Timestamp.now() - pd.DateOffset(months=18)
        trend  = (df_dated[df_dated["month"] >= cutoff]
                  .groupby(["month", "brand_name"])["stars"]
                  .mean()
                  .reset_index())
        fig2 = px.line(
            trend, x="month", y="stars", color="brand_name",
            color_discrete_map=COLOR_MAP, markers=True,
            labels={"month": "Month", "stars": "Avg Rating", "brand_name": "Brand"},
        )
        fig2.update_layout(
            height=320, yaxis=dict(range=[1, 5.5]),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig2, width="stretch")

    st.markdown("---")

    # ── Review volume ─────────────────────────────────────────────────────────
    st.markdown("### 📦 Review Volume")
    vol = (df.groupby("brand_name")
           .agg(reviews=("stars", "count"), avg_rating=("stars", "mean"))
           .reset_index()
           .sort_values("reviews", ascending=False))

    fig3 = px.bar(
        vol, x="brand_name", y="reviews",
        color="brand_name", color_discrete_map=COLOR_MAP,
        text="reviews",
        labels={"brand_name": "Brand", "reviews": "Reviews Analyzed"},
    )
    fig3.update_traces(textposition="outside")
    fig3.update_layout(
        height=300, showlegend=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(fig3, width="stretch")

    st.markdown("---")

    # ── AI Theme Comparison ───────────────────────────────────────────────────
    st.markdown("### 🧠 AI Theme Analysis per Brand")
    st.caption("Groq LLaMA surfaces the top 3 themes per brand so you can compare what each brand's customers care about.")

    if st.button("Run AI Theme Comparison", type="primary"):
        try:
            client = get_groq_client()
        except ValueError as e:
            st.error(str(e))
            return

        for bid in brands_in_data:
            bname = BRAND_MAP[bid]
            bdf   = df[df["brand_id"] == bid].dropna(subset=["text"])
            if bdf.empty:
                continue

            sample_parts = []
            for stars in [1, 2, 3, 4, 5]:
                bucket = bdf[bdf["stars"] == stars]["text"].tolist()
                sample_parts.extend(bucket[:20])
            sample_text = "\n".join(
                [f"[{i+1}] {t[:200]}" for i, t in enumerate(sample_parts[:60])]
            )

            with st.expander(f"**{bname}** - Top 3 Themes",
                             expanded=(bid == PRIMARY_BRAND_ID)):
                with st.spinner(f"Analyzing {bname}..."):
                    themes = get_ai_themes(bid, sample_text, client)
                st.markdown(themes)
