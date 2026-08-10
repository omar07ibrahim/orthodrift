import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
README = ROOT / "README.md"
MANIFEST = ROOT / "docs" / "evidence" / "orthodrift-evidence.json"
VISUALS = (
    "docs/evidence/grapheme-provenance.svg",
    "docs/evidence/rank-flip.svg",
    "docs/evidence/reduction-trace.svg",
    "docs/evidence/shaki-cli.png",
    "docs/evidence/shaki-interaction.gif",
    "docs/evidence/shaki-report-full.png",
    "docs/evidence/shaki-report-mobile.png",
    "docs/evidence/shaki-report.png",
    "docs/evidence/verification-architecture.svg",
)


def test_readme_visuals_are_manifest_bound_files() -> None:
    readme = README.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    records = {record["path"]: record for record in manifest["files"]}

    assert len(VISUALS) >= 8
    for relative in VISUALS:
        path = ROOT / relative
        assert relative in readme
        assert path.is_file()
        assert records[relative]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_readme_result_matches_the_verified_manifest() -> None:
    readme = README.read_text(encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    result = manifest["result"]

    assert result["baseline_rank"] == 1
    assert result["full_mutant_rank"] == 2
    assert result["minimal_edits"] == 1
    assert result["supplied_edits"] == 3
    assert result["minimality"] == "global"
    assert "**1 / 3 edits**" in readme
    assert "U+015E → U+0053 U+0327" in readme


def test_only_permanent_read_only_workflows_remain() -> None:
    workflows = ROOT / ".github" / "workflows"
    assert {path.name for path in workflows.glob("*.yml")} == {"ci.yml", "evidence.yml"}

    for path in workflows.glob("*.yml"):
        content = path.read_text(encoding="utf-8")
        assert "contents: write" not in content
        assert "one-shot" not in content.lower()
