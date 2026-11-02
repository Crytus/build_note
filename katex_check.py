#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""katex_check — note の KaTeX ブロックをブラウザで事前検証する HTML を生成する。

note は KaTeX のレンダリングに失敗したブロックを **無言で生テキスト表示** にする。
貼り付けてから気づくのを防ぐため、先にブラウザで例外の有無と幅を確かめる。

このページが再現していること:
  1. note の Markdown 層の変換（``\$`` ``\&`` ``\%`` のバックスラッシュ削除）
  2. その変換後テキストを KaTeX に throwOnError:true で渡す
  3. 描画できたブロックの実幅を測る（note の本文幅 ≒ 580px）

使い方:
    python katex_check.py output_note.md -o check.html   # 単体で使う
    python build_note.py input.md --check check.html     # 変換と同時に作る

生成した HTML をブラウザで開くと ``window.__r`` に結果が入る:

    { nblocks, rendered, errors[], warnChars{}, maxWidth, over580[], transformDiff[], ok }

``ok: true`` が合格条件（全ブロック描画・エラー0・580px以内・noteの変換で内容が変わらない）。
"""

import argparse
import json
import re
from pathlib import Path

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>note KaTeX check</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css"
      integrity="sha384-nB0miv6/jRmo5UMMR1wu3Gz6NLsoTkbqJghGIsx//Rlm+ZU03BU6SQNC66uf4l5+" crossorigin="anonymous">
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"
        integrity="sha384-7zkQWkzuo3B5mTepMUcHkMB5jZaolc2xDwL6VFqjFALcbeS9Ggm/Yr2r3Dy4lfFg" crossorigin="anonymous"></script>
<style>
  body { font-family: system-ui, sans-serif; margin: 16px; }
  #log { font-family: ui-monospace, monospace; font-size: 13px; white-space: pre-wrap;
         padding: 10px; border: 1px solid #ccc; border-radius: 6px; margin-bottom: 16px; }
  .ok   { background: #e7f6ec; border-color: #2f9e44 !important; }
  .fail { background: #fdecec; border-color: #e03131 !important; }
  #out { display: flex; flex-direction: column; align-items: flex-start; }
  .blk { width: max-content; margin: 6px 0; }
  .blk.over { outline: 2px solid #e03131; }
</style>
</head>
<body>
<div id="log">loading…</div>
<div id="out"></div>
<script>
const RAW = __PAYLOAD__;                 // 変換直後の KaTeX ブロック
// note の Markdown 層と同じ変換（バックスラッシュ付きの \$ \& \% からバックスラッシュを落とす）
const BLOCKS = RAW.map(t => t.split('\\$').join('$').split('\\&').join('&').split('\\%').join('%'));
const TRANSFORM_DIFF = RAW.map((t, i) => t === BLOCKS[i] ? -1 : i).filter(i => i >= 0);
window.__r = null;

window.addEventListener('load', () => {
  const out = document.getElementById('out');
  const res = { nblocks: BLOCKS.length, rendered: 0, errors: [], warnChars: {},
                maxWidth: 0, over580: [], transformDiff: TRANSFORM_DIFF };

  BLOCKS.forEach((tex, i) => {
    const d = document.createElement('div');
    d.className = 'blk';
    out.appendChild(d);
    try {
      katex.render(tex, d, {
        displayMode: true,
        throwOnError: true,
        strict: (code, msg) => {
          const ch = (String(msg).match(/character "(.+?)"/) || [])[1] || String(msg);
          res.warnChars[ch] = (res.warnChars[ch] || 0) + 1;
          return 'ignore';
        }
      });
      res.rendered++;
      const w = Math.round(d.getBoundingClientRect().width);
      if (w > res.maxWidth) res.maxWidth = w;
      if (w > 580) { res.over580.push([i, w]); d.classList.add('over'); }
    } catch (e) {
      res.errors.push([i, String(e.message).slice(0, 140)]);
    }
  });

  res.ok = (res.rendered === res.nblocks && res.errors.length === 0 &&
            res.over580.length === 0 && res.transformDiff.length === 0);

  window.__r = res;
  const log = document.getElementById('log');
  log.className = res.ok ? 'ok' : 'fail';
  log.textContent = (res.ok ? 'PASS — note にそのまま貼り付け可能\n' : 'FAIL — 修正が必要\n')
                  + JSON.stringify(res, null, 1);
});
</script>
</body>
</html>
"""


def extract_blocks(md_text: str):
    """note 用 Markdown から ``$$ … $$`` のブロックを取り出す。"""
    return re.findall(r"\$\$(.*?)\$\$", md_text, re.S)


def build_html(md_text: str, blocks=None) -> str:
    """検証用 HTML を組み立てる（md_text から自動でブロックを抽出する）。"""
    blocks = extract_blocks(md_text) if blocks is None else blocks
    return HTML_TEMPLATE.replace("__PAYLOAD__", json.dumps(blocks, ensure_ascii=False))


def main(argv=None):
    ap = argparse.ArgumentParser(description="note の KaTeX ブロックを検証する HTML を作る")
    ap.add_argument("input", help="note用Markdown（$$ ブロックを含む）")
    ap.add_argument("-o", "--output", default="katex_check.html")
    a = ap.parse_args(argv)
    md = Path(a.input).read_text(encoding="utf-8")
    blocks = extract_blocks(md)
    Path(a.output).write_text(build_html(md, blocks), encoding="utf-8")
    print(f"OK: {a.output} を生成（KaTeXブロック {len(blocks)}個）")
    print("  ブラウザで開き、window.__r を読んでください（rendered/errors/maxWidth/transformDiff/ok）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
