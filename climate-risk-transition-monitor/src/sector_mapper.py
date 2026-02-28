"""
sector_mapper.py
----------------
Maps between sector classification systems used by different data providers:

- GICS (Global Industry Classification Standard) — Bloomberg, MSCI, S&P
- NACE Rev.2 — European Union / Eurostat
- IEA sector categories — IEA World Energy Outlook
- NGFS sectors — NGFS/IIASA scenario database
- BMV sectors — Bolsa Mexicana de Valores

The mapping enables the portfolio_analyzer to work with company data
regardless of the classification system used by the input source.

References:
- MSCI GICS structure: https://www.msci.com/our-solutions/indexes/gics
- NACE Rev.2: https://ec.europa.eu/eurostat/documents/3859598/5902521/KS-RA-07-015-EN.PDF
- NGFS sector mapping: NGFS Phase V Technical Documentation (2024)
"""

from __future__ import annotations

from typing import Optional

# ── GICS → NGFS sector mapping ────────────────────────────────────────────────
# GICS Level 1 sectors → NGFS/IEA climate sectors
# Source: adapted from NGFS Phase V IAM-to-NACE variable mapping (Feb 2026)
GICS_TO_NGFS = {
    "Energy": "Energy",
    "Materials": "Industry",
    "Industrials": "Industry",
    "Consumer Discretionary": "Transport",   # auto manufacturers dominate
    "Consumer Staples": "Agriculture",
    "Health Care": "Buildings",
    "Financials": "Financials",              # cross-sector exposure
    "Information Technology": "Buildings",
    "Communication Services": "Buildings",
    "Utilities": "Energy",
    "Real Estate": "Buildings",
}

# GICS Level 2 (Industry Group) → NGFS for higher precision
GICS_L2_TO_NGFS = {
    "Oil, Gas & Consumable Fuels": "Energy",
    "Energy Equipment & Services": "Energy",
    "Metals & Mining": "Industry",
    "Chemicals": "Industry",
    "Construction Materials": "Industry",
    "Paper & Forest Products": "Land Use",
    "Aerospace & Defense": "Transport",
    "Airlines": "Transport",
    "Ground Transportation": "Transport",
    "Automobiles": "Transport",
    "Auto Components": "Transport",
    "Food Products": "Agriculture",
    "Beverages": "Agriculture",
    "Agricultural Products & Services": "Agriculture",
    "Electric Utilities": "Energy",
    "Gas Utilities": "Energy",
    "Multi-Utilities": "Energy",
    "Water Utilities": "Buildings",
    "Real Estate Management & Development": "Buildings",
    "Diversified REITs": "Buildings",
    "Industrial REITs": "Buildings",
    "Office REITs": "Buildings",
    "Residential REITs": "Buildings",
    "Retail REITs": "Buildings",
}

# NACE Rev.2 division codes → NGFS sectors
NACE_TO_NGFS = {
    # Agriculture, Forestry
    "A01": "Agriculture",
    "A02": "Land Use",
    "A03": "Agriculture",
    # Mining & energy extraction
    "B05": "Energy",
    "B06": "Energy",
    "B07": "Industry",
    "B08": "Industry",
    "B09": "Energy",
    # Manufacturing
    "C10": "Agriculture",
    "C11": "Agriculture",
    "C13": "Industry",
    "C14": "Industry",
    "C16": "Land Use",
    "C17": "Industry",
    "C19": "Energy",
    "C20": "Industry",
    "C23": "Industry",
    "C24": "Industry",
    "C25": "Industry",
    "C26": "Industry",
    "C27": "Industry",
    "C28": "Industry",
    "C29": "Transport",
    "C30": "Transport",
    # Utilities
    "D35": "Energy",
    "E36": "Buildings",
    "E37": "Buildings",
    "E38": "Buildings",
    # Construction
    "F41": "Buildings",
    "F42": "Buildings",
    "F43": "Buildings",
    # Transport & storage
    "H49": "Transport",
    "H50": "Transport",
    "H51": "Transport",
    "H52": "Transport",
    "H53": "Transport",
    # Real estate
    "L68": "Buildings",
}

# BMV sector names (Bolsa Mexicana de Valores) → NGFS
BMV_TO_NGFS = {
    "Energía": "Energy",
    "Materiales": "Industry",
    "Industrial": "Industry",
    "Consumo discrecional": "Transport",
    "Consumo básico": "Agriculture",
    "Salud": "Buildings",
    "Servicios financieros": "Financials",
    "Tecnología": "Buildings",
    "Telecomunicaciones": "Buildings",
    "Servicios públicos": "Energy",
    "Bienes raíces": "Buildings",
}

# IEA sector names → NGFS
IEA_TO_NGFS = {
    "Power": "Energy",
    "Industry": "Industry",
    "Transport": "Transport",
    "Buildings": "Buildings",
    "Agriculture": "Agriculture",
    "Other energy": "Energy",
    "AFOLU": "Land Use",
}

# Transition risk intensity by NGFS sector
# Scale 0–10: physical asset intensity, regulatory exposure, stranded asset risk
# Source: NGFS (2024), TCFD Sector Guidance (2021)
SECTOR_TRANSITION_RISK_BASE = {
    "Energy": 9.5,
    "Transport": 7.5,
    "Industry": 7.0,
    "Agriculture": 5.0,
    "Buildings": 5.5,
    "Land Use": 4.5,
    "Financials": 3.0,   # cross-sector exposure, modeled separately
}

