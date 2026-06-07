#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Name: Join Integrated SBGY Data with KRM Pronunciation Annotations
Copyright (c) 2026 Shoju Ikeda
Released under the MIT license
https://opensource.org/licenses/mit-license.php

sbgy_krm_join.py
────────────────────────────────────────────────────────────────────
sbgy_integrated.json と krm_pronunciations（TSV または JSON）を結合し、
各 KRM 音注エントリに対応する廣韻（sbgy）の音韻情報を付与する。

使用方法:
    python3 sbgy_krm_join.py \
        --sbgy   sbgy_integrated.json \
        --krm    krm_pronunciations.tsv \
        # または .json
        --output sbgy_krm_joined.json \
        [--pretty]

────────────────────────────────────────────────────────────────────
出力 JSON の構造（KRM pronunciation_id をキー）:

{
  "F00001_01": {
    // ── KRM 側の情報（krm_pronunciations 由来）───────────────
    "pronunciation_id":        "F00001_01",
    "definition_seq_id":       "F00001_01",
    "character_headword":      "人",
    "character_form":          "人",
    "tone_marks":              "平濁",
    "kana_phonetic_annotation":"ニン",
    "fanqie":                  "",
    "similar_sound":           "音仁（平濁）「ニン」",
    "annotation_format":       "音注声点有_類音注等",
    "material_location":       "K0100131",
    "remarks_pronunciation":   "",
    "is_headword_char":        true,    // false = 音注字（仁・費など）

    // ── 廣韻音調の候補（tone_marks から変換）──────────────────
    "gy_tone_candidates":      ["平声"],

    // ── sbgy 側の照合結果 ──────────────────────────────────
    "sbgy_matches": [           // 1件 = 確定, 複数 = ambiguous
      {
        "ipa":        "nʑĭĕn˩",
        "shengmu":    "日",
        "wuyun":      "正歯音3",
        "qingzhuo":   "次濁",
        "yunmu":      "眞",
        "she":        "通攝",   // ← 実際は臻攝。実データに依存
        "deng":       "三等",
        "kaihe":      "開口",
        "shengdiao":  "平声",
        "fanqie":     "如鄰切",
        "onyomi":     "ジン",
        "volume":     "v1",
        "rhyme_id":   "sp17",
        "word_id":    "w...",
        "gy": { ... },          // 廣韻.csv 由来（ondigi・釋義等）
        "match_method": "fanqie" // fanqie / kana_tone / tone_only / all
      }
    ],
    "join_status": "matched_1" // matched_1 / matched_n / ambiguous / no_sbgy_char
  },
  ...
}

────────────────────────────────────────────────────────────────────
join_status の値:
  matched_1    sbgy で 1 件に確定
  matched_n    sbgy 候補が複数だが tone/kana で絞り込み済み（最良候補あり）
  ambiguous    sbgy 候補が複数で絞り込み不能（全候補を sbgy_matches に保持）
  no_sbgy_char sbgy に対象漢字の収録なし
  annotation_char 類音注などの音注字であり、見出し字としては照合しない
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path


# ──────────────────────────────────────────────────────────────────
# 定数：声調変換テーブル
# KRM tone_marks → 廣韻 shengdiao の候補リスト
# ──────────────────────────────────────────────────────────────────
TONE_MAPPING: dict[str, list[str]] = {
    "平":   ["平声"],
    "平清": ["平声"],
    "平濁": ["平声"],
    "上":   ["上声"],
    "上清": ["上声"],
    "上濁": ["上声", "去声"],   # 全濁上声 → 去声転訛を考慮
    "去":   ["去声", "入声"],   # 入声からの日本語転訛を考慮
    "去清": ["去声", "入声"],
    "去濁": ["去声", "入声"],
    "入":   ["入声"],
    "入清": ["入声"],
    "入濁": ["入声"],
    "濁":   ["平声", "上声", "去声", "入声"],  # 声調不特定
    "":     ["平声", "上声", "去声", "入声"],  # 声点なし
}


