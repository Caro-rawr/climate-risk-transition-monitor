"""
climate-risk-transition-monitor
--------------------------------
NGFS-aligned climate transition risk analysis toolkit.

Modules:
- ngfs_loader      : NGFS Phase V scenario data (API + synthetic fallback)
- sector_mapper    : GICS / NACE / BMV / IEA → NGFS sector crosswalk
- transition_scorer: Transition Risk Exposure Index (TREI) engine
- portfolio_analyzer: Company portfolio analysis and aggregation
- reporter         : IFRS S2-aligned Excel + HTML reporting
"""

from .ngfs_loader import NGFSLoader, NGFSData
from .sector_mapper import map_sector, map_portfolio_sectors
from .transition_scorer import TransitionScorer, SectorTREI, PortfolioTREI
from .portfolio_analyzer import PortfolioAnalyzer, PortfolioAnalysisResult
from .reporter import GHGReporter

__all__ = [
    "NGFSLoader",
    "NGFSData",
    "map_sector",
    "map_portfolio_sectors",
    "TransitionScorer",
    "SectorTREI",
    "PortfolioTREI",
    "PortfolioAnalyzer",
    "PortfolioAnalysisResult",
    "GHGReporter",
]
