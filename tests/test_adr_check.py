"""Tests for the pure (non-git) helpers of adr_check + hook_install."""

from sigil.adr_check import (
    adr_id_from_filename,
    parse_frontmatter_code_anchors,
    bookmark_covered_ids,
)
from sigil.hook_install import install, uninstall, BEGIN_MARKER, END_MARKER


# ---------- adr_id_from_filename ----------


def test_adr_id_from_filename_variants():
    assert adr_id_from_filename("docs/decisions/ADR-0042-foo.md") == 42
    assert adr_id_from_filename("docs/decisions/adr-0089.md") == 89
    assert adr_id_from_filename("ADR42-bar.md") == 42
    # No ID in filename → None (body-only references MUST NOT satisfy the check)
    assert adr_id_from_filename("docs/decisions/index.md") is None


def test_adr_id_from_filename_ignores_body_mentions():
    # Caller passes filename, not body. A file named without an ID returns
    # None regardless of what the body contains. This is the contract that
    # prevents body references to OTHER ADRs from satisfying linkage.
    assert adr_id_from_filename("some-file.md") is None


# ---------- parse_frontmatter_code_anchors ----------


def test_frontmatter_opt_out():
    fm = parse_frontmatter_code_anchors("---\ncode_anchors: none\n---\nbody\n")
    assert fm.opted_out is True and fm.declared is True
    assert fm.parse_error is None


def test_frontmatter_non_empty_list():
    fm = parse_frontmatter_code_anchors("---\ncode_anchors: [a, b]\n---\n")
    assert fm.has_anchors is True and fm.opted_out is False


def test_frontmatter_empty_list():
    fm = parse_frontmatter_code_anchors("---\ncode_anchors: []\n---\n")
    assert fm.has_anchors is False and fm.declared is True


def test_frontmatter_missing_field():
    fm = parse_frontmatter_code_anchors("---\nid: ADR-0001\n---\n")
    assert fm.declared is False


def test_frontmatter_no_frontmatter_block():
    fm = parse_frontmatter_code_anchors("# just a markdown file\n")
    assert fm.declared is False


def test_frontmatter_invalid_value():
    fm = parse_frontmatter_code_anchors("---\ncode_anchors: required\n---\n")
    assert fm.parse_error is not None


# ---------- bookmark_covered_ids (stricter ^ADR-NNNN match) ----------


def test_bookmark_anchored_match_only():
    bookmarks = [
        # Starts with ADR-0042 → counts
        {"metadata": {"description": "ADR-0042 — why this loop"}},
        # ADR reference mid-description → MUST NOT count (this was the false
        # positive we specifically guarded against)
        {"metadata": {"description": "fix bug; supersedes ADR-0089"}},
        # Flat-schema fallback
        {"description": "ADR-0007 — top-level desc field"},
        # No ADR reference
        {"metadata": {"description": "random bookmark"}},
    ]
    assert bookmark_covered_ids(bookmarks) == {42, 7}


def test_bookmark_zero_padded_ids_normalized():
    bookmarks = [{"metadata": {"description": "ADR-089 — short"}}]
    assert bookmark_covered_ids(bookmarks) == {89}


# ---------- hook_install idempotency ----------


def _fake_repo(tmp_path):
    (tmp_path / ".git" / "hooks").mkdir(parents=True)
    return tmp_path


def test_install_creates_hook(tmp_path):
    root = _fake_repo(tmp_path)
    path, action = install(root)
    assert action == "created"
    assert path.exists()
    txt = path.read_text()
    assert BEGIN_MARKER in txt and END_MARKER in txt
    assert txt.startswith("#!/bin/sh")


def test_install_is_idempotent(tmp_path):
    root = _fake_repo(tmp_path)
    install(root)
    _, action = install(root)
    assert action == "unchanged"
    # Re-running must not duplicate markers
    content = (root / ".git" / "hooks" / "pre-commit").read_text()
    assert content.count(BEGIN_MARKER) == 1
    assert content.count(END_MARKER) == 1


def test_install_preserves_user_content(tmp_path):
    root = _fake_repo(tmp_path)
    hook = root / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\n# user's custom hook step\nrun_linter\n")
    path, action = install(root)
    assert action == "updated"
    txt = path.read_text()
    assert "run_linter" in txt  # user content preserved
    assert BEGIN_MARKER in txt


def test_uninstall_leaves_user_content(tmp_path):
    root = _fake_repo(tmp_path)
    hook = root / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\nrun_linter\n")
    install(root)
    _, action = uninstall(root)
    assert action == "removed"
    txt = hook.read_text()
    assert "run_linter" in txt
    assert BEGIN_MARKER not in txt
