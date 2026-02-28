"""
transition_scorer.py
--------------------
Computes the Transition Risk Exposure Index (TREI) for individual sectors
and aggregated portfolios under each NGFS climate scenario.

The TREI integrates three risk dimensions:
1. Policy Risk      — exposure to carbon pricing acceleration
2. Technology Risk  — gap between current trajectory and NZE pathway
3. Market Risk      — stranded asset probability weighted by timing

Score: 0 (no exposure) → 100 (maximum transition risk exposure)

Methodology references:
- NGFS (2024) Phase V scenarios and physical/transition risk framework
- Battiston et al. (2017) "A climate stress-test of the financial system"
  Nature Climate Change, 7, 283-288. DOI: 10.1038/nclimate3255
- TCFD (2021) Guidance on Scenario Analysis for Non-Financial Companies
- IPCC AR6 WG3 (2022) Chapter 3: Mitigation pathways compatible with
  long-term goals
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from .ngfs_loader import NGFSLoader, NGFSData, CARBON_PRICE_PATHS
from .sector_mapper import (
    get_transition_risk_base,
    get_carbon_intensity,
    get_stranded_asset_risk,
    SECTOR_TRANSITION_RISK_BASE,
)

# TREI component weights
TREI_WEIGHTS = {
    "policy_risk": 0.40,
    "technology_risk": 0.35,
    "market_risk": 0.25,
}

# Reference: NZE 2050 carbon price trajectory (USD/tCO2)
# Used as benchmark for policy risk calculation
NZE_CARBON_PRICE_2030 = 130.0
NZE_CARBON_PRICE_2050 = 1000.0

# Maximum carbon price used for normalization
MAX_CARBON_PRICE = 1200.0

# Horizon years for scoring
HORIZON_YEARS = {
    "short": 2030,
    "medium": 2040,
    "long": 2050,
}


@dataclass
class SectorTREI:
    """Transition Risk Exposure Index for a single sector × scenario."""
    sector: str
    scenario: str
    horizon: str                # "short" | "medium" | "long"
    year: int

    # Component scores (0–100)
    policy_risk_score: float
    technology_risk_score: float
    market_risk_score: float

    # Composite score
    trei: float

    # Risk tier
    risk_tier: str              # "Very Low" | "Low" | "Medium" | "High" | "Very High"

    # Supporting metrics
    carbon_price_usd: float
    stranded_asset_prob: float
    emission_gap_pct: float     # % gap vs NZE pathway

    metadata: dict = field(default_factory=dict)


@dataclass
class PortfolioTREI:
    """Aggregated TREI for a portfolio across scenarios and horizons."""
    scenario: str
    horizon: str
    year: int

    # Weighted portfolio TREI
    portfolio_trei: float
    risk_tier: str

    # Sector breakdown
    sector_scores: dict[str, float]       # sector → TREI
    sector_weights: dict[str, float]      # sector → portfolio weight

    # Top contributors to risk
    top_risk_sectors: list[str]

    # Metadata
    n_companies: int
    coverage_pct: float                   # % of portfolio mapped to sectors


def _assign_risk_tier(score: float) -> str:
    """Assign qualitative risk tier from numeric TREI score."""
    if score < 20:
        return "Very Low"
    elif score < 40:
        return "Low"
    elif score < 60:
        return "Medium"
    elif score < 80:
        return "High"
    else:
        return "Very High"


def _policy_risk_score(
    scenario: str,
    sector: str,
    year: int,
    ngfs_data: NGFSData,
) -> tuple[float, float]:
    """
    Calculate policy risk score for a sector under a scenario at a given year.

    Logic: Higher carbon prices = higher policy risk for carbon-intensive sectors.
    Score adjusted by sector carbon intensity relative to economy average.

    Returns (score_0_100, carbon_price_usd)
    """
    try:
        price = ngfs_data.carbon_prices.loc[scenario, year]
    except KeyError:
        # Interpolate if exact year not available
        available = ngfs_data.carbon_prices.columns.tolist()
        prices = [ngfs_data.carbon_prices.loc[scenario, y] for y in available]
        price = float(np.interp(year, available, prices))

    # Sector carbon intensity multiplier (normalized so energy = 1.0)
    base_intensity = get_carbon_intensity(sector)
    avg_intensity = np.mean(list(
        v for k, v in {
            "Energy": 850, "Transport": 320, "Industry": 480,
            "Agriculture": 380, "Buildings": 120,
        }.items()
    ))
    intensity_factor = min(base_intensity / avg_intensity, 2.0)

    # Normalize price to 0–100
    raw_score = (price / MAX_CARBON_PRICE) * 100 * intensity_factor
    score = min(raw_score, 100.0)

    return round(score, 1), round(price, 1)


def _technology_risk_score(
    scenario: str,
    sector: str,
    year: int,
    ngfs_data: NGFSData,
) -> tuple[float, float]:
    """
    Calculate technology risk score: gap between sector emissions trajectory
    and the NZE reference pathway.

    Higher gap = higher technology risk (sector lagging behind NZE).

    Returns (score_0_100, emission_gap_pct)
    """
    try:
        sector_emissions = ngfs_data.emissions.loc[(scenario, sector)]
        nze_emissions = ngfs_data.emissions.loc[("Net Zero 2050", sector)]
    except KeyError:
        return 50.0, 0.0

    # Get values for the target year
    available = sector_emissions.index.tolist()
    if year not in available:
        emis = float(np.interp(year, available, sector_emissions.values))
        nze_emis = float(np.interp(year, available, nze_emissions.values))
    else:
        emis = sector_emissions[year]
        nze_emis = nze_emissions[year]

    # Baseline 2020
    base_year = min(available)
    baseline = sector_emissions[base_year] if base_year in available else emis

    if baseline == 0:
        return 0.0, 0.0

    # Gap: how much higher than NZE pathway?
    gap = max(emis - nze_emis, 0.0)
    gap_pct = (gap / baseline) * 100

    # Normalize: 0% gap → 0 score, 100% gap → 100 score
    score = min(gap_pct, 100.0)

    return round(score, 1), round(gap_pct, 1)


def _market_risk_score(
    scenario: str,
    sector: str,
) -> tuple[float, float]:
    """
    Calculate market/stranded asset risk score.

    Returns (score_0_100, stranded_asset_probability)
    """
    prob = get_stranded_asset_risk(sector, scenario)
    score = prob * 100.0
    return round(score, 1), round(prob, 3)


class TransitionScorer:
    """
    Computes Transition Risk Exposure Index (TREI) for sectors and portfolios.

    Parameters
    ----------
    ngfs_data : NGFSData, optional
        Pre-loaded NGFS data. If None, loads synthetic data.
    scenarios : list[str], optional
        Scenarios to score. Defaults to all 5 main NGFS scenarios.
    """

    DEFAULT_SCENARIOS = [
        "Net Zero 2050",
        "Below 2°C",
        "Delayed Transition",
        "Current Policies",
        "Nationally Determined Contributions (NDCs)",
    ]

    def __init__(
        self,
        ngfs_data: Optional[NGFSData] = None,
        scenarios: Optional[list[str]] = None,
    ):
        if ngfs_data is None:
            loader = NGFSLoader()
            ngfs_data = loader.load()
        self.ngfs_data = ngfs_data
        self.scenarios = scenarios or self.DEFAULT_SCENARIOS

    def score_sector(
        self,
        sector: str,
        scenario: str,
        horizon: str = "medium",
    ) -> SectorTREI:
        """
        Compute TREI for a single sector × scenario × horizon.

        Parameters
        ----------
        sector : str
            NGFS sector name.
        scenario : str
            NGFS scenario name.
        horizon : str
            "short" (2030), "medium" (2040), or "long" (2050).

        Returns
        -------
        SectorTREI
        """
        year = HORIZON_YEARS.get(horizon, 2040)

        policy_score, carbon_price = _policy_risk_score(
            scenario, sector, year, self.ngfs_data
        )
        tech_score, gap_pct = _technology_risk_score(
            scenario, sector, year, self.ngfs_data
        )
        market_score, stranded_prob = _market_risk_score(scenario, sector)

        trei = (
            TREI_WEIGHTS["policy_risk"] * policy_score
            + TREI_WEIGHTS["technology_risk"] * tech_score
            + TREI_WEIGHTS["market_risk"] * market_score
        )

        return SectorTREI(
            sector=sector,
            scenario=scenario,
            horizon=horizon,
            year=year,
            policy_risk_score=policy_score,
            technology_risk_score=tech_score,
            market_risk_score=market_score,
            trei=round(trei, 1),
            risk_tier=_assign_risk_tier(trei),
            carbon_price_usd=carbon_price,
            stranded_asset_prob=stranded_prob,
            emission_gap_pct=gap_pct,
        )

    def score_all_sectors(
        self,
        horizon: str = "medium",
    ) -> pd.DataFrame:
        """
        Score all NGFS sectors across all scenarios.

        Returns
        -------
        pd.DataFrame with columns: sector, scenario, TREI, risk_tier,
        policy_risk, technology_risk, market_risk, carbon_price,
        stranded_asset_prob, emission_gap_pct
        """
        sectors = list(SECTOR_TRANSITION_RISK_BASE.keys())
        rows = []
        for scenario in self.scenarios:
            for sector in sectors:
                result = self.score_sector(sector, scenario, horizon)
                rows.append({
                    "Sector": sector,
                    "Scenario": scenario,
                    "TREI": result.trei,
                    "Risk Tier": result.risk_tier,
                    "Policy Risk (0–100)": result.policy_risk_score,
                    "Technology Risk (0–100)": result.technology_risk_score,
                    "Market Risk (0–100)": result.market_risk_score,
                    "Carbon Price (USD/tCO2)": result.carbon_price_usd,
                    "Stranded Asset Probability": result.stranded_asset_prob,
                    "Emission Gap vs NZE (%)": result.emission_gap_pct,
                    "Horizon Year": HORIZON_YEARS[horizon],
                })
        return pd.DataFrame(rows)

    def heatmap_data(self, horizon: str = "medium") -> pd.DataFrame:
        """
        Return TREI values in matrix form: sectors × scenarios.
        Useful for heatmap visualization.
        """
        df = self.score_all_sectors(horizon)
        return df.pivot_table(
            index="Sector",
            columns="Scenario",
            values="TREI",
        ).round(1)

    def score_portfolio(
        self,
        sector_weights: dict[str, float],
        scenario: str,
        horizon: str = "medium",
    ) -> PortfolioTREI:
        """
        Compute weighted portfolio TREI given sector allocation.

        Parameters
        ----------
        sector_weights : dict
            {sector_name: weight} — weights should sum to ~1.0.
        scenario : str
            NGFS scenario name.
        horizon : str
            "short", "medium", or "long".

        Returns
        -------
        PortfolioTREI
        """
        year = HORIZON_YEARS.get(horizon, 2040)

        # Normalize weights
        total_weight = sum(sector_weights.values())
        if total_weight == 0:
            raise ValueError("Sector weights sum to zero.")
        norm_weights = {k: v / total_weight for k, v in sector_weights.items()}

        sector_scores = {}
        weighted_trei = 0.0

        for sector, weight in norm_weights.items():
            result = self.score_sector(sector, scenario, horizon)
            sector_scores[sector] = result.trei
            weighted_trei += weight * result.trei

        # Top 3 risk contributors
        top_sectors = sorted(
            sector_scores,
            key=lambda s: sector_scores[s] * norm_weights.get(s, 0),
            reverse=True,
        )[:3]

        return PortfolioTREI(
            scenario=scenario,
            horizon=horizon,
            year=year,
            portfolio_trei=round(weighted_trei, 1),
            risk_tier=_assign_risk_tier(weighted_trei),
            sector_scores=sector_scores,
            sector_weights=norm_weights,
            top_risk_sectors=top_sectors,
            n_companies=len(sector_weights),
            coverage_pct=100.0,
        )

    def what_if_sbti(
        self,
        sector_weights: dict[str, float],
        scenario: str,
        sbti_adoption_pct: float = 0.30,
        horizon: str = "medium",
    ) -> tuple[PortfolioTREI, PortfolioTREI]:
        """
        What-if: compare portfolio TREI before and after SBTi target adoption.

        Assumes SBTi-aligned companies reduce their sector's technology risk
        proportionally to the SBTi adoption rate.

        Parameters
        ----------
        sbti_adoption_pct : float
            Fraction of portfolio companies adopting SBTi targets (0–1).

        Returns
        -------
        (baseline_ptrei, adjusted_ptrei) : tuple of PortfolioTREI
        """
        baseline = self.score_portfolio(sector_weights, scenario, horizon)

        # Reduce technology risk by sbti_adoption_pct × 50%
        # (SBTi-aligned companies reduce tech risk gap by ~50% on average)
        reduction_factor = 1 - (sbti_adoption_pct * 0.50)

        # Rebuild scorer with adjusted data for what-if
        adjusted_weights = {
            sector: weight * reduction_factor
            if weight > 0 else weight
            for sector, weight in sector_weights.items()
        }

        # Recompute with adjusted technology risk assumption
        year = HORIZON_YEARS.get(horizon, 2040)
        sector_scores = {}
        weighted_trei = 0.0
        total_weight = sum(sector_weights.values())
        norm_weights = {k: v / total_weight for k, v in sector_weights.items()}

        for sector, weight in norm_weights.items():
            result = self.score_sector(sector, scenario, horizon)
            # Apply SBTi reduction to technology risk component
            adjusted_tech = result.technology_risk_score * reduction_factor
            adjusted_trei = (
                TREI_WEIGHTS["policy_risk"] * result.policy_risk_score
                + TREI_WEIGHTS["technology_risk"] * adjusted_tech
                + TREI_WEIGHTS["market_risk"] * result.market_risk_score
            )
            sector_scores[sector] = round(adjusted_trei, 1)
            weighted_trei += weight * adjusted_trei

        top_sectors = sorted(
            sector_scores,
            key=lambda s: sector_scores[s] * norm_weights.get(s, 0),
            reverse=True,
        )[:3]

        adjusted = PortfolioTREI(
            scenario=scenario,
            horizon=horizon,
            year=year,
            portfolio_trei=round(weighted_trei, 1),
            risk_tier=_assign_risk_tier(weighted_trei),
            sector_scores=sector_scores,
            sector_weights=norm_weights,
            top_risk_sectors=top_sectors,
            n_companies=len(sector_weights),
            coverage_pct=100.0,
        )

        return baseline, adjusted

    def robustness_table(
        self,
        sector_weights: dict[str, float],
        horizon: str = "medium",
    ) -> pd.DataFrame:
        """
        Portfolio TREI across all scenarios — DMDU-style robustness view.
        Useful for identifying strategies robust to scenario uncertainty.
        """
        rows = []
        for scenario in self.scenarios:
            ptrei = self.score_portfolio(sector_weights, scenario, horizon)
            rows.append({
                "Scenario": scenario,
                "Portfolio TREI": ptrei.portfolio_trei,
                "Risk Tier": ptrei.risk_tier,
                "Top Risk Sector": ptrei.top_risk_sectors[0] if ptrei.top_risk_sectors else "N/A",
                "Horizon": ptrei.year,
            })
        return pd.DataFrame(rows).set_index("Scenario")
