"""Run the evaluation suite against the configured (live) model.

    python -m app.services.evaluation [--no-persist] [--json PATH]

Exit codes: 0 all cases passed, 1 some cases failed or errored, 2 configuration or
storage problem (e.g. no OPENAI_API_KEY, database unavailable).
"""

import argparse
import asyncio
import sys
from pathlib import Path

from app.core.config import Settings, get_settings
from app.core.logging_config import configure_logging
from app.db.errors import PersistenceError
from app.db.session import create_db_engine, create_session_factory
from app.repositories.evaluations import EvaluationRepository
from app.services.ai.config import ReviewConfig
from app.services.ai.factory import create_review_engine
from app.services.ai.openai_provider import create_openai_client
from app.services.ai.review_engine import ReviewEngine
from app.services.evaluation.cases import EVAL_CASES
from app.services.evaluation.runner import EvaluationRunner
from app.services.evaluation.schemas import EvaluationRunResult

EXIT_OK, EXIT_FAILED, EXIT_CONFIG = 0, 1, 2


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m app.services.evaluation")
    parser.add_argument(
        "--no-persist", action="store_true", help="Do not save the run to the database."
    )
    parser.add_argument("--json", type=Path, help="Also write the full run result to this file.")
    return parser.parse_args(argv)


async def run(
    args: argparse.Namespace, settings: Settings, engine: ReviewEngine | None = None
) -> int:
    """Run the suite. ``engine`` is injectable for tests; by default the OpenAI engine is used."""
    client = None
    if engine is None:
        client = create_openai_client(settings)
        if client is None:
            print("OPENAI_API_KEY is not set; live evaluation needs it.", file=sys.stderr)
            return EXIT_CONFIG
        engine = create_review_engine(settings, client)
    try:
        result = await EvaluationRunner(engine, ReviewConfig.from_settings(settings)).run(
            EVAL_CASES
        )
    finally:
        if client is not None:
            await client.close()

    print(format_report(result))
    if args.json:
        args.json.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    if not args.no_persist:
        try:
            _persist(result, settings)
        except PersistenceError as exc:
            print(f"Could not save the evaluation run: {exc.message}", file=sys.stderr)
            return EXIT_CONFIG
        print(f"Saved evaluation run {result.id}.")
    return EXIT_OK if result.passed_cases == result.total_cases else EXIT_FAILED


def _persist(result: EvaluationRunResult, settings: Settings) -> None:
    engine = create_db_engine(settings.database_url)
    try:
        with create_session_factory(engine)() as session:
            EvaluationRepository(session).save(result)
    finally:
        engine.dispose()


def format_report(result: EvaluationRunResult) -> str:
    lines = [
        f"Evaluation run {result.id}",
        f"model={result.model} provider={result.provider} prompt_version={result.prompt_version}",
        "",
    ]
    for case in result.cases:
        status = "ERROR" if case.error else ("PASS" if case.passed else "FAIL")
        lines.append(f"  {status:<5} {case.case_id} ({case.latency_ms} ms)")
        if case.error:
            lines.append(f"        {case.error}")
        lines.extend(f"        - {detail}" for detail in case.failed_expectations)
    lines += [
        "",
        f"passed {result.passed_cases}/{result.total_cases}, "
        f"failed {result.failed_cases}, errored {result.errored_cases}",
    ]
    for kind, metric in result.metrics.conditions.items():
        lines.append(f"  {kind}: {metric.passed}/{metric.evaluated}")
    return "\n".join(lines)


def main() -> int:
    configure_logging()
    return asyncio.run(run(parse_args(sys.argv[1:]), get_settings()))


if __name__ == "__main__":
    sys.exit(main())
