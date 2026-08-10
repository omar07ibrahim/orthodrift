"""Self-contained reports for verified OrthoDrift experiment runs."""

# ruff: noqa: E501 -- embedded standalone HTML is intentionally readable source

from __future__ import annotations

import html
from pathlib import Path

from orthodrift._io import atomic_write_text
from orthodrift._schema import canonical_dumps
from orthodrift.experiment import RetrievalCaseRun
from orthodrift.run_serialization import run_to_record, verify_run
from orthodrift.text import apply_grapheme_edits

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>@@TITLE@@ · OrthoDrift report</title>
  <style>
    :root {
      color-scheme: dark;
      --ink: #eef4ff;
      --muted: #94a9c6;
      --panel: rgba(12, 25, 46, .88);
      --line: rgba(148, 169, 198, .18);
      --cyan: #5ee7f7;
      --orange: #ffad5c;
      --rose: #ff7c8d;
      --green: #7be0b2;
      --shadow: 0 24px 80px rgba(0, 0, 0, .28);
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      min-width: 320px;
      background:
        radial-gradient(circle at 80% 4%, rgba(94, 231, 247, .14), transparent 29rem),
        radial-gradient(circle at 4% 28%, rgba(255, 173, 92, .10), transparent 24rem),
        #07111f;
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
    }
    body::before {
      position: fixed;
      inset: 0;
      z-index: -1;
      content: "";
      opacity: .18;
      background-image: linear-gradient(rgba(148,169,198,.08) 1px, transparent 1px), linear-gradient(90deg, rgba(148,169,198,.08) 1px, transparent 1px);
      background-size: 36px 36px;
      mask-image: linear-gradient(to bottom, black, transparent 75%);
    }
    a { color: var(--cyan); }
    button { font: inherit; }
    .shell { width: min(1160px, calc(100% - 40px)); margin: 0 auto; }
    .hero { padding: 64px 0 34px; }
    .eyebrow, .kicker {
      margin: 0 0 10px;
      color: var(--cyan);
      font-size: .76rem;
      font-weight: 800;
      letter-spacing: .15em;
      text-transform: uppercase;
    }
    .hero-grid { display: grid; grid-template-columns: 1.4fr .6fr; gap: 28px; align-items: end; }
    h1 { max-width: 820px; margin: 0; font-size: clamp(2.5rem, 6vw, 5.4rem); line-height: .97; letter-spacing: -.06em; }
    .lede { max-width: 720px; margin: 24px 0 0; color: var(--muted); font-size: 1.07rem; }
    .verified {
      justify-self: end;
      padding: 18px 20px;
      border: 1px solid rgba(123,224,178,.32);
      border-radius: 18px;
      background: rgba(123,224,178,.08);
    }
    .verified strong { display: block; color: var(--green); font-size: 1.05rem; }
    .verified span { color: var(--muted); font: .72rem/1.4 ui-monospace, SFMono-Regular, Consolas, monospace; }
    .metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 30px 0 0; }
    .metric, .panel {
      border: 1px solid var(--line);
      background: var(--panel);
      box-shadow: var(--shadow);
      backdrop-filter: blur(14px);
    }
    .metric { min-height: 116px; padding: 18px; border-radius: 18px; }
    .metric span { display: block; color: var(--muted); font-size: .78rem; }
    .metric strong { display: block; margin-top: 8px; font-size: 2rem; line-height: 1; }
    main { display: grid; gap: 20px; padding-bottom: 72px; }
    .panel { padding: 28px; border-radius: 24px; overflow: hidden; }
    .panel-head { display: flex; justify-content: space-between; gap: 20px; align-items: start; margin-bottom: 22px; }
    h2 { margin: 0; font-size: 1.5rem; letter-spacing: -.025em; }
    .panel-head p { max-width: 560px; margin: 0; color: var(--muted); font-size: .92rem; }
    .tabs { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 22px; }
    .tab {
      padding: 9px 14px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: transparent;
      color: var(--muted);
      cursor: pointer;
    }
    .tab[aria-selected="true"] { border-color: var(--cyan); background: rgba(94,231,247,.11); color: var(--ink); }
    .query-card { display: grid; grid-template-columns: 1fr auto; gap: 18px; align-items: center; padding: 20px; border: 1px solid var(--line); border-radius: 18px; background: rgba(4,13,27,.58); }
    .query-card code { display: block; overflow-wrap: anywhere; color: var(--ink); font: 700 1.1rem/1.5 ui-monospace, SFMono-Regular, Consolas, monospace; }
    .rank-pill { min-width: 92px; padding: 12px; border-radius: 14px; background: rgba(255,124,141,.1); text-align: center; }
    .rank-pill span { display: block; color: var(--muted); font-size: .7rem; text-transform: uppercase; }
    .rank-pill strong { color: var(--rose); font-size: 1.65rem; }
    .hits { display: grid; gap: 12px; margin-top: 18px; }
    .hit { display: grid; grid-template-columns: minmax(120px,.8fr) 2fr auto; gap: 14px; align-items: center; }
    .hit-name { overflow: hidden; text-overflow: ellipsis; font: .82rem ui-monospace, SFMono-Regular, Consolas, monospace; }
    .bar { height: 10px; border-radius: 99px; background: rgba(148,169,198,.11); overflow: hidden; }
    .bar > span { display: block; width: var(--score); height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--cyan), #58a6ff); }
    .hit.target .bar > span { background: linear-gradient(90deg, var(--orange), var(--rose)); }
    .score { color: var(--muted); font: .76rem ui-monospace, SFMono-Regular, Consolas, monospace; }
    .two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: .86rem; }
    th { color: var(--muted); font-size: .7rem; letter-spacing: .08em; text-align: left; text-transform: uppercase; }
    th, td { padding: 12px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }
    td code { color: var(--cyan); font: .76rem/1.5 ui-monospace, SFMono-Regular, Consolas, monospace; }
    .relation { display: inline-block; padding: 3px 8px; border-radius: 99px; background: rgba(94,231,247,.1); color: var(--cyan); font-size: .72rem; }
    .trace { display: grid; gap: 10px; }
    .trial { display: grid; grid-template-columns: 72px 1fr auto; gap: 12px; align-items: center; padding: 12px 14px; border: 1px solid var(--line); border-radius: 14px; }
    .trial code { overflow-wrap: anywhere; color: var(--ink); font-size: .78rem; }
    .status { font-size: .75rem; font-weight: 800; }
    .status.fail { color: var(--rose); }
    .status.pass { color: var(--green); }
    .runtime { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
    .runtime div { padding: 14px; border: 1px solid var(--line); border-radius: 14px; }
    .runtime span { display: block; color: var(--muted); font-size: .72rem; }
    .runtime code { display: block; margin-top: 5px; overflow-wrap: anywhere; color: var(--ink); font-size: .75rem; }
    .boundary { border-left: 3px solid var(--orange); padding-left: 18px; color: var(--muted); }
    footer { padding: 0 0 36px; color: var(--muted); font-size: .78rem; }
    @media (max-width: 780px) {
      .shell { width: min(100% - 24px, 1160px); }
      .hero { padding-top: 38px; }
      .hero-grid, .two-col { grid-template-columns: 1fr; }
      .verified { justify-self: start; }
      .metrics { grid-template-columns: repeat(2, 1fr); }
      .panel { padding: 20px; }
      .panel-head { display: block; }
      .panel-head p { margin-top: 8px; }
      .query-card, .hit { grid-template-columns: 1fr; }
      .rank-pill { justify-self: start; }
      .runtime { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header class="hero">
    <div class="shell">
      <div class="hero-grid">
        <div>
          <p class="eyebrow">OrthoDrift · verified experiment report</p>
          <h1>One grapheme.<br>One rank flip.</h1>
          <p class="lede">@@DESCRIPTION@@</p>
        </div>
        <div class="verified">
          <strong>✓ replay verified</strong>
          <span>case sha256<br>@@CASE_SHA@@</span>
        </div>
      </div>
      <div class="metrics">
        <div class="metric"><span>baseline target rank</span><strong>@@BASELINE_RANK@@</strong></div>
        <div class="metric"><span>full mutant rank</span><strong>@@FULL_RANK@@</strong></div>
        <div class="metric"><span>minimum failure</span><strong>@@MINIMUM@@</strong></div>
        <div class="metric"><span>oracle evaluations</span><strong>@@EVALUATIONS@@</strong></div>
      </div>
    </div>
  </header>
  <main class="shell">
    <section class="panel" id="explorer">
      <div class="panel-head">
        <div><p class="kicker">Live artifact</p><h2>Rank-flip explorer</h2></div>
        <p>Switch between the exact queries recorded in the replayable run. Scores come from the embedded deterministic BM25 specification.</p>
      </div>
      <div class="tabs" role="tablist" aria-label="Query variant">
        <button class="tab" type="button" data-variant="baseline" aria-selected="true">Baseline</button>
        <button class="tab" type="button" data-variant="full" aria-selected="false">All mutations</button>
        <button class="tab" type="button" data-variant="minimal" aria-selected="false">Minimal failure</button>
      </div>
      <div class="query-card">
        <div><p class="kicker" id="variant-label">Baseline query</p><code id="query">@@BASELINE_QUERY@@</code></div>
        <div class="rank-pill"><span>target rank</span><strong id="rank">@@BASELINE_RANK@@</strong></div>
      </div>
      <div class="hits" id="hits">@@BASELINE_HITS@@</div>
    </section>
    <div class="two-col">
      <section class="panel">
        <div class="panel-head"><div><p class="kicker">Provenance</p><h2>Typed mutations</h2></div></div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>#</th><th>rule</th><th>relation</th><th>grapheme edit</th></tr></thead>
            <tbody>@@MUTATION_ROWS@@</tbody>
          </table>
        </div>
      </section>
      <section class="panel">
        <div class="panel-head"><div><p class="kicker">Reduction</p><h2>Measured trials</h2></div></div>
        <div class="trace">@@TRIAL_ROWS@@</div>
      </section>
    </div>
    <section class="panel">
      <div class="panel-head">
        <div><p class="kicker">Reproducibility</p><h2>Runtime fingerprint</h2></div>
        <p>Verification requires an exact environment match and recomputes both retrieval measurements and the complete reduction trace.</p>
      </div>
      <div class="runtime">
        <div><span>OrthoDrift</span><code>@@VERSION@@</code></div>
        <div><span>Python / Unicode</span><code>@@PYTHON@@ · UCD @@UNICODE@@</code></div>
        <div><span>regex</span><code>@@REGEX@@</code></div>
        <div><span>engine sha256</span><code>@@ENGINE@@</code></div>
      </div>
    </section>
    <section class="panel">
      <p class="kicker">Claim boundary</p>
      <div class="boundary">This is a synthetic, deterministic lexical counterexample. It demonstrates that a canonically equivalent grapheme decomposition can flip this fixture's rank; it is not a broad multilingual benchmark, native-language validation, or evidence about dense retrievers.</div>
    </section>
  </main>
  <footer class="shell">Generated offline from an <code>orthodrift.experiment-run.v1</code> artifact. No network resources or personal data.</footer>
  <script id="experiment-data" type="application/json">@@DATA@@</script>
  <script>
    (() => {
      "use strict";
      const data = JSON.parse(document.getElementById("experiment-data").textContent);
      const buttons = Array.from(document.querySelectorAll("[data-variant]"));
      const query = document.getElementById("query");
      const rank = document.getElementById("rank");
      const label = document.getElementById("variant-label");
      const hits = document.getElementById("hits");

      function render(key) {
        const variant = data.variants.find((item) => item.id === key);
        if (!variant) return;
        query.textContent = variant.query;
        rank.textContent = variant.rank === null ? "miss" : String(variant.rank);
        label.textContent = variant.label;
        buttons.forEach((button) => button.setAttribute("aria-selected", String(button.dataset.variant === key)));
        hits.replaceChildren();
        const maximum = Math.max(...variant.hits.map((hit) => hit.score), 1);
        variant.hits.forEach((hit) => {
          const row = document.createElement("div");
          row.className = "hit" + (hit.target ? " target" : "");
          const name = document.createElement("span");
          name.className = "hit-name";
          name.textContent = "#" + hit.rank + " " + hit.document_id + (hit.target ? " · target" : "");
          const bar = document.createElement("div");
          bar.className = "bar";
          const fill = document.createElement("span");
          fill.style.setProperty("--score", String(Math.max(4, hit.score / maximum * 100)) + "%");
          bar.append(fill);
          const score = document.createElement("span");
          score.className = "score";
          score.textContent = hit.score.toFixed(6);
          row.append(name, bar, score);
          hits.append(row);
        });
      }

      buttons.forEach((button) => button.addEventListener("click", () => render(button.dataset.variant)));
    })();
  </script>
</body>
</html>
"""


def render_report(run: RetrievalCaseRun) -> str:
    verify_run(run)
    record = run_to_record(run)
    case_digest = str(record["case_sha256"])
    full_query = apply_grapheme_edits(run.case.query, run.case.edits)
    variants = [
        _variant_record(run, "baseline", "Baseline query", run.case.query),
        _variant_record(run, "full", "All mutations", full_query),
        _variant_record(run, "minimal", "Minimal failing query", run.reduction.text),
    ]
    data: dict[str, object] = {
        "schema": "orthodrift.report-data.v1",
        "case": run.case.name,
        "case_sha256": case_digest,
        "target_document_id": run.case.target_document_id,
        "variants": variants,
    }
    safe_data = canonical_dumps(data).replace("&", "\\u0026").replace("<", "\\u003c")
    replacements = {
        "@@TITLE@@": html.escape(run.case.name),
        "@@DESCRIPTION@@": html.escape(
            f"{run.case.name} isolates the smallest supplied mutation that moves "
            f"the target beyond rank {run.case.max_rank}."
        ),
        "@@CASE_SHA@@": html.escape(case_digest),
        "@@BASELINE_RANK@@": _rank(run.baseline_rank),
        "@@FULL_RANK@@": _rank(run.full_mutant_rank),
        "@@MINIMUM@@": (
            f"{len(run.reduction.reduced_edits)}/{len(run.case.edits)} "
            f"{html.escape(run.reduction.minimality.value)}"
        ),
        "@@EVALUATIONS@@": str(run.reduction.evaluations),
        "@@BASELINE_QUERY@@": html.escape(run.case.query),
        "@@BASELINE_HITS@@": _hits_html(variants[0]),
        "@@MUTATION_ROWS@@": _mutation_rows(run),
        "@@TRIAL_ROWS@@": _trial_rows(run),
        "@@VERSION@@": html.escape(run.runtime.orthodrift_version),
        "@@PYTHON@@": html.escape(
            f"{run.runtime.python_implementation} {run.runtime.python_version}"
        ),
        "@@UNICODE@@": html.escape(run.runtime.python_unicode_version),
        "@@REGEX@@": html.escape(run.runtime.regex_version),
        "@@ENGINE@@": html.escape(run.runtime.engine_sha256),
        "@@DATA@@": safe_data,
    }
    rendered = _TEMPLATE
    for marker, value in replacements.items():
        rendered = rendered.replace(marker, value)
    if "@@" in rendered:
        raise ValueError("report template contains an unresolved marker")
    return rendered


def write_report(
    path: Path,
    run: RetrievalCaseRun,
    *,
    overwrite: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, render_report(run), overwrite=overwrite)


def _variant_record(
    run: RetrievalCaseRun,
    identifier: str,
    label: str,
    query: str,
) -> dict[str, object]:
    index = run.retriever.build(run.case.documents)
    hits = [
        {
            "document_id": hit.document_id,
            "rank": hit.rank,
            "score": hit.score,
            "target": hit.document_id == run.case.target_document_id,
        }
        for hit in index.search(query, limit=len(run.case.documents))
    ]
    return {
        "id": identifier,
        "label": label,
        "query": query,
        "rank": index.rank_of(query, run.case.target_document_id),
        "hits": hits,
    }


def _hits_html(variant: dict[str, object]) -> str:
    raw_hits = variant["hits"]
    if not isinstance(raw_hits, list):
        raise ValueError("report variant hits must be a list")
    maximum = max(
        (float(hit["score"]) for hit in raw_hits if isinstance(hit, dict)),
        default=1.0,
    )
    rows: list[str] = []
    for item in raw_hits:
        if not isinstance(item, dict):
            raise ValueError("report hit must be an object")
        score = float(item["score"])
        width = max(4.0, score / maximum * 100)
        target = bool(item["target"])
        rows.append(
            f'<div class="hit{" target" if target else ""}">'
            f'<span class="hit-name">#{int(item["rank"])} '
            f"{html.escape(str(item['document_id']))}"
            f"{' · target' if target else ''}</span>"
            f'<div class="bar"><span style="--score:{width:.3f}%"></span></div>'
            f'<span class="score">{score:.6f}</span></div>'
        )
    return "".join(rows)


def _mutation_rows(run: RetrievalCaseRun) -> str:
    rows: list[str] = []
    for index, mutation in enumerate(run.case.mutations):
        before = _codepoints(mutation.edit.before)
        after = _codepoints(mutation.edit.after)
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td><code>{html.escape(mutation.rule_id)}</code></td>"
            f'<td><span class="relation">{html.escape(mutation.relation.value)}</span></td>'
            f"<td><code>{before} → {after}</code></td>"
            "</tr>"
        )
    return "".join(rows)


def _trial_rows(run: RetrievalCaseRun) -> str:
    rows: list[str] = []
    for trial, measurement in zip(
        run.reduction.trials,
        run.measurements,
        strict=True,
    ):
        indexes = ",".join(str(index) for index in trial.edit_indexes) or "∅"
        status = "fail" if trial.failed else "pass"
        rank = _rank(measurement.target_rank)
        rows.append(
            '<div class="trial">'
            f"<span>edits {indexes}</span>"
            f"<code>{html.escape(trial.text)}</code>"
            f'<span class="status {status}">{status} · rank {rank}</span>'
            "</div>"
        )
    return "".join(rows)


def _rank(value: int | None) -> str:
    return "miss" if value is None else str(value)


def _codepoints(clusters: tuple[str, ...]) -> str:
    value = "".join(clusters)
    return " ".join(f"U+{ord(character):04X}" for character in value) or "∅"
