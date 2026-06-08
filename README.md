# sbgy-data-tools

Python tools for integrating SBGY, Guangyun CSV, SGY fanqie data, and KRM/DHSJR pronunciation annotations.

`sbgy-data-tools` は、宋本廣韻 `sbgy.xml`、`廣韻.csv`、`SGY_fanqie.csv`、KRM/DHSJR 音注データをつなぎ、漢字ごとの音韻情報・釋義・校勘注・日本漢字音資料の声点情報を横断的に扱うための Python ツール群です。

MIT License での公開を想定しています。

## 動作環境

- Python 3.9 以上
- 現行の `scripts/` 直下の Python スクリプトは標準ライブラリのみで動作します。
- 外部ライブラリは不要です。将来、外部ライブラリを使う補助スクリプトを追加する場合は `requirements.txt` を用意してください。

## 使用するデータ

このツール群の基本処理では、以下の公開データを使用します。各データはライセンス・利用条件を確認したうえで取得してください。

| ファイル | 概要 | 入手元 |
|---|---|---|
| `sbgy.xml` | Kanji Database Project が公開する宋本廣韻の XML データ。廣韻の親字 25,551 字を収録し、各反切グループ `voice_part` に IPA 再構音、例: `tuŋ˥˩`、と日本語音読みが付与されています。 | https://github.com/cjkvi/cjkvi-dict |
| `廣韻.csv` | nk2028 プロジェクトが公開する廣韻音韻データベース。25,336 行のデータに、音韻地位、例: `端一東平`、と釋義が整備されています。 | https://github.com/nk2028/tshet-uinh-data |
| `宋本廣韻データ.html` | `sbgy.xml` のデータ仕様を解説した HTML ページ。声母・韻母・声調と IPA の対応表が掲載されており、データ処理の設計仕様書として参照します。 | https://kanji-database.sourceforge.net/dict/sbgy/index.html |

加えて、統合精度を高めるために次のデータを使用できます。

| ファイル | 概要 |
|---|---|
| `SGY_fanqie.csv` | 廣韻小韻首字について、三十六字母体系の声母、攝開合等、清濁、反切校勘注などを整理した研究用データ。 |
| KRM/DHSJR 音注 TSV または JSON | 観智院本類聚名義抄などの音注データ。声点、仮名注、類音注、反切注などを含む形式を想定します。 |

配置例:

```text
data/input/
  SGY_fanqie.csv
  廣韻.csv
  宋本廣韻データ.html

sbgy.xml  # 任意の場所に置き、実行時に --sbgy で指定
```

`sbgy.xml` はサイズや配布条件の都合により、リポジトリに同梱せず、利用者が別途取得してパスを指定する運用を想定しています。

## 主要フロー

### 1. 基礎データの統合

```text
[sbgy.xml] + [SGY_fanqie.csv] + [廣韻.csv]
   ↓ sbgy_integrate.py
data/output/sbgy_integrated.json
```

`sbgy_integrated.json` は、このツール群の中心となる統合 JSON です。漢字ごとに、SBGY 由来の IPA・声母・韻母・声調、SGY 由来の校勘情報、廣韻.csv 由来の音韻地位・釋義を持ちます。

### 2. KRM/DHSJR 音注との結合

```text
[sbgy_integrated.json] + [KRM/DHSJR 音注データ]
   ↓ sbgy_krm_join.py
data/output/sbgy_krm_joined.json
```

KRM 音注の見出し字、声点、仮名注、類音注を、廣韻側の音韻候補と結びます。

### 3. 特定の音韻分析・集計

```text
[sbgy_krm_joined.json]
   ↓ analyze_shang_zhuodu.py
shang_zhuodu*.tsv
```

上声全濁字が KRM 側でどの声点・照合状態として現れるかを分析する TSV 群を作ります。

### 4. DHSJR/KRM TSV と廣韻.csv の直接接続

```text
[DHSJR/KRM TSV] + [廣韻.csv] + [SGY_fanqie.csv]
   ↓ gy_dhsjr_link.py
*_gy_linked.tsv
dhsjr_gy_unmatched.tsv
dhsjr_gy_multi.tsv
```

JSON 統合フローとは別に、DHSJR/KRM 形式の TSV に廣韻音韻情報を直接付与できます。

## スクリプト一覧


