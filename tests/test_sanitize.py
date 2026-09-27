"""tests/test_sanitize.py – unit tests for branch-name sanitizing."""
import pytest
from ferry.gitops import sanitize_branch


def test_release_1x():
    assert sanitize_branch("release/1.x") == "release-1.x"


def test_release_2x():
    assert sanitize_branch("release/2.x") == "release-2.x"


def test_release_09():
    assert sanitize_branch("release/0.9") == "release-0.9"


def test_no_slash():
    assert sanitize_branch("main") == "main"


def test_multiple_slashes():
    assert sanitize_branch("backport/abc1234/release-1.x") == "backport-abc1234-release-1.x"
