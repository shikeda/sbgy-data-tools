#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Name: Summarize DHSJR Pronunciation Annotation TSV Files
Copyright (c) 2026 Shoju Ikeda
Released under the MIT license
https://opensource.org/licenses/mit-license.php

dhsjr_summary.py  —  DHSJR TSV 資料性格サマリー

資料ごとに以下を集計し、漢音・呉音の予備的判定に役立つ情報を出力する。

  1. 基本統計（行数・仮名注あり行数・声点あり行数）
  2. 声点型の分布（上位20件）
  3. 仮名注の分布（上位30件）
  4. 全濁声点（平濁・上濁・去濁・入濁）の仮名注一覧
  5. 仮名注の語頭モーラ別集計（漢音・呉音弁別に直結する初頭音）

使い方:
  # 単一ファイル
  python dhsjr_summary.py path/to/20-001-01_DHN.tsv

  # ディレクトリ内の全 TSV を一括処理（DHSJR/data/ など）
  python dhsjr_summary.py --dir path/to/DHSJR/data/

  # 出力先ディレクトリを指定（省略時は stdout）
  python dhsjr_summary.py --dir path/to/DHSJR/data/ --outdir ./summary_out/

  # フォーマット選択: text（デフォルト）/ tsv / json
  python dhsjr_summary.py --dir path/to/DHSJR/data/ --format tsv --outdir ./summary_out/

  # 基本統計のみ出力
  python dhsjr_summary.py path/to/20-001-01_DHN.tsv --basic-only

Python 3.9 以上。標準ライブラリのみ使用。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path


# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

# 声点の「濁」系に該当するパターン（声点列に含まれる場合に全濁と見なす）
DAKUTEN_PATTERNS = re.compile(r"濁|濁")

# 声点の大分類（照合用）
TONE_CLASSES = {
    "平": re.compile(r"^平(?!濁)"),
    "平濁": re.compile(r"平濁"),
    "上": re.compile(r"^上(?!濁)"),
    "上濁": re.compile(r"上濁"),
    "去": re.compile(r"^去(?!濁)"),
    "去濁": re.compile(r"去濁"),
    "入": re.compile(r"^入(?!濁)"),
    "入濁": re.compile(r"入濁"),
    "フ入": re.compile(r"フ入"),
}

# 仮名注から語頭モーラを抽出するための簡易パターン
# ・長い合拗音（クワ・クヱ・グヱ等）・拗音（シャ・キョ等）を先に処理
INITIAL_MORA_PATTERN = re.compile(
    r"^〔[^〕]+〕?"           # 〔墨〕〔朱〕等の注記を除去
    r"|^[＊和地]+"             # ＊・和・地 等の前置記号を除去
)

MORA_EXTRACT = re.compile(
    r"^([クグ][ワヱウ]|"        # クワ・クヱ・クウ・グワ等（合拗音）
    r"[ア-ン][ャュョァィゥェォ]|"  # 拗音（シャ・キュ・チョ等）
    r"[ア-ン])"                # 単独の片仮名1字
)


# ---------------------------------------------------------------------------
# TSV 読み込み
# ---------------------------------------------------------------------------

def read_dhsjr_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """
    DHSJR 形式の TSV を読み込む。
    ・先頭の # コメント行をスキップ
    ・最初の非コメント行をヘッダーとして扱う
    ・各行を {列名: 値} の辞書に変換して返す
    """
    header: list[str] | None = None
    rows: list[dict[str, str]] = []

    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh, delimiter="\t")
        for raw in reader:
            if not raw or all(c == "" for c in raw):
                continue
            first = raw[0].lstrip("\ufeff")
            if first.startswith("#"):
                continue
            if header is None:
                header = raw
                continue
            # 列数が合わない行はパディング
            if len(raw) < len(header):
                raw = raw + [""] * (len(header) - len(raw))
            rows.append(dict(zip(header, raw[:len(header)])))

    if header is None:
        raise ValueError(f"ヘッダー行が見つかりません: {path}")
    return header, rows


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def strip_prefix(kana: str) -> str:
    """仮名注の前置記号（〔墨〕〔朱〕和・地・＊等）を除去して純粋な仮名部分を返す。"""
    # 〔…〕 を除去
    kana = re.sub(r"〔[^〕]*〕", "", kana)
    # 先頭の 和・地・＊・音・又・フ・N 等を除去（仮名注の判別記号）
    kana = re.sub(r"^[和地音又フN＊○]+", "", kana)
    return kana.strip()


def extract_initial_mora(kana: str) -> str:
    """
    仮名注文字列から語頭モーラを抽出する。
    合拗音・拗音を優先して1モーラとして返す。
    抽出できない場合は '' を返す。
    """
    cleaned = strip_prefix(kana)
    m = MORA_EXTRACT.match(cleaned)
    return m.group(1) if m else ""


