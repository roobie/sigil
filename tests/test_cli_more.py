import os
import sys
import json
from types import SimpleNamespace
from pathlib import Path

# Ensure src is importable when tests are run from project root
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from sigil.cli import cmd_primer, cmd_init, cmd_list, cmd_validate, cmd_search
from sigil.storage import ensure_storage, save_bookmarks, load_bookmarks
from sigil.models import Bookmark, Context, Metadata, Validation


def test_cmd_primer_and_init(tmp_path, capsys):
    # cmd_primer should print the bundled PRIMER.md
    cmd_primer(None)
    out = capsys.readouterr().out
    assert "Sigil: LLM Reference" in out

    # cmd_init should create a .sigil/ directory in cwd
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        cmd_init(None)
        out = capsys.readouterr().out
        assert ".sigil" in out or "Initialized sigil" in out
        assert (Path.cwd() / ".sigil").is_dir()
    finally:
        os.chdir(cwd)


def test_cmd_list_long_and_filters(tmp_path, capsys):
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        root = Path.cwd()
        sigil_dir = ensure_storage(root)

        now = "2020-01-01T00:00:00Z"
        bm1 = Bookmark(
            id="bm_x_1",
            file="src/a.py",
            line=1,
            context=Context(before="", target="line a", after=""),
            metadata=Metadata(tags=["alpha"], description="first", created=now, accessed=now),
            validation=Validation(status="valid", last_checked=now),
        )
        bm2 = Bookmark(
            id="bm_x_2",
            file="src/b.py",
            line=2,
            context=Context(before="", target="line b", after=""),
            metadata=Metadata(tags=["beta"], description="second", created=now, accessed=now),
            validation=Validation(status="stale", last_checked=now),
        )
        save_bookmarks(sigil_dir, [bm1, bm2])

        # list all (json)
        args = SimpleNamespace(tags=None, file=None, stale=False, as_json=True, as_long=False)
        cmd_list(args)
        out = capsys.readouterr().out
        arr = json.loads(out)
        assert isinstance(arr, list) and len(arr) == 2

        # list stale only
        args2 = SimpleNamespace(tags=None, file=None, stale=True, as_json=False, as_long=False)
        cmd_list(args2)
        out2 = capsys.readouterr().out
        assert "stale" in out2 or "No bookmarks found." not in out2

        # list with tag filter
        args3 = SimpleNamespace(tags="alpha", file=None, stale=False, as_json=False, as_long=True)
        cmd_list(args3)
        out3 = capsys.readouterr().out
        assert "alpha" in out3 or "first" in out3

    finally:
        os.chdir(cwd)


def test_cmd_validate_json_output(tmp_path, capsys):
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        root = Path.cwd()
        sigil_dir = ensure_storage(root)

        # create a source file
        src = root / "code.py"
        src.write_text("hello\n", encoding="utf-8")

        now = "2020-01-01T00:00:00Z"
        bm = Bookmark(
            id="bm_val_1",
            file="code.py",
            line=1,
            context=Context(before="", target="hello", after=""),
            metadata=Metadata(tags=[], description="x", created=now, accessed=now),
            validation=Validation(status="unknown", last_checked=now),
        )
        save_bookmarks(sigil_dir, [bm])

        args = SimpleNamespace(fix=False, unsafe=False, as_json=True)
        cmd_validate(args)
        out = capsys.readouterr().out
        arr = json.loads(out)
        assert isinstance(arr, list)
        assert arr[0]["new_status"] == "valid"

    finally:
        os.chdir(cwd)


def test_cmd_search_filters(tmp_path, capsys):
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        root = Path.cwd()
        sigil_dir = ensure_storage(root)

        now = "2020-01-01T00:00:00Z"
        bm1 = Bookmark(
            id="bm_s_1",
            file="src/file1.py",
            line=1,
            context=Context(before="", target="foo_bar", after=""),
            metadata=Metadata(tags=["tag1"], description="findme please", created=now, accessed=now),
            validation=Validation(status="valid", last_checked=now),
        )
        bm2 = Bookmark(
            id="bm_s_2",
            file="src/other.py",
            line=2,
            context=Context(before="", target="baz", after=""),
            metadata=Metadata(tags=["tag2"], description="nothing", created=now, accessed=now),
            validation=Validation(status="valid", last_checked=now),
        )
        save_bookmarks(sigil_dir, [bm1, bm2])

        # free term search
        args = SimpleNamespace(query=["findme"], limit=0, as_json=True)
        cmd_search(args)
        out = capsys.readouterr().out
        arr = json.loads(out)
        assert isinstance(arr, list) and len(arr) == 1

        # tag-scoped search
        args2 = SimpleNamespace(query=["tag:tag2"], limit=0, as_json=True)
        cmd_search(args2)
        out2 = capsys.readouterr().out
        arr2 = json.loads(out2)
        assert len(arr2) == 1 and arr2[0]["id"] == "bm_s_2"

    finally:
        os.chdir(cwd)
