"""
Module 4 - Analyst Copilot
Powered by Groq LLaMA 3.3-70B (free, fast).
Sends a representative sample of reviews + full catalog context.
"""
import os, sys
import pandas as pd
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from config import REVIEWS_CSV, APP_NAME, GROQ_MODEL
from groq import Groq

def get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set.\n"
            "Get a free key at https://console.groq.com\n"
            "Add it to Streamlit Secrets: GROQ_API_KEY = 'your_key'"
        )
    return Groq(api_key=api_key)

def load_reviews() -> pd.DataFrame:
    if not os.path.exists(REVIEWS_CSV):
        return pd.DataFrame()
    df = pd.read_csv(REVIEWS_CSV)
    df["stars"] = pd.to_numeric(df["stars"], errors="coerce")
    return df

def load_merch_data() -> pd.DataFrame:
    try:
        from module5_merchandising.app import load_line_plan
        return load_line_plan()
    except Exception:
        return pd.DataFrame()

@st.cache_data(show_spinner=False)
def build_full_context() -> str:
    df = load_reviews()
    if df.empty:
        return ""

    total = len(df)
    avg   = df["stars"].mean() if df["stars"].notna().any() else 0

    lines = [
        f"CUSTOMER REVIEW DATASET - {APP_NAME}",
        "=" * 50,
        f"Total reviews: {total:,}",
        f"Average rating: {avg:.2f} / 5.0",
        "",
    ]

    # Rating distribution
    dist = df["stars"].value_counts().sort_index()
    lines.append("RATING DISTRIBUTION:")
    for k, v in dist.items():
        lines.append(f"  {int(k)} star: {int(v)} ({v/total*100:.1f}%)")
    lines.append("")

    # Version summary
    if "version" in df.columns and df["version"].notna().any():
        lines.append("VERSION PERFORMANCE:")
        va = (df.groupby("version")["stars"]
              .agg(avg="mean", count="count")
              .sort_values("avg")
              .reset_index())
        for _, row in va.iterrows():
            lines.append(f"  v{row['version']}: {row['avg']:.2f}⭐ ({row['count']} reviews)")
        lines.append("")

    # Location summary
    if "place_name" in df.columns and df["place_name"].notna().any():
        lines.append("LOCATION PERFORMANCE:")
        la = (df.groupby("place_name")["stars"]
              .agg(avg="mean", count="count")
              .sort_values("avg")
              .reset_index())
        for _, row in la.iterrows():
            lines.append(f"  {row['place_name']}: {row['avg']:.2f}⭐ ({row['count']} reviews)")
        lines.append("")

    # Sample reviews - stratified by star rating so all sentiments are covered
    lines.append("SAMPLE REVIEWS (stratified by rating):")
    lines.append("-" * 40)
    sample_frames = []
    for stars in [1, 2, 3, 4, 5]:
        bucket = df[df["stars"] == stars].dropna(subset=["text"])
        n = min(30, len(bucket))
        if n:
            sample_frames.append(bucket.sample(n, random_state=42))
    sample = pd.concat(sample_frames).sample(frac=1, random_state=42) if sample_frames else df.head(100)

    for _, row in sample.iterrows():
        stars   = row.get("stars", "")
        date    = str(row.get("date", ""))[:10]
        version = row.get("version", "")
        title   = row.get("title", "")
        text    = str(row.get("text", "")).strip()[:300]
        place   = row.get("place_name", "")
        meta = f"[{stars}⭐"
        if date:    meta += f" | {date}"
        if version: meta += f" | v{version}"
        if place:   meta += f" | {place}"
        meta += "]"
        lines.append(f"{meta} {title + ': ' if title else ''}{text}")

    # Merchandising data
    merch = load_merch_data()
    if not merch.empty:
        lines.append("\nNIKE PRODUCT CATALOG:")
        lines.append("-" * 40)
        lines.append(f"Total SKUs: {len(merch)}")
        price_col = "Retail Price ($)"
        if price_col in merch.columns and merch[price_col].notna().any():
            lines.append(f"Avg Retail Price: ${merch[price_col].mean():.2f}")
            most_common = merch[price_col].mode()
            if not most_common.empty:
                lines.append(f"Most Common Price: ${most_common.iloc[0]:.2f}")
        lines.append(f"New Launches: {(merch['Status']=='NEW').sum()}")
        lines.append(f"On Sale: {(merch['Status']=='SALE').sum()}")
        lines.append("")
        lines.append("FULL PRODUCT LIST:")
        for _, row in merch.iterrows():
            lines.append(
                f"SKU:{row.get('SKU / Product ID','')} | "
                f"{row.get('Product Name','')} | "
                f"{row.get('Colorway','')} | "
                f"{row.get('Category','')} | "
                f"${row.get(price_col,'')} | "
                f"{row.get('Status','')} | "
                f"{row.get('Gender','')}"
            )

    return "\n".join(lines)


def show():
    st.markdown("## 🤖 Analyst Copilot")
    st.markdown(
        f"Ask anything about **{APP_NAME}** reviews and product catalog. "
        f"Powered by **Groq LLaMA 3.3-70B** (free, fast)."
    )

    df = load_reviews()
    if df.empty:
        st.error("No review data found. Run the scraper workflow first.")
        return

    try:
        client = get_groq_client()
    except ValueError as e:
        st.error(str(e))
        return

    with st.spinner("Loading dataset into AI context..."):
        context = build_full_context()

    approx_tokens = len(context) // 4
    st.success(
        f"✅ AI has access to **{len(df):,} reviews** "
        f"(~{approx_tokens:,} tokens)"
    )

    st.markdown("### 💡 Try asking:")
    questions = [
        "What are the top 5 complaints across all reviews?",
        "Which app version caused the most negative reviews?",
        "What do customers love most?",
        "Which location has the worst ratings?",
        "How did sentiment change between versions?",
        "What percentage mention shipping issues?",
        "Summarize the biggest product quality complaints.",
        "Which Nike products are currently on sale?",
        "What is the most common price point in the catalog?",
        "Compare negative reviews from different locations.",
    ]
    cols = st.columns(4)
    for i, q in enumerate(questions):
        if cols[i % 4].button(q, key=f"q{i}"):
            st.session_state["pending"] = q

    st.markdown("---")

    if "history" not in st.session_state:
        st.session_state["history"] = []

    for msg in st.session_state["history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    pending  = st.session_state.pop("pending", "")
    user_in  = st.chat_input("Ask anything about reviews or products...")
    question = user_in or pending

    if question:
        with st.chat_message("user"):
            st.markdown(question)
        st.session_state["history"].append({"role": "user", "content": question})

        system = f"""You are an expert retail data analyst for {APP_NAME}.
You have access to the customer review dataset and product catalog below.
Be direct, specific, and use numbers. Under 200 words unless asked for detail.

{context}"""

        msgs = [{"role": "system", "content": system}]
        msgs += [{"role": m["role"], "content": m["content"]}
                 for m in st.session_state["history"][-6:]]

        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                try:
                    resp = client.chat.completions.create(
                        model=GROQ_MODEL,
                        messages=msgs,
                        temperature=0.3,
                        max_tokens=500,
                    )
                    answer = resp.choices[0].message.content.strip()
                except Exception as e:
                    answer = f"Error: {e}"
                st.markdown(answer)

        st.session_state["history"].append({"role": "assistant", "content": answer})

    if st.session_state.get("history"):
        if st.button("Clear conversation"):
            st.session_state["history"] = []
            st.rerun()

    with st.expander(f"🔍 View context sent to AI (~{approx_tokens:,} tokens)"):
        st.text(context[:5000] + "\n\n... [truncated for display]")
