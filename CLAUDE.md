# CLAUDE.md — sbgy-data-tools

## プロジェクト概要

宋本廣韻 (`sbgy.xml`)・`廣韻.csv`・`SGY_fanqie.csv`・KRM/DHSJR 音注データを統合するための Python ツール群。漢字ごとの音韻情報（IPA・声母・韻母・声調・攝・等・開合）、釋義、校勘注、日本漢字音（声点・仮名注）を横断的に処理する。

## 動作環境

- Python 3.9 以上
- 外部ライブラリ不使用（標準ライブラリのみ）
- `requirements.txt` なし

## ディレクトリ構成

```
sbgy-data-tools/
├── scripts/               # 実行スクリプト（7本）
├── data/
│   ├── input/             # 入力データ置き場
│   │   ├── SGY_fanqie.csv    # リポジトリ同梱（CC BY-SA 4.0）
│   │   ├── 廣韻.csv           # 各自取得（nk2028）
│   │   └── 宋本廣韻データ.html  # 各自取得（KDP）
│   ├── output/            # 生成ファイル置き場（.gitkeep のみ管理）
│   └── reference/         # 参照データ置き場（.gitkeep のみ管理）
├── README.md
└── LICENSE                # MIT
```

`sbgy.xml` はリポジトリ外に置き、実行時に `--sbgy` で指定する。

## スクリプト一覧と役割

| スクリプト | 主な入力 | 主な出力 |
|---|---|---|
| `sbgy_integrate.py` | `sbgy.xml` + `SGY_fanqie.csv` + `廣韻.csv` | `sbgy_integrated.json` |
| `sbgy_parse.py` | `sbgy.xml` | `sbgy_dict.json` |
| `sbgy_krm_join.py` | `sbgy_integrated.json` + KRM TSV/JSON | `sbgy_krm_joined.json` |
| `analyze_shang_zhuodu.py` | `sbgy_krm_joined.json` | `shang_zhuodu_*.tsv`（4種） |
| `gy_dhsjr_link.py` | DHSJR/KRM TSV + `廣韻.csv` | `*_gy_linked.tsv` + 未照合TSV |
| `dhsjr_summary.py` | DHSJR TSV（単一またはディレクトリ） | サマリー（text/tsv/json） |
| `list_no_gy_char.py` | `sbgy_integrated.json` | `unmatched_no_gy_char.csv` |

## 主要データ構造

### `sbgy_integrated.json` — 漢字をキー、エントリのリストを値

```json
{
  "東": [{
    "ipa": "tuŋ˥˩",
    "shengmu": "端", "wuyun": "舌頭音", "qingzhuo": "全清",
    "yunmu": "東", "she": "通攝", "deng": "一等", "kaihe": "開口",
    "shengdiao": "平声", "fanqie": "德紅切", "onyomi": "トウ",
    "volume": "v1", "rhyme_id": "sp01", "word_id": "w107b0601",
    "is_head": true,
    "sgy": { ... },   // is_head=true のみ付与
    "gy":  { ... },   // 照合成功時のみ付与
    "match_status": "matched"
  }]
}
```

**`match_status` の値**
- `matched` — sbgy と廣韻.csv の両方に対応エントリあり
- `unmatched_no_gy_char` — sbgy の漢字自体が廣韻.csv に収録されていない
- `unmatched` — sbgy の漢字は廣韻.csv にあるが、音韻地位・反切で結合できなかった

### `sbgy_krm_joined.json` — KRM pronunciation_id をキー

**`join_status` の値**
- `matched_1` — sbgy で1件に確定
- `matched_n` — 候補複数だが tone/kana で絞り込み済み
- `ambiguous` — 複数候補で絞り込み不能（全候補を `sbgy_matches` に保持）
- `no_sbgy_char` — sbgy に対象漢字の収録なし
- `annotation_char` — 類音注などの音注字であり、見出し字としては照合しない

## IPA 解析の仕組み（`sbgy_integrate.py` / `sbgy_parse.py`）

`SHENGMU_TABLE`（声母）・`YUNMU_TABLE`（韻母）・`TONE_TABLE`（声調）の3テーブルで IPA を分解する。声母は長い順にマッチング（`bʰ` を `b` より先にヒットさせる）。零声母（母音始まり）は「云母」扱い。

`sbgy_integrate.py` と `sbgy_parse.py` は同じ IPA 解析ロジックを持つ（`sbgy_integrate.py` は `sbgy_dict.json` を読まず `sbgy.xml` を直接解析する）。

## 廣韻.csv との照合ロジック（`sbgy_integrate.py`）

1. **反切照合** — sbgy 側の反切で `gy_by_fanqie` を引く（`FANQIE_NORM` で字体差を補正）
2. **音韻地位照合** — `{声母}{等[0]}{韻}{声調[0]}` 形式の `ondigi` で照合（`SM_NORM`・`YUN_NORM` で正規化）
3. **フォールバック** — 同声母・同声調の候補が1件のみの場合

## `gy_dhsjr_link.py` のオプション

- `--entry-col` — 見出し字列名（デフォルト: `単字_見出し`）
- `--tone-col` — 声調列名（デフォルト: `声点`）
- `--itaiji` — 異体字 TSV（複数ファイルはカンマ区切り）
- `--itaiji-json` — 異体字 JSON（`{"新字":["旧字",...]}`形式）

`gy_dhsjr_link.py` の出力列では、攝は `GY_摂` と表記する。

## 入出力の規則

- すべてのファイルは **UTF-8**
- CSV/TSV 出力は `newline=""` を使用
- 入力データは `data/input/` または `data/reference/`
- 変換・分析結果は `data/output/` に出力

## コーディング規則

- `argparse` でコマンドライン引数を定義（`--pretty` フラグで JSON インデント整形）
- `pathlib.Path` でファイルパスを扱う
- `collections.defaultdict` でエントリを集積、`dict()` に変換して返す
- 照合テーブル（`SHENGMU_TABLE`・`YUNMU_TABLE` 等）はモジュールレベルの定数として定義
- 統計情報を処理後に標準出力へ表示する慣行あり

## よくある作業パターン

### `sbgy_integrated.json` を再生成する

```bash
python3 scripts/sbgy_integrate.py \
  --sbgy /path/to/sbgy.xml \
  --sgy  data/input/SGY_fanqie.csv \
  --gy   data/input/廣韻.csv \
  --output data/output/sbgy_integrated.json \
  --pretty
```

### DHSJR TSV に廣韻音韻情報を付与する

```bash
python3 scripts/gy_dhsjr_link.py \
  --dhsjr path/to/target.tsv \
  --gy    data/input/廣韻.csv \
  --sgy   data/input/SGY_fanqie.csv \
  --outdir data/output/dhsjr_krm
```

### ディレクトリ内の DHSJR TSV を一括処理する

```bash
python3 scripts/gy_dhsjr_link.py \
  --dhsjr-dir path/to/DHSJR/data \
  --gy data/input/廣韻.csv \
  --outdir data/output/dhsjr_krm
```
