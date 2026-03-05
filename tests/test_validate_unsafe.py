import os
import sys
from pathlib import Path

# Ensure src is importable when tests are run from project root
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from sigil.cli import cmd_validate
from sigil.models import Bookmark, Context, Metadata, Validation
from sigil.storage import ensure_storage, save_bookmarks, load_bookmarks


class _Args:
    def __init__(self, fix=False, unsafe=False, as_json=False):
        self.fix = fix
        self.unsafe = unsafe
        self.as_json = as_json


def test_trim_duplicates_removes_earlier(tmp_path, capsys):
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        root = Path.cwd()
        sigil_dir = ensure_storage(root)

        now = "2020-01-01T00:00:00Z"
        # Duplicate bookmarks pointing to the same file and target. Later one should be kept.
        bm1 = Bookmark(
            id="bm_1_aaaaaaaa",
            file="src/file.py",
            line=10,
            context=Context(before="", target="def foo():", after=""),
            metadata=Metadata(tags=["t"], description="first", created=now, accessed=now),
            validation=Validation(status="valid", last_checked=now),
        )
        bm2 = Bookmark(
            id="bm_2_bbbbbbbb",
            file="src/file.py",
            line=20,
            context=Context(before="", target="def foo():", after=""),
            metadata=Metadata(tags=["t"], description="second", created=now, accessed=now),
            validation=Validation(status="valid", last_checked=now),
        )

        bookmarks = [bm1, bm2]
        save_bookmarks(sigil_dir, bookmarks)

        args = _Args(fix=True, unsafe=True)
        cmd_validate(args)
        captured = capsys.readouterr().out

        assert "Removed 1 duplicate bookmark(s):" in captured

        new = load_bookmarks(sigil_dir)
        assert len(new) == 1
        assert new[0].id == bm2.id

    finally:
        os.chdir(cwd)


def test_trim_duplicates_noop_when_no_duplicates(tmp_path, capsys):
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        root = Path.cwd()
        sigil_dir = ensure_storage(root)

        now = "2020-01-01T00:00:00Z"
        bm1 = Bookmark(
            id="bm_1_cccccccc",
            file="src/a.py",
            line=1,
            context=Context(before="", target="line a", after=""),
            metadata=Metadata(tags=[], description="a", created=now, accessed=now),
            validation=Validation(status="valid", last_checked=now),
        )
        bm2 = Bookmark(
            id="bm_2_dddddddd",
            file="src/b.py",
            line=2,
            context=Context(before="", target="line b", after=""),
            metadata=Metadata(tags=[], description="b", created=now, accessed=now),
            validation=Validation(status="valid", last_checked=now),
        )

        save_bookmarks(sigil_dir, [bm1, bm2])

        args = _Args(fix=True, unsafe=True)
        cmd_validate(args)
        captured = capsys.readouterr().out

        assert "No duplicate bookmarks found." in captured

        new = load_bookmarks(sigil_dir)
        assert len(new) == 2

    finally:
        os.chdir(cwd)


def test_trim_duplicates_different_files_not_considered(tmp_path, capsys):
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        root = Path.cwd()
        sigil_dir = ensure_storage(root)

        now = "2020-01-01T00:00:00Z"
        # Same target text, but different files -> should NOT be considered duplicates
        bm1 = Bookmark(
            id="bm_1_eeeeeeee",
            file="src/one.py",
            line=5,
            context=Context(before="", target="common line", after=""),
            metadata=Metadata(tags=[], description="one", created=now, accessed=now),
            validation=Validation(status="valid", last_checked=now),
        )
        bm2 = Bookmark(
            id="bm_2_ffffffff",
            file="src/two.py",
            line=6,
            context=Context(before="", target="common line", after=""),
            metadata=Metadata(tags=[], description="two", created=now, accessed=now),
            validation=Validation(status="valid", last_checked=now),
        )

        save_bookmarks(sigil_dir, [bm1, bm2])

        args = _Args(fix=True, unsafe=True)
        cmd_validate(args)
        captured = capsys.readouterr().out

        assert "No duplicate bookmarks found." in captured

        new = load_bookmarks(sigil_dir)
        assert len(new) == 2

    finally:
        os.chdir(cwd)
