# RFC 0001: Project scope and experimental contract

- Status: accepted
- Date: 2026-07-13

## Problem

Multilingual retrieval systems are normally evaluated on clean text. Production
queries contain canonically equivalent Unicode sequences, compatibility forms,
mixed scripts, transliterations, keyboard substitutions, and historical
orthographies. These are often grouped together as generic "noise", even though
they carry different semantic guarantees.

That shortcut hides two problems:

1. aggregate robustness scores do not explain which edit caused a relevant
   document to disappear;
2. aggressive normalization can recover recall by merging strings that should
   remain distinct.

OrthoDrift will make both failure modes observable.

## Decision

Build a local-first evaluation engine around a provenance-preserving text variant.
Each transformation records:

- the input and output text;
- edits in extended grapheme-cluster coordinates;
- a stable rule identifier and parameters;
- the claimed relationship between both strings;
- the Unicode data version and language-pack version;
- the random seed when a rule is stochastic.

The relationship is explicit rather than inferred from the rule name:

| Relationship | Meaning |
| --- | --- |
| `canonical` | Unicode canonical equivalence is expected. |
| `orthographic` | A language pack claims the forms are equivalent in its documented scope. |
| `confusable` | The strings may look alike; no semantic equivalence is claimed. |
| `adversarial` | The change intentionally violates a stated input invariant. |
| `unknown` | The engine makes no claim. |

Compatibility normalization is not labeled canonical. NFKC and NFKD can erase
meaningful distinctions and must be measured as mitigations with false-merge
tests, not enabled as a universal cleanup step.

## First research questions

1. How often do canonically equivalent forms change token count, embedding
   distance, or retrieval rank?
2. What is the smallest grapheme-level edit that pushes a relevant document
   outside the top *k*?
3. Which failures are specific to lexical, character, or dense retrieval?
4. Can query-side canonicalization or multi-view retrieval recover recall without
   merging known counterexamples?
5. How do Latin, Cyrillic, and Perso-Arabic Azerbaijani variants change the
   accuracy-cost trade-off?

## Initial vertical slice

Version 0.1 is deliberately narrower than the full benchmark. It will include:

1. immutable text variants and transformation provenance;
2. extended grapheme-cluster segmentation;
3. NFC/NFD mutation and selected mixed-script confusable rules;
4. a deterministic lexical retrieval baseline;
5. delta debugging for a minimal rank-flipping edit;
6. JSONL results and a plain offline report;
7. an Azerbaijani fixture set reviewed separately from engine code.

Dense retrievers and tokenizer adapters follow only after the deterministic
baseline is covered by tests. This keeps model variance out of the core failure
reducer.

## Experimental contract

Results are publishable only when all of the following are true:

- generation is reproducible from a committed config and seed;
- raw per-query results are retained, not only aggregate charts;
- the original and mutated query share a stable pair identifier;
- model, tokenizer, dataset, rule-pack, and Unicode versions are recorded;
- comparisons are paired and include uncertainty, not only a mean delta;
- mitigation results include false merges and clean-query regressions;
- network access is optional during evaluation after assets are prepared;
- failures and unsupported cases are reported alongside successful runs.

## Non-goals

OrthoDrift is not a spelling corrector, a universal Unicode sanitizer, a prompt
injection detector, or a wrapper around an LLM API. It will not claim that visual
similarity implies semantic equivalence. It will not publish generated language
data as native-quality Azerbaijani without human review.

## Reference points

- [Unicode Normalization Forms (UAX #15)](https://www.unicode.org/reports/tr15/)
- [Unicode Text Segmentation (UAX #29)](https://www.unicode.org/reports/tr29/)
- [Unicode Security Mechanisms (UTS #39)](https://www.unicode.org/reports/tr39/)
- [FLORES-200](https://github.com/facebookresearch/flores/tree/main/flores200)
- [NL-Augmenter](https://github.com/GEM-benchmark/NL-Augmenter)
- [Benchmarking Azerbaijani Neural Machine Translation](https://arxiv.org/abs/2207.14473)

These projects and standards supply definitions, datasets, or perturbation
baselines. OrthoDrift's intended contribution is the combination of typed
semantic claims, grapheme-level provenance, retrieval-specific measurements,
and automatic reduction to a minimal counterexample.

## Risks

The largest risk is invalid equivalence data. Unicode equivalence can be tested
mechanically; language-specific equivalence cannot. Azerbaijani rules therefore
live in a versioned pack with sources and review notes, and they cannot silently
inherit the stronger `canonical` label.

The second risk is benchmark overfitting. A mitigation that recognizes the exact
mutations used by the generator may look robust without generalizing. Held-out
rule families and natural noisy queries are required before making broader
claims.
