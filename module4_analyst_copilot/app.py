"""
Module 4 - Analyst Copilot
Powered by Gemini 1.5 Flash - 1 million token context window.
Sends ALL reviews + full merchandising catalog in one API call.
No sampling, no truncation - the AI sees everything.
"""

import os, sys
import pandas as pd
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from config import REVIEWS_CSV, APP_NAME, GROQ_MODEL

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")


def get_gemini_client():
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY not set.\n"
            "Get a free key at https://aistudio.google.com\n"
            "Add it to Streamlit Secrets: GEMINI_API_KEY = 'your_key'"
        )
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY)


def load_reviews() -> pd.DataFrame:
    if not os.path.exists(REVIEWS_CSV):
        return pd.DataFrame()
    df = pd.read_csv(REVIEWS_CSV)
    df["stars"] = pd.to_numeric(df["stars"], errors="coerce")
    return df


def load_merch_data() -> pd.DataFrame:
    """Try to load merchandising data if available."""
    try:
        sys.path.insert(0, BASE_DIR)
        from module5_merchandising.app import load_line_plan
        return load_line_plan()
    except Exception:
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def build_full_context() -> str:
    """
    Build complete context with ALL reviews + merchandising data.
    Gemini 1.5 Flash supports 1M tokens - no sampling needed.
    """
    df = load_reviews()
    if df.empty:
        return ""

    total = len(df)
    avg   = df["stars"].mean() if df["stars"].notna().any() else 0

    # ── Full review text ──────────────────────────────────────────────────────
    lines = [
        f"COMPLETE REVIEW DATASET - {APP_NAME}",
        f"=" * 50,
        f"Total reviews: {total:,}",
        f"Average rating: {avg:.2f} / 5.0",
        f"",
        f"ALL REVIEWS (complete, unsampled):",
        f"-" * 40,
    ]

    for _, row in df.iterrows():
        stars   = row.get("stars", "")
        date    = row.get("date", "")
        version = row.get("version", "")
        title   = row.get("title", "")
        text    = str(row.get("text", "")).strip()
        source  = row.get("source", "")
        place   = row.get("place_name", "")

        meta = f"[{stars}⭐"
        if date:    meta += f" | {str(date)[:10]}"
        if version: meta += f" | v{version}"
        if place:   meta += f" | {place}"
        if source:  meta += f" | {source}"
        meta += "]"

        if title:
            lines.append(f"{meta} {title}: {text}")
        else:
            lines.append(f"{meta} {text}")

    # ── Version summary ───────────────────────────────────────────────────────
    if "version" in df.columns and df["version"].notna().any():
        lines.append(f"\nVERSION PERFORMANCE SUMMARY:")
        lines.append("-" * 40)
        va = (df.groupby("version")["stars"]
              .agg(avg="mean", count="count")
              .sort_values("avg")
              .reset_index())
        for _, row in va.iterrows():
            lines.append(f"v{row['version']}: {row['avg']:.2f}⭐ ({row['count']} reviews)")

    # ── Location summary ──────────────────────────────────────────────────────
    if "place_name" in df.columns and df["place_name"].notna().any():
        lines.append(f"\nLOCATION PERFORMANCE SUMMARY:")
        lines.append("-" * 40)
        la = (df.groupby("place_name")["stars"]
              .agg(avg="mean", count="count")
              .sort_values("avg")
              .reset_index())
        for _, row in la.iterrows():
            lines.append(f"{row['place_name']}: {row['avg']:.2f}⭐ ({row['count']} reviews)")

    # ── Merchandising data ────────────────────────────────────────────────────
    merch = load_merch_data()
    if not merch.empty:
        lines.append(f"\nNIKE PRODUCT CATALOG (LIVE):")
        lines.append("-" * 40)
        lines.append(f"Total SKUs: {len(merch)}")
        lines.append(f"Avg Retail Price: ${merch['Retail Price ($)'].mean():.2f}")
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
                f"${row.get('Retail Price ($)','')} | "
                f"{row.get('Status','')} | "
                f"{row.get('Gender','')}"
            )

    return "\n".join(lines)


def ask_gemini(question: str, context: str, history: list) -> str:
    """Send question to Gemini with full context."""
    client = get_gemini_client()

    system = f"""You are an expert retail data analyst for {APP_NAME}.
You have access to the COMPLETE customer review dataset and live product catalog below.
Unlike typical AI assistants, you have access to ALL reviews - not just samples.

Use specific data from the reviews to answer questions accurately.
Be direct, specific, and use numbers. Under 200 words unless asked for detail.

{context}"""

    # Build conversation history
    messages = []
    for msg in history[-10:]:  # last 10 turns
        messages.append(msg["content"])

    full_prompt = system + "\n\nConversation so far:\n"
    for msg in history[-6:]:
        role = "User" if msg["role"] == "user" else "Assistant"
        full_prompt += f"\n{role}: {msg['content']}"
    full_prompt += f"\n\nUser: {question}\n\nAssistant:"

    from google.genai import types
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=full_prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=500,
            temperature=0.3,
        )
    )
    return response.text.strip()


def show():
    st.markdown("## 🤖 Analyst Copilot")
    st.markdown(
        f"Ask anything about **{APP_NAME}** reviews and product catalog. "
        f"Powered by **Gemini 1.5 Flash** - sees **all reviews**, not just samples."
    )

    # ── Load data ─────────────────────────────────────────────────────────────
    df = load_reviews()
    if df.empty:
        st.error("No review data found. Run the scraper workflow first.")
        return

    try:
        client = get_gemini_client()
    except ValueError as e:
        st.error(str(e))
        return

    # ── Build context ─────────────────────────────────────────────────────────
    with st.spinner("Loading complete dataset into AI context..."):
        context = build_full_context()

    total_chars = len(context)
    approx_tokens = total_chars // 4
    st.success(
        f"✅ AI has full access to **{len(df):,} reviews** "
        f"(~{approx_tokens:,} tokens - well within Gemini's 1M limit)"
    )

    # ── Suggested questions ───────────────────────────────────────────────────
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

    # ── Chat history ──────────────────────────────────────────────────────────
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

        with st.chat_message("assistant"):
            with st.spinner("Gemini analyzing all reviews..."):
                try:
                    answer = ask_gemini(
                        question, context,
                        st.session_state["history"]
                    )
                except Exception as e:
                    answer = f"Error: {e}"
                st.markdown(answer)

        st.session_state["history"].append({"role": "assistant", "content": answer})

    if st.session_state.get("history"):
        if st.button("Clear conversation"):
            st.session_state["history"] = []
            st.rerun()

    # ── Data context preview ──────────────────────────────────────────────────
    with st.expander(f"🔍 View full context sent to Gemini (~{approx_tokens:,} tokens)"):
        st.text(context[:5000] + "\n\n... [truncated for display - full context sent to AI]")
