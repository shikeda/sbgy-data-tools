#!/usr/bin/env python3
"""
extract_itaiji_from_notes.py
—  krm_notes.tsv の remarks 列から異体字ペアを抽出して JSON を生成する。

抽出対象パターン（かつ広韻/廣韻への言及を含む行）:
  P1: 「◯」と同字。     （例: 「扶」と同字。）
  P2: 「◯」と同字か    （例: 「麼」と同字か。）
  P3: 同字の「◯」は    （例: 同字の「𣃍」は、広韻…）
  P4: 「◯」の俗字。    （例: 「倪」の俗字。）

character_headword (= hanzi_entry) が c1、抽出した字が c2 となる。

注意:
  - c1 が IDS表記（⿱◯◯ 等）や補助漢字面の字も含まれる。
  - 1行から複数の「◯」が抽出される場合は1番目のみ採用（--all-matches で全採用）。
  - 廣韻/広韻言及チェックは省略可（--no-kanji-filter）。

使い方:
  python extract_itaiji_from_notes.py \\
      --notes krm_notes.tsv \\
      --out 独自異体字.json

  # フィルタなし（広韻言及に限らず全パターンを抽出）
  python extract_itaiji_from_notes.py \\
      --notes krm_notes.tsv \\
      --out 独自異体字.json \\
      --no-kanji-filter

  # 集計ログを標準エラーに出力
  python extract_itaiji_from_notes.py \\
      --notes krm_notes.tsv \\
      --out 独自異体字.json \\
      --verbose

Python 3.9 以上。標準ライブラリのみ使用。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

# 広韻/廣韻への言及チェック用パターン
GY_REF_PAT = re.compile(r"広韻|廣韻")

# 抽出パターン定義
# 各エントリ: (パターン名, 正規表現, 抽出グループ番号)
# 「◯」部分は漢字1字以上にマッチするよう [\S]+ を使用
# ただし「」の外に余分な文字が入らないよう慎重に設計
# 抽出パターン定義
# タプル構成: (パターン名, 正規表現, グループ番号 or "self")
# グループ番号 = 1 のとき: match.group(1) が c2
# "self" のとき: 「A」は「B」の俗字 形式 → group(2) が c2（group(1) は character_headword 相当）
EXTRACT_PATTERNS: list[tuple[str, re.Pattern, int | str]] = [
    (
        "同字",
        re.compile(r"「([\S]+?)」と同字[。、]"),
        1,
    ),
    (
        "同字か",
        re.compile(r"「([\S]+?)」と同字か"),
        1,
    ),
    (
        "同字の",
        re.compile(r"同字の「([\S]+?)」は"),
        1,
    ),
    (
        "俗字_self",                              # 「A」は「B」の俗字（とするが）
        re.compile(r"「[\S]+?」は「([\S]+?)」の俗字"),
        1,
    ),
    (
        "俗字",                                   # 「B」の俗字。  c1=headword, c2=B
        re.compile(r"「([\S]+?)」の俗字[。、]"),
        1,
    ),
]

# 抽出対象外の文字列（注記・記号等）
SKIP_C2: set[str] = {"◯", "○", "□", "■", "〓", ""}


# ---------------------------------------------------------------------------
# TSV 読み込み
# ---------------------------------------------------------------------------

def read_notes_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """krm_notes.tsv を読み込む。# コメント行をスキップしてヘッダーを検出する。"""
    header: list[str] | None = None
    rows: list[dict[str, str]] = []

    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for raw in csv.reader(fh, delimiter="\t"):
            if not raw or all(c == "" for c in raw):
                continue
            first = raw[0].lstrip("\ufeff")
            if first.startswith("#"):
                # "# eof列名" 形式のヘッダー検出
                if first.lower().startswith("# eof") and len(raw) > 1:
                    raw[0] = re.sub(r"^#\s*eof\S*\s*", "", first,
                                    flags=re.IGNORECASE).strip()
                    if not raw[0]:
                        raw[0] = re.sub(r"^#\s*eof", "", first,
                                        flags=re.IGNORECASE).strip()
                    header = raw
                continue
            if header is None:
                header = raw
                continue
            if len(raw) < len(header):
                raw = raw + [""] * (len(header) - len(raw))
            rows.append(dict(zip(header, raw[:len(header)])))

    if header is None:
        raise ValueError(f"ヘッダー行が見つかりません: {path}")
    return header, rows


# ---------------------------------------------------------------------------
# 抽出処理
# ---------------------------------------------------------------------------

