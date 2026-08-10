# Contributing

OrthoDrift welcomes focused fixes, new deterministic adapters, and carefully
sourced research cases.

## Before opening a pull request

1. Keep engine changes separate from generated evidence adoption.
2. Preserve explicit relation claims; never infer semantic equivalence from
   visual similarity or a rule name.
3. Add tests for schema, provenance, ranking, reduction, replay, and report
   behavior affected by the change.
4. Run the hash-locked quality commands from the README.
5. Update the RFC or add a new RFC when changing an artifact schema,
   experimental contract, trust boundary, or claim.
6. Do not commit credentials, private datasets, personal data, generated caches,
   or unreviewed language data.

Evidence must be regenerated from the real CLI in the pinned environment,
visually inspected, and adopted in a separate meaningful commit. Temporary
write-capable workflows must not remain in the final tree.

Security-sensitive findings belong in GitHub private vulnerability reporting,
not a public issue; see [SECURITY.md](SECURITY.md).
