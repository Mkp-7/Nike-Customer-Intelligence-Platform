"""
Voice of Customer AI engine - Groq/LLaMA
"""
import os, json
import pandas as pd
from groq import Groq
from dotenv import load_dotenv

load_dotenv()


def get_groq_client() -> Groq:
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set.\n"
            "Get a free key at https://console.groq.com\n"
            "Add it to Streamlit Secrets: GROQ_API_KEY = 'your_key'"
        )
    return Groq(api_key=api_key)


def cluster_themes(reviews_sample: list, client: Groq, industry: str = "athletic footwear") -> dict:
    numbered = "\n".join([f"[{i+1}] {r[:300]}" for i, r in enumerate(reviews_sample)])
    prompt = f"""You are analyzing customer reviews for a {industry} company.

Here are {len(reviews_sample)} customer reviews:

{numbered}

Identify the TOP 6 recurring themes. For each theme respond with:
- name: short label (3-5 words)
- description: what customers say (1 sentence)
- percent: estimated % of reviews mentioning it (integer)
- sentiment: exactly one of: positive, negative, mixed
- example_quote: one representative phrase under 15 words

Respond ONLY in this JSON format, no other text:
{{
  "themes": [
    {{
      "name": "...",
      "description": "...",
      "percent": 0,
      "sentiment": "positive",
      "example_quote": "..."
    }}
  ]
}}"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1000,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"themes": [], "error": "Parse error", "raw": raw}


def detect_anomalies(df: pd.DataFrame, threshold: float = 0.4) -> pd.DataFrame:
    df = df.copy()
    df["stars"] = pd.to_numeric(df["stars"], errors="coerce")
    df = df.dropna(subset=["stars"])
    if df.empty:
        return pd.DataFrame()

    loc_col = "place_name" if "place_name" in df.columns else (
              "business_id" if "business_id" in df.columns else None)
    if loc_col is None:
        return pd.DataFrame()

    df = df[df[loc_col].fillna("").str.strip() != ""]
    if df.empty:
        return pd.DataFrame()

    group_cols = [loc_col]
    if "brand_id" in df.columns:
        group_cols = ["brand_id", loc_col]

    loc_agg = (
        df.groupby(group_cols)["stars"]
        .agg(avg_rating="mean", total_reviews="count")
        .reset_index()
        .rename(columns={loc_col: "business_id"})
    )

    if "brand_id" in df.columns:
        brand_avgs = df.groupby("brand_id")["stars"].mean().rename("brand_avg")
        loc_agg = loc_agg.merge(brand_avgs, on="brand_id", how="left")
    else:
        loc_agg["brand_avg"] = df["stars"].mean()

    loc_agg["brand_avg"]      = loc_agg["brand_avg"].round(2)
    loc_agg["rating_drop"]    = (loc_agg["brand_avg"] - loc_agg["avg_rating"]).round(2)
    loc_agg["historical_avg"] = loc_agg["brand_avg"]
    loc_agg["recent_avg"]     = loc_agg["avg_rating"].round(2)
    loc_agg["recent_reviews"] = loc_agg["total_reviews"]

    anomalies = loc_agg[
        (loc_agg["rating_drop"] >= threshold) &
        (loc_agg["total_reviews"] >= 2)
    ].copy()
    return anomalies.sort_values("rating_drop", ascending=False)


def write_exec_summary(themes, anomaly_stores, total_reviews, avg_rating,
                       date_range, client, brand_name="Nike") -> str:
    themes_text = ""
    for t in themes[:5]:
        themes_text += f"- {t['name']} ({t['percent']}%, {t['sentiment']}): {t['description']}\n"

    anomaly_text = ""
    if not anomaly_stores.empty:
        for _, row in anomaly_stores.head(3).iterrows():
            loc = row.get("city", row.get("business_id", "Unknown"))
            anomaly_text += (f"- {loc}: {row['recent_avg']:.1f}⭐ "
                             f"(brand avg: {row['historical_avg']:.1f}⭐, gap: -{row['rating_drop']:.1f})\n")
    else:
        anomaly_text = "No locations significantly below brand average.\n"

    prompt = f"""You are writing a weekly executive summary for the VP of Consumer Insights at {brand_name}.

DATA:
- Period: {date_range}
- Reviews analyzed: {total_reviews:,}
- Average rating: {avg_rating:.2f} / 5.0

TOP THEMES:
{themes_text}

LOCATIONS NEEDING ATTENTION:
{anomaly_text}

Write a concise executive summary (3-4 short paragraphs):
1. Overall customer experience headline
2. Most important theme finding
3. Location anomalies as action items
4. One specific recommendation

Plain business English. No bullet points. No headers. Under 200 words."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=400,
    )
    return response.choices[0].message.content.strip()
