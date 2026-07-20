"""Cross-platform integrity checks for Manifest hashing."""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_tool(filename: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "tools" / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_manifest_hash_is_identical_for_lf_and_crlf(tmp_path):
    generator = load_tool(
        "gen-repository-manifest.py",
        "gen_repository_manifest",
    )
    verifier = load_tool("verify-manifest.py", "verify_manifest")

    lf_file = tmp_path / "lf.txt"
    crlf_file = tmp_path / "crlf.txt"
    lf_file.write_bytes(b"first\nsecond\n")
    crlf_file.write_bytes(b"first\r\nsecond\r\n")

    expected = generator.sha256_of(lf_file)
    assert generator.sha256_of(crlf_file) == expected
    assert verifier.sha256_of(lf_file) == expected
    assert verifier.sha256_of(crlf_file) == expected


def test_manifest_hash_preserves_binary_bytes(tmp_path):
    generator = load_tool(
        "gen-repository-manifest.py",
        "gen_repository_manifest_binary",
    )
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    first.write_bytes(b"\xff\r\n\x00")
    second.write_bytes(b"\xff\n\x00")

    assert generator.sha256_of(first) != generator.sha256_of(second)
