from __future__ import annotations

from brain_core.ingest.hashing import content_hash


def test_stable_hash_same_bytes() -> None:
    assert content_hash("hello") == content_hash("hello")


def test_different_input_different_hash() -> None:
    assert content_hash("a") != content_hash("b")


def test_handles_unicode() -> None:
    h = content_hash("hello — world ✓")
    assert len(h) == 64  # sha256 hex
    assert all(c in "0123456789abcdef" for c in h)


def test_bytes_input_matches_string_input() -> None:
    assert content_hash("hello") == content_hash(b"hello")
