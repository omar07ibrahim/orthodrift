# Architecture

OrthoDrift 0.1 is a local-first experiment engine, not an online search service.
Its primary output is a replay contract: the report and every portfolio visual
are downstream views of the same versioned JSONL artifact.

![Verification architecture](evidence/verification-architecture.svg)

## Data flow

1. **Case parser** reads at most 1 MiB of UTF-8 and rejects duplicate keys,
   unsupported fields, non-finite values, invalid Unicode scalars, and excessive
   nesting.
2. **Rule gate** reconstructs every declared mutation from a registered rule,
   rule-pack version, parameters, and Unicode version. A canonical claim is
   checked with Unicode canonical decomposition.
3. **Retriever** builds a deterministic in-memory BM25 index. Tokenization,
   case-folding, parameters, and document-order tie breaking are explicit.
4. **Reducer** treats “target rank is missing or above max_rank” as its oracle.
   It validates the passing baseline and failing full edit set, runs ddmin,
   enforces one-minimality, and uses the bounded proof budget to seek a global
   minimum.
5. **Run artifact** stores the embedded case and digest, BM25/tokenizer contract,
   every measured rank, every reducer trial, the reduction result, and an exact
   runtime/engine fingerprint.
6. **Replay verifier** requires that fingerprint, rebuilds the case, reruns
   retrieval and reduction, and compares the complete result—not only a summary.
7. **Report renderer** receives only a verified run and creates one standalone
   HTML file. The interactive states use data embedded from that run.
8. **Evidence pipeline** renders the report and CLI in a pinned, networkless
   Chromium container, generates data-derived SVGs, hashes sources/outputs, and
   compares the regenerated bundle byte for byte.

## Determinism decisions

- The corpus stays in committed case files; no dataset or model is downloaded.
- BM25 uses stable document-order tie breaking and an explicit tokenizer regex.
- Mutation coordinates are extended grapheme clusters, not Python string
  indexes or raw code-point offsets.
- JSON output is canonical: sorted keys, UTF-8, finite numbers, and LF records.
- Reducer trials are cached and retained in evaluation order.
- Existing output is no-clobber unless the caller explicitly passes `--force`.
- Runtime replay includes OrthoDrift, Python, Python's Unicode database, the
  `regex` package, and an SHA-256 over every engine module.

The runtime fingerprint intentionally makes artifacts from other environments
inspectable but not “verified.” This prevents a changed Unicode table or regex
release from silently inheriting an earlier result.

## Trust boundaries

Case and JSONL paths are untrusted. The CLI performs no network access and does
not execute case content. Bounds limit input bytes, record count, corpus size,
mutation count, nesting, and proof evaluations. A valid maximum-size case can
still consume meaningful CPU; bulk untrusted jobs should add OS-level resource
limits.

The report renderer escapes all experiment text before inserting it into HTML
and uses `textContent` for interactive updates. It has no remote resources.
The evidence browser runs with no network, a read-only root filesystem, dropped
capabilities, a PID/memory/CPU limit, and a platform-pinned image.

## Claim boundary

The committed Şəki case is synthetic and exercises the deterministic lexical
baseline. It proves that one declared canonical decomposition is the globally
minimal supplied edit that flips this fixture's target rank. It does not
establish prevalence, language quality, dense-retrieval behavior, or a generally
safe normalization policy.

Those wider questions require paired datasets, uncertainty estimates, native
review of language-specific equivalence, held-out rule families, false-merge
tests, and clean-query regression measurements, as required by
[RFC 0001](rfcs/0001-project-scope.md).
