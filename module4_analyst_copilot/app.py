"""
Module 4 - Analyst Copilot
Powered by Groq LLaMA 3.3-70B. Covers all brands + product catalog.
"""
import os, sys
import pandas as pd
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD_DIR  = os.path.join(BASE_DIR, "module1_voice_of_customer")
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, MOD_DIR)

from config import REVIEWS_CSV, APP_NAME, GROQ_MODEL, BRANDS, PRIMARY_BRAND_ID
from voc_analyzer import get_groq_client

BRAND_MAP = {b["brand_id"]: b["name"] for b in BRANDS}


@st.cache_data(show_spinner=False)
def build_context() -> str:
    if not os.path.exists(REVIEWS_CSV):
        return ""

    df = pd.read_csv(REVIEWS_CSV, parse_dates=["date"])
    df["stars"]      = pd.to_numeric(df["stars"], errors="coerce")
    df["brand_name"] = df["brand_id"].map(BRAND_MAP)
    df = df.dropna(subset=["stars"])

    total = len(df)
    avg   = df["stars"].mean()

    lines = [
        f"NIKE CONSUMER INTELLIGENCE PLATFORM - FULL DATASET",
        "=" * 50,
        f"Total reviews across all brands: {total:,}",
        f"Overall avg rating: {avg:.2f} / 5.0",
        "",
    ]

    # Per-brand summary
    lines.append("PER-BRAND BREAKDOWN:")
    for bid, bname in BRAND_MAP.items():
        bdf = df[df["brand_id"] == bid]
        if bdf.empty:
            continue
        b_avg = bdf["stars"].mean()
        b_pos = (bdf["stars"] >= 4).mean() * 100
        b_neg = (bdf["stars"] <= 2).mean() * 100
        lines.append(
            f"  {bname}: {len(bdf):,} reviews | avg {b_avg:.2f}⭐ | "
            f"{b_pos:.0f}% positive | {b_neg:.0f}% negative"
        )

    lines.append("")

    # Nike deep-dive
    nike_df = df[df["brand_id"] == PRIMARY_BRAND_ID]
    if not nike_df.empty:
        lines.append("NIKE RATING DISTRIBUTION:")
        dist = nike_df["stars"].value_counts().sort_index()
        for k, v in dist.items():
            lines.append(f"  {int(k)}⭐: {int(v)} ({v/len(nike_df)*100:.1f}%)")
        lines.append("")

        if "version" in nike_df.columns and nike_df["version"].notna().any():
            lines.append("NIKE APP VERSION PERFORMANCE:")
            va = (nike_df.groupby("version")["stars"]
                  .agg(avg="mean", count="count")
                  .sort_values("avg")
                  .reset_index())
            for _, row in va.iterrows():
                lines.append(f"  v{row['version']}: {row['avg']:.2f}⭐ ({row['count']} reviews)")
            lines.append("")

        if "state" in nike_df.columns:
            nike_loc = nike_df[nike_df["state"].fillna("").str.strip() != ""]
            if not nike_loc.empty:
                lines.append("NIKE PERFORMANCE BY STATE (top/bottom 5):")
                sa = (nike_loc.groupby("state")["stars"]
                      .agg(avg="mean", count="count")
                      .sort_values("avg")
                      .reset_index())
                for _, row in sa.head(5).iterrows():
                    lines.append(f"  ⬇ {row['state']}: {row['avg']:.2f}⭐ ({row['count']})")
                for _, row in sa.tail(5).iloc[::-1].iterrows():
                    lines.append(f"  ⬆ {row['state']}: {row['avg']:.2f}⭐ ({row['count']})")
                lines.append("")

    # Sample reviews - stratified
    lines.append("SAMPLE NIKE REVIEWS (stratified by rating):")
    lines.append("-" * 40)
    sample_parts = []
    for s in [1, 2, 3, 4, 5]:
        bucket = nike_df[nike_df["stars"] == s].dropna(subset=["text"])
        n = min(25, len(bucket))
        if n:
            sample_parts.append(bucket.sample(n, random_state=42))
    if sample_parts:
        sample = pd.concat(sample_parts).sample(frac=1, random_state=42)
        for _, row in sample.iterrows():
            stars   = row.get("stars", "")
            date    = str(row.get("date", ""))[:10]
            version = row.get("version", "")
            title   = str(row.get("title", ""))
            text    = str(row.get("text", "")).strip()[:300]
            meta    = f"[{stars}⭐ | {date}"
            if version: meta += f" | v{version}"
            meta   += "]"
            lines.append(f"{meta} {(title + ': ') if title else ''}{text}")

    # Merchandising
    try:
        sys.path.insert(0, BASE_DIR)
        from module5_merchandising.app import load_line_plan
        merch = load_line_plan()
        if not merch.empty:
            price_col = "Retail Price ($)"
            lines.append("\nNIKE PRODUCT CATALOG:")
            lines.append(f"  Total SKUs: {len(merch)}")
            if price_col in merch.columns and merch[price_col].notna().any():
                lines.append(f"  Avg price: ${merch[price_col].mean():.2f}")
                mc = merch[price_col].mode()
                if not mc.empty:
                    lines.append(f"  Most common price: ${mc.iloc[0]:.2f}")
            lines.append(f"  New: {(merch['Status']=='NEW').sum()} | "
                         f"Sale: {(merch['Status']=='SALE').sum()} | "
                         f"Out of stock: {(merch['Status']=='OUT OF STOCK').sum()}")
            lines.append("")
            for _, row in merch.iterrows():
                lines.append(
                    f"  SKU:{row.get('SKU / Product ID','')} | "
                    f"{row.get('Product Name','')} | "
                    f"{row.get('Category','')} | "
                    f"${row.get(price_col,'')} | "
                    f"{row.get('Status','')} | "
                    f"{row.get('Gender','')}"
                )
    except Exception:
        pass

    return "\n".join(lines)


