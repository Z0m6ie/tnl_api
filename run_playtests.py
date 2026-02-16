#!/usr/bin/env python3
"""
TNL Automated Playtesting CLI

Run multiple AI agents through the game to generate playthroughs for analysis.
"""

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from playtesting import PlaytestConfig, PlaytestOrchestrator
from playtesting.analysis import AnalysisReportGenerator


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet down noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def main():
    parser = argparse.ArgumentParser(
        description="TNL Automated Playtesting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run 10 agents with varied genres, 100 turns each
  python run_playtests.py

  # Quick test with 1 agent, 10 turns
  python run_playtests.py --agents 1 --turns 10

  # Run 5 agents with 50 turns, save to custom directory
  python run_playtests.py --agents 5 --turns 50 --output ./my_results

  # Generate review report from existing results
  python run_playtests.py --report-only --output ./playtest_results
        """
    )

    parser.add_argument(
        "--agents", "-n",
        type=int,
        default=10,
        help="Number of agents to run (default: 10)"
    )

    parser.add_argument(
        "--turns", "-t",
        type=int,
        default=100,
        help="Number of gameplay turns per agent (default: 100)"
    )

    parser.add_argument(
        "--output", "-o",
        type=str,
        default="./playtest_results",
        help="Output directory for results (default: ./playtest_results)"
    )

    parser.add_argument(
        "--concurrent", "-c",
        type=int,
        default=5,
        help="Max concurrent agents (default: 5, respect API rate limits)"
    )

    parser.add_argument(
        "--no-vary-genres",
        action="store_true",
        help="Don't vary genres across agents (all use random/surprise me)"
    )

    parser.add_argument(
        "--single", "-s",
        type=int,
        metavar="AGENT_ID",
        help="Run only a single agent by ID (0-9 for default configs)"
    )

    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Only generate review report from existing results (don't run new playtests)"
    )

    parser.add_argument(
        "--compact-report",
        action="store_true",
        help="Generate compact report (sampled turns) in addition to full report"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    parser.add_argument(
        "--delay",
        type=int,
        default=100,
        help="Delay between messages in ms (default: 100)"
    )

    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # Create config
    config = PlaytestConfig(
        num_agents=args.agents,
        messages_per_session=args.turns,
        output_dir=args.output,
        max_concurrent_agents=args.concurrent,
        vary_genres=not args.no_vary_genres,
        delay_between_messages_ms=args.delay,
    )

    # Create orchestrator
    orchestrator = PlaytestOrchestrator(config)

    if args.report_only:
        # Just generate report from existing results
        logger.info(f"Loading existing results from {args.output}")
        results = orchestrator.load_results()

        if not results:
            logger.error("No playthroughs found in output directory")
            sys.exit(1)

    elif args.single is not None:
        # Run single agent
        logger.info(f"Running single agent (ID: {args.single})")
        results = [orchestrator.run_single(args.single)]

    else:
        # Run all agents
        logger.info(f"Starting playtest: {args.agents} agents, {args.turns} turns each")
        results = orchestrator.run_all()

    # Generate reports
    logger.info("Generating analysis reports...")
    report_gen = AnalysisReportGenerator(args.output)

    # Full review prompt
    review_path = report_gen.save_review_prompt(results)
    logger.info(f"Full review prompt saved to: {review_path}")

    # Compact report if requested
    if args.compact_report:
        compact_path = report_gen.save_compact_report(results)
        logger.info(f"Compact report saved to: {compact_path}")

    # Summary
    successful = sum(1 for r in results if r.metadata.completed_normally)
    failed = len(results) - successful

    print("\n" + "=" * 60)
    print("PLAYTEST COMPLETE")
    print("=" * 60)
    print(f"Total playthroughs: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"\nResults saved to: {args.output}")
    print(f"Review prompt: {review_path}")
    print("\nNext steps:")
    print("1. Open review_prompt.md")
    print("2. Send to Claude for analysis")
    print("3. Review the structured feedback")
    print("=" * 60)


if __name__ == "__main__":
    main()
