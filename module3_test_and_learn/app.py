"""
Module 3 - Consumer Defection Radar
Detects Nike customers switching to competitors using NLP on review text.
Maps defection risk to product categories and generates an AI recovery brief.
"""
import os, sys
import pandas as pd
import plotly.express as px
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD_DIR  = os.path.join(BASE_DIR, "module1_voice_of_customer")
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, MOD_DIR)

from config import (
    REVIEWS_CSV, BRANDS, PRIMARY_BRAND_ID, GROQ_MODEL,
    DEFECTION_KEYWORDS, PRODUCT_CATEGORIES,
)
from voc_analyzer import get_groq_client

BRAND_MAP = {b["brand_id"]: b["name"]  for b in BRANDS}
COLOR_MAP = {b["name"]:     b["color"] for b in BRANDS}
COMPETITORS = [b["name"] for b in BRANDS if b["brand_id"] != PRIMARY_BRAND_ID]


def classify_category(text: str) -> str:
    text_lower = str(text).lower()
    for cat, keywords in PRODUCT_CATEGORIES.items():
        if any(k in text_lower for k in keywords):
            return cat
    return "General"


def detect_defection_signals(text: str) -> list:
    text_lower = str(text).lower()
    return [kw for kw in DEFECTION_KEYWORDS if kw in text_lower]


def detect_competitor_mentions(text: str) -> list:
    text_lower = str(text).lower()
    return [c for c in COMPETITORS if c.lower() in text_lower]


@st.cache_data(show_spinner=False)
def build_defection_df() -> pd.DataFrame:
    if not os.path.exists(REVIEWS_CSV):
        return pd.DataFrame()

    df = pd.read_csv(REVIEWS_CSV, parse_dates=["date"])
    df["stars"] = pd.to_numeric(df["stars"], errors="coerce")

    if "brand_id" in df.columns:
        df = df[df["brand_id"] == PRIMARY_BRAND_ID]

    df = df.dropna(subset=["text", "stars"])

    df["category"]            = df["text"].apply(classify_category)
    df["defection_signals"]   = df["text"].apply(detect_defection_signals)
    df["competitor_mentions"] = df["text"].apply(detect_competitor_mentions)
    df["is_defection"]        = df["defection_signals"].apply(len) > 0
    df["is_negative"]         = df["stars"] <= 2
    df["defection_risk"]      = df["is_defection"] & df["is_negative"]

    return df