def extract_pairs(
    rows: list[dict[str, str]],
    require_gy_ref: bool = True,
    all_matches: bool = False,
    verbose: bool = False,
) -> list[dict[str, str]]:
    """
    rows から異体字ペアを抽出する。

    Returns:
        [{"c1": 見出し字, "c2": 抽出字, "pattern": パターン名,
          "pronunciation_id": ..., "kazama_location": ...}, ...]
    """
    # 入力列名の検出（krm_notes.tsv と krm_pronunciation_notes_filtered.tsv 両対応）
    # krm_notes.tsv       : hanzi_entry, definition_seq_id, kazama_location, remarks
    # filtered版          : character_headword, pronunciation_id, kazama_location, remarks
    def get_col(row: dict, *candidates: str) -> str:
        for c in candidates:
            if c in row:
                return row[c]
        return ""

    results: list[dict[str, str]] = []
    pattern_counts: dict[str, int] = {p[0]: 0 for p in EXTRACT_PATTERNS}
    skip_counts = {"gy_ref_skip": 0, "skip_c2": 0, "no_match": 0}

    for row in rows:
        c1 = get_col(row, "hanzi_entry", "character_headword").strip()
        remarks = get_col(row, "remarks").strip()
        pron_id = get_col(row, "definition_seq_id", "pronunciation_id").strip()
        kazama  = get_col(row, "kazama_location").strip()

        if not c1 or not remarks:
            continue

        # 広韻/廣韻言及フィルタ
        if require_gy_ref and not GY_REF_PAT.search(remarks):
            skip_counts["gy_ref_skip"] += 1
            continue

        # 各パターンで抽出
        for pat_name, pat, grp in EXTRACT_PATTERNS:
            matches = list(pat.finditer(remarks))
            if not matches:
                continue

            targets = [m.group(grp) for m in matches]
            if not all_matches:
                targets = targets[:1]   # 1番目のみ

            for c2 in targets:
                c2 = c2.strip()
                if c2 in SKIP_C2 or not c2:
                    skip_counts["skip_c2"] += 1
                    continue
                results.append({
                    "c1": c1,
                    "c2": c2,
                    "pattern": pat_name,
                    "pronunciation_id": pron_id,
                    "kazama_location": kazama,
                    "remarks_excerpt": remarks[:80],
                })
                pattern_counts[pat_name] += 1

    if verbose:
        total = sum(pattern_counts.values())
        print(f"抽出件数: {total}", file=sys.stderr)
        for pname, cnt in pattern_counts.items():
            print(f"  {pname}: {cnt}", file=sys.stderr)
        print(f"スキップ（広韻言及なし）: {skip_counts['gy_ref_skip']}", file=sys.stderr)
        print(f"スキップ（c2が記号等）: {skip_counts['skip_c2']}", file=sys.stderr)

    return results


# ---------------------------------------------------------------------------
# 重複排除と出力形式の生成
# ---------------------------------------------------------------------------

def dedup_pairs(
    pairs: list[dict[str, str]]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """
    同一 (c1, c2) の重複を排除する。

    Returns:
        (deduplicated_pairs, duplicates_log)
    """
    seen: dict[tuple[str, str], dict] = {}
    dupes: list[dict] = []

    for p in pairs:
        key = (p["c1"], p["c2"])
        if key in seen:
            dupes.append({**p, "first_pron_id": seen[key]["pronunciation_id"]})
        else:
            seen[key] = p

    return list(seen.values()), dupes


def to_json_output(pairs: list[dict[str, str]]) -> list[dict[str, str]]:
    """gy_dhsjr_link.py が受け付ける SAT 形式に変換する。"""
    return [{"c1": p["c1"], "c2": p["c2"]} for p in pairs]


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="krm_notes.tsv から異体字ペアを抽出して JSON を生成する",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--notes", required=True,
                        help="krm_notes.tsv（またはフィルタ済みTSV）のパス")
    parser.add_argument("--out", required=True,
                        help="出力 JSON ファイルのパス")
    parser.add_argument("--log", default="",
                        help="重複・詳細ログの出力先TSVパス（省略時は出力しない）")
    parser.add_argument("--no-kanji-filter", dest="no_kanji_filter",
                        action="store_true",
                        help="広韻/廣韻言及チェックを省略して全パターンを抽出する")
    parser.add_argument("--all-matches", dest="all_matches",
                        action="store_true",
                        help="1行に複数マッチがある場合にすべて採用する（デフォルトは1番目のみ）")
    parser.add_argument("--verbose", action="store_true",
                        help="集計情報を標準エラーに出力する")
    args = parser.parse_args()

    path = Path(args.notes)
    print(f"読み込み: {path}", file=sys.stderr)
    _, rows = read_notes_tsv(path)
    print(f"  行数: {len(rows)}", file=sys.stderr)

    pairs = extract_pairs(
        rows,
        require_gy_ref=not args.no_kanji_filter,
        all_matches=args.all_matches,
        verbose=args.verbose,
    )

    deduped, dupes = dedup_pairs(pairs)
    if args.verbose:
        print(f"重複除去後: {len(deduped)} ペア（重複 {len(dupes)} 件）",
              file=sys.stderr)

    # JSON 出力
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    json_data = to_json_output(deduped)
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(json_data, fh, ensure_ascii=False, indent=2)
    print(f"JSON 出力: {out_path} ({len(json_data)} ペア)", file=sys.stderr)

    # ログ出力（詳細確認用）
    if args.log:
        log_path = Path(args.log)
        log_header = ["c1", "c2", "pattern", "pronunciation_id",
                      "kazama_location", "remarks_excerpt"]
        with log_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=log_header,
                                    delimiter="\t", extrasaction="ignore")
            writer.writeheader()
            writer.writerows(deduped)
        print(f"ログ出力: {log_path}", file=sys.stderr)

        if dupes:
            dupe_path = log_path.with_name(log_path.stem + "_dupes.tsv")
            dupe_header = ["c1", "c2", "pattern", "pronunciation_id",
                           "kazama_location", "first_pron_id"]
            with dupe_path.open("w", encoding="utf-8", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=dupe_header,
                                        delimiter="\t", extrasaction="ignore")
                writer.writeheader()
                writer.writerows(dupes)
            print(f"重複ログ: {dupe_path}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
