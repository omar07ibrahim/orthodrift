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

The project is in its initial design stage. The experimental contract and the
first release boundary are recorded in
[`docs/rfcs/0001-project-scope.md`](docs/rfcs/0001-project-scope.md).

## License

Apache License 2.0.
