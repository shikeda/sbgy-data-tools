# scripts/

このディレクトリには、SBGY・廣韻・SGY・KRM/DHSJR 音注データを処理する Python スクリプトを置いています。各スクリプトは Python 3.9 以上、標準ライブラリのみで動作します。

## `gy_dhsjr_link.py`

DHSJR/KRM 形式の TSV の見出し字を `廣韻.csv` に接続し、廣韻側の音韻地位、清濁、攝、声調、漢音・呉音の概略的な予測形などを付与します。攝の出力列名は `GY_摂` です。

実行例:

```bash
python3 scripts/gy_dhsjr_link.py \
  --dhsjr path/to/target.tsv \
  --gy data/input/廣韻.csv \
  --sgy data/input/SGY_fanqie.csv \
  --outdir data/output/dhsjr_krm
```

注意: `GY_漢音韻母形` / `GY_呉音韻母形` は概略的な候補形です。現行実装では、入声字でも非入声韻の形で表示される場合があります。入声字は `GY_声調=入` と `GY_韻目原貌` を確認し、適宜 `フ`・`ツ/チ`・`ク/キ` 系に読み替えてください。