def get_gy_tone_candidates(tone_marks: str) -> list[str]:
    """KRM tone_marks から廣韻声調の候補リストを返す。未知値は全候補。"""
    return TONE_MAPPING.get(tone_marks, ["平声", "上声", "去声", "入声"])


# ──────────────────────────────────────────────────────────────────
# KRM pronunciations の読み込み
# ──────────────────────────────────────────────────────────────────

def load_krm_tsv(path: str) -> list[dict]:
    """TSV 形式の krm_pronunciations を読み込む（先頭 # 行をスキップ）。"""
    rows = []
    with open(path, encoding="utf-8") as f:
        lines = [line for line in f if not line.startswith("#")]
    reader = csv.DictReader(lines, delimiter="\t")
    for row in reader:
        rows.append(dict(row))
    return rows


def load_krm_json(path: str) -> list[dict]:
    """JSON 形式の krm_pronunciations を読み込む。"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_krm(path: str) -> list[dict]:
    if path.endswith(".json"):
        return load_krm_json(path)
    return load_krm_tsv(path)


# ──────────────────────────────────────────────────────────────────
# sbgy_integrated の読み込み・索引化
# ──────────────────────────────────────────────────────────────────

def load_sbgy(path: str) -> dict[str, list[dict]]:
    """sbgy_integrated.json を漢字キーで読み込む。"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────────────────────────
# 照合ロジック
# ──────────────────────────────────────────────────────────────────

def normalize_fanqie(fq: str) -> str:
    """反切末尾の「切」「反」を除去して正規化する。"""
    return re.sub(r"[切反]$", "", fq.strip())


def kana_to_hira(kana: str) -> str:
    """片仮名を平仮名に変換（簡易）。"""
    result = []
    for ch in kana:
        cp = ord(ch)
        if 0x30A1 <= cp <= 0x30F6:
            result.append(chr(cp - 0x60))
        else:
            result.append(ch)
    return "".join(result)


def match_kana(krm_kana: str, sbgy_onyomi: str) -> bool:
    """
    KRM の仮名注と sbgy の音読みが対応するか判定する。
    歴史的仮名遣いの差（ウ列長音等）を簡易吸収。
    """
    if not krm_kana or not sbgy_onyomi:
        return False
    # 片仮名→平仮名
    k = kana_to_hira(krm_kana).strip()
    s = kana_to_hira(sbgy_onyomi).strip()
    if not k or not s:
        return False
    # 完全一致
    if k == s:
        return True
    # 先頭モーラ一致（1文字）でも正とする（仮名注が1字の場合等）
    if len(k) >= 1 and len(s) >= 1 and k[0] == s[0]:
        return True
    return False


def find_sbgy_matches(
    char: str,
    krm_fanqie: str,
    krm_tone: str,
    krm_kana: str,
    sbgy_dict: dict[str, list[dict]],
) -> tuple[list[dict], str]:
    """
    sbgy_dict から char に対応する音韻エントリを照合する。

    Returns
    -------
    (matches, method)
        matches : 照合結果のエントリリスト（match_method フィールド付き）
        method  : 'fanqie' | 'kana_tone' | 'tone_only' | 'all'
    """
    candidates = sbgy_dict.get(char, [])
    if not candidates:
        return [], "none"

    # ── 優先度 1: 反切一致 ────────────────────────────────────────
    if krm_fanqie:
        krm_fq_norm = normalize_fanqie(krm_fanqie)
        fanqie_hits = [
            e for e in candidates
            if normalize_fanqie(e.get("fanqie", "")) == krm_fq_norm and e.get("fanqie")
        ]
        if fanqie_hits:
            for e in fanqie_hits:
                e = dict(e)
                e["match_method"] = "fanqie"
            return [dict(e) | {"match_method": "fanqie"} for e in fanqie_hits], "fanqie"

    # ── 優先度 2: 仮名注 ＋ 声調候補 ────────────────────────────────
    gy_tones = get_gy_tone_candidates(krm_tone)

    if krm_kana:
        kana_tone_hits = [
            e for e in candidates
            if e.get("shengdiao") in gy_tones and match_kana(krm_kana, e.get("onyomi", ""))
        ]
        if kana_tone_hits:
            return [dict(e) | {"match_method": "kana_tone"} for e in kana_tone_hits], "kana_tone"

    # ── 優先度 3: 声調候補のみ ────────────────────────────────────
    tone_hits = [e for e in candidates if e.get("shengdiao") in gy_tones]
    if tone_hits:
        return [dict(e) | {"match_method": "tone_only"} for e in tone_hits], "tone_only"

    # ── 優先度 4: 全候補（絞り込み不能）────────────────────────────
    return [dict(e) | {"match_method": "all"} for e in candidates], "all"