def classify_tone(tone: str) -> str:
    """声点文字列を大分類キーに変換する。複数声点（漢語型）の場合は最初の単字分を対象とする。"""
    # 漢語型（例: 平平・去去濁）の場合、最初のトークンに注目
    # スラッシュ区切り（例: 去／平軽）の場合も最初を採用
    first = re.split(r"[・／\s]", tone)[0] if tone else ""
    for label, pat in TONE_CLASSES.items():
        if pat.search(first):
            return label
    return "その他" if first else "なし"


# ---------------------------------------------------------------------------
# 集計
# ---------------------------------------------------------------------------

def summarize(rows: list[dict[str, str]]) -> dict:
    """1資料分の行リストから集計辞書を作る。"""

    total = len(rows)
    kana_present = sum(1 for r in rows if r.get("仮名注", "").strip())
    tone_present = sum(1 for r in rows if r.get("声点", "").strip())
    fanqie_present = sum(1 for r in rows if r.get("反切", "").strip())
    ruion_present = sum(1 for r in rows if r.get("類音", "").strip())

    # 声点型分布
    tone_counter: Counter = Counter()
    dakuten_rows: list[dict] = []

    for r in rows:
        tone_raw = r.get("声点", "").strip()
        if not tone_raw:
            tone_counter["（なし）"] += 1
            continue
        label = classify_tone(tone_raw)
        tone_counter[label] += 1
        if DAKUTEN_PATTERNS.search(tone_raw):
            dakuten_rows.append(r)

    # 仮名注分布
    kana_counter: Counter = Counter()
    initial_counter: Counter = Counter()

    for r in rows:
        kana = r.get("仮名注", "").strip()
        if not kana:
            continue
        kana_counter[kana] += 1
        mora = extract_initial_mora(kana)
        if mora:
            initial_counter[mora] += 1

    # 全濁行の仮名注一覧（声点ごとに整理）
    dakuten_by_tone: dict[str, list[str]] = {}
    for r in dakuten_rows:
        tone_raw = r.get("声点", "").strip()
        kana = strip_prefix(r.get("仮名注", "")).strip()
        label = classify_tone(tone_raw)
        dakuten_by_tone.setdefault(label, [])
        if kana:
            dakuten_by_tone[label].append(
                f"{r.get('単字_見出し', '')}→{kana}"
            )

    return {
        "total_rows": total,
        "kana_present": kana_present,
        "kana_rate": round(kana_present / total * 100, 1) if total else 0,
        "tone_present": tone_present,
        "tone_rate": round(tone_present / total * 100, 1) if total else 0,
        "fanqie_present": fanqie_present,
        "ruion_present": ruion_present,
        "tone_distribution": dict(tone_counter.most_common(12)),
        "kana_top30": dict(kana_counter.most_common(30)),
        "initial_mora_top30": dict(initial_counter.most_common(30)),
        "dakuten_kana": {
            k: sorted(set(v))[:50] for k, v in sorted(dakuten_by_tone.items())
        },
    }


# ---------------------------------------------------------------------------
# 出力フォーマット
# ---------------------------------------------------------------------------

def basic_stats(stats: dict) -> dict:
    """基本統計だけを取り出した辞書を返す。"""
    keys = [
        "total_rows",
        "kana_present",
        "kana_rate",
        "tone_present",
        "tone_rate",
        "fanqie_present",
        "ruion_present",
    ]
    return {k: stats[k] for k in keys}


def render_text(resource_id: str, name: str, stats: dict, *, basic_only: bool = False) -> str:
    lines: list[str] = []
    sep = "=" * 60

    lines += [
        sep,
        f"資料番号: {resource_id}",
        f"資料名  : {name}",
        sep,
        "",
        "【基本統計】",
        f"  総行数          : {stats['total_rows']}",
        f"  仮名注あり      : {stats['kana_present']} ({stats['kana_rate']}%)",
        f"  声点あり        : {stats['tone_present']} ({stats['tone_rate']}%)",
        f"  反切あり        : {stats['fanqie_present']}",
        f"  類音あり        : {stats['ruion_present']}",
    ]
    if basic_only:
        lines.append("")
        return "\n".join(lines)

    lines += ["", "【声点分布】"]
    for label, cnt in stats["tone_distribution"].items():
        lines.append(f"  {label:<10} {cnt:>5}")

    lines += ["", "【仮名注 上位30】"]
    for kana, cnt in stats["kana_top30"].items():
        lines.append(f"  {kana:<12} {cnt:>4}")

    lines += ["", "【語頭モーラ 上位30】"]
    for mora, cnt in stats["initial_mora_top30"].items():
        lines.append(f"  {mora:<6} {cnt:>5}")

    if stats["dakuten_kana"]:
        lines += ["", "【全濁声点行の仮名注（字→仮名、最大50件）】"]
        for label, entries in stats["dakuten_kana"].items():
            lines.append(f"  [{label}]")
            # 10件ずつ折り返し
            for i in range(0, len(entries), 10):
                lines.append("    " + "  ".join(entries[i:i + 10]))
    else:
        lines += ["", "【全濁声点行の仮名注】", "  （該当なし）"]

    lines.append("")
    return "\n".join(lines)


