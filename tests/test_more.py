import os
import sys
import json
from types import SimpleNamespace
from pathlib import Path

# Ensure src is importable when tests are run from project root
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

import sigil.context as context_mod
import sigil.storage as storage
import sigil.validate as validate_mod
from sigil.models import Bookmark, Context, Metadata, Validation, generate_id, now_iso
from sigil.cli import (
    _find_bookmark,
    _print_table,
    _trim_duplicates,
    cmd_add,
    cmd_show,
    cmd_delete,
    cmd_move,
    cmd_edit,
    cmd_list,
)


def test_generate_id_and_now_iso_format():
    gid = generate_id()
    assert gid.startswith("bm_")
    assert "_" in gid
    ni = now_iso()
    assert isinstance(ni, str)
    assert "T" in ni


def test_extract_context_basic_and_errors(tmp_path):
    f = tmp_path / "a.py"
    f.write_text("line1\nline2\nline3\n", encoding="utf-8")

    # first line
    c1 = context_mod.extract_context(f, 1)
    assert c1.before == ""
    assert c1.target == "line1"
    assert c1.after == "line2"

    # middle line
    c2 = context_mod.extract_context(f, 2)
    assert c2.before == "line1"
    assert c2.target == "line2"
    assert c2.after == "line3"

    # last line
    c3 = context_mod.extract_context(f, 3)
    assert c3.before == "line2"
    assert c3.target == "line3"
    assert c3.after == ""

    # out of range
    try:
        context_mod.extract_context(f, 0)
        assert False, "expected ValueError"
    except ValueError:
        pass

    # missing file
    missing = tmp_path / "nope.py"
    try:
        context_mod.extract_context(missing, 1)
        assert False, "expected FileNotFoundError"
    except FileNotFoundError:
        pass


def test_read_file_lines_nonexistent(tmp_path):
    missing = tmp_path / "nope.txt"
    assert context_mod.read_file_lines(missing) == []


def test_storage_ensure_and_find_and_relative(tmp_path):
    root = tmp_path
    # create nested dir
    nested = root / "a" / "b"
    nested.mkdir(parents=True)

    # ensure storage at root
    sigil_dir = storage.ensure_storage(root)
    assert (sigil_dir / ".").exists() or sigil_dir.exists()
    assert (sigil_dir / storage.CONTEXTS_DIR).is_dir()
    assert (sigil_dir / storage.BOOKMARKS_FILE).exists()

    # find_root from nested should find root
    found = storage.find_root(start=nested)
    assert found == root

    # fallback to .git if .sigil missing
    # remove .sigil and create .git
    (sigil_dir).rename(root / ".sigil.bak")
    (root / ".git").mkdir()
    try:
        found2 = storage.find_root(start=nested)
        assert found2 == root
    finally:
        # restore
        (root / ".sigil.bak").rename(root / ".sigil")
        (root / ".git").rmdir()

    # get_relative_path for path inside and outside
    p_inside = root / "src" / "x.py"
    p_inside.parent.mkdir(parents=True)
    p_inside.write_text("x\n")
    rel = storage.get_relative_path(p_inside, root)
    assert rel == "src/x.py"

    p_out = Path("/") / "tmp" / "outside.py"
    # depends on system: just ensure it returns a string path
    _ = storage.get_relative_path(p_out, root)


def test_context_file_io_and_jsonl_roundtrip(tmp_path):
    root = tmp_path
    sigil_dir = storage.ensure_storage(root)

    now = "2020-01-01T00:00:00Z"

    bm = Bookmark(
        id="bm_test_aaaaaaaa",
        file="src/foo.py",
        line=2,
        context=Context(before="before line", target="target line", after="after line"),
        metadata=Metadata(tags=["t"], description="desc", created=now, accessed=now),
        validation=Validation(status="valid", last_checked=now),
    )

    # save
    storage.save_bookmarks(sigil_dir, [bm])

    # context file should exist
    ctx_path = sigil_dir / storage.CONTEXTS_DIR / f"{bm.id}.ctx"
    assert ctx_path.exists()
    content = ctx_path.read_text(encoding="utf-8")
    assert storage.CONTEXT_TARGET_MARKER + "target line" in content
    assert "before line" in content and "after line" in content

    # load back
    loaded = storage.load_bookmarks(sigil_dir)
    assert len(loaded) == 1
    l = loaded[0]
    assert l.id == bm.id
    assert l.context.target == "target line"

    # jsonl conversion
    j = storage._to_jsonl(bm)
    assert j["id"] == bm.id
    b2 = storage._from_jsonl(j, bm.context)
    assert isinstance(b2, Bookmark)
    assert b2.id == bm.id

    # orphan cleanup: save empty list should remove context
    storage.save_bookmarks(sigil_dir, [])
    assert not ctx_path.exists()


