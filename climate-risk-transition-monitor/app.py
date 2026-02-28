"""
app.py
------
Streamlit dashboard for climate transition risk analysis.
NGFS Phase V scenarios · IFRS S2 aligned · TCFD framework

Run: streamlit run app.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

from src.ngfs_loader import NGFSLoader, CARBON_PRICE_PATHS
from src.sector_mapper import SECTOR_TRANSITION_RISK_BASE, sector_summary_table
from src.transition_scorer import TransitionScorer, HORIZON_YEARS
from src.portfolio_analyzer import PortfolioAnalyzer
from src.reporter import GHGReporter, RISK_COLORS

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Climate Transition Risk Monitor",
    page_icon="🌡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.metric-card {
    background: #1e2d3d; border-radius: 10px; padding: 20px;
    text-align: center; margin: 4px;
}
.metric-value { font-size: 32px; font-weight: 700; color: #e8f4f8; }
.metric-label { font-size: 12px; color: #7f8c8d; text-transform: uppercase; }
.risk-badge-high { background: #e74c3c; color: white; padding: 2px 10px;
                   border-radius: 12px; font-size: 12px; }
.risk-badge-med  { background: #f39c12; color: white; padding: 2px 10px;
                   border-radius: 12px; font-size: 12px; }
.risk-badge-low  { background: #2ecc71; color: white; padding: 2px 10px;
                   border-radius: 12px; font-size: 12px; }
</style>
""", unsafe_allow_html=True)


# ── Data loading (cached) ─────────────────────────────────────────────────────
@st.cache_data
def load_data():
    loader = NGFSLoader()
    ngfs_data = loader.load()
    scorer = TransitionScorer(ngfs_data=ngfs_data)
    return ngfs_data, scorer


@st.cache_data
def run_portfolio_analysis():
    ngfs_data, scorer = load_data()
    analyzer = PortfolioAnalyzer(ngfs_data=ngfs_data)
    result = analyzer.analyze()
    return result, analyzer


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚙️ Controls")
    st.markdown("---")

    st.subheader("Scenario Selection")
    all_scenarios = [
        "Net Zero 2050",
        "Below 2°C",
        "Delayed Transition",
        "Current Policies",
        "Nationally Determined Contributions (NDCs)",
    ]
    selected_scenarios = st.multiselect(
        "NGFS Scenarios",
        all_scenarios,
        default=["Net Zero 2050", "Delayed Transition", "Current Policies"],
    )
    if not selected_scenarios:
        selected_scenarios = ["Net Zero 2050", "Current Policies"]

    st.subheader("Analysis Parameters")
    selected_horizon = st.selectbox(
        "Time Horizon",
        ["short (2030)", "medium (2040)", "long (2050)"],
        index=1,
    )
    horizon_key = selected_horizon.split(" ")[0]
    horizon_year = HORIZON_YEARS[horizon_key]

    show_uncertainty = st.checkbox("Show uncertainty bands", value=True)

    st.subheader("What-If Analysis")
    sbti_pct = st.slider(
        "SBTi Adoption Rate (%)",
        min_value=0, max_value=100, value=30, step=5,
    )

    st.markdown("---")
    st.subheader("📚 Data Sources")
    st.markdown("""
    **Scenarios:** [NGFS Phase V](https://www.ngfs.net/ngfs-scenarios-portal/data-resources/) (Nov 2024)

    **Framework:** [IFRS S2](https://www.ifrs.org/issued-standards/) · [TCFD](https://www.fsb-tcfd.org/)

    **Methodology:** [Battiston et al. 2017](https://doi.org/10.1038/nclimate3255) · IPCC AR6 WG3
    """)


# ── Main content ──────────────────────────────────────────────────────────────
st.title("🌡️ Climate Transition Risk Monitor")
st.markdown(
    "**NGFS Phase V · IFRS S2 Aligned · Latin American Portfolio Context**"
)
st.markdown("---")

# Load data
ngfs_data, scorer = load_data()
result, analyzer = run_portfolio_analysis()

# ── KPI Row ───────────────────────────────────────────────────────────────────
col1, col2, col3, col4, col5 = st.columns(5)

