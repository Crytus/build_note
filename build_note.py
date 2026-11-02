#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""build_note — Markdown ファイルを読み、中の表を note.com 用の KaTeX 表に書き換えて出力する。

note は Markdown のテーブル記法を描画しないため、表は ``$$ \begin{array} … $$``
（KaTeX）で書く必要がある。このツールはそれを自動で行い、貼り付け前に
「note 側で壊れないか」まで検査する。

使い方:
    python build_note.py input.md                          # → input_note.md
    python build_note.py input.md -o output.md             # 出力先を指定
    python build_note.py input.md --check check.html       # 検証用の HTML も作る
    python build_note.py input.md --budget 50              # 表の幅を狭める

終了コード: 0 = 検査 PASS / 1 = 検査 FAIL / 2 = 入力エラー
"""

import argparse
import sys
from pathlib import Path

from katex_check import build_html
from note_katex import DEFAULT_BUDGET, convert, preflight

__version__ = "1.0.0"


def build(input_path: Path, output_path: Path, budget: int, check_path=None, quiet=False):
    md = input_path.read_text(encoding="utf-8")
    doc, ntables, warnings = convert(md, budget)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(doc, encoding="utf-8")
    report = preflight(doc)
    if check_path is not None:
        check_path = Path(check_path)
        check_path.parent.mkdir(parents=True, exist_ok=True)
        check_path.write_text(build_html(doc), encoding="utf-8")

    if not quiet:
        print(f"入力: {input_path}")
        print(f"出力: {output_path}  （表 {ntables}個 → KaTeX {report['blocks']}ブロック）")
        if check_path is not None:
            print(f"検証: {check_path}  ← ブラウザで開いて window.__r を確認")
        if warnings:
            cols = max(w[1] for w in warnings)
            print()
            print(f"  ⚠ 幅が足りず語中で折った表が {len(warnings)}個あります（最大 {cols}列）。")
            print("     5列以上、または長い説明文を含む表は note の本文幅（約580px）に収まりません。")
            print("     「一覧表は短いセルだけ」＋「長い説明は項目別の2列詳細表か箇条書き」に分割してください。")
            print("     （列を減らして再実行すると警告は消えます）")
        print()
        print("  --- note 貼り付け前チェック ---")
        print(f"  KaTeXブロック数            : {report['blocks']}")
        print(f"  残ったMarkdown表の行数     : {report['md_table_rows']}（0であるべき）")
        print(f"  エスケープ \\$ \\& \\% の残存 : {report['bad_escape']}（すべて0であるべき）")
        print(f"  \\text{{}} 内の半角 $ & %    : {report['raw_symbol_in_text']}（すべて0であるべき）")
        print(f"  $ が奇数個の行があるブロック: {report['odd_dollar_lines']}（0であるべき）")
        print(f"  array が不整合なブロック   : {report['unbalanced']}（0であるべき）")
        print()
        print("  判定:", "PASS — note にそのまま貼り付け可能" if report["ok"]
              else "FAIL — note で生テキストになります。上の項目を修正してください")
    return report, ntables, warnings


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="build_note",
        description="Markdown の表を note.com 用の KaTeX 表に変換して出力する",
        epilog="例: python build_note.py article.md --check check.html")
    ap.add_argument("input", help="入力の Markdown ファイル")
    ap.add_argument("-o", "--output", help="出力先（省略時は <入力名>_note.md）")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help=f"表全体の幅（単位。既定{DEFAULT_BUDGET}、noteの本文幅 ≒ 60。"
                         "狭くすると折り返しが増えるがはみ出しにくくなる）")
    ap.add_argument("--check", metavar="HTML", help="ブラウザ検証用の HTML をこのパスに出力する")
    ap.add_argument("-q", "--quiet", action="store_true", help="レポートを表示しない（終了コードのみ）")
    ap.add_argument("--version", action="version", version=f"build_note {__version__}")
    a = ap.parse_args(argv)

    src = Path(a.input)
    if not src.is_file():
        print(f"エラー: 入力ファイルが見つかりません: {src}", file=sys.stderr)
        return 2
    dst = Path(a.output) if a.output else src.with_name(src.stem + "_note.md")

    report, _, _ = build(src, dst, a.budget, a.check, a.quiet)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