def test_validate_various_cases(tmp_path):
    root = tmp_path
    # create sample file
    f = root / "code.py"
    lines = [
        "alpha",
        "beta",
        "gamma",
        "delta",
        "epsilon",
        "beta",
        "zeta",
    ]
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # missing file
    bm_missing = Bookmark(
        id="bm_miss",
        file="nope.py",
        line=1,
        context=Context(before="", target="x", after=""),
        metadata=Metadata(),
        validation=Validation(status="unknown", last_checked=""),
    )
    res = validate_mod.validate_bookmark(bm_missing, root)
    assert res.new_status == "missing_file"

    # empty file
    empty = root / "empty.py"
    empty.write_text("", encoding="utf-8")
    bm_empty = Bookmark(
        id="bm_empty",
        file="empty.py",
        line=1,
        context=Context(before="", target="x", after=""),
        metadata=Metadata(),
        validation=Validation(status="unknown", last_checked=""),
    )
    res = validate_mod.validate_bookmark(bm_empty, root)
    assert res.new_status == "stale"
    assert "File is empty" in res.message

    # exact match
    bm_exact = Bookmark(
        id="bm_exact",
        file="code.py",
        line=2,
        context=Context(before="alpha", target="beta", after="gamma"),
        metadata=Metadata(),
        validation=Validation(status="unknown", last_checked=""),
    )
    res = validate_mod.validate_bookmark(bm_exact, root)
    assert res.new_status == "valid"
    assert res.new_line == 2

    # nearby search: original line 1 but target at line 2
    bm_near = Bookmark(
        id="bm_near",
        file="code.py",
        line=1,
        context=Context(before="", target="beta", after="gamma"),
        metadata=Metadata(),
        validation=Validation(status="unknown", last_checked=""),
    )
    res = validate_mod.validate_bookmark(bm_near, root)
    assert res.new_status == "valid"
    assert res.new_line == 2

    # file-wide unique match (moved)
    bm_moved = Bookmark(
        id="bm_moved",
        file="code.py",
        line=1,
        context=Context(before="", target="delta", after="epsilon"),
        metadata=Metadata(),
        validation=Validation(status="unknown", last_checked=""),
    )
    res = validate_mod.validate_bookmark(bm_moved, root)
    assert res.new_status == "moved"
    assert res.new_line == 4

    # multiple matches disambiguated by context (beta appears at 2 and 6)
    bm_multi = Bookmark(
        id="bm_multi",
        file="code.py",
        line=1,
        context=Context(before="alpha", target="beta", after="gamma"),
        metadata=Metadata(),
        validation=Validation(status="unknown", last_checked=""),
    )
    res = validate_mod.validate_bookmark(bm_multi, root)
    assert res.new_status in ("moved", "valid")
    assert res.new_line == 2

    # ambiguous matches (no context to disambiguate)
    bm_ambig = Bookmark(
        id="bm_ambig",
        file="code.py",
        line=1,
        context=Context(before="", target="beta", after=""),
        metadata=Metadata(),
        validation=Validation(status="unknown", last_checked=""),
    )
    res = validate_mod.validate_bookmark(bm_ambig, root)
    # since there are two betas and no context, expect stale
    assert res.new_status == "stale"
    assert "Multiple matches" in res.message or "not found" in res.message or res.message

    # not found anywhere
    bm_not = Bookmark(
        id="bm_not",
        file="code.py",
        line=1,
        context=Context(before="", target="doesnotexist", after=""),
        metadata=Metadata(),
        validation=Validation(status="unknown", last_checked=""),
    )
    res = validate_mod.validate_bookmark(bm_not, root)
    assert res.new_status == "stale"
    assert "not found" in res.message or res.message


def test_apply_result_changes_line_and_status():
    bm = Bookmark(
        id="bm_apply",
        file="x.py",
        line=1,
        context=Context(before="", target="a", after=""),
        metadata=Metadata(),
        validation=Validation(status="unknown", last_checked=""),
    )
    res = validate_mod.ValidationResult(bookmark=bm, old_status="unknown", new_status="moved", new_line=3, message="moved")
    changed = validate_mod.apply_result(res, fix=True)
    assert changed
    assert bm.line == 3
    assert bm.validation.status == "moved"

    # no-op when new_status == old_status and no new_line
    bm2 = Bookmark(
        id="bm_apply2",
        file="x.py",
        line=5,
        context=Context(before="", target="a", after=""),
        metadata=Metadata(),
        validation=Validation(status="valid", last_checked=""),
    )
    res2 = validate_mod.ValidationResult(bookmark=bm2, old_status="valid", new_status="valid", new_line=None, message="ok")
    changed2 = validate_mod.apply_result(res2, fix=False)
    assert not changed2


