"""
Module 2 - Store Pulse Map
Shows real store locations on a map when Google Maps data is available.
Falls back to version/trend analysis for App Store data.
"""

import os, sys
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
from config import REVIEWS_CSV, BUSINESSES_CSV, BRAND_NAME, SIGNIFICANT_DELTA_STARS


def load_data():
    if not os.path.exists(REVIEWS_CSV):
        return None
    df = pd.read_csv(REVIEWS_CSV)
    df["stars"] = pd.to_numeric(df["stars"], errors="coerce")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df


def has_location_data(df):
    """Check if we have real lat/lon data from Google Maps."""
    return (
        "latitude" in df.columns and
        "longitude" in df.columns and
        df["latitude"].notna().any() and
        df["longitude"].notna().any() and
        df["latitude"].astype(str).str.strip().ne("").any()
    )


def build_location_stats(df):
    """Aggregate reviews by location, compute peer benchmarking."""
    df = df.copy()
    df["latitude"]  = pd.to_numeric(df["latitude"],  errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude", "stars"])

    agg = (df.groupby(["place_name", "address", "city", "state", "latitude", "longitude",
                        "google_rating", "total_reviews_at_location"])
              .agg(avg_rating=("stars", "mean"),
                   review_count=("stars", "count"),
                   pct_negative=("stars", lambda x: (x <= 2).mean() * 100))
              .reset_index())

    agg["avg_rating"] = agg["avg_rating"].round(2)
    agg["pct_negative"] = agg["pct_negative"].round(1)

    # Peer benchmark by state
    if "state" in agg.columns and agg["state"].notna().any():
        agg["peer_avg"] = agg.groupby("state")["avg_rating"].transform("mean").round(2)
    else:
        agg["peer_avg"] = agg["avg_rating"].mean().round(2)

    agg["vs_peer"] = (agg["avg_rating"] - agg["peer_avg"]).round(2)

    delta = SIGNIFICANT_DELTA_STARS
    def status(d):
        if d >= delta:  return "Above Peer"
        if d <= -delta: return "Below Peer"
        return "On Par"

    agg["status"] = agg["vs_peer"].apply(status)
    agg["label"]  = (agg["place_name"] + "<br>" +
                     agg["address"].fillna("") + "<br>" +
                     agg["city"].fillna("") + ", " + agg["state"].fillna(""))

    return agg


def show_location_map(df):
    """Full geographic map with real store pins."""
    st.markdown("## 🗺️ Store Pulse Map")
    st.markdown(
        f"Every **{BRAND_NAME}** location benchmarked against its state peer group. "
        "🔴 Below peer · 🟡 On par · 🟢 Above peer"
    )

    locs = build_location_stats(df)

    if locs.empty:
        st.warning("No location data with valid coordinates found.")
        return

    # ── Sidebar filters ───────────────────────────────────────────────────────
    st.sidebar.markdown("### 🗺️ Map Filters")
    states = sorted(locs["state"].dropna().unique()) if "state" in locs.columns else []
    sel_states = st.sidebar.multiselect("States", options=states, default=states)
    sel_status = st.sidebar.multiselect(
        "Status", options=["Above Peer","On Par","Below Peer"],
        default=["Above Peer","On Par","Below Peer"]
    )
    min_rev = st.sidebar.slider("Min reviews per location", 1, 20, 1)

    mask = locs["status"].isin(sel_status) & (locs["review_count"] >= min_rev)
    if sel_states:
        mask &= locs["state"].isin(sel_states)
    filtered = locs[mask].copy()

    if filtered.empty:
        st.warning("No locations match current filters.")
        return

    # ── KPIs ──────────────────────────────────────────────────────────────────
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Locations",        len(filtered))
    c2.metric("Avg Rating",       f"{filtered['avg_rating'].mean():.2f} ⭐")
    c3.metric("Total Reviews",    f"{int(filtered['review_count'].sum()):,}")
    c4.metric("States Covered",   filtered["state"].nunique() if "state" in filtered.columns else "-")
    c5.metric("🔴 Below Peer",    int((filtered["status"]=="Below Peer").sum()))
    c6.metric("🟢 Above Peer",    int((filtered["status"]=="Above Peer").sum()))

    st.markdown("---")

    color_map = {"Above Peer":"#1D9E75","On Par":"#F59E0B","Below Peer":"#E24B4A"}

    # ── Map view toggle ───────────────────────────────────────────────────────
    view = st.sidebar.radio("Map view", ["📍 Individual pins","🔵 Cluster mode"], index=0)

    fig = go.Figure()
    for status_val, color in color_map.items():
        sub = filtered[filtered["status"] == status_val]
        if sub.empty:
            continue

        # Add slight jitter so overlapping pins separate
        np.random.seed(42)
        lat_j = sub["latitude"]  + np.random.uniform(-0.008, 0.008, len(sub))
        lon_j = sub["longitude"] + np.random.uniform(-0.008, 0.008, len(sub))

        marker_sizes = np.clip(8 + (sub["review_count"] / max(filtered["review_count"].max(), 1)) * 14, 8, 22)

        trace_kwargs = dict(
            lat=lat_j, lon=lon_j,
            mode="markers",
            marker=go.scattermapbox.Marker(size=marker_sizes, color=color, opacity=0.88),
            customdata=np.stack([
                sub["place_name"],
                sub["address"].fillna(""),
                sub["city"].fillna(""),
                sub["state"].fillna(""),
                sub["avg_rating"],
                sub["peer_avg"],
                sub["vs_peer"],
                sub["review_count"],
                sub["pct_negative"],
            ], axis=-1),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "%{customdata[1]}<br>"
                "%{customdata[2]}, %{customdata[3]}<br>"
                "──────────────────<br>"
                "⭐ Rating:       <b>%{customdata[4]:.2f}</b><br>"
                "📊 State avg:    %{customdata[5]:.2f}<br>"
                "📈 vs Peers:     <b>%{customdata[6]:+.2f}</b><br>"
                "💬 Reviews:      %{customdata[7]}<br>"
                "👎 Negative:     %{customdata[8]:.1f}%%"
                "<extra></extra>"
            ),
            name=status_val,
        )

        if "Cluster" in view:
            trace_kwargs["cluster"] = dict(enabled=True, color=color, size=20, step=3)

        fig.add_trace(go.Scattermapbox(**trace_kwargs))

    # Auto-center on data
    center_lat = filtered["latitude"].mean()
    center_lon = filtered["longitude"].mean()

    fig.update_layout(
        mapbox_style="carto-positron",
        mapbox_zoom=4,
        mapbox_center={"lat": center_lat, "lon": center_lon},
        height=560,
        margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(title="vs State Peers", bgcolor="rgba(255,255,255,0.9)"),
        dragmode="zoom",
    )
    st.plotly_chart(fig, use_container_width=True, config={
        "scrollZoom": True,
        "displayModeBar": True,
        "modeBarButtonsToRemove": ["select2d","lasso2d"],
    })
    st.caption("💡 Scroll to zoom · Pins sized by review count · Hover for full address & rating details")

    # ── Attention table ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔴 Locations Needing Attention")
    st.caption("Stores furthest below their state peer average - priority calls this week.")

    bottom = (filtered[filtered["status"]=="Below Peer"]
              .sort_values("vs_peer")
              [["place_name","address","city","state","avg_rating","peer_avg","vs_peer","review_count","pct_negative"]]
              .head(15).copy())

    if bottom.empty:
        st.success("✅ No locations significantly below state peer group.")
    else:
        for col in ["avg_rating","peer_avg","vs_peer"]:
            bottom[col] = bottom[col].round(2)
        st.dataframe(bottom, column_config={
            "place_name":   st.column_config.TextColumn("Location"),
            "address":      st.column_config.TextColumn("Address"),
            "city":         st.column_config.TextColumn("City"),
            "state":        st.column_config.TextColumn("State"),
            "avg_rating":   st.column_config.NumberColumn("Rating ⭐", format="%.2f"),
            "peer_avg":     st.column_config.NumberColumn("State Avg ⭐", format="%.2f"),
            "vs_peer":      st.column_config.ProgressColumn("Gap vs Peers", min_value=-2, max_value=0, format="%.2f ⭐"),
            "review_count": st.column_config.NumberColumn("Reviews"),
            "pct_negative": st.column_config.NumberColumn("Negative %", format="%.1f%%"),
        }, use_container_width=True, hide_index=True)

    # ── Top performers ────────────────────────────────────────────────────────
    st.markdown("### 🟢 Top Performing Locations")
    top = (filtered[filtered["status"]=="Above Peer"]
           .sort_values("vs_peer", ascending=False)
           [["place_name","address","city","state","avg_rating","peer_avg","vs_peer","review_count"]]
           .head(15).copy())

    if top.empty:
        st.info("No locations significantly above peer group.")
    else:
        for col in ["avg_rating","peer_avg","vs_peer"]:
            top[col] = top[col].round(2)
        st.dataframe(top, column_config={
            "place_name":   st.column_config.TextColumn("Location"),
            "address":      st.column_config.TextColumn("Address"),
            "city":         st.column_config.TextColumn("City"),
            "state":        st.column_config.TextColumn("State"),
            "avg_rating":   st.column_config.NumberColumn("Rating ⭐", format="%.2f"),
            "peer_avg":     st.column_config.NumberColumn("State Avg ⭐", format="%.2f"),
            "vs_peer":      st.column_config.ProgressColumn("Gap vs Peers", min_value=0, max_value=2, format="+%.2f ⭐"),
            "review_count": st.column_config.NumberColumn("Reviews"),
        }, use_container_width=True, hide_index=True)

    # ── State bar chart ───────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 Average Rating by State")
    if "state" in filtered.columns and filtered["state"].notna().any():
        sa = (filtered.groupby("state")
              .agg(avg_rating=("avg_rating","mean"), locations=("place_name","count"))
              .sort_values("avg_rating", ascending=False).reset_index())
        sa["avg_rating"] = sa["avg_rating"].round(2)
        chain_avg = filtered["avg_rating"].mean()

        fig2 = px.bar(sa, x="state", y="avg_rating",
                      color="avg_rating",
                      color_continuous_scale=["#E24B4A","#F59E0B","#1D9E75"],
                      range_color=[2.0,5.0], text="avg_rating",
                      hover_data={"locations":True},
                      labels={"state":"State","avg_rating":"Avg Rating"})
        fig2.add_hline(y=chain_avg, line_dash="dot", line_color="#60a5fa",
                       annotation_text=f"Chain avg: {chain_avg:.2f} ⭐",
                       annotation_position="top right")
        fig2.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig2.update_layout(height=360, margin=dict(l=0,r=0,t=20,b=0),
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           coloraxis_showscale=False)
        st.plotly_chart(fig2, use_container_width=True)

    # ── Rating trend ──────────────────────────────────────────────────────────
    if "date" in df.columns and df["date"].notna().any():
        st.markdown("### 📈 Rating Trend Over Time")
        biz_ids = filtered["place_name"].tolist()
        rev_f   = df[df["place_name"].isin(biz_ids)].copy() if "place_name" in df.columns else df
        if not rev_f.empty:
            monthly = rev_f.set_index("date")["stars"].resample("ME").mean().reset_index()
            monthly.columns = ["Month","Avg Rating"]
            fig3 = px.line(monthly, x="Month", y="Avg Rating", line_shape="spline")
            fig3.update_traces(line_color="#60a5fa", line_width=2.5)
            fig3.update_layout(height=240, margin=dict(l=0,r=0,t=10,b=0),
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                               yaxis=dict(range=[1,5]))
            st.plotly_chart(fig3, use_container_width=True)


