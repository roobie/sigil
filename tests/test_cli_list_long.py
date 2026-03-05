import sys
import os

# Ensure src is importable when tests are run from project root
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from sigil.cli import _print_long
from sigil.models import Bookmark, Context, Metadata, Validation


def test_print_long_basic(capsys):
    bm = Bookmark(
        id="bm_1_abcdefgh",
        file="server/scanner/orchestrator.ts",
        line=17,
        context=Context(before="", target="export async function runScan(store: Store): Promise<void> {", after=""),
        metadata=Metadata(tags=["scanner", "core"], description="runScan orchestrator — entry point for the scan pipeline"),
        validation=Validation(status="valid", last_checked=""),
    )

    _print_long([bm])
    captured = capsys.readouterr().out

    expected = (
        "abcdefgh  server/scanner/orchestrator.ts:17\n"
        "\t[scanner,core] runScan orchestrator — entry point for the scan pipeline\n"
        "\t→ export async function runScan(store: Store): Promise<void> {\n\n"
    )

    assert captured == expected


def test_print_long_multiline_description(capsys):
    desc = "First line of description\nSecond line with more detail\nThird line"
    bm = Bookmark(
        id="bm_2_ijklmnop",
        file="prisma/schema.prisma",
        line=4,
        context=Context(before="", target="generator client {", after=""),
        metadata=Metadata(tags=["database"], description=desc),
        validation=Validation(status="valid", last_checked=""),
    )

    _print_long([bm])
    captured = capsys.readouterr().out

    expected = (
        "ijklmnop  prisma/schema.prisma:4\n"
        "\t[database] First line of description\n"
        "\t  Second line with more detail\n"
        "\t  Third line\n"
        "\t→ generator client {\n\n"
    )

    assert captured == expected
