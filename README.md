# OrthoDrift

OrthoDrift finds the smallest orthographic change that makes a multilingual
retriever lose the right document.

Search and RAG benchmarks usually start with clean, normalized text. Real input
does not. Azerbaijani text alone can cross Latin, Cyrillic, and Perso-Arabic
orthographies; users also paste decomposed Unicode, keyboard substitutions, and
characters borrowed from neighboring scripts. Two queries that a reader treats
as the same can take very different paths through a tokenizer or retriever.

This project treats that gap as an experimental problem. It will generate
traceable text variants, measure retrieval and tokenization drift, reduce
failures to minimal counterexamples, and test mitigations without silently
assuming that every normalization is safe.

The first research lane is Azerbaijani retrieval. The engine is language-agnostic
and will expose a small rule-pack interface for other writing systems.

## What makes this different

- Changes are applied to grapheme clusters and retain their full provenance.
- Every rule declares whether it claims canonical equivalence, orthographic
  equivalence, visual confusability, or no semantic guarantee.
- A failure is not just a lower average score. OrthoDrift searches for the
  smallest edit that flips a rank, exceeds a token budget, or breaks a retrieval
  invariant.
- Mitigations are evaluated for false merges as well as recovered recall.

The current vertical slice can reproduce a lexical rank failure, prove its
smallest responsible mutation, and write a self-contained, replayable JSONL
artifact. The experimental contract and the first release boundary are recorded in
[`docs/rfcs/0001-project-scope.md`](docs/rfcs/0001-project-scope.md).

## Run the first case

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/orthodrift run examples/shaki-rank-flip.json
```

The committed case starts with a query that ranks the relevant document first.
Three mutations are applied; only one decomposed grapheme causes the rank flip.
Each mutation carries its rule, claimed relation, parameters, rule-pack version,
Unicode version, and optional seed.

```text
case: shaki-decomposed-grapheme
baseline rank: 1
full mutant rank: 2
global minimum: 1/3 edits
edit 0 [0:1]: U+015E -> U+0053 U+0327
```

Retain and independently replay the evidence:

```bash
.venv/bin/orthodrift run examples/shaki-rank-flip.json \
  --output reports/shaki.jsonl
.venv/bin/orthodrift verify reports/shaki.jsonl
```

The experiment-run artifact embeds the case and its SHA-256 identity, explicit
BM25 and tokenizer configuration, ranks for every reducer trial, the full
reduction trace, and an engine/runtime fingerprint. Registered rules regenerate
their claimed mutation before a case can run. Verification then requires the
recorded environment and recomputes every rank and reduction claim; a structurally
valid artifact from another environment can still be inspected but is not called
verified. Existing evidence is never replaced unless `--force` is explicit.

## License

Apache License 2.0.