def determine_join_status(matches: list[dict], method: str, char_in_sbgy: bool) -> str:
    """join_status を決定する。"""
    if not char_in_sbgy:
        return "no_sbgy_char"
    if not matches:
        return "no_sbgy_char"
    if len(matches) == 1:
        return "matched_1"
    if method in ("fanqie", "kana_tone"):
        return "matched_n"
    return "ambiguous"


# ──────────────────────────────────────────────────────────────────
# メイン結合処理
# ──────────────────────────────────────────────────────────────────

def join(sbgy_path: str, krm_path: str) -> tuple[dict, dict]:
    print(f"[1/3] sbgy_integrated を読み込み中: {sbgy_path}")
    sbgy_dict = load_sbgy(sbgy_path)

    print(f"[2/3] krm_pronunciations を読み込み中: {krm_path}")
    krm_rows = load_krm(krm_path)

    print(f"[3/3] 結合中 ({len(krm_rows):,} 件) …")

    result = {}
    stats = {
        "total":         0,
        "headword_only": 0,
        "matched_1":     0,
        "matched_n":     0,
        "ambiguous":     0,
        "no_sbgy_char":  0,
        "by_fanqie":     0,
        "by_kana_tone":  0,
        "by_tone_only":  0,
        "by_all":        0,
    }

    for row in krm_rows:
        pron_id  = row.get("pronunciation_id", "")
        char     = row.get("character_headword", "").strip()
        rem      = row.get("remarks_pronunciation", "").strip()
        tone     = row.get("tone_marks", "").strip()
        kana     = row.get("kana_phonetic_annotation", "").strip()
        fanqie   = row.get("fanqie", "").strip()

        stats["total"] += 1

        # 音注字（類音注の参照字）はスキップして join に含めない
        is_headword = (rem != "音注字")

        entry = {
            "pronunciation_id":         pron_id,
            "definition_seq_id":        row.get("definition_seq_id", ""),
            "character_headword":       char,
            "character_form":           row.get("character_form", ""),
            "tone_marks":               tone,
            "kana_phonetic_annotation": kana,
            "fanqie":                   fanqie,
            "similar_sound":            row.get("similar_sound", ""),
            "annotation_format":        row.get("annotation_format", ""),
            "material_location":        row.get("material_location", ""),
            "remarks_pronunciation":    rem,
            "is_headword_char":         is_headword,
            "gy_tone_candidates":       get_gy_tone_candidates(tone),
            "sbgy_matches":             [],
            "join_status":              "",
        }

        if not is_headword:
            # 音注字は照合せず記録のみ
            entry["join_status"] = "annotation_char"
            result[pron_id] = entry
            continue

        stats["headword_only"] += 1

        char_in_sbgy = char in sbgy_dict
        matches, method = find_sbgy_matches(char, fanqie, tone, kana, sbgy_dict)
        status = determine_join_status(matches, method, char_in_sbgy)

        entry["sbgy_matches"] = matches
        entry["join_status"]  = status

        # 統計
        stats[status] = stats.get(status, 0) + 1
        if method in ("fanqie", "kana_tone", "tone_only", "all"):
            stats[f"by_{method}"] += 1

        result[pron_id] = entry

    return result, stats


