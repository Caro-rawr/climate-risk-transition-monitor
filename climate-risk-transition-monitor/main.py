"""
main.py
-------
Command-line entry point for the climate-risk-transition-monitor toolkit.

Usage examples:
    python main.py                              # Full analysis, sample portfolio
    python main.py --portfolio my_portfolio.csv # Custom portfolio
    python main.py --scenario "Net Zero 2050"   # Single scenario
    python main.py --horizon long               # Long-term horizon (2050)
    python main.py --export excel html          # Generate reports
    python main.py --sector-scores              # Sector-only TREI table
    python main.py --what-if 0.50               # 50% SBTi adoption what-if
"""

import argparse
import sys
from pathlib import Path

# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="climate-risk-monitor",
        description=(
            "NGFS Phase V climate transition risk analysis · IFRS S2 aligned\n"
            "github.com/Caro-rawr/climate-risk-transition-monitor"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--portfolio", "-p",
        type=str,
        default=None,
        help="Path to portfolio CSV. Omit to use built-in sample (40 LatAm companies).",
    )
    parser.add_argument(
        "--sector-system", "-s",
        type=str,
        default="gics_l2",
        choices=["gics", "gics_l2", "nace", "bmv", "iea", "ngfs"],
        help="Sector classification system used in portfolio CSV. Default: gics_l2",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help=(
            'Single scenario to analyze. Default: all five NGFS scenarios.\n'
            'Options: "Net Zero 2050", "Below 2°C", "Delayed Transition", '
            '"Current Policies", "Nationally Determined Contributions (NDCs)"'
        ),
    )
    parser.add_argument(
        "--horizon",
        type=str,
        default="medium",
        choices=["short", "medium", "long"],
        help="Time horizon: short (2030), medium (2040), long (2050). Default: medium",
    )
    parser.add_argument(
        "--export",
        nargs="+",
        choices=["excel", "html"],
        default=[],
        help="Export report formats. Example: --export excel html",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs",
        help="Directory for exported reports. Default: outputs/",
    )
    parser.add_argument(
        "--sector-scores",
        action="store_true",
        help="Print sector TREI table across all scenarios and exit.",
    )
    parser.add_argument(
        "--what-if",
        type=float,
        default=None,
        metavar="SBTI_RATE",
        help=(
            "Run what-if analysis at this SBTi adoption rate (0.0–1.0). "
            "Example: --what-if 0.50 for 50%% adoption."
        ),
    )
    parser.add_argument(
        "--ngfs-summary",
        action="store_true",
        help="Print NGFS scenario summary table and exit.",
    )
    parser.add_argument(
        "--org-name",
        type=str,
        default="Portfolio",
        help="Organization name for report headers. Default: 'Portfolio'",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress informational output.",
    )
    return parser


# ── Runner ────────────────────────────────────────────────────────────────────

def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    from src.ngfs_loader import NGFSLoader
    from src.transition_scorer import TransitionScorer
    from src.portfolio_analyzer import PortfolioAnalyzer
    from src.reporter import GHGReporter

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── NGFS summary ─────────────────────────────────────────────────────────
    if args.ngfs_summary:
        loader = NGFSLoader()
        data = loader.load()
        print("\n── NGFS Phase V Scenario Summary ──────────────────────────")
        print(loader.summary_table().to_string())
        print()
        return 0

    # ── Sector scores ─────────────────────────────────────────────────────────
    if args.sector_scores:
        if not args.quiet:
            print("\n── Sector TREI Scores (medium horizon, 2040) ───────────")
        scorer = TransitionScorer()
        df = scorer.heatmap_data(horizon="medium")
        print(df.round(1).to_string())
        print()
        return 0

    # ── Load NGFS data ────────────────────────────────────────────────────────
    if not args.quiet:
        print("\n🌡️  Climate Transition Risk Monitor")
        print("   NGFS Phase V · IFRS S2 · TCFD\n")
        print("   Loading NGFS scenario data...")

    loader = NGFSLoader()
    ngfs_data = loader.load()
    scorer = TransitionScorer(ngfs_data=ngfs_data)

    # ── Portfolio analysis ────────────────────────────────────────────────────
    if not args.quiet:
        portfolio_label = args.portfolio or "built-in sample (40 LatAm companies)"
        print(f"   Portfolio: {portfolio_label}")
        print(f"   Horizon:   {args.horizon} ({{'short':2030,'medium':2040,'long':2050}[args.horizon]})\n")

    scenarios = [args.scenario] if args.scenario else None

    analyzer = PortfolioAnalyzer(
        portfolio_path=args.portfolio,
        sector_system=args.sector_system,
        ngfs_data=ngfs_data,
    )
    result = analyzer.analyze(scenarios=scenarios, horizons=[args.horizon])

    # ── Print summary ─────────────────────────────────────────────────────────
    reporter = GHGReporter(
        result=result,
        org_name=args.org_name,
        reporting_year=2025,
        scorer=scorer,
    )
    reporter.print_summary()

    # ── Robustness table ──────────────────────────────────────────────────────
    if not args.quiet and not args.scenario:
        rob = scorer.robustness_table(result.sector_weights, horizon=args.horizon)
        print("── DMDU Robustness Table ─────────────────────────────────────")
        print(rob.to_string())
        print()

    # ── What-if ───────────────────────────────────────────────────────────────
    if args.what_if is not None:
        rate = max(0.0, min(1.0, args.what_if))
        print(f"\n── What-If: {rate*100:.0f}% SBTi Adoption ───────────────────────")
        for scenario in (scenarios or [
            "Net Zero 2050",
            "Below 2°C",
            "Delayed Transition",
            "Current Policies",
            "Nationally Determined Contributions (NDCs)",
        ]):
            if result.sector_weights:
                baseline, adjusted = scorer.what_if_sbti(
                    result.sector_weights, scenario,
                    sbti_adoption_pct=rate,
                    horizon=args.horizon,
                )
                delta = baseline.portfolio_trei - adjusted.portfolio_trei
                print(
                    f"  {scenario:<48} "
                    f"Baseline: {baseline.portfolio_trei:5.1f}  →  "
                    f"Adjusted: {adjusted.portfolio_trei:5.1f}  "
                    f"(−{delta:.1f})"
                )
        print()

    # ── Export ────────────────────────────────────────────────────────────────
    if "excel" in args.export:
        out = output_dir / "climate_risk_report.xlsx"
        reporter.to_excel(out)

    if "html" in args.export:
        out = output_dir / "climate_risk_report.html"
        reporter.to_html(out)

    return 0


if __name__ == "__main__":
    sys.exit(main())
