# 🌡️ Climate Transition Risk Monitor

**NGFS Phase V · IFRS S2 Aligned · Latin American Portfolio Context**

An open-source Python toolkit for analyzing climate transition risk exposure across investment portfolios, built on NGFS Phase V scenarios and aligned with IFRS S2 disclosure requirements. Designed for financial analysts, sustainability teams, and ESG researchers working in emerging market contexts.

---

## What it does

| Module | Function |
|--------|----------|
| `ngfs_loader` | Downloads NGFS Phase V scenarios via IIASA API; offline fallback with Phase V-calibrated synthetic data |
| `sector_mapper` | Translates GICS / NACE / IEA / BMV sector classifications into NGFS climate sectors |
| `transition_scorer` | Computes Transition Risk Exposure Index (TREI, 0–100) across three risk dimensions |
| `portfolio_analyzer` | Loads company portfolios, maps sectors, aggregates TREI by scenario and horizon |
| `reporter` | Generates IFRS S2-structured Excel workbooks and standalone HTML reports |

---

## Methodology: Transition Risk Exposure Index (TREI)

The TREI is a composite 0–100 score integrating three dimensions under each NGFS scenario:

```
TREI = 0.40 × Policy Risk + 0.35 × Technology Risk + 0.25 × Market Risk
```

**Policy Risk** — carbon price acceleration (NGFS Phase V, REMIND-MAgPIE) weighted by sector carbon intensity. Energy-intensive sectors face disproportionate cost exposure under orderly transition scenarios.

**Technology Risk** — gap between a sector's current emissions trajectory and the NZE 2050 reference pathway. Measures how much technological transformation is required to remain competitive.

**Market Risk** — stranded asset probability derived from NGFS Phase V physical and transition risk outputs, adapted from Battiston et al. (2017).

---

## Scenarios

NGFS Phase V (November 2024) — five canonical pathways from the Network for Greening the Financial System:

| Scenario | Temp 2100 | Carbon Price 2030 | Type |
|----------|-----------|-------------------|------|
| Net Zero 2050 | 1.5°C | $130/tCO₂ | Orderly |
| Below 2°C | 1.7°C | $80/tCO₂ | Orderly |
| Delayed Transition | 1.8°C | $10/tCO₂ | Disorderly |
| NDC | 2.5°C | $35/tCO₂ | Partial |
| Current Policies | 3.0°C | $8/tCO₂ | Hot House |

---

## Quick start

```bash
git clone https://github.com/Caro-rawr/climate-risk-transition-monitor.git
cd climate-risk-transition-monitor
pip install -r requirements.txt
```

**Run with built-in sample portfolio (40 Latin American companies):**

```bash
python main.py
```

**Analyze your own portfolio:**

```bash
python main.py --portfolio my_portfolio.csv --sector-system gics_l2
```

**Export IFRS S2 reports:**

```bash
python main.py --export excel html --org-name "Fondo Sostenible"
```

**Launch Streamlit dashboard:**

```bash
streamlit run app.py
```

**Run test suite:**

```bash
pytest tests/ -v
```

---

## Portfolio CSV format

```csv
company_name,sector,weight,sbti_status,country
CEMEX,Construction Materials,0.05,committed,MEX
Petrobras,Oil Gas & Consumable Fuels,0.07,committed,BRA
Gruma,Food Products,0.03,approved,MEX
```

| Column | Required | Description |
|--------|----------|-------------|
| `company_name` | ✅ | Company identifier |
| `sector` | ✅ | Sector label in chosen classification |
| `weight` | Optional | Portfolio weight (auto-normalized if absent) |
| `sbti_status` | Optional | `approved`, `committed`, or `none` |
| `country` | Optional | ISO 3-letter country code |

Supported sector systems: `gics`, `gics_l2`, `nace`, `bmv`, `iea`, `ngfs`

---

## Output structure

**Excel (IFRS S2 pillars):**
- Cover — metadata
- Strategy — Scenario Analysis (IFRS S2 Para. 29)
- Risk Management — Sector Exposure (Para. 25)
- Metrics & Targets (Para. 22)
- Company Detail
- Sector TREI Heatmap
- Methodology

**HTML:** Standalone report with KPI cards, scenario table, sector risk bars, and disclaimer. Suitable for internal disclosure or board presentation.

---

## Enable live NGFS API

The tool defaults to NGFS Phase V synthetic data. To query the live IIASA API:

```bash
pip install pyam-iamc
```

```python
from src.ngfs_loader import NGFSLoader
loader = NGFSLoader(use_api=True)
data = loader.load()
```

---

## Limitations

This toolkit is designed for **analytical and educational purposes**. For regulatory compliance reporting, replace synthetic data with audited inputs from certified providers (Bloomberg, CDP, MSCI, TruCost). The TREI methodology is a research instrument, not an investment recommendation.

The sector crosswalk tables (GICS → NGFS) are custom mappings. Where sector boundaries are ambiguous, we follow the IEA-to-NGFS variable mapping released by NGFS in February 2026.

---

## References

- NGFS (2024). *Phase V Climate Scenarios*. PIK / IIASA / Climate Analytics. [ngfs.net](https://www.ngfs.net/ngfs-scenarios-portal/data-resources/)
- IFRS Foundation (2023). *IFRS S2 Climate-related Disclosures*. [ifrs.org](https://www.ifrs.org/issued-standards/ifrs-sustainability-standards-navigator/ifrs-s2-climate-related-disclosures/)
- Battiston, S. et al. (2017). A climate stress-test of the financial system. *Nature Climate Change*, 7, 283–288. [DOI: 10.1038/nclimate3255](https://doi.org/10.1038/nclimate3255)
- SBTi (2024). *Financial Institutions Near-Term Criteria v2.0*. [sciencebasedtargets.org](https://sciencebasedtargets.org)
- IPCC AR6 WG3 (2022). *Mitigation of Climate Change*. [ipcc.ch](https://www.ipcc.ch/report/ar6/wg3/)
- TCFD (2021). *Guidance on Scenario Analysis for Non-Financial Companies*. [fsb-tcfd.org](https://www.fsb-tcfd.org/)

---

## Related repositories

| Repo | Description |
|------|-------------|
| [carbon-offset-quality-screener](https://github.com/Caro-rawr/carbon-offset-quality-screener) | Voluntary carbon market integrity scoring (Verra Registry) |
| [mexico-decarb-scenario-explorer](https://github.com/Caro-rawr/mexico-decarb-scenario-explorer) | GHG decarbonization scenarios for Mexico 2020–2050 |
| [ghg-inventory-toolkit](https://github.com/Caro-rawr/ghg-inventory-toolkit) | Corporate GHG inventories (Scopes 1–3, GHG Protocol, INECC 2023) |

---
## Author

Carolina Cruz Núñez | M.Sc. Sustainability Sciences 
[linkedin.com/in/carostrepto](https://linkedin.com/in/carostrepto)