def show():
    st.markdown("## 🚨 Consumer Defection Radar")
    st.markdown(
        "Scans Nike App Store reviews for language patterns indicating consumers "
        "switching to competitors. Maps defection risk by product category and "
        "generates an AI-powered recovery brief for leadership."
    )

    df = build_defection_df()
    if df.empty:
        st.error("No data. Run scraper: GitHub Actions → Scrape Reviews.")
        return

    total         = len(df)
    n_defection   = int(df["is_defection"].sum())
    n_risk        = int(df["defection_risk"].sum())
    defection_pct = n_defection / total * 100 if total else 0

    # ── KPIs ──────────────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Nike Reviews Analyzed", f"{total:,}")
    c2.metric("Defection Signals",     f"{n_defection:,}")
    c3.metric("Defection Rate",        f"{defection_pct:.1f}%",
              delta="High risk" if defection_pct > 5 else "Manageable",
              delta_color="inverse" if defection_pct > 5 else "normal")
    c4.metric("High-Risk Reviews",     f"{n_risk:,}",
              help="Negative (≤2⭐) reviews that also contain switching language")

    st.markdown("---")

    # ── Defection rate by category ────────────────────────────────────────────
    st.markdown("### 📦 Defection Risk by Product Category")
    cat_stats = (df.groupby("category")
                 .agg(total=("stars", "count"),
                      defections=("is_defection", "sum"),
                      avg_rating=("stars", "mean"))
                 .reset_index())
    cat_stats["defection_rate"] = (
        cat_stats["defections"] / cat_stats["total"] * 100
    ).round(1)
    cat_stats = cat_stats.sort_values("defection_rate", ascending=False)

    fig = px.bar(
        cat_stats, x="category", y="defection_rate",
        color="defection_rate",
        color_continuous_scale=["#22c55e", "#f59e0b", "#ef4444"],
        text=cat_stats["defection_rate"].apply(lambda x: f"{x:.1f}%"),
        labels={"category": "Product Category", "defection_rate": "Defection Rate (%)"},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=320, coloraxis_showscale=False,
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown("---")

    # ── Which competitors are named ───────────────────────────────────────────
    st.markdown("### 🎯 Which Competitors Are Stealing Nike Customers?")
    defection_reviews = df[df["is_defection"]]

    if not defection_reviews.empty:
        all_mentions = []
        for mentions in defection_reviews["competitor_mentions"]:
            all_mentions.extend(mentions)

        if all_mentions:
            mc = (pd.Series(all_mentions)
                  .value_counts()
                  .reset_index())
            mc.columns = ["Competitor", "Mentions"]

            fig2 = px.bar(
                mc, x="Competitor", y="Mentions",
                color="Competitor", color_discrete_map=COLOR_MAP,
                text="Mentions",
                labels={"Competitor": "Competitor Brand",
                        "Mentions": "Mentions in Defection Reviews"},
            )
            fig2.update_traces(textposition="outside")
            fig2.update_layout(
                height=300, showlegend=False,
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig2, width="stretch")
        else:
            st.info("Defection signals detected but no specific competitors named in reviews.")

    st.markdown("---")

    # ── Defection review samples ──────────────────────────────────────────────
    st.markdown("### 📋 Defection Review Samples")
    st.caption("Reviews containing switching language - lowest rated first.")

    if not defection_reviews.empty:
        show_df = (defection_reviews
                   .sort_values("stars")[
                       ["stars", "date", "category",
                        "defection_signals", "competitor_mentions", "text"]
                   ]
                   .head(25)
                   .copy())
        show_df["date"]               = show_df["date"].astype(str).str[:10]
        show_df["defection_signals"]  = show_df["defection_signals"].apply(
            lambda x: ", ".join(x)
        )
        show_df["competitor_mentions"] = show_df["competitor_mentions"].apply(
            lambda x: ", ".join(x) if x else "-"
        )
        show_df["text"] = show_df["text"].str[:300]

        st.dataframe(
            show_df,
            column_config={
                "stars":               st.column_config.NumberColumn("⭐", width="small"),
                "date":                st.column_config.TextColumn("Date", width="small"),
                "category":            st.column_config.TextColumn("Category", width="medium"),
                "defection_signals":   st.column_config.TextColumn("Trigger Phrase", width="large"),
                "competitor_mentions": st.column_config.TextColumn("Competitor Named", width="medium"),
                "text":                st.column_config.TextColumn("Review", width="large"),
            },
            hide_index=True, width="stretch", height=420,
        )

    st.markdown("---")

    # ── AI Recovery Brief ─────────────────────────────────────────────────────
    st.markdown("### 🧠 AI Recovery Brief")
    st.caption(
        "Groq LLaMA analyzes defection patterns and writes an executive-ready "
        "recovery plan aligned with Nike's Return to Sport strategy."
    )

    if st.button("Generate Recovery Brief", type="primary"):
        try:
            client = get_groq_client()
        except ValueError as e:
            st.error(str(e))
            return

        top_cats     = cat_stats.head(3)["category"].tolist()
        sample_revs  = (defection_reviews
                        .nsmallest(20, "stars")["text"]
                        .tolist())
        review_text  = "\n".join([f"- {r[:250]}" for r in sample_revs])

        prompt = f"""You are a senior consumer insights analyst at Nike.
Nike's CEO Elliott Hill has tasked you with diagnosing and reversing consumer defection.

DATA SUMMARY:
- {n_defection} Nike reviews ({defection_pct:.1f}%) contain defection signals
- Highest-risk product categories: {', '.join(top_cats)}
- High-risk reviews (negative + switching language): {n_risk}

SAMPLE DEFECTION REVIEWS:
{review_text}

Write a concise executive recovery brief (4 short paragraphs) for Nike leadership:
1. Root causes - what product/experience failures are driving defection
2. Competitive threat - which competitor is benefiting most and why
3. Immediate actions - top 3 specific fixes Nike must prioritize
4. Strategic recommendation aligned with Nike's "Return to Sport" mission under Elliott Hill

Plain business English. Specific and data-driven. Under 250 words. No bullet points."""

        with st.spinner("AI analyzing defection patterns..."):
            resp = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=600,
            )
            brief = resp.choices[0].message.content.strip()

        st.markdown("#### Recovery Brief")
        st.info(brief)

        # ── Return to Sport Score ─────────────────────────────────────────────
        st.markdown("#### 🏃 Return to Sport Readiness Score")
        running_df = df[df["category"] == "Running"]
        if not running_df.empty:
            run_avg      = running_df["stars"].mean()
            run_pos      = (running_df["stars"] >= 4).mean()
            run_def_rate = running_df["is_defection"].mean()
            rts_score    = round(
                (run_avg / 5) * 50 + run_pos * 30 + (1 - run_def_rate) * 20, 1
            )
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Running Avg Rating",    f"{run_avg:.2f}⭐")
            r2.metric("Running Positive %",    f"{run_pos*100:.0f}%")
            r3.metric("Running Defection Rate", f"{run_def_rate*100:.1f}%")
            r4.metric("Return to Sport Score", f"{rts_score}/100",
                      delta="On track" if rts_score >= 70 else "Needs work",
                      delta_color="normal" if rts_score >= 70 else "inverse")
        else:
            st.info("Not enough running-specific reviews to compute Return to Sport score.")