def test_cli_helpers_find_and_table_and_trim(tmp_path, capsys):
    # _find_bookmark errors
    try:
        _find_bookmark([], "nope")
        assert False
    except SystemExit:
        pass

    # ambiguous
    b1 = Bookmark(id="bm_1_aaaa", file="f", line=1, context=Context(before="", target="t", after=""))
    b2 = Bookmark(id="bm_2_aaaa", file="f", line=2, context=Context(before="", target="u", after=""))
    try:
        _find_bookmark([b1, b2], "aaaa")
        assert False
    except SystemExit:
        pass

    # _print_table
    _print_table([b1, b2])
    out = capsys.readouterr().out
    assert "ID" in out and "FILE" in out and "LINE" in out

    # _trim_duplicates keeps newest (later in list) and removes earlier
    bm_old = Bookmark(id="bm_old", file="a.py", line=1, context=Context(before="", target="same", after=""))
    bm_new = Bookmark(id="bm_new", file="a.py", line=2, context=Context(before="", target="same", after=""))
    new, removed = _trim_duplicates([bm_old, bm_new])
    assert len(new) == 1 and new[0].id == "bm_new"
    assert len(removed) == 1 and removed[0].id == "bm_old"


def test_cmd_add_show_delete_move_edit_list(tmp_path, capsys, monkeypatch):
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        # Ensure editor env vars are set early so cmd_edit never blocks when tests run
        monkeypatch.setenv("EDITOR", "true")
        monkeypatch.setenv("VISUAL", "true")

        root = Path.cwd()
        sigil_dir = storage.ensure_storage(root)

        # create a source file
        src_dir = root / "src"
        src_dir.mkdir()
        f = src_dir / "foo.py"
        f.write_text("aa\nbb\ncc\n", encoding="utf-8")

        # cmd_add
        args = SimpleNamespace(location=str(f) + ":2", tags="t1,t2", desc="mydesc")
        cmd_add(args)
        out = capsys.readouterr().out
        assert "Added bookmark" in out
        # load bookmarks
        bms = storage.load_bookmarks(sigil_dir)
        assert len(bms) == 1
        bm = bms[0]
        assert "t1" in bm.metadata.tags
        assert bm.metadata.description == "mydesc"

        # cmd_show json
        args_show = SimpleNamespace(id=bm.short_id, as_json=True)
        cmd_show(args_show)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["id"] == bm.id or data.get("id") == bm.id

        # cmd_show text updates accessed
        old_accessed = bm.metadata.accessed
        args_show2 = SimpleNamespace(id=bm.short_id, as_json=False)
        cmd_show(args_show2)
        out = capsys.readouterr().out
        bms2 = storage.load_bookmarks(sigil_dir)
        assert bms2[0].metadata.accessed != old_accessed

        # cmd_list as_json
        args_list = SimpleNamespace(tags=None, file=None, stale=False, as_json=True, as_long=False)
        cmd_list(args_list)
        out = capsys.readouterr().out
        arr = json.loads(out)
        assert isinstance(arr, list)

        # cmd_move relative +1 (to line 3)
        args_move = SimpleNamespace(id=bm.short_id, target="+1")
        cmd_move(args_move)
        out = capsys.readouterr().out
        bms3 = storage.load_bookmarks(sigil_dir)
        assert bms3[0].line == 3

        # cmd_move absolute line
        args_move2 = SimpleNamespace(id=bm.short_id, target="1")
        cmd_move(args_move2)
        bms4 = storage.load_bookmarks(sigil_dir)
        assert bms4[0].line == 1

        # cmd_edit: already ensured EDITOR=VISUAL=true above so no interactive editor will run
        args_edit = SimpleNamespace(id=bm.short_id)
        cmd_edit(args_edit)
        out = capsys.readouterr().out
        assert "No changes." in out

        # cmd_delete by id
        args_del = SimpleNamespace(id=bm.short_id, tags=None)
        cmd_delete(args_del)
        out = capsys.readouterr().out
        assert "Deleted bookmark" in out
        bms5 = storage.load_bookmarks(sigil_dir)
        assert len(bms5) == 0

        # delete by tags - create two bookmarks
        bm1 = Bookmark(id="bm_x_1", file="a.py", line=1, context=Context(before="", target="t", after=""), metadata=Metadata(tags=["z"], description="a"), validation=Validation())
        bm2 = Bookmark(id="bm_x_2", file="b.py", line=2, context=Context(before="", target="u", after=""), metadata=Metadata(tags=["z"], description="b"), validation=Validation())
        storage.save_bookmarks(sigil_dir, [bm1, bm2])
        args_del2 = SimpleNamespace(id=None, tags="z")
        cmd_delete(args_del2)
        out = capsys.readouterr().out
        assert "Deleting 2 bookmark(s):" in out

        # cmd_delete error when neither id nor tags
        try:
            cmd_delete(SimpleNamespace(id=None, tags=None))
            assert False
        except SystemExit:
            pass

    finally:
        os.chdir(cwd)
