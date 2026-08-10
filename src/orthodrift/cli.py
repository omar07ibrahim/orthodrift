"""Command-line interface for reproducible OrthoDrift cases."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from orthodrift.experiment import RetrievalCaseRun, load_case, run_case
from orthodrift.reduction import Minimality
from orthodrift.report import write_report
from orthodrift.run_serialization import read_runs_jsonl, verify_run, write_runs_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="orthodrift")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="run a versioned retrieval failure case")
    run.add_argument("case", type=Path, help="path to an orthodrift.case.v1 JSON file")
    run.add_argument(
        "--output",
        type=Path,
        help="write a self-contained orthodrift.experiment-run.v1 JSONL artifact",
    )
    run.add_argument(
        "--force",
        action="store_true",
        help="replace an existing output artifact",
    )

    verify = commands.add_parser("verify", help="replay and verify experiment-run JSONL")
    verify.add_argument("artifact", type=Path, help="path to experiment-run JSONL")

    report = commands.add_parser("report", help="render one verified run as offline HTML")
    report.add_argument("artifact", type=Path, help="path to experiment-run JSONL")
    report.add_argument("--output", type=Path, required=True, help="write a self-contained HTML report")
    report.add_argument("--force", action="store_true", help="replace an existing report")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)

    try:
        if arguments.command == "run":
            run = _run(arguments.case, arguments.output, force=arguments.force)
            _print_run(run, arguments.output)
        elif arguments.command == "verify":
            runs = read_runs_jsonl(arguments.artifact)
            if not runs:
                raise ValueError("artifact contains no experiment runs")
            for run in runs:
                verify_run(run)
            print(f"verified: {len(runs)} experiment run(s)")
        else:
            _report(arguments.artifact, arguments.output, force=arguments.force)
            print(f"report: {arguments.output}")
    except (OSError, ValueError) as error:
        print(f"{parser.prog}: error: {error}", file=sys.stderr)
        return 1

    return 0


def _run(case_path: Path, output_path: Path | None, *, force: bool) -> RetrievalCaseRun:
    case = load_case(case_path)
    run = run_case(case)
    if output_path is not None:
        if case_path.resolve() == output_path.resolve():
            raise ValueError("output path must not overwrite the input case")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            write_runs_jsonl(output_path, [run], overwrite=force)
        except FileExistsError as error:
            raise ValueError("output already exists; pass --force to replace it") from error
        persisted = read_runs_jsonl(output_path)
        if persisted != (run,):
            raise ValueError("persisted artifact does not match the completed run")
        verify_run(persisted[0])
    return run


def _report(artifact_path: Path, output_path: Path, *, force: bool) -> None:
    if artifact_path.resolve() == output_path.resolve():
        raise ValueError("report output must not overwrite the experiment artifact")
    runs = read_runs_jsonl(artifact_path)
    if len(runs) != 1:
        raise ValueError("report requires exactly one experiment run")
    verify_run(runs[0])
    try:
        write_report(output_path, runs[0], overwrite=force)
    except FileExistsError as error:
        raise ValueError("report already exists; pass --force to replace it") from error


def _print_run(run: RetrievalCaseRun, output_path: Path | None) -> None:
    print(f"case: {run.case.name}")
    print(f"baseline rank: {_rank(run.baseline_rank)}")
    print(f"full mutant rank: {_rank(run.full_mutant_rank)}")
    print(_reduction_summary(run))
    for index, edit in zip(
        run.reduction.reduced_indexes,
        run.reduction.reduced_edits,
        strict=True,
    ):
        print(
            f"edit {index} [{edit.start}:{edit.end}]: "
            f"{_codepoints(edit.before)} -> {_codepoints(edit.after)}"
        )
    if output_path is not None:
        print(f"evidence: {output_path}")


def _reduction_summary(run: RetrievalCaseRun) -> str:
    count = f"{len(run.reduction.reduced_edits)}/{len(run.case.edits)} edits"
    if run.reduction.minimality is Minimality.GLOBAL:
        return f"global minimum: {count}"
    return f"one-minimal counterexample: {count}"


def _rank(rank: int | None) -> str:
    return "miss" if rank is None else str(rank)


def _codepoints(clusters: tuple[str, ...]) -> str:
    text = "".join(clusters)
    return " ".join(f"U+{ord(character):04X}" for character in text) or "∅"


if __name__ == "__main__":
    raise SystemExit(main())