nz_trei = result.portfolio_trei.get("Net Zero 2050", {}).get("medium", 0)
cp_trei = result.portfolio_trei.get("Current Policies", {}).get("medium", 0)
ndc_trei = result.portfolio_trei.get(
    "Nationally Determined Contributions (NDCs)", {}
).get("medium", 0)

with col1:
    st.metric("Companies", result.n_companies, f"{result.coverage_pct:.0f}% mapped")
with col2:
    st.metric("TREI — NZ2050", f"{nz_trei:.1f}", delta=None)
with col3:
    st.metric("TREI — NDC", f"{ndc_trei:.1f}", delta=None)
with col4:
    st.metric("TREI — Current Policies", f"{cp_trei:.1f}", delta=None)
with col5:
    st.metric(
        "SBTi-Aligned",
        f"{result.sbti_pct:.0f}%",
        delta=f"+{sbti_pct - result.sbti_pct:.0f}pp target",
    )

st.markdown("---")

# ── Tab layout ────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Scenario Analysis",
    "🏭 Sector Heatmap",
    "💼 Portfolio",
    "🔄 What-If",
    "📋 IFRS S2 Robustness",
])

# ── Tab 1: Scenario Analysis ──────────────────────────────────────────────────
with tab1:
    st.subheader("TREI by Scenario and Time Horizon")
    st.caption("Transition Risk Exposure Index (0–100). Higher = greater financial exposure to climate transition.")

    # Build bar chart: scenarios × horizons
    chart_data = []
    for scenario in selected_scenarios:
        for h_label, h_key in [("2030", "short"), ("2040", "medium"), ("2050", "long")]:
            val = result.portfolio_trei.get(scenario, {}).get(h_key, 0)
            chart_data.append({
                "Scenario": scenario.replace(
                    "Nationally Determined Contributions (NDCs)", "NDCs"
                ),
                "Year": h_label,
                "TREI": val,
            })

    df_chart = pd.DataFrame(chart_data)
    fig_bar = px.bar(
        df_chart, x="Scenario", y="TREI", color="Year",
        barmode="group",
        color_discrete_sequence=["#3498db", "#e67e22", "#e74c3c"],
        title=f"Portfolio TREI by Scenario and Horizon",
    )
    fig_bar.update_layout(
        plot_bgcolor="#1e2d3d", paper_bgcolor="#1e2d3d",
        font_color="#e8f4f8", legend_title="Horizon",
        yaxis=dict(range=[0, 100], gridcolor="#2c3e50"),
        xaxis=dict(gridcolor="#2c3e50"),
    )
    fig_bar.add_hline(y=60, line_dash="dash", line_color="#e74c3c",
                      annotation_text="High risk threshold")
    st.plotly_chart(fig_bar, use_container_width=True)

    # Carbon price trajectories
    st.subheader("Shadow Carbon Price Trajectories (NGFS Phase V)")
    years = [2025, 2030, 2035, 2040, 2045, 2050]
    fig_price = go.Figure()
    colors_map = {
        "Net Zero 2050": "#e74c3c",
        "Below 2°C": "#e67e22",
        "Delayed Transition": "#f39c12",
        "Current Policies": "#3498db",
        "Nationally Determined Contributions (NDCs)": "#2ecc71",
    }
    for scenario in selected_scenarios:
        path = CARBON_PRICE_PATHS.get(scenario, {})
        prices = [path.get(y, 0) for y in years]
        fig_price.add_trace(go.Scatter(
            x=years, y=prices,
            name=scenario.replace("Nationally Determined Contributions (NDCs)", "NDCs"),
            line=dict(color=colors_map.get(scenario, "#95a5a6"), width=2),
            mode="lines+markers",
        ))
    fig_price.update_layout(
        title="Shadow Carbon Price — USD/tCO2 (NGFS Phase V, REMIND-MAgPIE)",
        plot_bgcolor="#1e2d3d", paper_bgcolor="#1e2d3d",
        font_color="#e8f4f8",
        yaxis=dict(title="USD/tCO2", gridcolor="#2c3e50"),
        xaxis=dict(title="Year", gridcolor="#2c3e50"),
    )
    st.plotly_chart(fig_price, use_container_width=True)

