#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""note_katex — Markdown の表を note.com 用の KaTeX 表に変換するエンジン。

このモジュールは変換ロジックだけを持つ。コマンドとして使うなら build_note.py を使う。

    from note_katex import convert, preflight
    doc, ntables, warnings = convert(markdown_text, budget=58)
    report = preflight(doc)

やること:
  - Markdown のテーブルを ``$$ \begin{array} ... $$`` に置換（\cr / \hline / \text）
  - セルは「語の途中で折らない」単位分割で折り返し、複数行に積む
    （KaTeX の array は折り返さないため、行を自分で作る必要がある）
  - 半角 $ & % は全角 ＄ ＆ ％ に置換（note の Markdown 層が \ $ \& \% を壊すため）
  - → は \to に、€ は EUR に置換（KaTeX に字形がない）
  - 表以外の本文はそのまま通す（本文中の半角 $ だけ全角化する）
"""

import re
import sys

__all__ = [
    "esc", "disp_w", "units", "wrap_cell", "column_widths", "katex_table",
    "convert", "preflight", "MIN_COL", "DEFAULT_BUDGET", "COL_PAD", "HANG",
]

# ------------------------------------------------------------------ 文字変換

TEX_ESCAPE = {
    "\\": r"\textbackslash{}",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def esc(text: str) -> str:
    r"""セル文字列を ``\text{}`` の中身に変換する。

    半角の $ & % は使わない。note の Markdown 層が ``\$`` ``\&`` ``\%`` の
    バックスラッシュを削除し、KaTeX に素の $ & % が渡って解析エラーになる。
    その結果 note は、そのブロックを生の LaTeX ソースのまま本文に表示してしまう。
    全角の ＄ ＆ ％ は Markdown も KaTeX も素通しするので安全。
    """
    s = text.replace("**", "").replace("|", "｜").strip()
    s = s.replace("€", "EUR ")
    s = re.sub(r"\s+", " ", s)
    out = []
    for ch in s:
        if ch == "&":
            out.append("＆")
        elif ch == "%":
            out.append("％")
        elif ch == "$":
            out.append("＄")
        elif ch == "→":
            out.append(r"}\to\text{")      # KaTeX に字形がないので数式の \to を出す
        else:
            out.append(TEX_ESCAPE.get(ch, ch))
    return "".join(out)


# ------------------------------------------------------------------ 幅の計算
# note の本文幅は約 580px。1単位 = 全角1文字の半分で、実測 ≒ 9.7px。

def disp_w(s: str) -> float:
    """描画幅を「全角1文字 = 2単位」に正規化して返す。

    係数はブラウザ実測（KaTeX 0.16）:
      全角形(FF00-FFEF) 2.4 / CJK 2.0 / 英字 1.3 / 数字 1.2 / 空白 1.15 / 半角記号 0.82
    """
    w = 0.0
    for c in s:
        o = ord(c)
        if 0xFF00 <= o <= 0xFFEF:
            w += 2.4
        elif o > 0x1100:
            w += 2.0
        elif c.isalpha():
            w += 1.3
        elif c.isdigit():
            w += 1.2
        elif c.isspace():
            w += 1.15
        else:
            w += 0.82
    return w


KATAKANA = lambda c: 0x30A0 <= ord(c) <= 0x30FF or c in "ー・"
KANJI = lambda c: 0x4E00 <= ord(c) <= 0x9FFF
ASCII_WORD = lambda c: c.isascii() and (c.isalnum() or c in "%$#@&=+-/.")
PUNCT_ONLY = "。、，：；／・）】＋"
HANG = 1.0            # 行末にぶら下げる句読点の許容はみ出し（単位）


def units(s: str):
    """「ここで折ってはいけない最小単位」に分解する。

    カタカナ語・英数語・漢字の連なりは分割しない（``プロバイ/ダ`` のような
    語中改行を防ぐ）。括弧内は再帰的に分解し、開き/閉じ括弧は隣の語に付ける。
    """
    out, i, n = [], 0, len(s)
    while i < n:
        ch = s[i]
        if ch in "（(「【":
            close = {"（": "）", "(": ")", "「": "」", "【": "】"}[ch]
            j = s.find(close, i + 1)
            j = n - 1 if j == -1 else j
            sub = units(s[i + 1:j])
            if not sub:
                out.append(s[i:j + 1])
            elif len(sub) == 1:
                out.append(ch + sub[0] + close)
            else:
                out.append(ch + sub[0])
                out.extend(sub[1:-1])
                out.append(sub[-1] + close)
            i = j + 1
        elif KATAKANA(ch) or KANJI(ch) or ASCII_WORD(ch):
            j = i
            test = KATAKANA if KATAKANA(ch) else (KANJI if KANJI(ch) else ASCII_WORD)
            while j < n and test(s[j]):
                j += 1
            out.append(s[i:j])
            i = j
        else:
            out.append(ch)
            i += 1
    return [u for u in out if u]


def split_unit(u: str, limit: int):
    """単位自体が上限を超えるとき、空白優先で分割する。"""
    if " " in u.strip():
        for k in range(len(u) - 1, 0, -1):
            if u[k] == " " and disp_w(u[:k]) <= limit:
                return u[:k], u[k + 1:]
    head = ""
    for ch in u:
        if disp_w(head) + disp_w(ch) > limit:
            break
        head += ch
    return (head or u[:1]), u[len(head or u[:1]):]


def wrap_cell(text: str, limit: int):
    """セルを表示幅 limit 以内の行に折る（語中では折らない）。"""
    s = text.replace("**", "").strip()
    s = s.replace("€", "EUR ")
    if not s:
        return [""]
    lines, cur = [], ""
    for u in units(s):
        if not cur.strip() and u == " ":          # 行頭の空白は捨てる
            continue
        if disp_w(cur) + disp_w(u) <= limit:
            cur += u
            continue
        if cur.strip():
            if all(c in PUNCT_ONLY for c in u) and disp_w(cur) + disp_w(u) <= limit + HANG:
                lines.append((cur + u).rstrip())  # 句読点は行末にぶら下げる（禁則処理）
                cur = ""
                continue
            lines.append(cur.rstrip())
        cur = u.lstrip()
        while disp_w(cur) > limit:                # 単位自体が長すぎる場合
            head, rest = split_unit(cur, limit)
            if not head or not rest:
                break
            if all(c in PUNCT_ONLY for c in rest) and disp_w(head) + disp_w(rest) <= limit + HANG:
                head, rest = head + rest, ""      # 句読点だけ残るなら、はみ出しを許してまとめる
            lines.append(head.rstrip())
            cur = rest.lstrip()
    if cur.strip():
        lines.append(cur.rstrip())
    return lines or [s]


MIN_COL = 5           # 1列あたりの最小幅（単位）
DEFAULT_BUDGET = 58   # 表全体の幅（単位・列間の空きを含む）。noteの本文幅580px ≒ 60単位
COL_PAD = 2.1         # KaTeXの配列が列ごとに取る空き＋罫線（単位 ≒ 20px）


def column_widths(header, rows, budget=DEFAULT_BUDGET):
    """列幅を決める。合計が budget を超えず、短いセル（ラベル等）は折らないこと。

    2段階の下限を使う:
      hard = 語を割らずに済む最小（最長の分割不能単位）。均等割で頭打ち → 合計は必ず予算内
      soft = セル全体が1行に収まる幅。余りがある限りこちらを満たす
    こうしないと「使用できるLLM」が「使用できる／LLM」に割れる。
    """
    ncol = len(header)
    eff = max(budget - ncol * (COL_PAD + HANG), ncol * MIN_COL)
    natural, longest_unit = [], []
    for c in range(ncol):
        cells = [header[c]] + [r[c] for r in rows if c < len(r)]
        natural.append(max(disp_w(x.replace("**", "")) for x in cells))
        longest_unit.append(max((disp_w(u) for x in cells for u in units(x.replace("**", ""))),
                                default=0))
    # soft から出発し、はみ出す分を削って eff に収める。
    # 削り方は2段階: まず「1行に収まる分を超えた余り」を均し、それでも超えるなら
    # 長い列（natural が大きい列）から削る。短い列を犠牲にしないための順序。
    hard = [min(max(longest_unit[i] + 1, MIN_COL), eff / ncol) for i in range(ncol)]
    soft = [min(natural[i] + 1, eff * 0.6) for i in range(ncol)]
    w = soft[:]
    over = sum(w) - eff
    if over > 0:
        surplus = [max(w[i] - natural[i], 0.0) for i in range(ncol)]
        tot = sum(surplus)
        if tot > 0:
            take = min(over, tot)
            for i in range(ncol):
                w[i] -= take * surplus[i] / tot
            over -= take
    for i in sorted(range(ncol), key=lambda k: natural[k], reverse=True):
        if over <= 1e-9:
            break
        cut = min(over, max(w[i] - hard[i], 0.0))
        w[i] -= cut
        over -= cut
    rest = eff - sum(w)
    if rest > 1e-9:                         # 余りは長い列に配る（折り返しを減らす）
        weight = [max(natural[i], 1.0) for i in range(ncol)]
        tw = sum(weight)
        w = [w[i] + rest * weight[i] / tw for i in range(ncol)]
    widths = [max(int(round(x)), MIN_COL - 1) for x in w]
    # 「語の途中で割れる列」だけを警告対象にする（長い文章が折り返すのは正常）
    forced = [i for i in range(ncol) if widths[i] + 1.5 < longest_unit[i]]
    return widths, forced


def katex_table(header, rows, budget=DEFAULT_BUDGET, warnings=None):
    """1つの表を、note に貼れる KaTeX ブロック（文字列）に変換する。"""
    widths, forced = column_widths(header, rows, budget)
    # 5列以上は note の本文幅に収まらないことが多い。語中で割れた列があれば確実に読みにくい。
    if (forced or len(header) >= 5) and warnings is not None:
        warnings.append((header[0], len(header), forced))
    ncol = len(header)
    L = [r"\newcommand{\arraystretch}{1.5}%",
         r"\begin{array}{" + "|" + "|".join(["l"] * ncol) + "|}",
         r"\hline"]

    def emit(chunks):
        """セルを列幅で折り返しつつ、行番号を揃えて複数行に積む。"""
        for k in range(max(len(c) for c in chunks)):
            cells = []
            for j in range(ncol):
                t = chunks[j][k] if k < len(chunks[j]) else ""
                cells.append(r"\text{" + esc(t) + "}" if t else r"\text{}")
            L.append(" & ".join(cells) + r" \cr")

    # ヘッダーも同じ列幅で折り返す。ここを素通しにすると、長いヘッダー文字列が
    # 列の最小幅を決めてしまい、指定した幅を無視して表が横にはみ出す（実測139px）。
    emit([wrap_cell(h, widths[i]) for i, h in enumerate(header)])
    for row in rows:
        L.append(r"\hline")
        emit([wrap_cell(row[i] if i < len(row) else "", widths[i]) for i in range(ncol)])
    L += [r"\hline", r"\end{array}"]
    return "$$\n" + "\n".join(L) + "\n$$"


# ------------------------------------------------------------------ 変換本体

SEP_CELL = re.compile(r":?-{2,}:?$")


def convert(md: str, budget: int = DEFAULT_BUDGET):
    """Markdown 全体を note 用に変換する。

    Returns:
        (変換後のMarkdown, 変換した表の数, 幅が足りず折り返した表の警告リスト)
    """
    lines = md.split("\n")
    out, i, ntables, warnings = [], 0, 0, []
    while i < len(lines):
        if lines[i].lstrip().startswith("|"):
            block = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                block.append(lines[i].strip())
                i += 1
            table = [[c.strip() for c in b.strip("|").split("|")] for b in block]
            table = [r for r in table if not all(SEP_CELL.fullmatch(c) for c in r if c)]
            if len(table) >= 2:
                out.append(katex_table(table[0], table[1:], budget, warnings))
                ntables += 1
            else:
                out.extend(block)
        else:
            out.append(lines[i])
            i += 1
    doc = "\n".join(out)
    # 本文中の半角 $ は note の Markdown 層で数式扱いされ得るので全角化（$$ 区切りは残す）
    doc = "\n".join(l if l.strip() == "$$" else l.replace("$", "＄") for l in doc.split("\n"))
    return doc, ntables, warnings


# ------------------------------------------------------------------ 事前チェック

def preflight(doc: str):
    """note の Markdown 層で壊れる記法が残っていないか検査する。

    note は KaTeX のレンダリングに失敗したブロックを、無言で生テキスト表示に
    フォールバックする。貼り付ける前にここで落とす。
    """
    blk = re.findall(r"\$\$(.*?)\$\$", doc, re.S)
    md_tables = len(re.findall(r"^\|.*\|\s*$", doc, re.M))
    bad_esc = {e: sum(b.count(e) for b in blk) for e in ("\\$", "\\&", "\\%")}
    risky = {c: sum(t.count(c) for t in re.findall(r"\\text\{([^{}]*)\}", "\n".join(blk)))
             for c in "$&%"}
    parity = [i for i, b in enumerate(blk)
              if any(l.count("$") % 2 for l in b.split("\n"))]
    asym = [i for i, b in enumerate(blk)
            if b.count(r"\begin{array}") != b.count(r"\end{array}")]
    ok = (not md_tables and not any(bad_esc.values()) and not any(risky.values())
          and not parity and not asym)
    return {"blocks": len(blk), "md_table_rows": md_tables, "bad_escape": bad_esc,
            "raw_symbol_in_text": risky, "odd_dollar_lines": parity,
            "unbalanced": asym, "ok": ok}


def main(argv=None):
    """単体でも動くようにしておく（通常は build_note.py を使う）。"""
    import argparse
    from pathlib import Path
    ap = argparse.ArgumentParser(description="Markdownの表をnote用KaTeX表に変換する")
    ap.add_argument("input")
    ap.add_argument("-o", "--output", help="省略時は <input>_note.md")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    a = ap.parse_args(argv)
    src = Path(a.input)
    dst = Path(a.output) if a.output else src.with_name(src.stem + "_note.md")
    doc, n, _ = convert(src.read_text(encoding="utf-8"), a.budget)
    dst.write_text(doc, encoding="utf-8")
    r = preflight(doc)
    print(f"OK: {dst} （表 {n}個 → KaTeX {r['blocks']}ブロック）")
    print("  判定:", "PASS" if r["ok"] else "FAIL")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
