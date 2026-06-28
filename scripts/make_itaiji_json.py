#!/usr/bin/env python3

import csv
import json

INPUT_FILE = "dhsjr_gy_unmatched.itaiji.tsv"
OUTPUT_FILE = "itaiji_krm_20260626.json"

pairs = set()

with open(INPUT_FILE, encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter="\t")

    for row in reader:
        cls = row["Class"]
        head = row["単字_見出し"]
        kanji = row["kanji"]

        if cls == "C1":
            c1, c2 = head, kanji
        else:
            c1, c2 = kanji, head

        pairs.add((c1, c2))

# c1でソート
result = [
    {"c1": c1, "c2": c2}
    for c1, c2 in sorted(pairs)
]

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"Wrote {len(result)} pairs to {OUTPUT_FILE}")
