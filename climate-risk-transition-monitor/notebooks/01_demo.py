# %% [markdown]
# # Climate Transition Risk Monitor — Demo Notebook
#
# **NGFS Phase V · IFRS S2 Aligned · TCFD Framework**
#
# This notebook demonstrates the full analytical pipeline:
# 1. Loading NGFS Phase V climate scenarios
# 2. Computing sector Transition Risk Exposure Index (TREI)
# 3. Analyzing a Latin American portfolio
# 4. What-if analysis under SBTi adoption scenarios
# 5. Generating IFRS S2-aligned outputs
#
# ---
# **Data Source:** NGFS Phase V (November 2024) — IIASA/PIK/Climate Analytics
# **Framework:** IFRS S2 (June 2023), TCFD (2021)
# **Methodology:** Battiston et al. (2017) *Nature Climate Change*

# %% [markdown]
# ## 1 · Load NGFS Phase V Scenario Data

# %%
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

from src.ngfs_loader import NGFSLoader

loader = NGFSLoader(use_api=False, use_cache=False)
ngfs_data = loader.load()

print(f"Data source: {ngfs_data.source}")
print(f"Scenarios: {ngfs_data.scenarios}")
print(f"Years: {ngfs_data.years}")

# %% [markdown]
# ### NGFS Scenario Summary Table

# %%
loader.summary_table()

# %% [markdown]
# ### Carbon Price Trajectories
#
# Shadow carbon prices from NGFS Phase V (REMIND-MAgPIE model).
# These represent the implicit cost of carbon needed to achieve each pathway.

# %%
from src.ngfs_loader import CARBON_PRICE_PATHS

fig = go.Figure()
colors = {
    "Net Zero 2050": "#e74c3c",
    "Below 2°C": "#e67e22",
    "Delayed Transition": "#f39c12",
    "Current Policies": "#3498db",
    "Nationally Determined Contributions (NDCs)": "#2ecc71",
}
years = [2025, 2030, 2035, 2040, 2045, 2050]

for scenario, path in CARBON_PRICE_PATHS.items():
    prices = [path.get(y, 0) for y in years]
    fig.add_trace(go.Scatter(
        x=years, y=prices, name=scenario,
        line=dict(color=colors.get(scenario), width=2),
        mode="lines+markers",
    ))

fig.update_layout(
    title="NGFS Phase V — Shadow Carbon Price (USD/tCO₂)",
    xaxis_title="Year", yaxis_title="USD/tCO₂",
    template="plotly_dark", height=450,
)
fig.show()

# %% [markdown]
# ## 2 · Sector Transition Risk Exposure Index (TREI)
#
# The TREI integrates three risk dimensions:
# - **Policy risk** (40%): carbon price acceleration × sector intensity
# - **Technology risk** (35%): emissions gap vs. NZE reference pathway
# - **Market risk** (25%): stranded asset probability (NGFS Phase V)

# %%
from src.transition_scorer import TransitionScorer

scorer = TransitionScorer(ngfs_data=ngfs_data)

# Score all sectors across all scenarios (medium horizon, 2040)
sector_df = scorer.score_all_sectors(horizon="medium")
print(f"Total scores computed: {len(sector_df)}")
sector_df.head(10)

# %% [markdown]
# ### TREI Heatmap: Sectors × Scenarios

# %%
heatmap_df = scorer.heatmap_data(horizon="medium")

fig = px.imshow(
    heatmap_df,
    color_continuous_scale="RdYlGn_r",
    zmin=0, zmax=100,
    text_auto=".0f",
    title="TREI Heatmap — Sectors × NGFS Scenarios (Medium Horizon, 2040)",
    aspect="auto",
)
fig.update_layout(template="plotly_dark", height=450)
fig.show()

# %% [markdown]
# ### Risk Component Breakdown for Energy Sector

# %%
scenarios = [
    "Net Zero 2050",
    "Delayed Transition",
    "Current Policies",
]

results = []
for scenario in scenarios:
    r = scorer.score_sector("Energy", scenario, "medium")
    results.append({
        "Scenario": scenario,
        "Policy Risk": r.policy_risk_score,
        "Technology Risk": r.technology_risk_score,
        "Market Risk": r.market_risk_score,
        "TREI (Total)": r.trei,
        "Carbon Price 2040 (USD/tCO₂)": r.carbon_price_usd,
    })

pd.DataFrame(results).set_index("Scenario")

# %% [markdown]
# ## 3 · Portfolio Analysis
#
# 40-company Latin American portfolio with GICS L2 → NGFS sector mapping.
# Includes companies from México, Brasil, Colombia, and Argentina.

# %%
from src.portfolio_analyzer import PortfolioAnalyzer

analyzer = PortfolioAnalyzer(ngfs_data=ngfs_data)
df = analyzer.load_portfolio()

print(f"Companies loaded: {len(df)}")
print(f"Sector system: gics_l2 → ngfs")
print(f"\nSector distribution:")
print(df.groupby("ngfs_sector")["weight"].sum().sort_values(ascending=False).apply(
    lambda x: f"{x*100:.1f}%"
))

