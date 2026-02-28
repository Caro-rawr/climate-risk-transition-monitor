"""
reporter.py
-----------
Generates climate risk disclosure reports aligned with IFRS S2 / TCFD structure.

Output formats:
- Multi-sheet Excel workbook (IFRS S2 pillar structure)
- Standalone HTML report with embedded charts

IFRS S2 structure (June 2023):
1. Governance
2. Strategy
3. Risk Management
4. Metrics & Targets

Reference: IFRS Foundation (2023). IFRS S2 Climate-related Disclosures.
https://www.ifrs.org/issued-standards/ifrs-sustainability-standards-navigator/
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from .portfolio_analyzer import PortfolioAnalysisResult
from .transition_scorer import TransitionScorer


# Risk tier color codes for HTML/Excel
RISK_COLORS = {
    "Very Low": "#2ecc71",
    "Low": "#a8e6cf",
    "Medium": "#f39c12",
    "High": "#e74c3c",
    "Very High": "#922b21",
}

TIER_BG = {
    "Very Low": "D5F5E3",
    "Low": "ABEBC6",
    "Medium": "FAD7A0",
    "High": "F1948A",
    "Very High": "E74C3C",
}


class GHGReporter:
    """
    Generates IFRS S2-aligned climate risk disclosure reports.

    Parameters
    ----------
    result : PortfolioAnalysisResult
        Output from PortfolioAnalyzer.analyze().
    org_name : str
        Organization or fund name for report header.
    reporting_year : int
        Year of the analysis.
    scorer : TransitionScorer, optional
        For generating supplementary sector data.
    """

    def __init__(
        self,
        result: PortfolioAnalysisResult,
        org_name: str = "Portfolio",
        reporting_year: int = 2025,
        scorer: Optional[TransitionScorer] = None,
    ):
        self.result = result
        self.org_name = org_name
        self.reporting_year = reporting_year
        self.scorer = scorer or TransitionScorer()
        self._timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # ── Console ───────────────────────────────────────────────────────────────

    def print_summary(self) -> None:
        """Print portfolio risk summary to console."""
        r = self.result
        print(f"\n{'='*65}")
        print(f"  CLIMATE TRANSITION RISK REPORT — {self.org_name.upper()}")
        print(f"  Reporting Year: {self.reporting_year} | Generated: {self._timestamp}")
        print(f"{'='*65}")
        print(f"\n  Portfolio Coverage: {r.n_mapped}/{r.n_companies} companies "
              f"({r.coverage_pct:.0f}%)")
        print(f"  Most Exposed Sector: {r.most_exposed_sector}")
        print(f"  SBTi-Aligned Companies: {r.sbti_pct:.0f}%\n")

        print(f"  {'Scenario':<45} {'TREI (Medium)':<15} {'Risk Tier'}")
        print(f"  {'-'*70}")
        for scenario in r.portfolio_trei:
            trei = r.portfolio_trei[scenario].get("medium", 0)
            tier = r.risk_tiers.get(scenario, "—")
            print(f"  {scenario:<45} {trei:<15.1f} {tier}")

        print(f"\n  Most stressful scenario: {r.highest_risk_scenario}")
        print(f"  Least stressful scenario: {r.lowest_risk_scenario}")
        print(f"{'='*65}\n")

    # ── Excel ─────────────────────────────────────────────────────────────────

    def to_excel(self, output_path: str | Path) -> Path:
        """
        Generate multi-sheet Excel workbook with IFRS S2 pillar structure.

        Sheets:
        1. Cover              — report metadata
        2. Governance         — IFRS S2 pillar 1 (manual input template)
        3. Strategy           — scenario analysis and TREI results
        4. Risk Management    — sector and company risk profiles
        5. Metrics & Targets  — TREI scores, SBTi gap, carbon price exposure
        6. Company Detail     — full company-level data
        7. Sector Heatmap     — TREI matrix
        8. Methodology        — data sources and assumptions
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        r = self.result

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:

            # ── Sheet 1: Cover ────────────────────────────────────────────────
            cover_data = {
                "Field": [
                    "Report Title",
                    "Organization",
                    "Reporting Year",
                    "Framework",
                    "Generated",
                    "Data Source",
                    "NGFS Phase",
                    "Scenarios Analyzed",
                    "Companies Analyzed",
                    "Portfolio Coverage",
                ],
                "Value": [
                    "Climate Transition Risk Disclosure",
                    self.org_name,
                    str(self.reporting_year),
                    "IFRS S2 / TCFD",
                    self._timestamp,
                    "NGFS Phase V Synthetic (Nov 2024)",
                    "V",
                    str(len(r.portfolio_trei)),
                    str(r.n_companies),
                    f"{r.coverage_pct:.0f}%",
                ],
            }
            pd.DataFrame(cover_data).to_excel(
                writer, sheet_name="Cover", index=False
            )

            # ── Sheet 2: Strategy (scenario analysis) ─────────────────────────
            strategy_rows = []
            for scenario, horizons in r.portfolio_trei.items():
                strategy_rows.append({
                    "Scenario": scenario,
                    "TREI Short-Term (2030)": horizons.get("short"),
                    "TREI Medium-Term (2040)": horizons.get("medium"),
                    "TREI Long-Term (2050)": horizons.get("long"),
                    "Risk Tier (Medium)": r.risk_tiers.get(scenario),
                    "TREI Reduction if 30% SBTi Adopted": r.sbti_impact.get(scenario),
                })
            pd.DataFrame(strategy_rows).to_excel(
                writer, sheet_name="Strategy - Scenario Analysis", index=False
            )

            # ── Sheet 3: Risk Management ──────────────────────────────────────
            sector_rows = []
            for sector, weight in r.sector_weights.items():
                trei_nz = r.sector_trei_nz2050.get(sector, 0)
                sector_rows.append({
                    "NGFS Sector": sector,
                    "Portfolio Weight (%)": round(weight * 100, 2),
                    "TREI under NZ2050": trei_nz,
                    "Weighted Risk Contribution": round(weight * trei_nz, 1),
                })
            sector_df = pd.DataFrame(sector_rows).sort_values(
                "Weighted Risk Contribution", ascending=False
            )
            sector_df.to_excel(
                writer, sheet_name="Risk Management - Sectors", index=False
            )

            # ── Sheet 4: Metrics & Targets ────────────────────────────────────
            metrics_data = {
                "Metric": [
                    "Portfolio TREI — NZ2050 (Medium Horizon)",
                    "Portfolio TREI — Current Policies (Medium Horizon)",
                    "Portfolio TREI — NDC (Medium Horizon)",
                    "Most Exposed Sector",
                    "Current SBTi Coverage (%)",
                    "TREI Reduction at 30% SBTi (NZ2050 scenario)",
                    "Highest Risk Scenario",
                    "Number of Companies with HIGH+ Risk Flags",
                ],
                "Value": [
                    r.portfolio_trei.get("Net Zero 2050", {}).get("medium", "N/A"),
                    r.portfolio_trei.get("Current Policies", {}).get("medium", "N/A"),
                    r.portfolio_trei.get(
                        "Nationally Determined Contributions (NDCs)", {}
                    ).get("medium", "N/A"),
                    r.most_exposed_sector,
                    f"{r.sbti_pct:.0f}%",
                    r.sbti_impact.get("Net Zero 2050", "N/A"),
                    r.highest_risk_scenario,
                    sum(
                        1 for c in r.companies
                        if any("HIGH" in f for f in c.risk_flags)
                    ),
                ],
                "IFRS S2 Reference": [
                    "Para. 29(a) — Climate scenario analysis",
                    "Para. 29(a) — Climate scenario analysis",
                    "Para. 29(a) — Climate scenario analysis",
                    "Para. 29(b) — Sector exposure",
                    "Para. 22(c) — Internal carbon price",
                    "Para. 22(c) — Transition plan",
                    "Para. 10 — Risk identification",
                    "Para. 25 — Risk management process",
                ],
            }
            pd.DataFrame(metrics_data).to_excel(
                writer, sheet_name="Metrics and Targets", index=False
            )

            # ── Sheet 5: Company Detail ───────────────────────────────────────
            from .portfolio_analyzer import PortfolioAnalyzer
            analyzer = PortfolioAnalyzer.__new__(PortfolioAnalyzer)
            analyzer.scorer = self.scorer
            companies_df = analyzer.companies_dataframe(r)
            companies_df.to_excel(
                writer, sheet_name="Company Detail", index=False
            )

            # ── Sheet 6: Sector Heatmap ───────────────────────────────────────
            heatmap = self.scorer.heatmap_data(horizon="medium")
            heatmap.to_excel(writer, sheet_name="Sector TREI Heatmap")

            # ── Sheet 7: Methodology ──────────────────────────────────────────
            methodology_data = {
                "Item": [
                    "TREI Methodology",
                    "Policy Risk Weight",
                    "Technology Risk Weight",
                    "Market Risk Weight",
                    "Scenario Data Source",
                    "Carbon Price Reference",
                    "Sector Classification",
                    "Stranded Asset Methodology",
                    "SBTi Data",
                    "Framework Alignment",
                ],
                "Description": [
                    "Transition Risk Exposure Index: composite 0–100 score",
                    "40% — based on carbon price trajectory vs. sector intensity",
                    "35% — emissions gap vs. NZE reference pathway",
                    "25% — stranded asset probability from NGFS Phase V",
                    "NGFS Phase V (November 2024), IIASA/PIK/NIESR",
                    "NGFS Phase V REMIND-MAgPIE shadow carbon prices",
                    "GICS L2 → NGFS sector mapping (custom crosswalk)",
                    "Adapted from Battiston et al. (2017), Nature Climate Change",
                    "SBTi Companies Taking Action dataset (public, weekly update)",
                    "IFRS S2 (June 2023), TCFD (2021), NGFS (2024)",
                ],
            }
            pd.DataFrame(methodology_data).to_excel(
                writer, sheet_name="Methodology", index=False
            )

        print(f"[Reporter] Excel report saved: {output_path}")
        return output_path

    # ── HTML ──────────────────────────────────────────────────────────────────

    def to_html(self, output_path: str | Path) -> Path:
        """Generate standalone HTML climate risk disclosure report."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        r = self.result

        # Build scenario table HTML
        scenario_rows_html = ""
        for scenario, horizons in r.portfolio_trei.items():
            tier = r.risk_tiers.get(scenario, "Medium")
            bg = TIER_BG.get(tier, "FFFFFF")
            trei_m = horizons.get("medium", 0)
            scenario_rows_html += f"""
            <tr>
                <td>{scenario}</td>
                <td style="text-align:center">{horizons.get('short', 0):.1f}</td>
                <td style="text-align:center">{trei_m:.1f}</td>
                <td style="text-align:center">{horizons.get('long', 0):.1f}</td>
                <td style="text-align:center;background-color:#{bg};
                    font-weight:bold">{tier}</td>
            </tr>"""

        # Sector breakdown bars
        sector_bars_html = ""
        for sector, weight in sorted(
            r.sector_weights.items(), key=lambda x: -x[1]
        ):
            pct = weight * 100
            trei = r.sector_trei_nz2050.get(sector, 0)
            color = RISK_COLORS.get(
                "High" if trei >= 60 else ("Medium" if trei >= 40 else "Low"),
                "#3498db"
            )
            sector_bars_html += f"""
            <div class="sector-bar">
                <div class="sector-label">{sector}</div>
                <div class="bar-container">
                    <div class="bar" style="width:{pct*5:.0f}px;
                        background:{color}"></div>
                    <span class="bar-value">{pct:.1f}% weight | TREI: {trei:.0f}</span>
                </div>
            </div>"""

        nz2050_trei = r.portfolio_trei.get("Net Zero 2050", {}).get("medium", 0)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Climate Transition Risk Report — {self.org_name}</title>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0;
         background: #f5f7fa; color: #2c3e50; }}
  .header {{ background: linear-gradient(135deg, #1a252f 0%, #2c3e50 100%);
             color: white; padding: 40px 60px; }}
  .header h1 {{ margin: 0; font-size: 26px; font-weight: 300; }}
  .header h2 {{ margin: 8px 0 0; font-size: 18px; font-weight: 600; }}
  .header .meta {{ margin-top: 12px; font-size: 13px; opacity: 0.75; }}
  .container {{ max-width: 1100px; margin: 40px auto; padding: 0 40px; }}
  .kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr);
               gap: 20px; margin-bottom: 40px; }}
  .kpi {{ background: white; border-radius: 10px; padding: 24px;
          box-shadow: 0 2px 12px rgba(0,0,0,0.06); }}
  .kpi .value {{ font-size: 36px; font-weight: 700; color: #2c3e50; }}
  .kpi .label {{ font-size: 12px; color: #7f8c8d; margin-top: 6px;
                 text-transform: uppercase; letter-spacing: 0.5px; }}
  .section {{ background: white; border-radius: 10px; padding: 32px;
              margin-bottom: 32px; box-shadow: 0 2px 12px rgba(0,0,0,0.06); }}
  .section h3 {{ margin: 0 0 24px; font-size: 16px; color: #2c3e50;
                 border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
  .ifrs-badge {{ font-size: 11px; color: #3498db; font-weight: 600;
                 float: right; padding: 2px 8px; border: 1px solid #3498db;
                 border-radius: 4px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th {{ background: #2c3e50; color: white; padding: 10px 14px;
        text-align: left; font-weight: 500; }}
  td {{ padding: 10px 14px; border-bottom: 1px solid #ecf0f1; }}
  tr:hover td {{ background: #f8f9fa; }}
  .sector-bar {{ display: flex; align-items: center; margin: 10px 0; }}
  .sector-label {{ width: 140px; font-size: 13px; font-weight: 500; }}
  .bar-container {{ display: flex; align-items: center; gap: 12px; }}
  .bar {{ height: 20px; border-radius: 4px; min-width: 4px; }}
  .bar-value {{ font-size: 12px; color: #7f8c8d; }}
  .footer {{ text-align: center; padding: 40px; color: #95a5a6; font-size: 12px; }}
  .disclaimer {{ background: #fef9e7; border-left: 4px solid #f39c12;
                 padding: 16px 20px; border-radius: 4px; font-size: 13px;
                 margin-top: 24px; color: #7d6608; }}
</style>
</head>
<body>

<div class="header">
  <div class="meta">CLIMATE TRANSITION RISK DISCLOSURE</div>
  <h2>{self.org_name}</h2>
  <h1>IFRS S2 Aligned — Reporting Year {self.reporting_year}</h1>
  <div class="meta">Framework: IFRS S2 / TCFD &nbsp;|&nbsp;
    Scenarios: NGFS Phase V (Nov 2024) &nbsp;|&nbsp;
    Generated: {self._timestamp}</div>
</div>

<div class="container">

  <!-- KPIs -->
  <div class="kpi-grid">
    <div class="kpi">
      <div class="value">{r.n_companies}</div>
      <div class="label">Companies Analyzed</div>
    </div>
    <div class="kpi">
      <div class="value">{r.coverage_pct:.0f}%</div>
      <div class="label">Portfolio Coverage</div>
    </div>
    <div class="kpi">
      <div class="value">{r.sbti_pct:.0f}%</div>
      <div class="label">SBTi-Aligned</div>
    </div>
    <div class="kpi">
      <div class="value" style="color:#e74c3c">{nz2050_trei:.0f}</div>
      <div class="label">TREI — NZ2050 Scenario</div>
    </div>
  </div>

  <!-- Strategy: Scenario Analysis -->
  <div class="section">
    <h3>Strategy — Scenario Analysis
      <span class="ifrs-badge">IFRS S2 Para. 29</span></h3>
    <p style="font-size:13px;color:#7f8c8d">
      Portfolio Transition Risk Exposure Index (TREI, 0–100) across five
      NGFS Phase V scenarios and three time horizons. Higher scores indicate
      greater financial exposure to climate transition risks.
    </p>
    <table>
      <tr>
        <th>NGFS Scenario</th>
        <th style="text-align:center">Short-Term<br>2030</th>
        <th style="text-align:center">Medium-Term<br>2040</th>
        <th style="text-align:center">Long-Term<br>2050</th>
        <th style="text-align:center">Risk Tier</th>
      </tr>
      {scenario_rows_html}
    </table>
  </div>

  <!-- Risk Management: Sector Exposure -->
  <div class="section">
    <h3>Risk Management — Sector Exposure
      <span class="ifrs-badge">IFRS S2 Para. 25</span></h3>
    <p style="font-size:13px;color:#7f8c8d">
      Portfolio weight and TREI under NZ2050 scenario by NGFS sector.
      Bar width proportional to portfolio weight.
    </p>
    {sector_bars_html}
  </div>

  <!-- Metrics & Targets -->
  <div class="section">
    <h3>Metrics &amp; Targets
      <span class="ifrs-badge">IFRS S2 Para. 22</span></h3>
    <table>
      <tr><th>Metric</th><th>Value</th></tr>
      <tr><td>Most Exposed Sector</td><td>{r.most_exposed_sector}</td></tr>
      <tr><td>Highest Risk Scenario</td><td>{r.highest_risk_scenario}</td></tr>
      <tr><td>TREI Reduction at 30% SBTi Adoption (NZ2050)</td>
          <td>{r.sbti_impact.get('Net Zero 2050', 'N/A'):.1f} points</td></tr>
      <tr><td>Companies with High+ Risk Flags</td>
          <td>{sum(1 for c in r.companies if any('HIGH' in f for f in c.risk_flags))}</td></tr>
    </table>
  </div>

  <div class="disclaimer">
    <strong>Disclaimer:</strong> This report uses synthetic NGFS Phase V-calibrated
    data for analytical purposes. Scores are indicative and do not constitute
    investment or regulatory advice. For compliance reporting, replace with
    audited data from certified data providers (Bloomberg, CDP, MSCI, TruCost).
    Methodology aligned with IFRS S2 (June 2023) and NGFS Phase V (November 2024).
  </div>

</div>

<div class="footer">
  Generated by climate-risk-transition-monitor &nbsp;|&nbsp;
  github.com/Caro-rawr/climate-risk-transition-monitor &nbsp;|&nbsp;
  NGFS Phase V · IFRS S2 · TCFD
</div>
</body>
</html>"""

        output_path.write_text(html, encoding="utf-8")
        print(f"[Reporter] HTML report saved: {output_path}")
        return output_path