def render_tsv_lines(resource_id: str, name: str, stats: dict, *, basic_only: bool = False) -> list[list[str]]:
    rows: list[list[str]] = []
    base = [resource_id, name]

    rows.append(base + ["基本", "総行数", str(stats["total_rows"])])
    rows.append(base + ["基本", "仮名注あり", str(stats["kana_present"])])
    rows.append(base + ["基本", "仮名注率(%)", str(stats["kana_rate"])])
    rows.append(base + ["基本", "声点あり", str(stats["tone_present"])])
    rows.append(base + ["基本", "声点率(%)", str(stats["tone_rate"])])
    rows.append(base + ["基本", "反切あり", str(stats["fanqie_present"])])
    rows.append(base + ["基本", "類音あり", str(stats["ruion_present"])])

    if basic_only:
        return rows

    for label, cnt in stats["tone_distribution"].items():
        rows.append(base + ["声点分布", label, str(cnt)])
    for kana, cnt in stats["kana_top30"].items():
        rows.append(base + ["仮名注top30", kana, str(cnt)])
    for mora, cnt in stats["initial_mora_top30"].items():
        rows.append(base + ["語頭モーラ", mora, str(cnt)])
    for label, entries in stats["dakuten_kana"].items():
        rows.append(base + ["全濁仮名注", label, "  ".join(entries)])

    return rows


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def collect_targets(args: argparse.Namespace) -> list[Path]:
    targets: list[Path] = []
    if args.tsv:
        targets.append(Path(args.tsv))
    if args.dir:
        d = Path(args.dir)
        targets.extend(sorted(d.glob("*.tsv")))
    if not targets:
        raise SystemExit("ファイルまたは --dir を指定してください。")
    return targets


def process_file(path: Path) -> tuple[str, str, dict]:
    header, rows = read_dhsjr_tsv(path)
    if not rows:
        raise ValueError(f"データ行がありません: {path}")
    resource_id = rows[0].get("資料番号", path.stem)
    name = rows[0].get("資料名", path.stem)
    stats = summarize(rows)
    return resource_id, name, stats


def write_text(path: Path | None, content: str) -> None:
    if path is None:
        print(content, end="")
    else:
        path.write_text(content, encoding="utf-8")
        print(f"  → {path}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DHSJR TSV 資料性格サマリー",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("tsv", nargs="?", help="単一 TSV ファイルのパス")
    parser.add_argument("--dir", help="TSV ファイルが入ったディレクトリ（全 *.tsv を処理）")
    parser.add_argument(
        "--outdir", help="出力ディレクトリ（省略時は stdout）"
    )
    parser.add_argument(
        "--format", choices=["text", "tsv", "json"], default="text",
        help="出力フォーマット（デフォルト: text）"
    )
    parser.add_argument(
        "--basic-only", action="store_true",
        help="基本統計（総行数・仮名注あり・声点あり・反切あり・類音あり）のみ出力する"
    )
    args = parser.parse_args()

    targets = collect_targets(args)
    outdir = Path(args.outdir) if args.outdir else None
    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)

    # TSV 一括出力用バッファ
    tsv_header = ["資料番号", "資料名", "カテゴリ", "キー", "値"]
    tsv_all: list[list[str]] = [tsv_header]
    json_all: list[dict] = []

    for path in targets:
        print(f"処理中: {path.name}", file=sys.stderr)
        try:
            resource_id, name, stats = process_file(path)
        except Exception as e:
            print(f"  スキップ（{e}）", file=sys.stderr)
            continue

        if args.format == "text":
            content = render_text(resource_id, name, stats, basic_only=args.basic_only)
            if outdir:
                out_path = outdir / f"{path.stem}_summary.txt"
                write_text(out_path, content)
            else:
                print(content)

        elif args.format == "tsv":
            tsv_all.extend(render_tsv_lines(resource_id, name, stats, basic_only=args.basic_only))

        elif args.format == "json":
            json_all.append({
                "resource_id": resource_id,
                "name": name,
                "stats": basic_stats(stats) if args.basic_only else stats,
            })

    # TSV / JSON は最後にまとめて出力
    if args.format == "tsv":
        lines = "\n".join("\t".join(r) for r in tsv_all)
        if outdir:
            write_text(outdir / "dhsjr_summary_all.tsv", lines + "\n")
        else:
            print(lines)

    elif args.format == "json":
        content = json.dumps(json_all, ensure_ascii=False, indent=2)
        if outdir:
            write_text(outdir / "dhsjr_summary_all.json", content + "\n")
        else:
            print(content)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
