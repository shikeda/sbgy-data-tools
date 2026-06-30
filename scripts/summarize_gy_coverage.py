#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
summarize_gy_coverage.py — gy_dhsjr_link.py の出力(*_gy_linked.tsv群)から
資料ごとの宋本廣韻マッチ率を集計する。

前提:
  gy_dhsjr_link.py --dhsjr-dir であらかじめ一括リンクを実行し、
  outdir に {資料番号}_{略称}_gy_linked.tsv が74個並んでいる状態。

使い方:
  python summarize_gy_coverage.py --linked-dir linked_out/ \\
                                   --out gy_coverage_summary.tsv

出力列:
  資料番号, 資料名, ファイル名,
  総字数, 照合対象数(照合不要除く),
  一意, 複数音, 未収録,
  一意率, 複数音率, 未収録率, 広義マッチ率(一意+複数音)
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

MATCH_UNIQUE = "一意"
MATCH_NONE = "未収録"
MATCH_SKIP = "照合不要"
MATCH_MULTI_PREFIX = "複数音"  # 実際は "複数音(2)" のように候補数付きで入る


def is_multi(status: str) -> bool:
    return status.startswith(MATCH_MULTI_PREFIX)


def summarize_file(path: Path) -> dict:
    counts = defaultdict(int)
    resource_id = ""
    resource_name = ""
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            if not resource_id:
                resource_id = row.get("資料番号", "")
                resource_name = row.get("資料名", "")
            status = row.get("GY_マッチ状況", "")
            if status == MATCH_UNIQUE:
                counts["unique"] += 1
            elif is_multi(status):
                counts["multi"] += 1
            elif status == MATCH_NONE:
                counts["none"] += 1
            elif status == MATCH_SKIP:
                counts["skip"] += 1
            else:
                counts["other"] += 1

    total = sum(counts.values())
    target = total - counts["skip"]  # 照合不要(見出し字が空など)を除く

    def pct(n: int) -> str:
        return f"{(n / target * 100):.1f}" if target else "0.0"

    return {
        "資料番号": resource_id,
        "資料名": resource_name,
        "ファイル名": path.name,
        "総字数": total,
        "照合対象数": target,
        "一意": counts["unique"],
        "複数音": counts["multi"],
        "未収録": counts["none"],
        "照合不要": counts["skip"],
        "一意率(%)": pct(counts["unique"]),
        "複数音率(%)": pct(counts["multi"]),
        "未収録率(%)": pct(counts["none"]),
        "広義マッチ率(%)": pct(counts["unique"] + counts["multi"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="DHSJR資料ごとの宋本廣韻マッチ率集計")
    parser.add_argument("--linked-dir", required=True, dest="linked_dir",
                         help="gy_dhsjr_link.py の出力ディレクトリ "
                              "(*_gy_linked.tsv が並んでいるディレクトリ)")
    parser.add_argument("--out", default="gy_coverage_summary.tsv",
                         help="集計結果の出力先TSVパス")
    args = parser.parse_args()

    linked_dir = Path(args.linked_dir)
    files = sorted(linked_dir.glob("*_gy_linked.tsv"))
    if not files:
        raise SystemExit(f"*_gy_linked.tsv が見つかりません: {linked_dir}")

    print(f"対象ファイル数: {len(files)}", file=sys.stderr)

    rows = []
    for path in files:
        print(f"  集計中: {path.name}", file=sys.stderr)
        rows.append(summarize_file(path))

    # 広義マッチ率の低い順（要対応の資料が先頭に来る）でソート
    rows.sort(key=lambda r: float(r["広義マッチ率(%)"]))

    fieldnames = ["資料番号", "資料名", "ファイル名", "総字数", "照合対象数",
                  "一意", "複数音", "未収録", "照合不要",
                  "一意率(%)", "複数音率(%)", "未収録率(%)", "広義マッチ率(%)"]

    out_path = Path(args.out)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    # 全体集計も併せて表示
    total_target = sum(r["照合対象数"] for r in rows)
    total_unique = sum(r["一意"] for r in rows)
    total_multi = sum(r["複数音"] for r in rows)
    total_none = sum(r["未収録"] for r in rows)
    overall_pct = (total_unique + total_multi) / total_target * 100 if total_target else 0.0

    print(f"\n資料数: {len(rows)}", file=sys.stderr)
    print(f"全体 照合対象数: {total_target}", file=sys.stderr)
    print(f"全体 一意: {total_unique} / 複数音: {total_multi} / 未収録: {total_none}", file=sys.stderr)
    print(f"全体 広義マッチ率: {overall_pct:.1f}%", file=sys.stderr)
    print(f"\n出力 -> {out_path} ({len(rows)} 行)", file=sys.stderr)


if __name__ == "__main__":
    main()