# ──────────────────────────────────────────────────────────────────
# 検証
# ──────────────────────────────────────────────────────────────────

def verify(result: dict):
    """サンプル文字（人・佛・行・易）で結合結果を表示。"""
    test_chars = {"人", "佛", "行", "易", "樂", "傳"}
    shown = set()
    for pron_id, entry in result.items():
        char = entry["character_headword"]
        if char not in test_chars or char in shown:
            continue
        if not entry["is_headword_char"]:
            continue
        shown.add(char)
        print(f"\n【{char}】 pronunciation_id={pron_id}")
        print(f"  tone_marks={entry['tone_marks']!r:10s}"
              f" kana={entry['kana_phonetic_annotation']!r:6s}"
              f" fanqie={entry['fanqie']!r}")
        print(f"  gy_tone_candidates={entry['gy_tone_candidates']}")
        print(f"  join_status={entry['join_status']}  "
              f"sbgy_matches={len(entry['sbgy_matches'])}件")
        for m in entry["sbgy_matches"]:
            gy = m.get("gy") or {}
            print(f"    method={m.get('match_method'):10s} "
                  f"IPA={m.get('ipa',''):18s} "
                  f"{m.get('shengmu',''):3s} {m.get('yunmu',''):3s} "
                  f"{m.get('shengdiao','')}"
                  f"  ondigi={gy.get('ondigi','')}")


# ──────────────────────────────────────────────────────────────────
# エントリーポイント
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="sbgy_integrated.json と krm_pronunciations を結合"
    )
    parser.add_argument("--sbgy",   default="/mnt/user-data/outputs/sbgy_integrated.json")
    parser.add_argument("--krm",    default="/mnt/project/krm_pronunciations_sample.tsv")
    parser.add_argument("--output", default="/mnt/user-data/outputs/sbgy_krm_joined.json")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    for path, label in [(args.sbgy, "sbgy_integrated.json"),
                        (args.krm,  "krm_pronunciations")]:
        if not Path(path).exists():
            print(f"ERROR: {label} が見つかりません: {path}", file=sys.stderr)
            sys.exit(1)

    result, stats = join(args.sbgy, args.krm)

    print(f"\n出力中: {args.output}")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2 if args.pretty else None)

    # ── 統計表示 ──────────────────────────────────────────────────
    hw = stats["headword_only"]
    print()
    print("=" * 58)
    print("  結合統計")
    print("=" * 58)
    print(f"  KRM 音注総件数              : {stats['total']:,} 件")
    print(f"  うち見出し字（音注字除く）  : {hw:,} 件")
    print()
    if hw:
        print(f"  matched_1  （1件確定）      : {stats['matched_1']:,} 件"
              f"  ({stats['matched_1']/hw*100:.1f}%)")
        print(f"  matched_n  （絞り込み済み） : {stats['matched_n']:,} 件"
              f"  ({stats['matched_n']/hw*100:.1f}%)")
        print(f"  ambiguous  （全候補保持）   : {stats['ambiguous']:,} 件"
              f"  ({stats['ambiguous']/hw*100:.1f}%)")
        print(f"  no_sbgy_char（sbgy未収録）  : {stats['no_sbgy_char']:,} 件"
              f"  ({stats['no_sbgy_char']/hw*100:.1f}%)")
        print()
        print("  照合方法の内訳（見出し字）:")
        print(f"    反切一致 (fanqie)         : {stats['by_fanqie']:,} 件")
        print(f"    仮名+声調 (kana_tone)     : {stats['by_kana_tone']:,} 件")
        print(f"    声調のみ (tone_only)      : {stats['by_tone_only']:,} 件")
        print(f"    全候補保持 (all)          : {stats['by_all']:,} 件")
    sz = Path(args.output).stat().st_size
    print(f"\n  出力ファイルサイズ          : {sz/1e6:.1f} MB")
    print("=" * 58)

    verify(result)


if __name__ == "__main__":
    main()
