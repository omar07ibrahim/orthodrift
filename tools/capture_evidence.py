"""Generate and verify source-bound OrthoDrift portfolio evidence."""

# ruff: noqa: E501 -- SVG and terminal HTML are intentionally readable source

from __future__ import annotations

import argparse
import hashlib
import html
import json
import struct
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from io import BytesIO
from pathlib import Path
from typing import Any

FORMAT = "orthodrift.evidence.v1"
EVIDENCE_DIRECTORY = Path("docs/evidence")
MANIFEST_NAME = "orthodrift-evidence.json"
EXPECTED_FILES = {
    "grapheme-provenance.svg",
    "rank-flip.svg",
    "reduction-trace.svg",
    "shaki-cli.png",
    "shaki-cli.txt",
    "shaki-interaction.gif",
    "shaki-report-full.png",
    "shaki-report-mobile.png",
    "shaki-report.html",
    "shaki-report.png",
    "shaki-run.jsonl",
    "verification-architecture.svg",
}
MEDIA_TYPES = {
    ".gif": "image/gif",
    ".html": "text/html",
    ".jsonl": "application/x-ndjson",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".txt": "text/plain",
}
FORBIDDEN_TEXT = (
    "/home/",
    "/Users/",
    "github_pat_",
    "ghp_",
    "sk-proj-",
    "BEGIN PRIVATE KEY",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare")
    prepare.add_argument("--root", type=Path, required=True)
    prepare.add_argument("--artifact", type=Path, required=True)
    prepare.add_argument("--report", type=Path, required=True)
    prepare.add_argument("--cli", type=Path, required=True)
    prepare.add_argument("--output-root", type=Path, required=True)

    capture = commands.add_parser("capture")
    capture.add_argument("--output-root", type=Path, required=True)
    capture.add_argument("--container-image", required=True)

    finalize = commands.add_parser("finalize")
    finalize.add_argument("--root", type=Path, required=True)
    finalize.add_argument("--output-root", type=Path, required=True)
    finalize.add_argument("--source-revision", required=True)
    finalize.add_argument("--source-tree", required=True)
    finalize.add_argument("--container-image", required=True)
    finalize.add_argument("--browser", required=True)
    finalize.add_argument("--playwright", required=True)
    finalize.add_argument("--pillow", required=True)

    verify = commands.add_parser("verify")
    verify.add_argument("--root", type=Path, required=True)
    verify.add_argument("--output-root", type=Path, required=True)
    verify.add_argument("--source-revision", required=True)
    verify.add_argument("--source-tree", required=True)
    verify.add_argument("--container-image", required=True)

    visuals = commands.add_parser("verify-visuals")
    visuals.add_argument("--output-root", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    if arguments.command == "prepare":
        prepare(arguments.root, arguments.artifact, arguments.report, arguments.cli, arguments.output_root)
    elif arguments.command == "capture":
        capture(arguments.output_root, arguments.container_image)
    elif arguments.command == "finalize":
        finalize(
            arguments.root,
            arguments.output_root,
            arguments.source_revision,
            arguments.source_tree,
            arguments.container_image,
            arguments.browser,
            arguments.playwright,
            arguments.pillow,
        )
    elif arguments.command == "verify":
        verify(
            arguments.root,
            arguments.output_root,
            arguments.source_revision,
            arguments.source_tree,
            arguments.container_image,
        )
    else:
        verify_visuals(arguments.output_root)
    return 0


def prepare(root: Path, artifact: Path, report: Path, cli: Path, output_root: Path) -> None:
    root = root.resolve()
    if output_root.exists():
        raise ValueError("evidence output root already exists")
    evidence = output_root / EVIDENCE_DIRECTORY
    evidence.mkdir(parents=True)

    run = _load_verified_run(artifact)
    from orthodrift.report import render_report

    artifact_bytes = artifact.read_bytes()
    report_text = report.read_text(encoding="utf-8")
    cli_text = cli.read_text(encoding="utf-8")
    if report_text != render_report(run):
        raise ValueError("CLI report does not equal the verified library rendering")
    _reject_sensitive_text(cli_text)
    if not cli_text.startswith("$ orthodrift run "):
        raise ValueError("CLI transcript does not start with the executed run command")

    (evidence / "shaki-run.jsonl").write_bytes(artifact_bytes)
    (evidence / "shaki-report.html").write_text(report_text, encoding="utf-8", newline="\n")
    (evidence / "shaki-cli.txt").write_text(cli_text, encoding="utf-8", newline="\n")
    _write_text(evidence / "rank-flip.svg", _rank_flip_svg(run))
    _write_text(evidence / "grapheme-provenance.svg", _provenance_svg(run))
    _write_text(evidence / "reduction-trace.svg", _reduction_svg(run))
    _write_text(evidence / "verification-architecture.svg", _architecture_svg())

    for path in _source_paths(root):
        if not path.is_file():
            raise ValueError(f"missing evidence source: {path.relative_to(root)}")


def capture(output_root: Path, container_image: str) -> None:
    from PIL import Image
    from playwright.sync_api import sync_playwright

    evidence = output_root / EVIDENCE_DIRECTORY
    report = (evidence / "shaki-report.html").resolve()
    cli_text = (evidence / "shaki-cli.txt").read_text(encoding="utf-8")
    _reject_sensitive_text(cli_text)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=["--disable-gpu"])
        if browser.version != "151.0.7922.34":
            raise ValueError(f"unexpected Chromium version: {browser.version}")

        desktop = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
        desktop.goto(report.as_uri(), wait_until="load")
        desktop.locator("[data-variant=baseline]").wait_for()
        desktop.screenshot(path=evidence / "shaki-report.png", animations="disabled")
        desktop.screenshot(path=evidence / "shaki-report-full.png", full_page=True, animations="disabled")

        mobile = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        mobile.goto(report.as_uri(), wait_until="load")
        mobile.locator("[data-variant=baseline]").wait_for()
        mobile.screenshot(path=evidence / "shaki-report-mobile.png", animations="disabled")
        mobile.close()

        interaction = browser.new_page(viewport={"width": 1120, "height": 820}, device_scale_factor=1)
        interaction.goto(report.as_uri(), wait_until="load")
        frames = [interaction.screenshot(animations="disabled")]
        for selector in ("[data-variant=full]", "[data-variant=minimal]"):
            interaction.locator(selector).click()
            frames.append(interaction.screenshot(animations="disabled"))
        images = [Image.open(BytesIO(frame)).convert("P", palette=Image.Palette.ADAPTIVE, colors=128) for frame in frames]
        images[0].save(
            evidence / "shaki-interaction.gif",
            save_all=True,
            append_images=images[1:],
            duration=[900, 1_100, 1_500],
            loop=0,
            disposal=2,
            optimize=False,
        )
        interaction.close()

        terminal = browser.new_page(viewport={"width": 1180, "height": 650}, device_scale_factor=1)
        terminal.set_content(_terminal_html(cli_text), wait_until="load")
        terminal.locator("pre").wait_for()
        terminal.screenshot(path=evidence / "shaki-cli.png", animations="disabled")
        terminal.close()
        desktop.close()
        browser.close()

    if container_image != "mcr.microsoft.com/playwright/python@sha256:51d31fdfacb0cff99a1a724152e34ae408d2bd4e7da310ff157450f49261cc59":
        raise ValueError("capture image does not match the reviewed platform manifest")


def finalize(
    root: Path,
    output_root: Path,
    source_revision: str,
    source_tree: str,
    container_image: str,
    browser: str,
    playwright: str,
    pillow: str,
) -> None:
    _validate_oid(source_revision, "source revision")
    _validate_oid(source_tree, "source tree")
    evidence = output_root / EVIDENCE_DIRECTORY
    actual = {path.name for path in evidence.iterdir() if path.is_file()}
    if actual != EXPECTED_FILES:
        raise ValueError(f"evidence files differ before finalization: {sorted(actual ^ EXPECTED_FILES)}")

    run = _load_verified_run(evidence / "shaki-run.jsonl")
    from orthodrift.run_serialization import run_to_record

    record = run_to_record(run)
    sources = [_file_record(path, root) for path in _source_paths(root)]
    files = [_file_record(path, output_root) for path in sorted(evidence.iterdir())]
    for item in files:
        path = output_root / str(item["path"])
        if path.suffix == ".png":
            item["dimensions"] = list(_png_dimensions(path))
        elif path.suffix == ".gif":
            item["dimensions"] = list(_gif_dimensions(path))
            item["frames"] = 3

    manifest: dict[str, object] = {
        "format": FORMAT,
        "source_revision": source_revision,
        "source_tree": source_tree,
        "case_sha256": record["case_sha256"],
        "artifact_sha256": _sha256(evidence / "shaki-run.jsonl"),
        "runtime": record["runtime"],
        "result": {
            "case": run.case.name,
            "baseline_rank": run.baseline_rank,
            "full_mutant_rank": run.full_mutant_rank,
            "minimal_rank": run.rank_for(run.reduction.reduced_indexes),
            "minimal_edits": len(run.reduction.reduced_edits),
            "supplied_edits": len(run.case.edits),
            "minimality": run.reduction.minimality.value,
            "evaluations": run.reduction.evaluations,
        },
        "capture": {
            "browser": browser,
            "playwright": playwright,
            "pillow": pillow,
            "container_image": container_image,
            "viewports": ["1440x1000", "390x844", "1120x820", "1180x650"],
            "gif_frames": 3,
            "network": "disabled",
        },
        "claim_boundary": {
            "fixture": "synthetic Şəki lexical retrieval case",
            "is_broad_benchmark": False,
            "is_dense_retrieval_evidence": False,
            "has_native_language_review": False,
            "contains_personal_data": False,
        },
        "sources": sources,
        "files": files,
    }
    _write_text(evidence / MANIFEST_NAME, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    verify(root, output_root, source_revision, source_tree, container_image)


def verify(
    root: Path,
    output_root: Path,
    source_revision: str,
    source_tree: str,
    container_image: str,
) -> None:
    root = root.resolve()
    _validate_oid(source_revision, "source revision")
    _validate_oid(source_tree, "source tree")
    evidence = output_root / EVIDENCE_DIRECTORY
    manifest_path = evidence / MANIFEST_NAME
    manifest = _load_unique_json(manifest_path)
    expected_keys = {
        "artifact_sha256",
        "capture",
        "case_sha256",
        "claim_boundary",
        "files",
        "format",
        "result",
        "runtime",
        "source_revision",
        "source_tree",
        "sources",
    }
    if set(manifest) != expected_keys:
        raise ValueError("evidence manifest fields differ")
    if manifest["format"] != FORMAT:
        raise ValueError("unsupported evidence manifest")
    if manifest["source_revision"] != source_revision or manifest["source_tree"] != source_tree:
        raise ValueError("evidence source binding differs")
    capture_record = _mapping(manifest["capture"], "capture")
    if capture_record.get("container_image") != container_image or capture_record.get("network") != "disabled":
        raise ValueError("capture environment differs")

    actual_names = {path.name for path in evidence.iterdir() if path.is_file()}
    if actual_names != EXPECTED_FILES | {MANIFEST_NAME}:
        raise ValueError(f"evidence file set differs: {sorted(actual_names)}")
    if any(path.is_symlink() for path in output_root.rglob("*")):
        raise ValueError("evidence bundle cannot contain symlinks")

    expected_sources = [_file_record(path, root) for path in _source_paths(root)]
    if manifest["sources"] != expected_sources:
        raise ValueError("evidence source hashes differ")
    expected_records = [_file_record(path, output_root) for path in sorted(evidence.iterdir()) if path.name != MANIFEST_NAME]
    recorded_files = manifest["files"]
    if not isinstance(recorded_files, list):
        raise ValueError("manifest files must be an array")
    stripped_records = []
    for item in recorded_files:
        record = dict(_mapping(item, "file"))
        record.pop("dimensions", None)
        record.pop("frames", None)
        stripped_records.append(record)
    if stripped_records != expected_records:
        raise ValueError("evidence file hashes differ")

    run = _load_verified_run(evidence / "shaki-run.jsonl")
    from orthodrift.report import render_report
    from orthodrift.run_serialization import run_to_record

    if (evidence / "shaki-report.html").read_text(encoding="utf-8") != render_report(run):
        raise ValueError("committed report differs from verified rendering")
    if manifest["case_sha256"] != run_to_record(run)["case_sha256"]:
        raise ValueError("manifest case digest differs")
    if manifest["artifact_sha256"] != _sha256(evidence / "shaki-run.jsonl"):
        raise ValueError("manifest artifact digest differs")

    _reject_sensitive_text((evidence / "shaki-cli.txt").read_text(encoding="utf-8"))
    for path in evidence.glob("*.svg"):
        _verify_svg(path)
    for item in recorded_files:
        record = _mapping(item, "file")
        path = output_root / str(record["path"])
        if path.suffix == ".png" and list(_png_dimensions(path)) != record.get("dimensions"):
            raise ValueError(f"PNG dimensions differ: {path}")
        if path.suffix == ".gif":
            if list(_gif_dimensions(path)) != record.get("dimensions") or record.get("frames") != 3:
                raise ValueError("GIF contract differs")


def verify_visuals(output_root: Path) -> None:
    from PIL import Image

    evidence = output_root / EVIDENCE_DIRECTORY
    for path in evidence.glob("*.png"):
        with Image.open(path) as image:
            image.load()
            if image.format != "PNG":
                raise ValueError(f"unexpected raster format: {path}")
    with Image.open(evidence / "shaki-interaction.gif") as animation:
        if animation.format != "GIF" or animation.n_frames != 3 or animation.size != (1120, 820):
            raise ValueError("interaction GIF contract differs")


def _load_verified_run(path: Path) -> Any:
    from orthodrift.run_serialization import read_runs_jsonl, verify_run

    runs = read_runs_jsonl(path)
    if len(runs) != 1:
        raise ValueError("evidence requires exactly one experiment run")
    verify_run(runs[0])
    return runs[0]


def _source_paths(root: Path) -> list[Path]:
    relative = [
        Path("examples/shaki-rank-flip.json"),
        Path("pyproject.toml"),
        Path("requirements/evidence-browser-image.lock.json"),
        Path("requirements/evidence-browser.txt"),
        Path("requirements/runtime.in"),
        Path("requirements/runtime.txt"),
        Path("tools/capture_evidence.py"),
    ]
    relative.extend(path.relative_to(root) for path in sorted((root / "src/orthodrift").glob("*.py")))
    relative.append(Path("src/orthodrift/py.typed"))
    return [root / path for path in sorted(set(relative))]


def _file_record(path: Path, root: Path) -> dict[str, object]:
    relative = path.relative_to(root).as_posix()
    record: dict[str, object] = {
        "path": relative,
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }
    if path.suffix in MEDIA_TYPES:
        record["media_type"] = MEDIA_TYPES[path.suffix]
    return record


def _variants(run: Any) -> list[dict[str, object]]:
    from orthodrift.text import apply_grapheme_edits

    queries = [
        ("Baseline", run.case.query),
        ("All mutations", apply_grapheme_edits(run.case.query, run.case.edits)),
        ("Minimal failure", run.reduction.text),
    ]
    index = run.retriever.build(run.case.documents)
    variants: list[dict[str, object]] = []
    for label, query in queries:
        hits = index.search(query, limit=len(run.case.documents))
        target = next((hit for hit in hits if hit.document_id == run.case.target_document_id), None)
        variants.append(
            {
                "label": label,
                "query": query,
                "rank": None if target is None else target.rank,
                "score": 0.0 if target is None else target.score,
            }
        )
    return variants


def _rank_flip_svg(run: Any) -> str:
    variants = _variants(run)
    maximum_score = max(float(item["score"]) for item in variants) or 1.0
    groups = []
    for index, item in enumerate(variants):
        x = 145 + index * 310
        rank = item["rank"]
        y = 202 + ((int(rank) - 1) * 92 if rank is not None else 190)
        score = float(item["score"])
        width = score / maximum_score * 180
        groups.append(
            f'<g><text x="{x}" y="142" class="label">{_xml(str(item["label"]))}</text>'
            f'<circle cx="{x + 90}" cy="{y}" r="28" class="point"/><text x="{x + 90}" y="{y + 7}" class="rank">#{rank if rank is not None else "miss"}</text>'
            f'<text x="{x}" y="396" class="small">target BM25 score · {score:.6f}</text>'
            f'<rect x="{x}" y="418" width="180" height="12" rx="6" class="track"/><rect x="{x}" y="418" width="{width:.2f}" height="12" rx="6" class="bar"/></g>'
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1040 500" role="img">
<title>Target document rank across the recorded query variants</title>
<desc>The synthetic target ranks first for the baseline and second for both failing variants.</desc>
<style>text{{font-family:Inter,system-ui,sans-serif;fill:#eaf2ff}}.title{{font-size:30px;font-weight:750}}.sub{{font-size:15px;fill:#91a8c7}}.label{{font-size:16px;font-weight:700}}.small{{font-size:13px;fill:#91a8c7}}.rank{{font-size:16px;font-weight:800;text-anchor:middle;fill:#07111f}}.point{{fill:#ffad5c;stroke:#ffd2a4;stroke-width:3}}.track{{fill:#1a2b44}}.bar{{fill:#5ee7f7}}.threshold{{stroke:#ff7c8d;stroke-width:2;stroke-dasharray:8 7}}</style>
<rect width="1040" height="500" rx="24" fill="#0b172a"/>
<text x="54" y="58" class="title">A canonical decomposition flips the target rank</text>
<text x="54" y="88" class="sub">Actual deterministic BM25 measurements from shaki-decomposed-grapheme</text>
<line x1="70" y1="248" x2="970" y2="248" class="threshold"/><text x="74" y="271" class="small">failure boundary · max rank {run.case.max_rank}</text>
{"".join(groups)}
</svg>"""


def _provenance_svg(run: Any) -> str:
    from orthodrift.text import apply_grapheme_edits

    full = apply_grapheme_edits(run.case.query, run.case.edits)
    cards = []
    for index, mutation in enumerate(run.case.mutations):
        x = 52 + index * 378
        minimal = index in run.reduction.reduced_indexes
        before = _codepoints(mutation.edit.before)
        after = _codepoints(mutation.edit.after)
        cards.append(
            f'<g transform="translate({x} 330)"><rect width="340" height="210" rx="18" class="card{" chosen" if minimal else ""}"/>'
            f'<text x="22" y="34" class="number">mutation {index}{" · minimal witness" if minimal else ""}</text>'
            f'<text x="22" y="68" class="rule">{_xml(mutation.rule_id)}</text><text x="22" y="99" class="muted">{_xml(mutation.relation.value)} · grapheme [{mutation.edit.start}:{mutation.edit.end}]</text>'
            f'<text x="22" y="137" class="code">{_xml(before)}</text><text x="22" y="166" class="arrow">↓</text><text x="22" y="195" class="code">{_xml(after)}</text></g>'
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 600" role="img">
<title>Grapheme-level provenance for every supplied mutation</title>
<desc>The NFD decomposition of Ş is the globally minimal rank-flipping mutation.</desc>
<style>text{{font-family:Inter,system-ui,sans-serif;fill:#eaf2ff}}.title{{font-size:30px;font-weight:750}}.muted{{font-size:14px;fill:#91a8c7}}.query{{font:700 22px ui-monospace,SFMono-Regular,monospace}}.label{{font-size:12px;letter-spacing:.13em;text-transform:uppercase;fill:#5ee7f7}}.card{{fill:#101f35;stroke:#2a3f5e}}.chosen{{stroke:#ffad5c;stroke-width:3}}.number{{font-size:14px;font-weight:750;fill:#ffad5c}}.rule{{font:700 14px ui-monospace,SFMono-Regular,monospace}}.code{{font:14px ui-monospace,SFMono-Regular,monospace;fill:#5ee7f7}}.arrow{{font-size:18px;fill:#91a8c7}}</style>
<rect width="1200" height="600" rx="24" fill="#0b172a"/>
<text x="52" y="58" class="title">Every character change keeps its provenance</text>
<text x="52" y="91" class="muted">Rules, relation claims, versions, and extended-grapheme coordinates are embedded in the case.</text>
<text x="52" y="142" class="label">baseline query</text><text x="52" y="178" class="query">{_xml(run.case.query)}</text>
<path d="M52 212 H1148" stroke="#2a3f5e"/><text x="52" y="252" class="label">all mutations applied</text><text x="52" y="288" class="query">{_xml(full)}</text>
{"".join(cards)}
</svg>"""


def _reduction_svg(run: Any) -> str:
    height = 180 + 78 * len(run.reduction.trials)
    rows = []
    for index, (trial, measurement) in enumerate(zip(run.reduction.trials, run.measurements, strict=True)):
        y = 144 + index * 78
        indexes = ",".join(str(value) for value in trial.edit_indexes) or "∅"
        status = "FAIL" if trial.failed else "PASS"
        color = "#ff7c8d" if trial.failed else "#7be0b2"
        rank = "miss" if measurement.target_rank is None else str(measurement.target_rank)
        rows.append(
            f'<g transform="translate(46 {y})"><rect width="1108" height="58" rx="13" fill="#101f35" stroke="#243a58"/>'
            f'<text x="18" y="25" class="meta">trial {index + 1} · edits [{indexes}]</text><text x="18" y="46" class="query">{_xml(trial.text)}</text>'
            f'<text x="940" y="27" class="status" fill="{color}">{status}</text><text x="940" y="47" class="meta">target rank {rank}</text></g>'
        )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {height}" role="img">
<title>Actual failure-reduction trace</title>
<desc>Every cached oracle evaluation and measured target rank used by the reducer.</desc>
<style>text{{font-family:Inter,system-ui,sans-serif;fill:#eaf2ff}}.title{{font-size:30px;font-weight:750}}.sub{{font-size:14px;fill:#91a8c7}}.meta{{font-size:13px;fill:#91a8c7}}.query{{font:13px ui-monospace,SFMono-Regular,monospace}}.status{{font-size:14px;font-weight:850}}</style>
<rect width="1200" height="{height}" rx="24" fill="#0b172a"/>
<text x="46" y="56" class="title">{run.reduction.minimality.value.title()} minimum · {len(run.reduction.reduced_edits)} of {len(run.case.edits)} edits</text>
<text x="46" y="88" class="sub">{run.reduction.evaluations} deterministic oracle evaluations; failure means target rank exceeds {run.case.max_rank}.</text>
{"".join(rows)}
</svg>"""


def _architecture_svg() -> str:
    labels = [
        ("case.v1", "strict JSON + digest"),
        ("rule gate", "typed relation claims"),
        ("BM25", "explicit tokenizer"),
        ("reducer", "ddmin + proof budget"),
        ("run.v1", "ranks + trace + runtime"),
        ("replay", "exact recomputation"),
        ("report", "offline verified UI"),
    ]
    boxes = []
    arrows = []
    for index, (title, subtitle) in enumerate(labels):
        x = 32 + index * 164
        boxes.append(
            f'<g transform="translate({x} 150)"><rect width="140" height="122" rx="18" class="box"/>'
            f'<text x="18" y="46" class="name">{title}</text><text x="18" y="76" class="detail">{subtitle.split(" + ")[0]}</text>'
            f'<text x="18" y="96" class="detail">{subtitle.split(" + ")[1] if " + " in subtitle else ""}</text></g>'
        )
        if index < len(labels) - 1:
            arrows.append(f'<path d="M{x + 140} 211 H{x + 161}" class="arrow"/>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 420" role="img">
<title>OrthoDrift verification architecture</title>
<desc>The artifact binds strict input validation, deterministic retrieval and reduction, runtime fingerprinting, exact replay, and offline reporting.</desc>
<defs><marker id="head" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8 Z" fill="#5ee7f7"/></marker></defs>
<style>text{{font-family:Inter,system-ui,sans-serif;fill:#eaf2ff}}.title{{font-size:30px;font-weight:750}}.sub{{font-size:15px;fill:#91a8c7}}.box{{fill:#101f35;stroke:#2a3f5e}}.name{{font-size:17px;font-weight:800;fill:#ffad5c}}.detail{{font-size:11px;fill:#91a8c7}}.arrow{{stroke:#5ee7f7;stroke-width:2;marker-end:url(#head)}}</style>
<rect width="1200" height="420" rx="24" fill="#0b172a"/><text x="40" y="60" class="title">Evidence is a replay contract, not a screenshot claim</text>
<text x="40" y="92" class="sub">Every visual is downstream of the same versioned artifact verified by the CLI.</text>
{"".join(arrows)}{"".join(boxes)}
<text x="40" y="340" class="sub">Offline after installation · no model API · no dataset download · no hidden normalization</text>
</svg>"""


def _terminal_html(text: str) -> str:
    escaped = html.escape(text)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;width:100%;height:100%;background:#07111f;color:#eaf2ff}}body{{display:grid;place-items:center;font-family:Inter,system-ui,sans-serif}}
.window{{width:1080px;border:1px solid #263d5d;border-radius:18px;background:#0b172a;box-shadow:0 30px 90px #0008;overflow:hidden}}
.chrome{{display:flex;align-items:center;gap:8px;height:46px;padding:0 18px;border-bottom:1px solid #263d5d;background:#101f35}}.dot{{width:11px;height:11px;border-radius:50%}}.r{{background:#ff7c8d}}.y{{background:#ffad5c}}.g{{background:#7be0b2}}.title{{margin-left:12px;color:#91a8c7;font-size:13px}}
pre{{min-height:485px;margin:0;padding:28px 32px;white-space:pre-wrap;font:16px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace}}pre::first-line{{color:#5ee7f7}}
</style></head><body><div class="window"><div class="chrome"><span class="dot r"></span><span class="dot y"></span><span class="dot g"></span><span class="title">reproducible CLI · synthetic fixture</span></div><pre>{escaped}</pre></div></body></html>"""


def _verify_svg(path: Path) -> None:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    if root.tag != "{http://www.w3.org/2000/svg}svg" or "viewBox" not in root.attrib:
        raise ValueError(f"invalid SVG root: {path}")
    for element in root.iter():
        local = element.tag.rsplit("}", 1)[-1]
        if local in {"script", "foreignObject"}:
            raise ValueError(f"active SVG content is forbidden: {path}")
        for name, value in element.attrib.items():
            if name.rsplit("}", 1)[-1] == "href" and ":" in value:
                raise ValueError(f"external SVG reference is forbidden: {path}")


def _png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) != 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError(f"invalid PNG: {path}")
    return struct.unpack(">II", data[16:24])


def _gif_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:10]
    if len(data) != 10 or data[:6] not in {b"GIF87a", b"GIF89a"}:
        raise ValueError(f"invalid GIF: {path}")
    return struct.unpack("<HH", data[6:10])


def _load_unique_json(path: Path) -> Mapping[str, object]:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate manifest key: {key}")
            result[key] = value
        return result

    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    return _mapping(value, "manifest")


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} must be an object")
    return value


def _write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_oid(value: str, name: str) -> None:
    if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{name} is not a lowercase Git object ID")


def _reject_sensitive_text(value: str) -> None:
    if any(marker in value for marker in FORBIDDEN_TEXT):
        raise ValueError("evidence contains a forbidden path or credential marker")


def _xml(value: str) -> str:
    return html.escape(value, quote=True)


def _codepoints(clusters: tuple[str, ...]) -> str:
    text = "".join(clusters)
    return " ".join(f"U+{ord(character):04X}" for character in text) or "∅"


if __name__ == "__main__":
    raise SystemExit(main())
