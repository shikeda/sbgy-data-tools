# `gy_dhsjr_link.py` の使い方

`scripts/gy_dhsjr_link.py` は、DHSJR/KRM 形式の TSV の見出し字を `廣韻.csv` に接続し、廣韻側の音韻地位を分解した音韻情報を付与するスクリプトです。

## 基本コマンド

```bash
python3 scripts/gy_dhsjr_link.py \
  --dhsjr path/to/target.tsv \
  --gy data/input/廣韻.csv \
  --sgy data/input/SGY_fanqie.csv \
  --outdir data/output/dhsjr_krm
```

ディレクトリ内の TSV を一括処理する場合:

```bash
python3 scripts/gy_dhsjr_link.py \
  --dhsjr-dir path/to/DHSJR/data \
  --gy data/input/廣韻.csv \
  --outdir data/output/dhsjr_krm
```

## 主な出力列

- `GY_声母`: 声母。
- `GY_清濁`: 清濁。
- `GY_等`: 等。
- `GY_開合`: 開合。
- `GY_韻`: 韻。
- `GY_摂`: 攝。
- `GY_声調`: 声調。
- `GY_漢音行` / `GY_呉音行`: 声母から推定した漢音・呉音の行。
- `GY_漢音韻母形` / `GY_呉音韻母形`: 攝・等区分などから推定した漢音・呉音の韻母候補形。
- `GY_反切`: 廣韻.csv 側の反切。
- `GY_韻目原貌`: 廣韻.csv 側の韻目原貌。
- `GY_小韻號`: 廣韻.csv 側の小韻號。
- `GY_マッチ状況`: `一意`、`複数音(n)`、`未収録`、`照合不要` のいずれか。

## 入声韻の韻母形について

`GY_漢音韻母形` と `GY_呉音韻母形` は、現在の実装では主に「攝」と「等区分」に基づく概略的な候補形です。

そのため、廣韻で入声に属する字でも、対応する陽声韻・陰声韻側の非入声形で表示される場合があります。たとえば `佛` は廣韻では `並三C文入`、韻目原貌 `物` の入声字ですが、現行出力では臻攝三四等の非入声形として `iン/iユン/uン` などが表示されます。

入声字を検討する場合は、`GY_声調` が `入` であること、および `GY_韻目原貌` を確認し、必要に応じて `-p` 系は `フ`、`-t` 系は `ツ/チ`、`-k` 系は `ク/キ` 系として読み替えてください。
