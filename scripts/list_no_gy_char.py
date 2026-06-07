#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Name: List SBGY Characters Not Found in Guangyun CSV
Copyright (c) 2026 Shoju Ikeda
Released under the MIT license
https://opensource.org/licenses/mit-license.php

list_no_gy_char.py
廣韻.csv に漢字自体がない 553 件（unmatched_no_gy_char）を CSV に出力する。
"""

import csv
import json
import sys
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = REPO_ROOT / "data/output/sbgy_integrated.json"
DEFAULT_OUTPUT = REPO_ROOT / "data/output/unmatched_no_gy_char.csv"

COLUMNS = [
    "hanzi",
    "fanqie",
    "yunmu",
    "shengdiao",
    "shengmu",
    "deng",
    "word_id",
    "onyomi",
    "is_head",
    "volume",
    "rhyme_id",
]

def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract unmatched_no_gy_char entries from sbgy_integrated.json."
    )
    parser.add_argument(
        "--input",
        "-i",
        default=str(DEFAULT_INPUT),
        help="Path to sbgy_integrated.json.",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=str(DEFAULT_OUTPUT),
        help="Output CSV path.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    with input_path.open(encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for hanzi, entries in data.items():
        for e in entries:
            if e.get("match_status") != "unmatched_no_gy_char":
                continue
            rows.append({
                "hanzi":     hanzi,
                "fanqie":    e.get("fanqie", ""),
                "yunmu":     e.get("yunmu", ""),
                "shengdiao": e.get("shengdiao", ""),
                "shengmu":   e.get("shengmu", ""),
                "deng":      e.get("deng", ""),
                "word_id":   e.get("word_id", ""),
                "onyomi":    e.get("onyomi", ""),
                "is_head":   e.get("is_head", ""),
                "volume":    e.get("volume", ""),
                "rhyme_id":  e.get("rhyme_id", ""),
            })

    rows.sort(key=lambda r: r["word_id"])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)} 件を出力しました: {output_path}", file=sys.stderr)

if __name__ == "__main__":
    main()
