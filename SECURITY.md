# Security policy

## Supported version

OrthoDrift is pre-1.0 research software. Security fixes are applied to the latest
commit on `main`; tagged releases document stable experiment contracts.

## Report a vulnerability

Use GitHub's private vulnerability reporting for issues that could expose data,
overwrite files unexpectedly, or exhaust resources. Do not include credentials,
private corpora, or personal data in a public issue.

## Trust boundary

OrthoDrift is a local, offline experiment runner. Case and JSONL paths are
untrusted inputs; the CLI does not fetch models, datasets, or code from the
network. It rejects duplicate JSON fields, non-finite numbers, invalid Unicode,
excessive nesting, case files over 1 MiB, artifacts over 16 MiB or 1,000 records,
more than 4,096 documents, more than 64 mutations, and proof budgets above
100,000 evaluations.

Output publication is atomic. Existing evidence is preserved unless the caller
passes `--force`. A verified artifact means that its schema, embedded case
digest, runtime fingerprint, retrieval ranks, and reduction trace replay exactly;
it is not a claim about language quality, semantic equivalence, or production
model robustness.

The remaining resource assumption is explicit: a valid in-budget case may still
perform up to its declared proof budget. Run untrusted bulk workloads with
ordinary OS-level CPU and memory limits.
