#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""note_katex / build_note のテスト（標準ライブラリのみ）。

    python -m unittest discover -s tests -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from note_katex import (convert, disp_w, esc, katex_table, preflight,  # noqa: E402
                        wrap_cell, HANG, DEFAULT_BUDGET)


class TestEscape(unittest.TestCase):
    """note の Markdown 層に壊されない表記に変換されること。"""

    def test_halfwidth_symbols_become_fullwidth(self):
        self.assertEqual(esc("A & B"), "A ＆ B")
        self.assertEqual(esc("77.3%"), "77.3％")
        self.assertEqual(esc("$20"), "＄20")

    def test_never_emits_tex_escaped_dollar_etc(self):
        # \$ \& \% は note がバックスラッシュを消して壊すため、絶対に出してはいけない
        out = esc("$100 & 50% \\ end")
        for bad in ("\\$", "\\&", "\\%"):
            self.assertNotIn(bad, out)

    def test_arrow_becomes_math_command(self):
        self.assertEqual(esc("調査→資料"), r"調査}\to\text{資料")

    def test_star_becomes_math_command(self):
        # ★ は KaTeX に字形がないため警告になる。数式の \star に置き換える。
        self.assertEqual(esc("393,763★"), r"393,763}\star\text{")

    def test_euro_becomes_ascii(self):
        self.assertIn("EUR", esc("€20"))

    def test_bold_markers_removed(self):
        self.assertEqual(esc("**強調**"), "強調")


class TestWrap(unittest.TestCase):
    """語の途中で折らない・行が幅を大きく超えないこと。"""

    def test_does_not_split_katakana_word(self):
        # 幅が足りていれば、カタカナ語の途中では折らない
        self.assertEqual(wrap_cell("単一プロバイダ", 10), ["単一", "プロバイダ"])

    def test_lines_respect_limit(self):
        text = "常時稼働のクラウドPC。Slack／Teamsから指示、数日単位の長期タスクを継続。"
        for limit in (8, 12, 20):
            for ln in wrap_cell(text, limit):
                self.assertLessEqual(disp_w(ln), limit + HANG + 1e-6, ln)

    def test_no_punctuation_only_line(self):
        lines = wrap_cell("定額＋トークン／クレジット従量", 10)
        self.assertFalse([ln for ln in lines if all(c in "。、，：；／・）】＋" for c in ln)])


class TestTable(unittest.TestCase):
    """KaTeX 表として成立し、ヘッダーも列幅で折り返されること。"""

    def test_structure(self):
        t = katex_table(["項目", "内容"], [["提供会社", "Anthropic"]], 58)
        self.assertTrue(t.startswith("$$"))
        self.assertTrue(t.endswith("$$"))
        self.assertEqual(t.count(r"\begin{array}"), 1)
        self.assertEqual(t.count(r"\end{array}"), 1)
        self.assertEqual(t.count(r"\hline"), 3)          # 上・行間・下

    def test_header_is_wrapped(self):
        # 回帰テスト: ヘッダーを素通しにすると長いヘッダーが列幅を無視してはみ出す（実測139px）
        t = katex_table(["使用できるLLM"], [["マルチモデル"]], budget=12)
        self.assertNotIn(r"\text{使用できるLLM}", t)      # 1行で素通しされていない
        lines = t.split("\n")
        head_i = next(i for i, ln in enumerate(lines) if "使用" in ln)
        self.assertNotIn(r"\hline", lines[head_i + 1])    # ヘッダーの続き行がある

    def test_cells_use_text_wrapper(self):
        t = katex_table(["A"], [["B"]], 58)
        self.assertIn(r"\text{A}", t)
        self.assertIn(r"\text{B}", t)


class TestConvert(unittest.TestCase):
    """Markdown 全体の変換と事前チェック。"""

    MD = """# 見出し

説明文です。$20 と 50% と A & B。

| 製品 | 料金 |
|---|---|
| Alpha | $20 |
| Beta | $100 |
"""

    def test_table_replaced_and_body_kept(self):
        doc, ntables, _ = convert(self.MD)
        self.assertEqual(ntables, 1)
        self.assertIn("# 見出し", doc)
        self.assertIn("説明文です。", doc)
        self.assertNotIn("| 製品 | 料金 |", doc)
        self.assertIn(r"\begin{array}", doc)

    def test_body_dollar_fullwidth(self):
        doc, _, _ = convert(self.MD)
        self.assertIn("＄20", doc)
        self.assertNotIn("$20", doc.replace("$$", ""))

    def test_preflight_passes(self):
        doc, _, _ = convert(self.MD)
        r = preflight(doc)
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["blocks"], 1)
        self.assertEqual(r["md_table_rows"], 0)

    def test_preflight_catches_broken_block(self):
        bad = "$$\n\\begin{array}{|l|}\\hline \\text{Pro \\$20} \\cr \\hline\\end{array}\n$$"
        r = preflight(bad)
        self.assertFalse(r["ok"])
        self.assertGreater(r["bad_escape"]["\\$"], 0)

    def test_no_pipe_table_left(self):
        md = "| a | b |\n|---|---|\n| 1 | 2 |\n"
        doc, n, _ = convert(md)
        self.assertEqual(n, 1)
        self.assertEqual(preflight(doc)["md_table_rows"], 0)


class TestBudget(unittest.TestCase):
    """--budget が列幅に効いていること。"""

    def test_smaller_budget_gives_narrower_lines(self):
        header, rows = ["項目", "内容"], [["特徴", "あ" * 40]]
        wide = katex_table(header, rows, 58)
        narrow = katex_table(header, rows, 30)
        width = lambda t: max(disp_w(m) for m in t.split("\n"))
        self.assertLess(width(narrow), width(wide))


if __name__ == "__main__":
    unittest.main(verbosity=2)