| ファイル | 重要度 | 概要 |
|---|---|---|
| `sbgy_integrate.py` | **高** | `sbgy.xml`、`SGY_fanqie.csv`、`廣韻.csv` を統合し、`sbgy_integrated.json` を生成するメインスクリプト。 |
| `sbgy_parse.py` | 中 | `sbgy.xml` 単独解析用。IPA から声母・韻母・声調・攝・等・開合を導出し、`sbgy_dict.json` を生成する。 |
| `sbgy_krm_join.py` | **高** | `sbgy_integrated.json` と KRM 音注データ TSV/JSON を結合し、`sbgy_krm_joined.json` を生成する。 |
| `analyze_shang_zhuodu.py` | **高** | `sbgy_krm_joined.json` から上声全濁字関連の候補を抽出・展開し、分析用 TSV 群を生成する。 |
| `gy_dhsjr_link.py` | **高** | DHSJR/KRM 形式の TSV の見出し字を `廣韻.csv` に接続し、GY 音韻地位、清濁、攝、声調、漢音・呉音予測形などを付与する。 |
| `dhsjr_summary.py` | 中 | DHSJR TSV の資料別サマリーを作成する。行数、声点分布、仮名注分布、全濁声点付き仮名注などを集計する。 |
| `list_no_gy_char.py` | 低 | `sbgy_integrated.json` から `unmatched_no_gy_char` を抽出して CSV 化する補助スクリプト。 |

## 各スクリプト

### `sbgy_integrate.py`

`sbgy.xml`、`SGY_fanqie.csv`、`廣韻.csv` の 3 データを統合します。

主な処理:

- `sbgy.xml` の `voice_part/@ipa` を解析し、声母・韻母・声調・攝・等・開合を導出する。
- SGY の首字データを `word_id` で付与する。
- 廣韻.csv の音韻地位・小韻番号・釋義を、反切照合、音韻地位照合、フォールバック照合で結合する。
- `match_status` により、照合成功・未照合理由を分類する。

実行例:

```bash
python3 scripts/sbgy_integrate.py \
  --sbgy sbgy.xml \
  --sgy data/input/SGY_fanqie.csv \
  --gy data/input/廣韻.csv \
  --output data/output/sbgy_integrated.json \
  --pretty
```

主な出力:

- `data/output/sbgy_integrated.json`

備考:

- `sbgy_integrate.py` は `sbgy_dict.json` を読まず、`sbgy.xml` を直接解析します。
- `match_status` は `matched`、`unmatched_no_gy_char`、`unmatched` を出力します。
- 照合ロジックを変更した場合は、総エントリ数や `match_status` 分布を確認してください。

### `sbgy_parse.py`

`sbgy.xml` 単独から、漢字ごとの IPA・声母・韻母・声調情報を JSON 化します。

用途:

- IPA 解析テーブルの動作確認
- `sbgy.xml` 単独の音韻情報確認
- 統合前の中間データ作成

実行例:

```bash
python3 scripts/sbgy_parse.py \
  --input sbgy.xml \
  --output data/output/sbgy_dict.json \
  --pretty
```

主な出力:

- `data/output/sbgy_dict.json`

### `sbgy_krm_join.py`

`sbgy_integrated.json` と KRM 音注データを結合します。

主な処理:

- KRM 音注 TSV または JSON を読み込む。
- `character_headword` をもとに SBGY/GY 候補を取得する。
- `remarks_pronunciation == "音注字"` の行は `annotation_char` として記録し、見出し字照合から除外する。
- KRM 声点 `tone_marks` から廣韻声調候補を推定する。
- 反切、仮名注、声調候補を使って候補を絞り込む。
- `join_status` を `matched_1`、`matched_n`、`ambiguous`、`no_sbgy_char`、`annotation_char` に分類する。

実行例:

```bash
python3 scripts/sbgy_krm_join.py \
  --sbgy data/output/sbgy_integrated.json \
  --krm path/to/krm_pronunciations.tsv \
  --output data/output/sbgy_krm_joined.json \
  --pretty
```

主な出力:

- `data/output/sbgy_krm_joined.json`

備考:

- KRM の声点は日本漢字音側の声調であり、廣韻声調と常に一致するわけではありません。
- `去` は入声転訛も考慮して `去声`・`入声` の両候補にするなど、声調変換表を内蔵しています。

### `analyze_shang_zhuodu.py`

`sbgy_krm_joined.json` から、廣韻上声全濁字と KRM 音注の関係を分析する TSV を生成します。

対象:

- 廣韻で `上声` かつ全濁声母の候補
- `join_status` が `matched_1`、`matched_n`、`ambiguous` の KRM 音注
- 必要に応じて、呉音・和音の明記があるエントリを `--exclude-goon` で除外