def show():
    st.markdown("## 🤖 Analyst Copilot")
    st.markdown(
        f"Ask anything about **{APP_NAME}** reviews, competitive landscape, "
        f"and product catalog. Powered by **Groq LLaMA 3.3-70B**."
    )

    if not os.path.exists(REVIEWS_CSV):
        st.error("No review data. Run scraper first.")
        return

    try:
        client = get_groq_client()
    except ValueError as e:
        st.error(str(e))
        return

    with st.spinner("Loading full dataset into AI context..."):
        context = build_context()

    approx_tokens = len(context) // 4
    st.success(f"✅ AI context ready (~{approx_tokens:,} tokens)")

    st.markdown("### 💡 Try asking:")
    questions = [
        "What are the top 5 complaints in Nike reviews?",
        "How does Nike's rating compare to On Running?",
        "Which app version caused the most issues?",
        "What do customers love most about Nike?",
        "Which states have the worst Nike store ratings?",
        "Which Nike products are currently on sale?",
        "What is the most common price point?",
        "Are customers switching to HOKA or On Running?",
        "Summarize Nike's biggest quality complaints.",
        "What should Nike fix first based on this data?",
    ]
    cols = st.columns(4)
    for i, q in enumerate(questions):
        if cols[i % 4].button(q, key=f"q{i}"):
            st.session_state["copilot_pending"] = q

    st.markdown("---")

    if "copilot_history" not in st.session_state:
        st.session_state["copilot_history"] = []

    for msg in st.session_state["copilot_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    pending  = st.session_state.pop("copilot_pending", "")
    user_in  = st.chat_input("Ask anything about Nike, competitors, or products...")
    question = user_in or pending

    if question:
        with st.chat_message("user"):
            st.markdown(question)
        st.session_state["copilot_history"].append({"role": "user", "content": question})

        system = f"""You are an expert retail data analyst for Nike.
You have access to the full consumer intelligence dataset below - Nike reviews,
competitor benchmarks, and product catalog. Be direct, specific, and use numbers.
Under 200 words unless asked for more detail.

{context}"""

        msgs = [{"role": "system", "content": system}]
        msgs += [{"role": m["role"], "content": m["content"]}
                 for m in st.session_state["copilot_history"][-6:]]

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

        st.session_state["copilot_history"].append(
            {"role": "assistant", "content": answer}
        )

    if st.session_state.get("copilot_history"):
        if st.button("Clear conversation"):
            st.session_state["copilot_history"] = []
            st.rerun()

    with st.expander(f"🔍 View AI context (~{approx_tokens:,} tokens)"):
        st.text(context[:5000] + "\n\n... [truncated for display]")
