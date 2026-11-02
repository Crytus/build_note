# build_note

[![test](https://github.com/Crytus/build_note/actions/workflows/test.yml/badge.svg)](https://github.com/Crytus/build_note/actions/workflows/test.yml)

Markdown ファイルを読み、**中の表だけを note.com 用の KaTeX 表に書き換えて出力**する小さなコマンドラインツールです。

note は Markdown のテーブル記法を描画しないため、表は `$$ … $$` で囲んだ KaTeX の `array` 環境で書く必要があります。手で書くと必ずと言っていいほど特定の落とし穴（[後述](#なぜ専用ツールが必要か)）で壊れるので、変換と**貼り付け前の検査**を自動化しました。

- 外部依存なし（Python 標準ライブラリのみ）
- 表以外の本文（見出し・段落・箇条書き・リンク）はそのまま通す
- 変換結果を機械的に検査し、note 側で生テキストになる記法が残っていないか確認する

```
$ python build_note.py article.md
入力: article.md
出力: article_note.md  （表 3個 → KaTeX 3ブロック）

  --- note 貼り付け前チェック ---
  KaTeXブロック数            : 3
  残ったMarkdown表の行数     : 0（0であるべき）
  エスケープ \$ \& \% の残存 : {'\\$': 0, '\\&': 0, '\\%': 0}（すべて0であるべき）
  \text{} 内の半角 $ & %    : {'$': 0, '&': 0, '%': 0}（すべて0であるべき）
  $ が奇数個の行があるブロック: []（0であるべき）
  array が不整合なブロック   : []（0であるべき）

  判定: PASS — note にそのまま貼り付け可能
```

---

## 必要環境

| 項目 | 内容 |
|---|---|
| Python | 3.9 以上（3.14 で動作確認） |
| 外部パッケージ | 不要（標準ライブラリのみ） |
| OS | Windows / macOS / Linux |
| ブラウザ検証を使う場合 | ブラウザとネット接続（KaTeX を CDN から読み込みます） |

## インストール

ダウンロードして展開するだけです。`pip install` は不要です。

```bash
git clone https://github.com/Crytus/build_note.git
cd build_note
```

`git` を使わない場合は、GitHub の「Code → Download ZIP」で取得して展開してください。

動作確認:

```bash
python build_note.py --version
# build_note 1.0.0
```

どのディレクトリからでも使いたい場合は、PATH の通った場所に置くかエイリアスを設定します。

```bash
# 例: ~/bin にシンボリックリンクを置く（macOS / Linux）
ln -s "$(pwd)/build_note.py" ~/bin/build_note
```

## 使い方

### 基本

```bash
python build_note.py article.md
```

`article.md` と同じ場所に `article_note.md` ができます。これを note の編集画面に貼り付けてください。

### 出力先を指定する

```bash
python build_note.py article.md -o out/article_note.md
```

### 貼り付け前にブラウザで検証する（推奨）

```bash
python build_note.py article.md --check check.html
```

生成された `check.html` をブラウザで開くと、**note と同じ変換を再現したうえで** KaTeX が描画され、結果が画面に表示されます。

- 緑の枠に `PASS` と出れば、note に貼っても表になります
- 赤の枠に `FAIL` と出たら、その表は note 上で生のLaTeXソースとして表示されます（理由も表示されます）
- 幅が 580px を超えた表は赤い枠線で強調されます（note の本文幅からはみ出します）

### 表の幅を調整する

```bash
python build_note.py article.md --budget 50
```

`--budget` は表の総幅を「単位」で指定します（全角1文字 = 2単位、note の本文幅 580px ≒ 60単位）。既定は 58 です。狭くすると折り返しが増えますが、はみ出しにくくなります。

### オプション一覧

| オプション | 説明 |
|---|---|
| `input` | 入力の Markdown ファイル（必須） |
| `-o, --output PATH` | 出力先。省略時は `<入力名>_note.md` |
| `--budget N` | 表全体の幅（単位）。既定 58 |
| `--check HTML` | ブラウザ検証用の HTML を出力 |
| `-q, --quiet` | レポートを表示しない（終了コードだけ見る用途） |
| `--version` | バージョン表示 |

### 終了コード

| コード | 意味 |
|---|---|
| `0` | 検査 PASS（note に貼り付け可能） |
| `1` | 検査 FAIL（note で生テキストになる。表示された項目を修正） |
| `2` | 入力ファイルが見つからない |

CI やシェルスクリプトから `python build_note.py article.md -q || echo "要修正"` のように使えます。

## 入出力の例

入力（`examples/example.md` の抜粋）:

```markdown
| 製品 | 提供会社 | 料金 |
|---|---|---|
| Claude Code | Anthropic | 月 $20 から |
| GitHub Copilot | GitHub（Microsoft） | 月 $10 から |
```

出力（`examples/example_note.md` の抜粋）:

```latex
$$
\newcommand{\arraystretch}{1.5}%
\begin{array}{|l|l|l|}
\hline
\text{製品} & \text{提供会社} & \text{料金} \cr
\hline
\text{Claude} & \text{Anthropic} & \text{月 ＄20 から} \cr
\text{Code} & \text{} & \text{} \cr
\hline
\text{GitHub} & \text{GitHub} & \text{月 ＄10 から} \cr
\text{Copilot} & \text{（Microsoft）} & \text{} \cr
\hline
\end{array}
$$
```

`examples/` に実際の入力と出力を置いてあります。

## なぜ専用ツールが必要か

note の KaTeX には、**エラーを出さずに壊れる**挙動がいくつかあります。このツールはそれを回避するために作っています。

### 1. note は `\$` `\&` `\%` のバックスラッシュを削除する

これが最大の罠です。TeX で `$` を出すには `\$` と書きますが、note は KaTeX に渡す前に Markdown 層を通し、**このバックスラッシュを落とします**。すると数式の中に素の `$` が現れ、KaTeX が解析エラーを起こし、note はそのブロックを**生のLaTeXソースのまま本文に表示**します（無言でフォールバックします）。

対策として、このツールは半角の `$ & %` を全角の `＄ ＆ ％` に置換します。全角なら Markdown も KaTeX も素通しします。

| 使ってはいけない | 代わりに使う | 起きること |
|---|---|---|
| `\$` | `＄` | 表が生テキストになる／記号が消える |
| `\&` | `＆` | 列区切りと解釈されてエラー |
| `\%` | `％` | TeX のコメント扱いで行が壊れる |
| `→` | `}\to\text{` | KaTeX に字形がなく警告（`\text{調査}\to\text{資料}`） |
| `€` | `EUR` | KaTeX に字形がない |

### 2. エラーにならない破損がある

`$` が同じ行に偶数個あると、KaTeX は「インライン数式」として解釈してしまい、**エラーを出さずに内容が変わります**（記号が消える、斜体になる）。そのため検査では「エラーが出たか」だけでなく、**note の変換で内容が変わるブロックがないか**も確認します（`transformDiff`）。

### 3. `array` は折り返さない

KaTeX の `array` はセル内で自動改行しません。長い文章を1つのセルに入れると、表が横に伸びて読めなくなります。このツールはセルを「語の途中で折らない」単位（カタカナ語・英数語・漢字の連なり・括弧書き）に分解し、列幅に収まるよう**複数行に積みます**。

### 4. ヘッダーも折り返さないと列幅を無視する

ヘッダー行だけを素通しにすると、長いヘッダー文字列が列の最小幅を決めてしまい、指定した幅を無視して表がはみ出します（実測 139px）。このツールはヘッダーも同じ列幅で折り返します。

### 5. 5列以上は本文幅に収まらない

note の本文幅は約 580px です。散文を含む 5〜6 列の表は物理的に収まらないため、ツールは警告を出します。

```
  ⚠ 幅が足りず語中で折った表が 2個あります（最大 6列）。
     5列以上、または長い説明文を含む表は note の本文幅（約580px）に収まりません。
     「一覧表は短いセルだけ」＋「長い説明は項目別の2列詳細表か箇条書き」に分割してください。
```

表を分割するのが正解です。一覧表は短いセルだけにし、長い説明は項目別の2列詳細表か箇条書きに逃がしてください。

## 制限事項

- 変換するのは**表だけ**です。見出し・段落・箇条書き・リンクはそのまま出力されます。
- セル内の `|` は全角の `｜` に置換します（Markdown の表を壊さないため）。
- セル結合・複数行セルなど、Markdown の表記法で表現できない表には対応しません。
- 幅の計算は近似です。最終的な判断は `--check` の実測値（`maxWidth`）を使ってください。
- note 側の仕様変更で挙動が変わる可能性があります。貼り付け後に**プレビューで全表が表になっているか**を目視で確認してください。

## 構成

```
build_note/
├── build_note.py          # エントリポイント（CLI）
├── note_katex.py          # 変換エンジン（Markdown → note用KaTeX）
├── katex_check.py         # ブラウザ検証用HTMLの生成
├── examples/
│   ├── example.md         # 入力サンプル
│   └── example_note.md    # 出力サンプル（このツールで生成）
├── tests/
│   └── test_note_katex.py # ユニットテスト（標準ライブラリのみ）
└── legacy/
    └── build_note_ai_agent.py  # 特定記事向けの旧スクリプト（参考・非推奨）
```

## 開発

```bash
# テスト
python -m unittest discover -s tests -v

# サンプルを変換して検証HTMLも作る
python build_note.py examples/example.md --check check.html
```

`note_katex.py` はライブラリとしても使えます。

```python
from note_katex import convert, preflight

doc, ntables, warnings = convert(open("article.md", encoding="utf-8").read())
assert preflight(doc)["ok"]
```

## 参考

- note で表を書く方法（KaTeX 記法の解説）: <https://note.com/masato_powerup/n/n1e28ba44cbab>
- KaTeX 対応コマンド一覧: <https://katex.org/docs/supported.html>

## ライセンス

MIT License. 詳細は [LICENSE](LICENSE) を参照してください。
