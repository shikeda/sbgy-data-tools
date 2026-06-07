# AGENTS.md — sbgy-data-tools

このリポジトリで作業するエージェント向けの実務メモです。まず `README.md` と必要に応じて `CLAUDE.md` を確認してください。

## プロジェクト概要

`sbgy-data-tools` は、宋本廣韻 `sbgy.xml`、`廣韻.csv`、`SGY_fanqie.csv`、KRM/DHSJR 音注データを統合・分析する Python スクリプト群です。漢字ごとの IPA、声母、韻母、声調、攝、等、開合、釋義、校勘注、日本漢字音資料の声点・仮名注を横断的に扱います。

スクリプト本体は MIT License 想定です。ただし入力データには個別のライセンス・利用条件があります。

## 環境

- Python 3.9 以上。
- 現行スクリプトは標準ライブラリのみで動作します。
- `requirements.txt` はありません。外部依存を追加する場合は、必要性を明確にし、依存ファイルも追加してください。
- ファイルは UTF-8 前提です。

## ディレクトリ構成

```text
scripts/              実行スクリプト
data/input/           入力データ置き場
data/output/          生成ファイル置き場
data/reference/       参照データ置き場
README.md             利用者向け説明
CLAUDE.md             既存のエージェント向け詳細メモ
```

`data/input/SGY_fanqie.csv` は同梱されています。`sbgy.xml`、`data/input/廣韻.csv`、`data/input/宋本廣韻データ.html` は利用者が各自取得する非同梱データです。これらをコミット対象として扱わないでください。

## 主要スクリプト

- `scripts/sbgy_integrate.py`: `sbgy.xml`、`SGY_fanqie.csv`、`廣韻.csv` を統合し、`data/output/sbgy_integrated.json` を生成します。
- `scripts/sbgy_parse.py`: `sbgy.xml` 単独を解析し、`sbgy_dict.json` を生成します。
- `scripts/sbgy_krm_join.py`: `sbgy_integrated.json` と KRM 音注 TSV/JSON を結合し、`sbgy_krm_joined.json` を生成します。
- `scripts/analyze_shang_zhuodu.py`: `sbgy_krm_joined.json` から上声全濁字関連の分析 TSV を生成します。
- `scripts/gy_dhsjr_link.py`: DHSJR/KRM TSV に廣韻音韻情報を直接付与します。
- `scripts/dhsjr_summary.py`: DHSJR TSV の資料別サマリーを出力します。
- `scripts/list_no_gy_char.py`: `sbgy_integrated.json` から廣韻未照合字を CSV 化します。

## よく使うコマンド

構文チェック:

```bash
python3 -m py_compile scripts/*.py
```

統合 JSON 生成:

```bash
python3 scripts/sbgy_integrate.py \
  --sbgy /path/to/sbgy.xml \
  --sgy data/input/SGY_fanqie.csv \
  --gy data/input/廣韻.csv \
  --output data/output/sbgy_integrated.json \
  --pretty
```

KRM/DHSJR TSV と廣韻.csv の直接接続:

```bash
python3 scripts/gy_dhsjr_link.py \
  --dhsjr path/to/target.tsv \
  --gy data/input/廣韻.csv \
  --sgy data/input/SGY_fanqie.csv \
  --outdir data/output/dhsjr_krm
```

DHSJR TSV サマリー:

```bash
python3 scripts/dhsjr_summary.py \
  --dir path/to/DHSJR/data \
  --format tsv \
  --outdir data/output/dhsjr_summary
```

## コーディング方針

- CLI は既存スクリプトに合わせて `argparse` を使ってください。
- パス処理は `pathlib.Path` を優先してください。
- CSV/TSV の読み書きでは `encoding="utf-8"` と `newline=""` を明示してください。
- JSON 出力では既存の `--pretty` 慣行を尊重してください。
- 音韻照合用の表や正規化表は、既存と同じくモジュールレベル定数として置く方針です。
- 処理後に件数や照合状態分布を標準出力へ表示する既存慣行があります。
- 研究データ処理なので、照合ロジックを変更した場合は総件数、ステータス分布、未照合件数を必ず確認してください。

## データと生成物の扱い

- 入力元データは `data/input/` または `data/reference/` に置きます。
- 変換・分析結果は `data/output/` に置きます。
- 非同梱データ、XML、大きな生成物、バックアップファイルを不用意に追加しないでください。
- `.gitignore` では `data/input/廣韻.csv`、`data/input/宋本廣韻データ.html`、`*.xml`、`*.bak`、Python キャッシュ類が除外されています。
- `SGY_fanqie.csv` は CC BY-SA 4.0 の研究用データです。再配布や派生物の扱いでは出典と条件を確認してください。

## 検証

最低限、Python ファイルを変更したら次を実行してください。

```bash
python3 -m py_compile scripts/*.py
```

入力データが揃っている場合は、変更したスクリプトの代表コマンドを実行し、出力件数や `match_status` / `join_status` の分布が意図した変化になっているか確認してください。`sbgy.xml` や `廣韻.csv` が手元にない場合は、構文チェックまで実施し、未実施の実データ検証を作業報告に明記してください。

## 注意点

- `sbgy_integrate.py` と `sbgy_parse.py` は IPA 解析ロジックをそれぞれ持っています。片方だけ変更すると挙動差が出る可能性があります。
- `sbgy_integrate.py` は `sbgy_dict.json` を読みません。`sbgy.xml` を直接解析します。
- KRM の声点は日本漢字音側の声調であり、廣韻声調と常に一致するとは限りません。
- 異体字正規化や反切正規化は照合結果に直結します。既存の正規化表と出力ステータスを確認してから変更してください。
- 既存の中国語・日本語の学術用語、漢字表記、列名を安易に英訳・改名しないでください。
