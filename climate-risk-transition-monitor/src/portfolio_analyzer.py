"""
portfolio_analyzer.py
---------------------
Analyzes a portfolio of companies or assets for climate transition risk
exposure using the TREI methodology.

Accepts:
- CSV with company names, sectors (any classification system), and weights
- Optional SBTi status column for what-if analysis
- Optional CDP emissions data for direct Scope 1/2/3 integration

Output:
- Portfolio-level TREI across all NGFS scenarios
- Company-level risk flags
- Sector decomposition
- What-if analysis under SBTi adoption scenarios
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from .ngfs_loader import NGFSLoader, NGFSData
from .sector_mapper import map_portfolio_sectors, SECTOR_TRANSITION_RISK_BASE
from .transition_scorer import TransitionScorer, PortfolioTREI


# Required columns in portfolio CSV
REQUIRED_COLS = ["company_name", "sector"]
OPTIONAL_COLS = ["weight", "sector_system", "sbti_status", "scope1_tco2e",
                 "scope2_tco2e", "country", "ticker"]

# Default sector classification to assume if not specified
DEFAULT_SECTOR_SYSTEM = "gics"


@dataclass
class CompanyRiskProfile:
    """Transition risk profile for a single company."""
    company_name: str
    sector_input: str
    ngfs_sector: Optional[str]
    weight: float
    sbti_status: str          # "committed", "approved", "none"
    trei_by_scenario: dict[str, float]
    highest_risk_scenario: str
    lowest_risk_scenario: str
    risk_flags: list[str]


@dataclass
class PortfolioAnalysisResult:
    """Full portfolio analysis output."""
    n_companies: int
    n_mapped: int
    coverage_pct: float
    total_weight: float

    # TREI by scenario × horizon
    portfolio_trei: dict[str, dict[str, float]]   # scenario → horizon → TREI
    risk_tiers: dict[str, str]                     # scenario → tier

    # Sector decomposition
    sector_weights: dict[str, float]
    sector_trei_nz2050: dict[str, float]

    # What-if
    sbti_pct: float
    sbti_impact: dict[str, float]   # scenario → TREI reduction

    # Company profiles
    companies: list[CompanyRiskProfile]

    # Summary metrics
    highest_risk_scenario: str
    lowest_risk_scenario: str
    most_exposed_sector: str


class PortfolioAnalyzer:
    """
    Analyzes a portfolio CSV for NGFS-aligned transition risk exposure.

    Parameters
    ----------
    portfolio_path : str or Path, optional
        Path to CSV file. If None, uses built-in sample portfolio.
    sector_system : str
        Classification system for the sector column.
        One of: 'gics', 'gics_l2', 'nace', 'bmv', 'iea', 'ngfs'.
    ngfs_data : NGFSData, optional
        Pre-loaded NGFS data.
    """

    SAMPLE_PORTFOLIO_PATH = (
        Path(__file__).parent.parent / "data" / "sample_portfolio.csv"
    )

    def __init__(
        self,
        portfolio_path: Optional[str | Path] = None,
        sector_system: str = DEFAULT_SECTOR_SYSTEM,
        ngfs_data: Optional[NGFSData] = None,
    ):
        self.portfolio_path = Path(portfolio_path) if portfolio_path else None
        self.sector_system = sector_system

        if ngfs_data is None:
            loader = NGFSLoader()
            ngfs_data = loader.load()
        self.ngfs_data = ngfs_data
        self.scorer = TransitionScorer(ngfs_data=ngfs_data)

        self._portfolio_df: Optional[pd.DataFrame] = None

    def load_portfolio(self) -> pd.DataFrame:
        """Load and validate portfolio CSV."""
        if self.portfolio_path and self.portfolio_path.exists():
            df = pd.read_csv(self.portfolio_path)
        else:
            df = self._generate_sample_portfolio()

        # Validate required columns
        missing = [c for c in REQUIRED_COLS if c not in df.columns]
        if missing:
            raise ValueError(
                f"Portfolio CSV missing required columns: {missing}. "
                f"Required: {REQUIRED_COLS}"
            )

        # Add defaults for optional columns
        if "weight" not in df.columns:
            df["weight"] = 1.0 / len(df)
        else:
            df["weight"] = pd.to_numeric(df["weight"], errors="coerce").fillna(0)
            if df["weight"].sum() == 0:
                df["weight"] = 1.0 / len(df)

        if "sbti_status" not in df.columns:
            df["sbti_status"] = "none"

        if "country" not in df.columns:
            df["country"] = "unknown"

        # Determine sector system
        system = (
            df["sector_system"].iloc[0]
            if "sector_system" in df.columns
            else self.sector_system
        )

        # Map to NGFS sectors
        df = map_portfolio_sectors(df, "sector", from_system=system)

        self._portfolio_df = df
        return df

    def analyze(
        self,
        scenarios: Optional[list[str]] = None,
        horizons: Optional[list[str]] = None,
    ) -> PortfolioAnalysisResult:
        """
        Run full portfolio transition risk analysis.

        Parameters
        ----------
        scenarios : list[str], optional
            Scenarios to analyze. Defaults to all 5 main NGFS scenarios.
        horizons : list[str], optional
            Horizons to analyze. Defaults to ["short", "medium", "long"].

        Returns
        -------
        PortfolioAnalysisResult
        """
        df = self.load_portfolio()

        scenarios = scenarios or self.scorer.DEFAULT_SCENARIOS
        horizons = horizons or ["short", "medium", "long"]

        n_companies = len(df)
        mapped_df = df[df["ngfs_sector"].notna()].copy()
        n_mapped = len(mapped_df)
        coverage_pct = (n_mapped / n_companies * 100) if n_companies > 0 else 0.0

        # Normalize weights among mapped companies
        total_mapped_weight = mapped_df["weight"].sum()
        if total_mapped_weight > 0:
            mapped_df["weight_norm"] = mapped_df["weight"] / total_mapped_weight
        else:
            mapped_df["weight_norm"] = 1.0 / n_mapped

        # Aggregate weights by NGFS sector
        sector_weights = (
            mapped_df.groupby("ngfs_sector")["weight_norm"].sum().to_dict()
        )

        # Score portfolio across scenarios × horizons
        portfolio_trei: dict[str, dict[str, float]] = {}
        risk_tiers: dict[str, str] = {}

        for scenario in scenarios:
            portfolio_trei[scenario] = {}
            for horizon in horizons:
                ptrei = self.scorer.score_portfolio(
                    sector_weights, scenario, horizon
                )
                portfolio_trei[scenario][horizon] = ptrei.portfolio_trei
            # Use medium horizon for primary tier
            risk_tiers[scenario] = self.scorer.score_portfolio(
                sector_weights, scenario, "medium"
            ).risk_tier

        # Sector TREI under NZE 2050 (most stressful)
        nze_df = self.scorer.score_all_sectors(horizon="medium")
        nze_df = nze_df[nze_df["Scenario"] == "Net Zero 2050"]
        sector_trei_nz2050 = dict(zip(nze_df["Sector"], nze_df["TREI"]))

        # SBTi what-if
        sbti_count = (mapped_df["sbti_status"]
                      .isin(["approved", "committed"]).sum())
        sbti_pct = sbti_count / n_mapped if n_mapped > 0 else 0.0

        sbti_impact = {}
        for scenario in scenarios:
            baseline, adjusted = self.scorer.what_if_sbti(
                sector_weights, scenario,
                sbti_adoption_pct=max(sbti_pct, 0.30),  # min 30% for illustration
                horizon="medium",
            )
            sbti_impact[scenario] = round(
                baseline.portfolio_trei - adjusted.portfolio_trei, 1
            )

        # Company-level profiles
        companies = self._build_company_profiles(
            mapped_df, scenarios, sector_weights
        )

        # Summary
        medium_treis = {
            s: portfolio_trei[s]["medium"] for s in scenarios
        }
        highest_risk_scenario = max(medium_treis, key=medium_treis.get)
        lowest_risk_scenario = min(medium_treis, key=medium_treis.get)
        most_exposed_sector = max(
            sector_weights,
            key=lambda s: sector_weights[s] * sector_trei_nz2050.get(s, 0),
            default="N/A",
        )

        return PortfolioAnalysisResult(
            n_companies=n_companies,
            n_mapped=n_mapped,
            coverage_pct=round(coverage_pct, 1),
            total_weight=round(total_mapped_weight, 3),
            portfolio_trei=portfolio_trei,
            risk_tiers=risk_tiers,
            sector_weights={k: round(v, 3) for k, v in sector_weights.items()},
            sector_trei_nz2050=sector_trei_nz2050,
            sbti_pct=round(sbti_pct * 100, 1),
            sbti_impact=sbti_impact,
            companies=companies,
            highest_risk_scenario=highest_risk_scenario,
            lowest_risk_scenario=lowest_risk_scenario,
            most_exposed_sector=most_exposed_sector,
        )

    def _build_company_profiles(
        self,
        df: pd.DataFrame,
        scenarios: list[str],
        sector_weights: dict[str, float],
    ) -> list[CompanyRiskProfile]:
        """Build individual company risk profiles."""
        profiles = []
        for _, row in df.iterrows():
            sector = row.get("ngfs_sector")
            if not sector:
                continue

            trei_by_scenario = {}
            for scenario in scenarios:
                result = self.scorer.score_sector(sector, scenario, "medium")
                trei_by_scenario[scenario] = result.trei

            highest = max(trei_by_scenario, key=trei_by_scenario.get)
            lowest = min(trei_by_scenario, key=trei_by_scenario.get)

            # Risk flags
            flags = []
            nz_trei = trei_by_scenario.get("Net Zero 2050", 0)
            if nz_trei >= 70:
                flags.append("HIGH_TRANSITION_RISK_NZE")
            if row.get("sbti_status", "none") == "none" and nz_trei >= 50:
                flags.append("NO_SBTI_TARGET")
            dt_trei = trei_by_scenario.get("Delayed Transition", 0)
            if dt_trei >= 80:
                flags.append("DELAYED_TRANSITION_CLIFF_RISK")

            profiles.append(CompanyRiskProfile(
                company_name=row.get("company_name", "Unknown"),
                sector_input=str(row.get("sector", "")),
                ngfs_sector=sector,
                weight=round(row.get("weight_norm", 0), 4),
                sbti_status=str(row.get("sbti_status", "none")),
                trei_by_scenario=trei_by_scenario,
                highest_risk_scenario=highest,
                lowest_risk_scenario=lowest,
                risk_flags=flags,
            ))

        return profiles

    def companies_dataframe(self, result: PortfolioAnalysisResult) -> pd.DataFrame:
        """Return company profiles as a tidy DataFrame."""
        rows = []
        for c in result.companies:
            row = {
                "Company": c.company_name,
                "Sector (Input)": c.sector_input,
                "NGFS Sector": c.ngfs_sector,
                "Weight (%)": round(c.weight * 100, 2),
                "SBTi Status": c.sbti_status,
                "TREI NZ2050": c.trei_by_scenario.get("Net Zero 2050"),
                "TREI NDC": c.trei_by_scenario.get(
                    "Nationally Determined Contributions (NDCs)"
                ),
                "TREI Current Policies": c.trei_by_scenario.get("Current Policies"),
                "Highest Risk Scenario": c.highest_risk_scenario,
                "Risk Flags": "; ".join(c.risk_flags) if c.risk_flags else "None",
            }
            rows.append(row)
        return pd.DataFrame(rows)

    def _generate_sample_portfolio(self) -> pd.DataFrame:
        """Generate a synthetic portfolio of 40 Latin American companies."""
        np.random.seed(42)

        companies = [
            # Energy / Oil & Gas
            ("Pemex", "Oil, Gas & Consumable Fuels", 0.08, "none", "MEX"),
            ("Petrobras", "Oil, Gas & Consumable Fuels", 0.07, "committed", "BRA"),
            ("Ecopetrol", "Oil, Gas & Consumable Fuels", 0.05, "none", "COL"),
            ("YPF", "Oil, Gas & Consumable Fuels", 0.04, "none", "ARG"),
            ("CFE", "Electric Utilities", 0.06, "committed", "MEX"),
            ("Engie México", "Electric Utilities", 0.03, "approved", "MEX"),
            # Industry / Metals
            ("Cemex", "Construction Materials", 0.05, "committed", "MEX"),
            ("Ternium", "Metals & Mining", 0.04, "none", "MEX"),
            ("Gerdau", "Metals & Mining", 0.04, "committed", "BRA"),
            ("Vale", "Metals & Mining", 0.05, "approved", "BRA"),
            ("ArcelorMittal", "Metals & Mining", 0.03, "approved", "LUX"),
            # Transport
            ("Aeropuertos y Servicios Auxiliares", "Airlines", 0.02, "none", "MEX"),
            ("Copa Holdings", "Airlines", 0.02, "none", "PAN"),
            ("FEMSA", "Ground Transportation", 0.03, "committed", "MEX"),
            ("Grupo TMM", "Ground Transportation", 0.01, "none", "MEX"),
            # Agriculture / Food
            ("Gruma", "Food Products", 0.03, "committed", "MEX"),
            ("Maseca / GRUMA", "Agricultural Products & Services", 0.02, "none", "MEX"),
            ("JBS", "Food Products", 0.03, "none", "BRA"),
            ("Bunge", "Agricultural Products & Services", 0.02, "committed", "BRA"),
            # Buildings / Real Estate
            ("FIBRA Uno", "Diversified REITs", 0.03, "none", "MEX"),
            ("Vesta", "Industrial REITs", 0.02, "committed", "MEX"),
            ("GFa DANHOS", "Retail REITs", 0.02, "none", "MEX"),
            # Chemicals / Industry
            ("Alpek", "Chemicals", 0.03, "committed", "MEX"),
            ("Mexichem / Orbia", "Chemicals", 0.03, "approved", "MEX"),
            ("Braskem", "Chemicals", 0.03, "committed", "BRA"),
            # Utilities / Water
            ("Rotoplas", "Water Utilities", 0.02, "none", "MEX"),
            ("Sabesp", "Water Utilities", 0.02, "committed", "BRA"),
            # Consumer Staples
            ("Grupo Bimbo", "Food Products", 0.03, "approved", "MEX"),
            ("Lala", "Food Products", 0.02, "none", "MEX"),
            ("Sigma Alimentos", "Food Products", 0.02, "none", "MEX"),
            # Financials
            ("Banorte", "Financials", 0.03, "committed", "MEX"),
            ("Bancolombia", "Financials", 0.02, "committed", "COL"),
            ("Itaú Unibanco", "Financials", 0.03, "approved", "BRA"),
            # Technology / Buildings
            ("América Móvil", "Communication Services", 0.03, "committed", "MEX"),
            ("Televisa", "Communication Services", 0.01, "none", "MEX"),
            # Paper / Land Use
            ("Klabin", "Paper & Forest Products", 0.02, "approved", "BRA"),
            ("Suzano", "Paper & Forest Products", 0.02, "approved", "BRA"),
            # Health / Buildings
            ("Genomma Lab", "Health Care", 0.01, "none", "MEX"),
            ("Ultragenyx LatAm", "Health Care", 0.01, "none", "MEX"),
            # Mining
            ("Peñoles", "Metals & Mining", 0.02, "none", "MEX"),
        ]

        df = pd.DataFrame(
            companies,
            columns=["company_name", "sector", "weight", "sbti_status", "country"],
        )
        df["sector_system"] = "gics_l2"

        # Normalize weights
        df["weight"] = df["weight"] / df["weight"].sum()

        return df

    def save_sample_portfolio(self) -> Path:
        """Save sample portfolio to data directory."""
        df = self._generate_sample_portfolio()
        path = self.SAMPLE_PORTFOLIO_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
        print(f"[PortfolioAnalyzer] Sample portfolio saved to {path}")
        return path
