import importlib.metadata
import importlib.resources
from pathlib import Path

import orthodrift
from orthodrift import experiment


def test_public_version_matches_installed_metadata() -> None:
    assert orthodrift.__version__ == importlib.metadata.version("orthodrift")


def test_typed_package_marker_is_installed() -> None:
    assert importlib.resources.files("orthodrift").joinpath("py.typed").is_file()


def test_engine_fingerprint_manifest_covers_every_python_module() -> None:
    package = Path(experiment.__file__).parent
    modules = {
        path.relative_to(package).as_posix()
        for path in package.rglob("*.py")
        if "__pycache__" not in path.parts
    }

    assert set(experiment._ENGINE_PATHS) == modules
