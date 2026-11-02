# サンプル：ツールの入出力例

このファイルは `build_note.py` の入力サンプルです。表だけが KaTeX に変換され、
見出しや段落はそのまま残ります。

## 一覧表（短いセルだけで作る）

$$
\newcommand{\arraystretch}{1.5}%
\begin{array}{|l|l|l|}
\hline
\text{製品} & \text{提供会社} & \text{月額} \cr
\hline
\text{Claude Code} & \text{Anthropic} & \text{＄20〜} \cr
\hline
\text{GitHub Copilot} & \text{GitHub} & \text{＄10〜} \cr
\hline
\text{Cursor} & \text{Cursor} & \text{＄20〜} \cr
\hline
\end{array}
$$

## 詳細（2列にすると折り返しても読める）

$$
\newcommand{\arraystretch}{1.5}%
\begin{array}{|l|l|}
\hline
\text{項目} & \text{内容} \cr
\hline
\text{提供会社} & \text{Anthropic} \cr
\hline
\text{使用できるLLM} & \text{Claude のみ（Amazon Bedrock /} \cr
\text{} & \text{Google Cloud Vertex AI 経由も} \cr
\text{} & \text{可）} \cr
\hline
\text{価格} & \text{Pro ＄20（年払 ＄17）、Max ＄} \cr
\text{} & \text{100〜、Team ＄20〜25／席、API} \cr
\text{} & \text{従量} \cr
\hline
\text{特徴} & \text{ターミナル常駐＋モバイル。} \cr
\text{} & \text{リポジトリ横断の変更とテスト実行がで} \cr
\text{} & \text{きる。}\to\text{ 手順書をテキストで渡す運用} \cr
\text{} & \text{に強い} \cr
\hline
\end{array}
$$

## 統計（％ や ＆ を含む表）

$$
\newcommand{\arraystretch}{1.5}%
\begin{array}{|l|l|l|}
\hline
\text{指標} & \text{数値} & \text{出典} \cr
\hline
\text{本番稼働している企業} & \text{95.3％} & \text{IDC} \cr
\hline
\text{組織として配備した割合} & \text{17％} & \text{Gartner} \cr
\hline
\text{改善率（A ＆ B の比較）} & \text{+77.3％} & \text{Gartner} \cr
\hline
\end{array}
$$

> 半角の `＄` `&` `%` は自動で全角（＄ ＆ ％）に置き換わります。
> これは note の Markdown 層が `\＄` `\&` `\%` のバックスラッシュを削除してしまい、
> 数式が壊れて**表が生のLaTeXソースのまま表示される**ためです。
