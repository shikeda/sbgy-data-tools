# scripts/

SBGY・廣韻・SGY・KRM/DHSJR 音注データを処理する Python スクリプト。Python 3.9 以上、標準ライブラリのみで動作します（`investigate_itaiji_v2.py` のみ pandas が必要）。

## GY × DHSJR 接続

### `gy_dhsjr_link.py`

DHSJR/KRM 形式 TSV の見出し字を `廣韻.csv` に接続し、音韻地位・清濁・攝・声調・漢音/呉音の概略形などを付与します。

```bash
python3 scripts/gy_dhsjr_link.py \
  --dhsjr path/to/target.tsv \
  --gy data/input/廣韻.csv \
  --outdir data/output/dhsjr_krm

# 異体字テーブル・JSON を使う場合
python3 scripts/gy_dhsjr_link.py \
  --dhsjr path/to/target.tsv \
  --gy data/input/廣韻.csv \
  --itaiji data/input/異体漢字対応テーブル111220版_TSV221111.txt \
  --itaiji-json scripts/itaiji_gy_compare.json \
  --outdir data/output/dhsjr_krm
```

`GY_漢音韻母形` / `GY_呉音韻母形` は概略的な候補形です。入声字は `GY_声調=入` と `GY_韻目原貌` を確認し、適宜読み替えてください。

## 廣韻.csv × sbgy.xml 比較

### `compare_guangyun_sbgy.py`

`廣韻.csv` と `sbgy.xml` を韻内の出現位置で照合し、同位置にあるはずなのにコードポイントが異なる字頭を抽出します。補字行（小韻字號 `1a1` 等）は廣韻側からスキップして字数を揃えます。

```bash
cd scripts/
python3 compare_guangyun_sbgy.py
# → ./mismatched_count_report.tsv  (字数不一致の韻)
# → ./char_mismatch_report.tsv     (コードポイント相違の字頭一覧)
```

入力パスはスクリプト先頭の `GY_CSV`・`SBGY_XML`・`OUT_DIR` で変更してください（デフォルト: `../廣韻.csv`、`../sbgy.xml`、カレントディレクトリ）。

## 未照合字の分析

### `check_blocks.py`

廣韻未照合字 TSV の先頭文字を Unicode ブロック（CJK統合漢字・拡張A〜I・IDC 等）で分類し、`ブロック` 列を追加した TSV を標準出力します。

```bash
python3 scripts/check_blocks.py dhsjr_gy_unmatched.tsv > dhsjr_gy_unmatched.blocks.tsv
```

### `summarize_gy_unmatched_blocks.py`

`dhsjr_gy_unmatched.blocks.tsv` をブロック別に集計し、件数・割合・ユニーク文字数・例字を含む Markdown レポートを生成します。

```bash
python3 scripts/summarize_gy_unmatched_blocks.py \
  --tsv dhsjr_gy_unmatched.blocks.tsv \
  --out dhsjr_gy_unmatched.blocks_集計.md
```

### `list_no_gy_char.py`

廣韻.csv に字頭自体が存在しない字（`GY_マッチ状況=未収録`）を CSV に出力します。

```bash
python3 scripts/list_no_gy_char.py --input sbgy_integrated.json --output no_gy_char.csv
```

## 異体字調査・ペア生成

### `investigate_itaiji_v2.py`

廣韻未照合字を NIHU 異体字対応テーブルと外部 JSON と照合し、収録状況を type 1〜5 に分類します（pandas を使用）。

```bash
cd scripts/
python3 investigate_itaiji_v2.py
# unmatch.md がスクリプトと同ディレクトリに必要
# → result_type{1-5}.txt, itaiji_log.tsv
```

### `export_type5_as_tsv.py`

`investigate_itaiji_v2.py` の結果から type5（いずれかのデータに収録）を TSV 形式で出力します。

```bash
cd scripts/
python3 export_type5_as_tsv.py
```

### `extract_itaiji_from_notes.py`

`krm_notes.tsv` の校勘注（「◯と同字」「◯の俗字」等のパターン）から異体字ペアを抽出し、`--itaiji-json` 用 JSON を生成します。

```bash
python3 scripts/extract_itaiji_from_notes.py \
  --notes path/to/krm_notes.tsv \
  --out 独自異体字.json
```

### `make_itaiji_json.py`

`dhsjr_gy_unmatched.itaiji.tsv` の Class（C1/C2）に従って `(c1, c2)` ペアを整理し、`--itaiji-json` 用 JSON を生成します。

```bash
cd scripts/
python3 make_itaiji_json.py
# → itaiji_krm_20260626.json
```

### `make_itaiji_from_compare_gy.py`

`compare_guangyun_sbgy.py` が生成した `char_mismatch_report.tsv` を読み込み、廣韻.csv と sbgy.xml のコードポイント差異から `--itaiji-json` 用ペアリスト JSON を生成します。

```bash
python3 scripts/make_itaiji_from_compare_gy.py \
  --input char_mismatch_report.tsv \
  --out itaiji_gy_compare.json

# 単純な字体差のみ
python3 scripts/make_itaiji_from_compare_gy.py --only-simple --out itaiji_gy_simple.json

# 本字部分も不一致（要確認）も含める
python3 scripts/make_itaiji_from_compare_gy.py --include-uncertain --out itaiji_gy_all.json
```

## SBGY 統合・分析

### `sbgy_parse.py`

`sbgy.xml` を解析し、各漢字の声母・韻母・声調・攝・韻・等・開合・反切・音読みなどを含む JSON 辞書を生成します。

```bash
python3 scripts/sbgy_parse.py --input sbgy.xml --output sbgy_dict.json
```

### `sbgy_integrate.py`

`sbgy.xml`・`SGY_fanqie.csv`・`廣韻.csv` の 3 データを統合し、各漢字エントリに IPA・音韻地位・三十六字母・釋義等を付与した JSON を生成します。

```bash
python3 scripts/sbgy_integrate.py \
  --sbgy sbgy.xml \
  --sgy SGY_fanqie.csv \
  --gy 廣韻.csv \
  --output sbgy_integrated.json
```

### `sbgy_krm_join.py`

`sbgy_integrated.json` と KRM 音注 TSV を結合し、各 KRM エントリに対応する廣韻の音韻情報を付与します。

```bash
python3 scripts/sbgy_krm_join.py \
  --sbgy sbgy_integrated.json \
  --krm krm_pronunciations.tsv \
  --output sbgy_krm_joined.json
```

### `dhsjr_summary.py`

DHSJR TSV 資料の基本統計・声点型分布・仮名注分布・全濁声点の仮名注一覧を集計します。

```bash
python3 scripts/dhsjr_summary.py path/to/target.tsv
```

### `analyze_shang_zhuodu.py`

`sbgy_krm_joined.json` から上声全濁字に関連するエントリを抽出・展開し、KRM 側の声点・照合状態を分析するための 4 種の TSV を生成します。

```bash
python3 scripts/analyze_shang_zhuodu.py \
  --joined sbgy_krm_joined.json \
  --outdir data/output/shang_zhuodu
```