def show_version_trends(df):
    """Fallback for App Store data - version and time analysis."""
    st.markdown("## 📊 Version & Trend Intelligence")
    st.markdown(f"How **{BRAND_NAME}** ratings evolve across app versions and time.")

    total      = len(df)
    rated      = df.dropna(subset=["stars"])
    avg        = rated["stars"].mean() if len(rated) > 0 else 0
    pct_neg    = (rated["stars"] <= 2).mean() * 100 if len(rated) > 0 else 0
    pct_pos    = (rated["stars"] >= 4).mean() * 100 if len(rated) > 0 else 0
    versions   = df["version"].nunique() if "version" in df.columns else "-"

    try:
        if "date" in df.columns and df["date"].notna().any():
            latest = df["date"].max()
            recent = df[df["date"] >= latest - pd.Timedelta(days=30)]["stars"].mean()
            prior  = df[(df["date"] >= latest - pd.Timedelta(days=60)) &
                        (df["date"] <  latest - pd.Timedelta(days=30))]["stars"].mean()
            trend  = round(recent - prior, 2) if not (np.isnan(prior) or np.isnan(recent)) else 0
        else:
            trend = 0
    except Exception:
        trend = 0

    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.metric("Total Reviews",  f"{total:,}")
    c2.metric("Avg Rating",     f"{avg:.2f} ⭐")
    c3.metric("1-2 Star",       f"{pct_neg:.1f}%")
    c4.metric("4-5 Star",       f"{pct_pos:.1f}%")
    c5.metric("App Versions",   versions)
    c6.metric("30-day Trend",   f"{trend:+.2f} ⭐", delta=f"{trend:+.2f}")

    if "date" in df.columns and df["date"].notna().any():
        st.markdown("---")
        st.markdown("### 📈 Rating Trend Over Time")
        col1, col2 = st.columns([3,1])
        with col2:
            freq = st.selectbox("Interval", ["Weekly","Monthly"], index=1)
        rf = "W" if freq == "Weekly" else "ME"
        monthly = df.set_index("date")["stars"].resample(rf).mean().reset_index()
        monthly.columns = ["Period","Avg Rating"]
        monthly = monthly.dropna()
        fig = px.line(monthly, x="Period", y="Avg Rating", line_shape="spline")
        fig.update_traces(line_color="#60a5fa", line_width=2.5)
        fig.add_hline(y=avg, line_dash="dot", line_color="#94a3b8",
                      annotation_text=f"Overall avg: {avg:.2f}")
        fig.update_layout(height=280, margin=dict(l=0,r=0,t=10,b=0),
                          plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                          yaxis=dict(range=[1,5]))
        st.plotly_chart(fig, use_container_width=True, config={"scrollZoom":True})

    if "version" in df.columns and df["version"].notna().any() and df["version"].nunique() > 1:
        st.markdown("---")
        st.markdown("### 📱 Rating by App Version")
        va = (df.groupby("version")["stars"]
              .agg(avg_rating="mean", review_count="count")
              .reset_index())
        va = va[va["review_count"] >= 1].copy()
        va["avg_rating"] = va["avg_rating"].round(2)
        va = va.sort_values("avg_rating")

        fig2 = px.bar(va, x="avg_rating", y="version", orientation="h",
                      color="avg_rating",
                      color_continuous_scale=["#E24B4A","#F59E0B","#1D9E75"],
                      range_color=[1,5], text="avg_rating",
                      hover_data={"review_count":True})
        fig2.update_traces(texttemplate="%{text:.2f}", textposition="outside")
        fig2.update_layout(height=max(300, len(va)*35),
                           margin=dict(l=0,r=80,t=10,b=0),
                           plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                           coloraxis_showscale=False, yaxis_title="")
        st.plotly_chart(fig2, use_container_width=True)

        worst = va.nsmallest(5,"avg_rating")[["version","avg_rating","review_count"]]
        best  = va.nlargest(5,"avg_rating")[["version","avg_rating","review_count"]]
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**🔴 Lowest Rated Versions**")
            st.dataframe(worst, column_config={
                "avg_rating":   st.column_config.NumberColumn("Avg Rating ⭐", format="%.2f"),
                "review_count": st.column_config.NumberColumn("Reviews"),
            }, use_container_width=True, hide_index=True)
        with col2:
            st.markdown("**🟢 Highest Rated Versions**")
            st.dataframe(best, column_config={
                "avg_rating":   st.column_config.NumberColumn("Avg Rating ⭐", format="%.2f"),
                "review_count": st.column_config.NumberColumn("Reviews"),
            }, use_container_width=True, hide_index=True)


def show():
    df = load_data()
    if df is None or df.empty:
        st.error("No data found. Trigger the GitHub Actions workflow to scrape data.")
        return

    if has_location_data(df):
        show_location_map(df)
    else:
        show_version_trends(df)