# ── Tab 2: Sector Heatmap ─────────────────────────────────────────────────────
with tab2:
    st.subheader(f"TREI Heatmap: Sectors × Scenarios ({horizon_year})")
    st.caption(
        "Color intensity = transition risk exposure. "
        "Energy and Transport face highest risk under orderly transition scenarios."
    )

    heatmap_df = scorer.heatmap_data(horizon=horizon_key)

    # Filter to selected scenarios
    available_cols = [s for s in selected_scenarios if s in heatmap_df.columns]
    if available_cols:
        hm_display = heatmap_df[available_cols]
        short_names = {
            "Nationally Determined Contributions (NDCs)": "NDCs",
            "Net Zero 2050": "NZ2050",
            "Below 2°C": "B2°C",
            "Delayed Transition": "Delayed",
            "Current Policies": "Current",
        }
        hm_display = hm_display.rename(columns=short_names)

        fig_hm = px.imshow(
            hm_display,
            color_continuous_scale="RdYlGn_r",
            zmin=0, zmax=100,
            text_auto=".0f",
            title=f"TREI Heatmap — Medium Horizon ({horizon_year})",
            aspect="auto",
        )
        fig_hm.update_layout(
            paper_bgcolor="#1e2d3d", font_color="#e8f4f8",
        )
        st.plotly_chart(fig_hm, use_container_width=True)

    # Sector detail table
    st.subheader("Sector Properties")
    st.dataframe(
        sector_summary_table(),
        use_container_width=True,
    )