# %% [markdown]
# ### Run Full Analysis

# %%
result = analyzer.analyze()

print(f"\nPortfolio coverage: {result.coverage_pct:.0f}%")
print(f"Most exposed sector: {result.most_exposed_sector}")
print(f"Current SBTi alignment: {result.sbti_pct:.0f}%")
print(f"\n{'Scenario':<50} {'TREI (2040)':>12} {'Risk Tier'}")
print("-" * 75)
for scenario, horizons in result.portfolio_trei.items():
    trei_m = horizons.get("medium", 0)
    tier = result.risk_tiers.get(scenario, "—")
    print(f"{scenario:<50} {trei_m:>12.1f} {tier}")

# %% [markdown]
# ### Sector Allocation and Risk Contribution

# %%
sector_data = pd.DataFrame({
    "Sector": list(result.sector_weights.keys()),
    "Weight (%)": [v * 100 for v in result.sector_weights.values()],
    "TREI under NZ2050": [result.sector_trei_nz2050.get(s, 0)
                          for s in result.sector_weights],
})
sector_data["Weighted Risk"] = (
    sector_data["Weight (%)"] / 100 * sector_data["TREI under NZ2050"]
)
sector_data = sector_data.sort_values("Weighted Risk", ascending=False)

fig = px.scatter(
    sector_data,
    x="Weight (%)", y="TREI under NZ2050",
    size="Weighted Risk", color="TREI under NZ2050",
    color_continuous_scale="RdYlGn_r",
    text="Sector",
    title="Sector Weight vs. TREI (NZ2050) — Bubble = Weighted Risk Contribution",
    template="plotly_dark",
)
fig.update_traces(textposition="top center")
fig.update_layout(height=500)
fig.show()

# %% [markdown]
# ## 4 · What-If: SBTi Adoption Impact

# %%
print("What-If Analysis: 30% vs. 50% SBTi Adoption\n")
print(f"{'Scenario':<50} {'Baseline':>10} {'30% SBTi':>10} {'50% SBTi':>10}")
print("-" * 85)

for scenario in list(result.portfolio_trei.keys())[:5]:
    baseline_ptrei = result.portfolio_trei[scenario]["medium"]
    _, adj_30 = scorer.what_if_sbti(
        result.sector_weights, scenario, sbti_adoption_pct=0.30
    )
    _, adj_50 = scorer.what_if_sbti(
        result.sector_weights, scenario, sbti_adoption_pct=0.50
    )
    label = scenario.replace("Nationally Determined Contributions (NDCs)", "NDCs")
    print(f"{label:<50} {baseline_ptrei:>10.1f} {adj_30.portfolio_trei:>10.1f} "
          f"{adj_50.portfolio_trei:>10.1f}")

# %% [markdown]
# ## 5 · DMDU Robustness Table
#
# Aligned with Decision Making Under Deep Uncertainty methodology.
# A climate-resilient portfolio minimizes TREI across the full scenario space,
# not just under the most likely scenario.

# %%
rob = scorer.robustness_table(result.sector_weights, horizon="medium")
rob

# %% [markdown]
# ## 6 · Generate IFRS S2 Reports

# %%
from src.reporter import GHGReporter
from pathlib import Path

reporter = GHGReporter(
    result=result,
    org_name="Latin American Climate Portfolio — Demo",
    reporting_year=2025,
    scorer=scorer,
)

# Console summary
reporter.print_summary()

# Export reports
output_dir = Path("../outputs")
output_dir.mkdir(exist_ok=True)

excel_path = reporter.to_excel(output_dir / "demo_climate_risk_report.xlsx")
html_path = reporter.to_html(output_dir / "demo_climate_risk_report.html")

print(f"\n✅ Reports exported:")
print(f"   Excel: {excel_path}")
print(f"   HTML:  {html_path}")

# %% [markdown]
# ---
#
# ## References
#
# - **NGFS (2024).** Phase V Climate Scenarios. Network for Greening the Financial System.
#   https://www.ngfs.net/ngfs-scenarios-portal/data-resources/
#
# - **IFRS Foundation (2023).** IFRS S2 Climate-related Disclosures.
#   https://www.ifrs.org/issued-standards/ifrs-sustainability-standards-navigator/ifrs-s2-climate-related-disclosures/
#
# - **Battiston, S. et al. (2017).** A climate stress-test of the financial system.
#   *Nature Climate Change*, 7, 283–288. DOI: 10.1038/nclimate3255
#
# - **IPCC AR6 WG3 (2022).** Mitigation of Climate Change.
#   https://www.ipcc.ch/report/ar6/wg3/
#
# - **TCFD (2021).** Guidance on Scenario Analysis for Non-Financial Companies.
#   https://www.fsb-tcfd.org/
#
# - **SBTi (2024).** Financial Institutions Near-Term Criteria Version 2.0.
#   https://sciencebasedtargets.org/resources/files/Financial-Institutions-Near-Term-Criteria.pdf