実行例:

```bash
python3 scripts/analyze_shang_zhuodu.py \
  --joined data/output/sbgy_krm_joined.json \
  --outdir data/output/shang_zhuodu_exclude_goon \
  --exclude-goon
```

主な出力:

- `shang_zhuodu_candidates.tsv`
- `shang_zhuodu_tone_cross.tsv`
- `shang_zhuodu_by_shengmu.tsv`
- `shang_zhuodu_ambig_profile.tsv`

備考:

- `is_goon` は `similar_sound` の文字列パターンで自動判定します。
- 個別例の解釈では、KRM 原文・類音注・仮名注を確認してください。

### `gy_dhsjr_link.py`

DHSJR/KRM 形式の TSV と `廣韻.csv` を接続します。

主な処理:

- 入力 TSV の見出し字列を `廣韻.csv` の字頭に照合する。
- 複数音字は、指定された声点列があれば声調で絞り込む。
- GY の声母・清濁・等・開合・重紐・韻・攝・声調を付与する。出力列名では `GY_摂` を使用する。
- 高松・沼本表に基づく漢音行・呉音行・韻母形を付与する。
- SGY を指定した場合、SGY の声母・清濁・攝開合等・反切も付与する。
- 異体字 TSV/JSON を指定した場合、正規化前の字形を `GY_正規化前` に記録する。

単一ファイルの実行例:

```bash
python3 scripts/gy_dhsjr_link.py \
  --dhsjr path/to/krm_pronunciations.tsv \
  --gy data/input/廣韻.csv \
  --sgy data/input/SGY_fanqie.csv \
  --outdir data/output/dhsjr_krm
```

ディレクトリ一括処理:

```bash
python3 scripts/gy_dhsjr_link.py \
  --dhsjr-dir path/to/DHSJR/data \
  --gy data/input/廣韻.csv \
  --outdir data/output/dhsjr_krm
```

主な出力:

- `<入力ファイル名>_gy_linked.tsv`
- `dhsjr_gy_unmatched.tsv`
- `dhsjr_gy_multi.tsv`

### `dhsjr_summary.py`

DHSJR TSV の資料性格を把握するためのサマリーを作成します。

主な集計:

- 行数
- 仮名注あり行数
- 声点あり行数
- 声点型の分布
- 仮名注の分布
- 全濁声点の仮名注一覧
- 仮名注の語頭モーラ別集計

単一ファイルの実行例:

```bash
python3 scripts/dhsjr_summary.py path/to/30-001-01.tsv
```

ディレクトリ一括処理:

```bash
python3 scripts/dhsjr_summary.py \
  --dir path/to/DHSJR/data \
  --format tsv \
  --outdir data/output/dhsjr_summary
```

基本統計のみ出力:

```bash
python3 scripts/dhsjr_summary.py \
  path/to/30-001-01.tsv \
  --basic-only
```

出力:

- `--outdir` なしの場合は標準出力
- `--format text` の場合は `<入力ファイル名>_summary.txt`
- `--format tsv` の場合は `dhsjr_summary_all.tsv`
- `--format json` の場合は `dhsjr_summary_all.json`

### `list_no_gy_char.py`

`sbgy_integrated.json` から、`match_status == "unmatched_no_gy_char"` のエントリを CSV に出力します。

実行例:

```bash
python3 scripts/list_no_gy_char.py \
  --input data/output/sbgy_integrated.json \
  --output data/output/unmatched_no_gy_char.csv
```

出力列:

- `hanzi`
- `fanqie`
- `yunmu`
- `shengdiao`
- `shengmu`
- `deng`
- `word_id`
- `onyomi`
- `is_head`
- `volume`
- `rhyme_id`

## 入出力の基本方針

- 入力 CSV/TSV/JSON/XML は UTF-8 を前提とします。
- CSV/TSV 出力は UTF-8、改行処理は Python の `newline=""` を使います。
- `data/input/` と `data/reference/` は元データ置き場です。変換結果や分析結果は `data/output/` に出力してください。
- 公開時にデータファイルを同梱しない場合は、取得元・配置場所・ファイル名を README に明記してください。

## ライセンス

スクリプト本体は MIT License での公開を想定しています。

ただし、入力データにはそれぞれ別のライセンス・利用条件があります。`sbgy.xml`、`廣韻.csv`、KRM/DHSJR 音注データ、SGY_fanqie.csv などを再配布する場合は、各データの出典と条件を個別に確認してください。