# ── Tab 3: Portfolio ──────────────────────────────────────────────────────────
with tab3:
    st.subheader("Portfolio Composition and Risk Profile")

    col_l, col_r = st.columns([1, 1])

    with col_l:
        # Sector allocation pie
        sector_wts = result.sector_weights
        fig_pie = px.pie(
            values=list(sector_wts.values()),
            names=list(sector_wts.keys()),
            title="Portfolio Allocation by NGFS Sector",
            color_discrete_sequence=px.colors.qualitative.Set3,
        )
        fig_pie.update_layout(
            paper_bgcolor="#1e2d3d", font_color="#e8f4f8"
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_r:
        # Sector TREI under NZ2050
        sector_df = pd.DataFrame({
            "Sector": list(result.sector_trei_nz2050.keys()),
            "TREI (NZ2050)": list(result.sector_trei_nz2050.values()),
            "Weight (%)": [result.sector_weights.get(s, 0) * 100
                           for s in result.sector_trei_nz2050],
        }).sort_values("TREI (NZ2050)", ascending=True)

        fig_sector = px.bar(
            sector_df, x="TREI (NZ2050)", y="Sector",
            orientation="h",
            color="TREI (NZ2050)",
            color_continuous_scale="RdYlGn_r",
            range_color=[0, 100],
            title="Sector TREI under NZ2050 Scenario",
        )
        fig_sector.update_layout(
            paper_bgcolor="#1e2d3d", font_color="#e8f4f8",
            xaxis=dict(range=[0, 100]),
        )
        st.plotly_chart(fig_sector, use_container_width=True)

    # Company detail table
    st.subheader("Company Risk Profiles")
    companies_df = analyzer.companies_dataframe(result)
    st.dataframe(
        companies_df.style.background_gradient(
            subset=["TREI NZ2050", "TREI NDC", "TREI Current Policies"],
            cmap="RdYlGn_r", vmin=0, vmax=100,
        ),
        use_container_width=True,
        height=400,
    )

# ── Tab 4: What-If ────────────────────────────────────────────────────────────
with tab4:
    st.subheader("What-If: SBTi Adoption Impact on Portfolio TREI")
    st.caption(
        f"Simulating {sbti_pct}% SBTi target adoption across portfolio companies. "
        "SBTi-aligned companies reduce technology risk gap by ~50%."
    )

    what_if_rows = []
    for scenario in selected_scenarios:
        sw = result.sector_weights
        if sw:
            baseline, adjusted = scorer.what_if_sbti(
                sw, scenario,
                sbti_adoption_pct=sbti_pct / 100,
                horizon=horizon_key,
            )
            what_if_rows.append({
                "Scenario": scenario.replace(
                    "Nationally Determined Contributions (NDCs)", "NDCs"
                ),
                "Baseline TREI": baseline.portfolio_trei,
                "TREI with SBTi Adoption": adjusted.portfolio_trei,
                "Reduction": round(baseline.portfolio_trei - adjusted.portfolio_trei, 1),
            })

    if what_if_rows:
        df_wi = pd.DataFrame(what_if_rows)
        fig_wi = go.Figure()
        fig_wi.add_trace(go.Bar(
            x=df_wi["Scenario"], y=df_wi["Baseline TREI"],
            name="Baseline", marker_color="#e74c3c",
        ))
        fig_wi.add_trace(go.Bar(
            x=df_wi["Scenario"], y=df_wi["TREI with SBTi Adoption"],
            name=f"With {sbti_pct}% SBTi", marker_color="#2ecc71",
        ))
        fig_wi.update_layout(
            barmode="group",
            title=f"Portfolio TREI: Baseline vs. {sbti_pct}% SBTi Adoption",
            plot_bgcolor="#1e2d3d", paper_bgcolor="#1e2d3d",
            font_color="#e8f4f8", yaxis=dict(range=[0, 100]),
        )
        st.plotly_chart(fig_wi, use_container_width=True)
        st.dataframe(df_wi, use_container_width=True)

# ── Tab 5: IFRS S2 Robustness ─────────────────────────────────────────────────
with tab5:
    st.subheader("IFRS S2 Robustness Table — DMDU View")
    st.caption(
        "Portfolio performance across all scenarios. "
        "A robust strategy minimizes TREI across the full scenario space. "
        "Aligned with DMDU methodology and IFRS S2 Para. 29 (scenario analysis)."
    )

    rob_data = []
    for scenario in all_scenarios:
        t_short = result.portfolio_trei.get(scenario, {}).get("short", 0)
        t_med = result.portfolio_trei.get(scenario, {}).get("medium", 0)
        t_long = result.portfolio_trei.get(scenario, {}).get("long", 0)
        tier = result.risk_tiers.get(scenario, "—")
        rob_data.append({
            "Scenario": scenario,
            "TREI 2030": t_short,
            "TREI 2040": t_med,
            "TREI 2050": t_long,
            "Risk Tier": tier,
            "SBTI Impact": result.sbti_impact.get(scenario, 0),
        })
    rob_df = pd.DataFrame(rob_data).set_index("Scenario")
    st.dataframe(
        rob_df.style.background_gradient(
            subset=["TREI 2030", "TREI 2040", "TREI 2050"],
            cmap="RdYlGn_r", vmin=0, vmax=100,
        ).format("{:.1f}", subset=["TREI 2030", "TREI 2040", "TREI 2050", "SBTI Impact"]),
        use_container_width=True,
    )

    st.markdown("---")

    # Download buttons
    st.subheader("📥 Export Reports")
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        if st.button("Generate Excel Report (IFRS S2)"):
            reporter = GHGReporter(
                result, org_name="Sample Portfolio", scoring_year=2025
            )
            out = Path("outputs/climate_risk_report.xlsx")
            reporter.to_excel(out)
            st.success(f"Report saved: {out}")
    with col_dl2:
        if st.button("Generate HTML Report"):
            reporter = GHGReporter(
                result, org_name="Sample Portfolio", scoring_year=2025
            )
            out = Path("outputs/climate_risk_report.html")
            reporter.to_html(out)
            st.success(f"Report saved: {out}")

    st.markdown("""
    ---
    **References:**
    - NGFS (2024). *Phase V Climate Scenarios*. [ngfs.net](https://www.ngfs.net)
    - IFRS Foundation (2023). *IFRS S2 Climate-related Disclosures*. [ifrs.org](https://www.ifrs.org)
    - Battiston et al. (2017). A climate stress-test of the financial system. *Nature Climate Change*, 7, 283–288.
    - IPCC AR6 WG3 (2022). Mitigation of Climate Change. Chapter 3.
    """)
