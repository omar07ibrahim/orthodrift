# Evidence method

The files in `docs/evidence/` are generated outputs, not design mockups. The
source of truth is the committed synthetic case plus the released OrthoDrift
engine.

## Bundle contents

The bundle contains:

- the exact `orthodrift.experiment-run.v1` JSONL record;
- the exact CLI transcript and a terminal capture of it;
- the standalone HTML report, desktop/full-page/mobile captures, and a
  three-state interaction GIF;
- rank, grapheme-provenance, reduction-trace, and verification-architecture
  SVGs;
- `orthodrift-evidence.json`, which binds all inputs and outputs.

The manifest records byte length and SHA-256 for every output and every relevant
source file. It also records the most recent source revision, that commit's tree,
the case/artifact digests, result summary, runtime fingerprint, browser
environment, dimensions, GIF frame count, and the research claim boundary.

## Generation sequence

1. Install the hash-locked quality environment on exact CPython 3.14.6.
2. Build and install the ordinary wheel without dependency resolution.
3. Execute the real `orthodrift run`, `verify`, and `report` entry points
   in a clean temporary directory.
4. Verify that the CLI report is byte-identical to the library renderer.
5. Generate SVGs directly from the verified run's queries, ranks, scores,
   mutations, and trials.
6. Download the hash-locked Playwright/Pillow wheel set.
7. Pull the reviewed linux/amd64 browser image by platform-manifest digest.
8. Disable networking and capture fixed desktop, mobile, terminal, and
   interaction viewports inside the constrained container.
9. Restore Python 3.14.6, replay the artifact again, validate SVG/PNG/GIF
   structure, scan text for credential/path markers, and write the manifest.
10. Replay and validate the committed bundle independently, then compare all 13
    files byte for byte.

The permanent GitHub Actions workflow has `contents: read`; it cannot update
evidence or repository state.

## Source binding

`source_revision` is the newest commit touching the case, package metadata,
runtime/browser locks, engine modules, or evidence generator. Documentation-only
commits do not invalidate a correct capture. Any relevant source change produces
a different revision, source hash, engine fingerprint, report, or visual and
causes evidence drift until the full bundle is deliberately regenerated.

## Updating evidence

A maintainer should:

1. change the source and tests in one focused commit;
2. regenerate into a temporary directory in the pinned environment;
3. verify the candidate twice and visually inspect desktop, mobile, CLI, and
   interaction states;
4. adopt only the verified `docs/evidence/` files in a separate Omar-authored
   commit;
5. remove any temporary write-capable workflow;
6. require the permanent read-only drift check before merge.

Do not edit screenshots, SVG values, JSONL, or the manifest by hand. Do not add
credentials, home-directory paths, private corpora, personal data, or a
language-quality claim that the fixture does not support.
