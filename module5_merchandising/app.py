"""
Module 5 - Merchandising Line Plan
Pulls real Nike product catalog data via RapidAPI
Displays SKU-level line plan and exports formatted Excel
Mirrors the work of a Nike Merchandising Information Analyst
"""

import os
import sys
import json
import urllib.request
import urllib.parse
import pandas as pd
import plotly.express as px
import streamlit as st
from io import BytesIO

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")

CATEGORIES = {
    "Men's Shoes":    {"endpoint": "query-shoes-men",    "gender": "Men"},
    "Women's Shoes":  {"endpoint": "query-shoes-women",  "gender": "Women"},
}


def fetch_nike_products(endpoint: str, limit: int = 50) -> list:
    """Fetch Nike products from RapidAPI."""
    url = f"https://nike-products.p.rapidapi.com/{endpoint}?limit={limit}"
    req = urllib.request.Request(url, headers={
        "x-rapidapi-host": "nike-products.p.rapidapi.com",
        "x-rapidapi-key":  RAPIDAPI_KEY,
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as ex:
        st.error(f"API error: {ex}")
        return []


def parse_products(raw: list, gender: str) -> list:
    """Parse raw API response into flat product rows."""
    rows = []
    for p in raw:
        # Handle both list and dict response formats
        if isinstance(p, dict):
            pid        = p.get("id", p.get("productId", ""))
            title      = p.get("title", p.get("name", ""))
            subtitle   = p.get("subtitle", p.get("subTitle", ""))
            price      = p.get("price", {})
            if isinstance(price, dict):
                retail_price = price.get("current", {}).get("value",
                               price.get("fullPrice", ""))
            else:
                retail_price = price

            colorway   = p.get("colorDescription", p.get("colorway", ""))
            category   = p.get("productType", p.get("category", ""))
            url        = p.get("url", p.get("pdpUrl", ""))
            is_new     = p.get("isNew", False)
            badge      = p.get("badge", "")
            status     = "NEW" if is_new else ("SALE" if badge == "Sale" else "ACTIVE")

            rows.append({
                "SKU / Product ID": pid,
                "Product Name":     title,
                "Subtitle":         subtitle,
                "Colorway":         colorway,
                "Gender":           gender,
                "Category":         category,
                "Retail Price ($)": retail_price,
                "Status":           status,
                "Badge":            badge,
                "URL":              url,
            })
    return rows


@st.cache_data(show_spinner=False, ttl=3600)
def load_line_plan() -> pd.DataFrame:
    """Load full line plan from API - cached for 1 hour."""
    all_rows = []
    for label, meta in CATEGORIES.items():
        raw   = fetch_nike_products(meta["endpoint"], limit=50)
        rows  = parse_products(raw, meta["gender"])
        all_rows.extend(rows)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    df["Retail Price ($)"] = pd.to_numeric(df["Retail Price ($)"], errors="coerce")
    return df


def export_excel(df: pd.DataFrame) -> BytesIO:
    """
    Export a formatted Excel file mimicking a Nike MIA line plan report.
    Includes:
    - Line Plan sheet (full SKU list)
    - Pivot: Price by Category
    - Pivot: Status Summary
    - Pivot: Gender Split
    """
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # ── Sheet 1: Full Line Plan ───────────────────────────────────────────
        df.to_excel(writer, sheet_name="Line Plan", index=False)

        ws = writer.sheets["Line Plan"]
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        # Header formatting
        header_fill   = PatternFill("solid", fgColor="111827")
        header_font   = Font(name="Arial", bold=True, color="FFFFFF", size=10)
        border_side   = Side(style="thin", color="D1D5DB")
        thin_border   = Border(left=border_side, right=border_side,
                               top=border_side, bottom=border_side)
        status_colors = {
            "NEW":    "D1FAE5",
            "SALE":   "FEE2E2",
            "ACTIVE": "EFF6FF",
        }

        for col_idx, col in enumerate(df.columns, 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill      = header_fill
            cell.font      = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center",
                                       wrap_text=True)
            cell.border    = thin_border
            ws.row_dimensions[1].height = 30

        # Data rows
        for row_idx, row in enumerate(df.itertuples(index=False), 2):
            status = getattr(row, "Status", "ACTIVE")
            row_fill = PatternFill("solid",
                                   fgColor=status_colors.get(status, "FFFFFF"))
            for col_idx in range(1, len(df.columns) + 1):
                cell        = ws.cell(row=row_idx, column=col_idx)
                cell.fill   = row_fill
                cell.font   = Font(name="Arial", size=9)
                cell.border = thin_border
                cell.alignment = Alignment(vertical="center", wrap_text=True)

        # Column widths
        col_widths = [20, 32, 20, 20, 10, 16, 14, 10, 12, 40]
        for i, w in enumerate(col_widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(df.columns))}{len(df)+1}"

        # ── Sheet 2: Price Analysis by Category ──────────────────────────────
        if "Category" in df.columns and "Retail Price ($)" in df.columns:
            price_pivot = (df.groupby("Category")["Retail Price ($)"]
                           .agg(Products="count", Avg_Price="mean",
                                Min_Price="min", Max_Price="max")
                           .round(2).reset_index())
            price_pivot.columns = ["Category", "# Products",
                                   "Avg Price ($)", "Min Price ($)", "Max Price ($)"]
            price_pivot.to_excel(writer, sheet_name="Price by Category", index=False)

            ws2 = writer.sheets["Price by Category"]
            for col_idx in range(1, len(price_pivot.columns) + 1):
                cell = ws2.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center")
            for i, w in enumerate([20, 12, 14, 14, 14], 1):
                ws2.column_dimensions[get_column_letter(i)].width = w

        # ── Sheet 3: Status Summary ───────────────────────────────────────────
        if "Status" in df.columns:
            status_pivot = (df.groupby(["Gender", "Status"])
                            .size().reset_index(name="Count"))
            status_pivot.to_excel(writer, sheet_name="Status Summary", index=False)

            ws3 = writer.sheets["Status Summary"]
            for col_idx in range(1, 4):
                cell = ws3.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center")
            for i, w in enumerate([14, 12, 10], 1):
                ws3.column_dimensions[get_column_letter(i)].width = w

        # ── Sheet 4: Gender Split ─────────────────────────────────────────────
        if "Gender" in df.columns and "Retail Price ($)" in df.columns:
            gender_pivot = (df.groupby("Gender")
                            .agg(Products=("SKU / Product ID", "count"),
                                 Avg_Price=("Retail Price ($)", "mean"))
                            .round(2).reset_index())
            gender_pivot.columns = ["Gender", "# Products", "Avg Price ($)"]
            gender_pivot.to_excel(writer, sheet_name="Gender Split", index=False)

            ws4 = writer.sheets["Gender Split"]
            for col_idx in range(1, 4):
                cell = ws4.cell(row=1, column=col_idx)
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center")

    output.seek(0)
    return output


def show():
    st.markdown("## 📋 Merchandising Line Plan")
    st.markdown(
        "Real Nike product catalog - SKU-level line plan with pricing, "
        "status, and assortment analysis. Export to Excel for stakeholder reporting."
    )

    if not RAPIDAPI_KEY:
        st.error(
            "RAPIDAPI_KEY not set.\n\n"
            "Add it to Streamlit Secrets:\n"
            "```toml\nRAPIDAKEY = 'your_key_here'\n```"
        )
        return

    # ── Load data ─────────────────────────────────────────────────────────────
    with st.spinner("Fetching live Nike product catalog..."):
        df = load_line_plan()

    if df.empty:
        st.error("No product data returned. Check your RapidAPI key and subscription.")
        return

    # ── KPIs ──────────────────────────────────────────────────────────────────
    total_skus   = len(df)
    avg_price    = df["Retail Price ($)"].mean() if "Retail Price ($)" in df.columns else 0
    new_count    = (df["Status"] == "NEW").sum() if "Status" in df.columns else 0
    sale_count   = (df["Status"] == "SALE").sum() if "Status" in df.columns else 0
    categories   = df["Category"].nunique() if "Category" in df.columns else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total SKUs",    total_skus)
    c2.metric("Avg Retail $",  f"${avg_price:.2f}")
    c3.metric("New Launches",  new_count)
    c4.metric("On Sale",       sale_count)
    c5.metric("Categories",    categories)

    st.markdown("---")

    # ── Sidebar filters ───────────────────────────────────────────────────────
    st.sidebar.markdown("### 📋 Line Plan Filters")

    if "Gender" in df.columns:
        genders = ["All"] + sorted(df["Gender"].dropna().unique().tolist())
        sel_gender = st.sidebar.selectbox("Gender", genders)

    if "Category" in df.columns:
        cats = ["All"] + sorted(df["Category"].dropna().unique().tolist())
        sel_cat = st.sidebar.selectbox("Category", cats)

    if "Status" in df.columns:
        statuses = ["All"] + sorted(df["Status"].dropna().unique().tolist())
        sel_status = st.sidebar.selectbox("Status", statuses)

    price_min = float(df["Retail Price ($)"].min()) if "Retail Price ($)" in df.columns else 0
    price_max = float(df["Retail Price ($)"].max()) if "Retail Price ($)" in df.columns else 500
    price_range = st.sidebar.slider(
        "Price Range ($)",
        min_value=price_min,
        max_value=price_max,
        value=(price_min, price_max),
    )

    # Apply filters
    filtered = df.copy()
    if sel_gender != "All" and "Gender" in filtered.columns:
        filtered = filtered[filtered["Gender"] == sel_gender]
    if sel_cat != "All" and "Category" in filtered.columns:
        filtered = filtered[filtered["Category"] == sel_cat]
    if sel_status != "All" and "Status" in filtered.columns:
        filtered = filtered[filtered["Status"] == sel_status]
    if "Retail Price ($)" in filtered.columns:
        filtered = filtered[
            filtered["Retail Price ($)"].between(price_range[0], price_range[1])
        ]

    # ── Line Plan Table ───────────────────────────────────────────────────────
    st.markdown(f"### 🗂️ Line Plan - {len(filtered)} SKUs")
    st.caption("Live Nike product data · Color coded: 🟢 New · 🔴 Sale · ⬜ Active")

    display_cols = [c for c in [
        "SKU / Product ID", "Product Name", "Subtitle",
        "Colorway", "Gender", "Category", "Retail Price ($)", "Status"
    ] if c in filtered.columns]

    st.dataframe(
        filtered[display_cols],
        column_config={
            "SKU / Product ID": st.column_config.TextColumn("SKU / Product ID", width="medium"),
            "Product Name":     st.column_config.TextColumn("Product Name", width="large"),
            "Retail Price ($)": st.column_config.NumberColumn("Retail Price ($)", format="$%.2f"),
            "Status":           st.column_config.TextColumn("Status", width="small"),
        },
        use_container_width=True,
        hide_index=True,
        height=450,
    )

    # ── Charts ────────────────────────────────────────────────────────────────
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 💰 Price Distribution by Category")
        if "Category" in filtered.columns and "Retail Price ($)" in filtered.columns:
            cat_price = (filtered.groupby("Category")["Retail Price ($)"]
                         .mean().sort_values(ascending=False).reset_index())
            cat_price.columns = ["Category", "Avg Price"]
            cat_price["Avg Price"] = cat_price["Avg Price"].round(2)
            fig = px.bar(cat_price, x="Avg Price", y="Category",
                         orientation="h",
                         color="Avg Price",
                         color_continuous_scale=["#60a5fa", "#1D9E75"],
                         text="Avg Price")
            fig.update_traces(texttemplate="$%{text:.0f}", textposition="outside")
            fig.update_layout(height=300, margin=dict(l=0, r=60, t=10, b=0),
                              plot_bgcolor="rgba(0,0,0,0)",
                              paper_bgcolor="rgba(0,0,0,0)",
                              coloraxis_showscale=False, yaxis_title="")
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### 📊 Assortment by Status")
        if "Status" in filtered.columns:
            status_counts = filtered["Status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]
            colors = {"NEW": "#1D9E75", "ACTIVE": "#60a5fa", "SALE": "#E24B4A"}
            fig2 = px.pie(status_counts, names="Status", values="Count",
                          color="Status", color_discrete_map=colors,
                          hole=0.4)
            fig2.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0),
                               paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig2, use_container_width=True)

    # ── Gender split ──────────────────────────────────────────────────────────
    if "Gender" in filtered.columns and "Retail Price ($)" in filtered.columns:
        st.markdown("### 👥 Gender Assortment Analysis")
        g1, g2, g3 = st.columns(3)
        for gender in filtered["Gender"].unique():
            sub = filtered[filtered["Gender"] == gender]
            with (g1 if gender == "Men" else g2):
                st.metric(f"{gender} SKUs", len(sub),
                          f"Avg ${sub['Retail Price ($)'].mean():.0f}")

    # ── Price band analysis ───────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🏷️ Price Band Analysis")
    st.caption("Assortment distribution across price tiers - key for line plan strategy")

    if "Retail Price ($)" in filtered.columns:
        bins   = [0, 50, 100, 150, 200, 999]
        labels = ["Under $50", "$50–$100", "$100–$150", "$150–$200", "$200+"]
        filtered["Price Band"] = pd.cut(filtered["Retail Price ($)"],
                                         bins=bins, labels=labels)
        band_counts = filtered["Price Band"].value_counts().sort_index().reset_index()
        band_counts.columns = ["Price Band", "SKUs"]

        fig3 = px.bar(band_counts, x="Price Band", y="SKUs",
                      color="SKUs",
                      color_continuous_scale=["#60a5fa", "#1D9E75"],
                      text="SKUs")
        fig3.update_traces(textposition="outside")
        fig3.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0),
                           plot_bgcolor="rgba(0,0,0,0)",
                           paper_bgcolor="rgba(0,0,0,0)",
                           coloraxis_showscale=False)
        st.plotly_chart(fig3, use_container_width=True)

    # ── Excel Export ──────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📥 Export Line Plan Report")
    st.caption(
        "Download a formatted Excel workbook with 4 sheets: "
        "Full Line Plan · Price by Category · Status Summary · Gender Split"
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Generate Excel Report", type="primary"):
            with st.spinner("Building Excel report..."):
                excel_data = export_excel(filtered)
            st.download_button(
                label="📥 Download Line Plan.xlsx",
                data=excel_data,
                file_name="Nike_Line_Plan_Report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    with col2:
        st.info(
            "**What's in the Excel:**\n"
            "- **Line Plan** - Full SKU list with pricing, colorway, status, color coded\n"
            "- **Price by Category** - Average, min, max pricing per category\n"
            "- **Status Summary** - New vs Active vs Sale by gender\n"
            "- **Gender Split** - Men vs Women assortment breakdown"
        )
