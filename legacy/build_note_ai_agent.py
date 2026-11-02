#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai_agent_comparison_2026-11.md から note 掲載用マークダウン（表はKaTeX形式）を生成する。

note はマークダウンのテーブル記法を描画しないため、すべての表を KaTeX の array 環境に
変換する。長文セルは note 上で横に伸びて読めなくなるので、
「継続行（\\text{} & ...）」でセル内改行して縦持ちの表にしている。
参照: https://note.com/masato_powerup/n/n1e28ba44cbab

使い方: python build_note.py
"""
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE / "ai_agent_comparison_2026-11.md"
OUT = BASE / "ai_agent_comparison_2026-11_note.md"

# ---------------------------------------------------------------- md 解析


def parse_sections(text: str):
    secs, cur = [], None
    for line in text.splitlines():
        if line.startswith("## "):
            if cur:
                secs.append(cur)
            cur = {"head": line[3:].strip(), "lines": []}
        elif cur is not None:
            cur["lines"].append(line)
    if cur:
        secs.append(cur)
    return secs


def tables_in(section):
    out, rows = [], []
    for line in section["lines"]:
        s = line.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            rows.append(cells)
        elif rows:
            out.append(rows)
            rows = []
    if rows:
        out.append(rows)
    return out


def _get_section(sections, key):
    for s in sections:
        if key in s["head"]:
            return s
    raise SystemExit(f"セクションが見つかりません: {key}")


def find_table(sections, key, first_cell):
    for rows in tables_in(_get_section(sections, key)):
        if any(first_cell in r[0] for r in rows):
            return rows
    raise SystemExit(f"テーブルが見つかりません: {key} / {first_cell}")


def find_text(sections, key):
    sec = _get_section(sections, key)
    return "\n".join(l for l in sec["lines"] if not l.strip().startswith("|"))


def clip(s: str) -> str:
    """説明文から KaTeX セル用のプレーンテキストにする（太字記号を除去）。"""
    s = s.replace("**", "").strip()
    # KaTeX が字形を持たない通貨記号は、意味を保ったままASCII表記にする
    s = s.replace("€", "EUR ")
    return re.sub(r"\s{2,}", " ", s)


# ---------------------------------------------------------------- KaTeX 生成

# 幅の単位（KaTeX実測: 全角 ≒ 19px、欧文英数 ≒ 14.2px、記号 ≒ 7.6px。
# 全角=2単位に正規化すると 1単位 ≒ 9.5px）。
# noteの本文幅は約580px。KaTeXの配列は余白を約20px食うので、
# 列幅の合計が 50単位（≒475px）前後になるよう調整する。
W_INDEX = [22, 18, 15]    # 製品 / 提供会社 / LLMの選択
W_CAT = [16, 21, 14]      # カテゴリ / 何を買うか / 価格の性質
W_DETAIL = [16, 39]       # 項目 / 内容
W_STAT = [20, 32]         # 指標 / 数値・出典
W_LLM = [16, 18, 19]      # タイプ / 該当製品 / 実務上の意味
NARROW = W_DETAIL[0]      # 旧名の互換（ラベル列）
WIDE = W_DETAIL[1]        # 旧名の互換（長文列）


def esc(s: str) -> str:
    r"""\text{} 内で安全な文字列に変換する。

    重要: note の Markdown 層は `\$` `\&` `\%` のバックスラッシュを削除する。
    その結果 KaTeX に素の $ & % が渡り、数式解析エラー→noteが生テキスト表示に
    フォールバックする（2026/11 実測）。したがって半角の $ & % は使わず、
    KaTeXが受理しMarkdownが触らない全角の ＄ ＆ ％ に置き換える。
    """
    out = []
    for ch in s:
        if ch == "&":
            out.append("＆")
        elif ch == "%":
            out.append("％")
        elif ch == "$":
            out.append("＄")
        elif ch == "#":
            out.append(r"\#")
        elif ch == "_":
            out.append(r"\_")
        elif ch == "{":
            out.append(r"\{")
        elif ch == "}":
            out.append(r"\}")
        elif ch == "~":
            out.append(r"\textasciitilde{}")
        elif ch == "\\":
            out.append(r"\textbackslash{}")
        elif ch == "^":
            out.append(r"\textasciicircum{}")
        elif ch == "→":
            # KaTeX に字形がないため、いったん \text{} を閉じて数式の \to を出す
            out.append(r"}\to\text{")
        else:
            out.append(ch)
    return "".join(out)


def disp_w(s: str) -> float:
    """KaTeX上の描画幅を「全角1文字=2単位」に正規化して返す。"""
    w = 0.0
    for c in s:
        if ord(c) > 0x1100:      # 全角・CJK ≒ 19px
            w += 2
        elif c.isalnum():        # 欧文英数 ≒ 14.2px
            w += 1.5
        else:                    # 記号・空白 ≒ 7.6px
            w += 0.8
    return w


KATAKANA = lambda c: 0x30A0 <= ord(c) <= 0x30FF or c in "ー・"
KANJI = lambda c: 0x4E00 <= ord(c) <= 0x9FFF
ASCII_WORD = lambda c: c.isascii() and (c.isalnum() or c in "%$#@&=+-/.")
PUNCT_ONLY = "。、，：；／・）】＋"


def _units(s: str):
    """セルを「ここで折ってはいけない最小単位」に分解する。

    カタカナ語・英数語・漢字の連なり・括弧でくくったまとまりは分割しない。
    ひらがなと記号は1文字ずつ（日本語の禁則に近い挙動）。
    """
    out, i, n = [], 0, len(s)
    while i < n:
        ch = s[i]
        if ch in "（(「【":
            close = {"（": "）", "(": ")", "「": "」", "【": "】"}[ch]
            j = s.find(close, i + 1)
            j = n - 1 if j == -1 else j
            inner = s[i + 1:j]
            # 括弧内も単語単位に分解し、開き括弧は直後の語に、閉じ括弧は直前の語に付ける。
            # （長い括弧書きを1単位にすると語中で機械的に切れてしまうため）
            sub = _units(inner)
            if not sub:
                out.append(s[i:j + 1])
            elif len(sub) == 1:
                out.append(ch + sub[0] + close)
            else:
                out.append(ch + sub[0])
                out.extend(sub[1:-1])
                out.append(sub[-1] + close)
            i = j + 1
        elif KATAKANA(ch):
            j = i
            while j < n and KATAKANA(s[j]):
                j += 1
            out.append(s[i:j])
            i = j
        elif KANJI(ch):
            j = i
            while j < n and KANJI(s[j]):
                j += 1
            out.append(s[i:j])
            i = j
        elif ASCII_WORD(ch):
            j = i
            while j < n and ASCII_WORD(s[j]):
                j += 1
            out.append(s[i:j])
            i = j
        else:
            out.append(ch)
            i += 1
    return [u for u in out if u]


def _split_unit(u: str, limit: int):
    """単位そのものが上限を超えるとき、空白優先で分割する。"""
    if " " in u.strip():
        for k in range(len(u) - 1, 0, -1):
            if u[k] == " " and disp_w(u[:k]) <= limit:
                return u[:k], u[k + 1:]
    head = ""
    for ch in u:
        if disp_w(head) + disp_w(ch) > limit:
            break
        head += ch
    if not head:
        head = u[:1]
    return head, u[len(head):]


def wrap_cell(s: str, limit: int):
    """表示幅 limit を超えないよう、語の途中で折らないようにセルを分割する。"""
    s = clip(s)
    if not s:
        return [""]

    lines, cur = [], ""
    for u in _units(s):
        if not cur.strip() and u == " ":        # 行頭の空白は捨てる
            continue
        if disp_w(cur) + disp_w(u) <= limit:
            cur += u
            continue
        if cur.strip():
            lines.append(cur.rstrip())
        cur = u.lstrip()
        while disp_w(cur) > limit:              # 単位自体が長すぎる場合
            head, rest = _split_unit(cur, limit)
            if not head:
                break
            lines.append(head.rstrip())
            cur = rest.lstrip()
    if cur.strip():
        lines.append(cur.rstrip())

    # 句読点だけの行は前の行に吸収する（「／」だけの行を作らない）
    fixed = []
    for ln in lines:
        if fixed and ln and all(c in PUNCT_ONLY for c in ln):
            fixed[-1] += ln
        else:
            fixed.append(ln)
    return fixed or [s]


def katex_table(headers, rows, widths, align=None):
    """note 用の KaTeX 表を組み立てる。rows の各セルは自動で折り返す。"""
    ncol = len(headers)
    spec = "|" + "|".join(align or ["l"] * ncol) + "|"
    L = [r"\newcommand{\arraystretch}{1.5}%", r"\begin{array}{" + spec + "}", r"\hline"]
    L.append(" & ".join(r"\text{" + esc(clip(h)) + "}" if h else r"\text{}" for h in headers) + r" \cr")
    for row in rows:
        L.append(r"\hline")
        chunks = [wrap_cell(row[i] if i < len(row) else "", widths[i]) for i in range(ncol)]
        for i in range(max(len(c) for c in chunks)):
            cells = []
            for j in range(ncol):
                t = chunks[j][i] if i < len(chunks[j]) else ""
                cells.append(r"\text{" + esc(t) + r"}" if t else r"\text{}")
            L.append(" & ".join(cells) + r" \cr")
    L.append(r"\hline")
    L.append(r"\end{array}")
    return "$$\n" + "\n".join(L) + "\n$$"


# ---------------------------------------------------------------- バッジ判定

def llm_kind(cell: str):
    t = clip(cell)
    if "BYOK" in t or "プロバイダ" in t or "任意" in t or "Ollama" in t or "数百モデル" in t:
        return "BYOK（自前キー）"
    if "マルチ" in t or "複数モデル" in t or "選択可" in t:
        return "マルチモデル"
    return "単一プロバイダ"


# ---------------------------------------------------------------- 組み立て

def product_block(head, cells):
    """1製品を「項目／内容」の2列 KaTeX 表にする。"""
    rows = [[head[i + 1], cells[i + 1]] for i in range(len(head) - 1)]
    return katex_table(["項目", "内容"], rows, W_DETAIL)


def main():
    text = SRC.read_text(encoding="utf-8")
    secs = parse_sections(text)

    idx = find_table(secs, "0. まず結論", "カテゴリ")
    a = find_table(secs, "A. 汎用", "Meta Muse")
    b = find_table(secs, "B. コーディング", "Claude Code")
    c = find_table(secs, "C. エンタープライズ", "Copilot Studio")
    adopt = find_table(secs, "普及度合い", "指標")
    llm = find_table(secs, "使用できるLLM", "タイプ")

    sec4 = find_text(secs, "4. 選び方の判定フロー")
    sec5 = find_text(secs, "5. 導入前に確認")
    sec_src = find_text(secs, "参考ソース")

    n_prod = (len(a) - 1) + (len(b) - 1) + (len(c) - 1)

    P = []
    A = P.append

    A("# AIエージェント製品 比較表【2026年11月版】")
    A("")
    A(f"2026年11月2日時点で公開されている **AIエージェント製品{n_prod}件**を、"
      "「提供会社・使用できるLLM・価格・特徴・普及度合い」で横並びに比較しました。")
    A("")
    A("「AIエージェント」という言葉には、性格の違う3つの市場が混ざっています。"
      "同じ表に並べても選べないので、**出来合いを使う型／開発する型／基盤を作る型**の3カテゴリに分けています。")
    A("")
    A("> 価格はすべてUSD・月額です（特に断りがない限り）。料金と提供条件は改定が速い領域なので、"
      "導入前に各社の公式ページで最終確認してください。")
    A("")

    # ---- 結論
    A("## 結論：まず3カテゴリに分ける")
    A("")
    cat_rows = [[r[0], r[1], r[3]] for r in idx[1:]]
    A(katex_table(["カテゴリ", "何を買うか", "価格の性質"], cat_rows, W_CAT))
    A("")
    A("代表製品は次のとおりです。")
    A("")
    for r in idx[1:]:
        A(f"- **{clip(r[0])}**：{clip(r[2])}")
    A("")

    # ---- カテゴリ別
    cat_meta = [
        ("A", "汎用パーソナル／業務エージェント", a, "consumer"),
        ("B", "コーディングエージェント", b, "coding"),
        ("C", "エンタープライズ基盤・業務特化エージェント", c, "enterprise"),
    ]
    for num, label, rows, _ in cat_meta:
        head, body = rows[0], rows[1:]
        A(f"## {num}. {label}（{len(body)}製品）")
        A("")
        A("### ひと目で比較")
        A("")
        index_rows = [[d[0], d[1], llm_kind(d[2])] for d in body]
        A(katex_table(["製品", "提供会社", "LLMの選択"], index_rows, W_INDEX))
        A("")
        A("### 各製品の詳細")
        A("")
        for cells in body:
            A(f"#### {clip(cells[0])}")
            A("")
            A(product_block(head, cells))
            A("")

    # ---- 普及度
    A("## 普及度合い：市場全体の数字（2026年10〜11月時点）")
    A("")
    A("同じ「導入率」でも、調査主体によって数字はこれだけ違います。**どの数字も口径（カウントの定義）が違う**点に注意してください。")
    A("")
    stat_rows = [[r[0], f"{clip(r[1])}／{clip(r[2])}"] for r in adopt[1:]]
    A(katex_table(["指標", "数値／出典"], stat_rows, W_STAT))
    A("")
    A("**読み方**：「導入している」と「スケールしている」の間には大きな裂け目があります。"
      "95.3%（IDC）と17%（Gartner）の差は、前者が「1つでも動いている」、"
      "後者が「組織として配備した」を数えているためで、**両方が同時に正しい数字**です。")
    A("")

    # ---- LLMの見方
    A("## 「使用できるLLM」列の見方")
    A("")
    A("同じ機能でも、**モデルを選べるかどうか**で意味が変わります。ここが最大の実務差です。")
    A("")
    A(katex_table(["タイプ", "該当製品", "実務上の意味"],
                  [[r[0], r[1], r[2]] for r in llm[1:]], W_LLM))
    A("")
    A("**2026年の変化**：大企業の調達基準が「どのモデルか」から「どれだけ統制できるか」に移りました。"
      "Anthropicの Agent Skills が Linux Foundation の Agentic AI Foundation（AAIF）に寄贈され、"
      "OpenAIの Open Responses、Hugging Faceの OpenEnv なども同時期に中立化。"
      "エージェントを「バージョン管理・評価・ロールバックできる殻」に収める競争が本線です。")
    A("")

    # ---- 判定フロー
    A("## 選び方の判定フロー")
    A("")
    A("上から順に判定してください。1つでも該当したら、そこで候補は絞られます。")
    A("")
    for i, it in enumerate(re.findall(r"^\d+\.\s+(.*)$", sec4, re.M), 1):
        A(f"{i}. {it.replace('**', '**')}")
    A("")

    # ---- 注意点
    A("## 導入前に確認すべき注意点")
    A("")
    for it in re.findall(r"^-\s+(.*)$", sec5, re.M):
        A(f"- {it}")
    A("")

    # ---- 出典
    A("## 参考ソース")
    A("")
    for it in re.findall(r"^-\s+(.*)$", sec_src, re.M):
        chunks = re.split(r"\s*／\s*", it)
        links = []
        for ch in chunks:
            if ": http" in ch:
                label, url = ch.split(": http", 1)
                links.append(f"[{label.strip()}](http{url.strip()})")
            else:
                links.append(ch)
        A(f"- {' ／ '.join(links)}")
    A("")
    A("---")
    A("")
    A("本記事は公開情報の要約です。価格はUSD・月額（特に断りがない限り）で、"
      "税・従量課金・年間契約割引は含みません。数値の口径は出典ごとに異なります。")

    doc = "\n".join(P)

    # 本文テキスト中の半角 $ は note の Markdown 層で数式扱いされ得るため全角化する
    # （$$ の区切り行だけはそのまま残す）
    doc = "\n".join(l if l.strip() == "$$" else l.replace("$", "＄") for l in doc.split("\n"))
    OUT.write_text(doc, encoding="utf-8")

    # ---- note 事前チェック：Markdown層で壊れる記法が残っていないか
    md_tables = len(re.findall(r"^\|.*\|\s*$", doc, re.M))
    blk = re.findall(r"\$\$(.*?)\$\$", doc, re.S)
    bad_esc = {e: sum(b.count(e) for b in blk) for e in ("\\$", "\\&", "\\%")}
    inner = re.findall(r"\\text\{([^{}]*)\}", "\n".join(blk))
    risky = {c: sum(t.count(c) for t in inner) for c in "$&%"}
    parity_bad = sum(1 for b in blk for l in b.split("\n") if l.count("$") % 2 == 1)
    asym = [i for i, b in enumerate(blk)
            if b.count(r"\begin{array}") != b.count(r"\end{array}")]

    print(f"OK: {OUT.name} を生成")
    print(f"  製品ブロック={n_prod}  カテゴリ={len(cat_meta)}")
    print(f"  残存マークダウン表の行数={md_tables}（0であるべき）")
    print(f"  KaTeXブロック数={len(blk)}")
    print(f"  行数={len(doc.splitlines())}")
    print(f"  array環境が不整合なブロック={asym}")
    print("  --- note事前チェック ---")
    print(f"  エスケープ \\$ \\& \\% の残存={bad_esc}（すべて0であるべき）")
    print(f"  \\text{{}} 内の半角 $ & % の残存={risky}（すべて0であるべき）")
    print(f"  $ が奇数個の行={parity_bad}（0であるべき）")
    ok = (md_tables == 0 and not asym and not any(bad_esc.values())
          and not any(risky.values()) and parity_bad == 0)
    print(f"  判定: {'PASS — noteにそのまま貼り付け可能' if ok else 'FAIL — 修正が必要'}")


if __name__ == "__main__":
    main()