# Carbon intensity by sector (tCO2e per USD million revenue, 2022 estimates)
# Source: IEA (2023) World Energy Outlook, IPCC AR6 WG3 Chapter 2
SECTOR_CARBON_INTENSITY = {
    "Energy": 850.0,
    "Transport": 320.0,
    "Industry": 480.0,
    "Agriculture": 380.0,
    "Buildings": 120.0,
    "Land Use": 290.0,
    "Financials": 45.0,
}

# Stranded asset risk score by scenario × sector (0–1, probability of material stranding by 2035)
# Derived from NGFS Phase V physical risk outputs and IEA Net Zero 2050 analysis
STRANDED_ASSET_RISK = {
    "Net Zero 2050": {
        "Energy": 0.75,
        "Transport": 0.50,
        "Industry": 0.40,
        "Agriculture": 0.15,
        "Buildings": 0.20,
        "Land Use": 0.10,
        "Financials": 0.05,
    },
    "Below 2°C": {
        "Energy": 0.55,
        "Transport": 0.35,
        "Industry": 0.28,
        "Agriculture": 0.10,
        "Buildings": 0.15,
        "Land Use": 0.08,
        "Financials": 0.03,
    },
    "Delayed Transition": {
        "Energy": 0.85,
        "Transport": 0.60,
        "Industry": 0.55,
        "Agriculture": 0.20,
        "Buildings": 0.30,
        "Land Use": 0.15,
        "Financials": 0.08,
    },
    "Current Policies": {
        "Energy": 0.10,
        "Transport": 0.08,
        "Industry": 0.06,
        "Agriculture": 0.05,
        "Buildings": 0.04,
        "Land Use": 0.03,
        "Financials": 0.01,
    },
    "Nationally Determined Contributions (NDCs)": {
        "Energy": 0.30,
        "Transport": 0.20,
        "Industry": 0.18,
        "Agriculture": 0.08,
        "Buildings": 0.10,
        "Land Use": 0.06,
        "Financials": 0.02,
    },
}

SUPPORTED_SYSTEMS = ["gics", "gics_l2", "nace", "bmv", "iea", "ngfs"]


def map_sector(
    sector: str,
    from_system: str,
    to_system: str = "ngfs",
) -> Optional[str]:
    """
    Map a sector name from one classification system to another.

    Parameters
    ----------
    sector : str
        Input sector name.
    from_system : str
        Source classification: 'gics', 'gics_l2', 'nace', 'bmv', 'iea', 'ngfs'.
    to_system : str
        Target classification. Currently only 'ngfs' is fully supported.

    Returns
    -------
    str or None
        Mapped sector name, or None if no mapping found.
    """
    from_system = from_system.lower()
    to_system = to_system.lower()

    if to_system != "ngfs":
        raise NotImplementedError(
            f"Mapping to '{to_system}' not yet implemented. Use 'ngfs'."
        )

    mapping_tables = {
        "gics": GICS_TO_NGFS,
        "gics_l2": GICS_L2_TO_NGFS,
        "nace": NACE_TO_NGFS,
        "bmv": BMV_TO_NGFS,
        "iea": IEA_TO_NGFS,
        "ngfs": {s: s for s in SECTOR_TRANSITION_RISK_BASE},
    }

    table = mapping_tables.get(from_system)
    if table is None:
        raise ValueError(
            f"Unknown source system '{from_system}'. "
            f"Supported: {SUPPORTED_SYSTEMS}"
        )

    return table.get(sector)


def map_portfolio_sectors(
    df: "pd.DataFrame",
    sector_col: str,
    from_system: str,
    output_col: str = "ngfs_sector",
) -> "pd.DataFrame":
    """
    Add an NGFS sector column to a portfolio DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Portfolio data with a sector column.
    sector_col : str
        Name of the column containing sector labels.
    from_system : str
        Classification system of sector_col.
    output_col : str
        Name of the new column to add.

    Returns
    -------
    pd.DataFrame
        Input DataFrame with output_col added.
    """
    import pandas as pd  # local import to keep module lightweight

    result = df.copy()
    result[output_col] = result[sector_col].map(
        lambda s: map_sector(str(s), from_system=from_system)
    )
    unmapped = result[output_col].isna().sum()
    if unmapped > 0:
        print(
            f"[SectorMapper] {unmapped} companies could not be mapped "
            f"from '{from_system}' to NGFS. They will be excluded from "
            f"sector-level analysis."
        )
    return result


def get_transition_risk_base(sector: str) -> float:
    """Return base transition risk score (0–10) for an NGFS sector."""
    return SECTOR_TRANSITION_RISK_BASE.get(sector, 5.0)


def get_carbon_intensity(sector: str) -> float:
    """Return estimated carbon intensity (tCO2e/USD million revenue)."""
    return SECTOR_CARBON_INTENSITY.get(sector, 200.0)


def get_stranded_asset_risk(sector: str, scenario: str) -> float:
    """Return stranded asset probability (0–1) for sector × scenario."""
    scenario_risks = STRANDED_ASSET_RISK.get(scenario, {})
    return scenario_risks.get(sector, 0.05)


def sector_summary_table() -> "pd.DataFrame":
    """Return a summary DataFrame of all sector properties."""
    import pandas as pd  # local import

    rows = []
    for sector in SECTOR_TRANSITION_RISK_BASE:
        rows.append({
            "Sector": sector,
            "Base Transition Risk (0–10)": SECTOR_TRANSITION_RISK_BASE[sector],
            "Carbon Intensity (tCO2e/USDm)": SECTOR_CARBON_INTENSITY.get(sector),
            "Stranded Asset Risk NZ2050": STRANDED_ASSET_RISK.get(
                "Net Zero 2050", {}
            ).get(sector),
        })
    return pd.DataFrame(rows).set_index("Sector")
