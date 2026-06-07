#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Name: Analyze Shangsheng Quanzhuo Entries in SBGY-KRM Joined Data
Copyright (c) 2026 Shoju Ikeda
Released under the MIT license
https://opensource.org/licenses/mit-license.php

analyze_shang_zhuodu.py
────────────────────────────────────────────────────────────────────
sbgy_krm_joined.json から上声全濁字に関連するエントリを抽出・展開し、
4種の分析用 TSV を生成する。

目的:
    廣韻で上声全濁に属する字が KRM 側でどの声点・照合状態として
    扱われているかを分析するための基礎データを作成する。
    特に ambiguous エントリの候補を分解し、声点との対応を確認する。
    呉音・和音の明記があるエントリは is_goon フラグで識別し、
    漢音による分析から切り分ける。

使用方法:
    python3 analyze_shang_zhuodu.py \
        --joined  sbgy_krm_joined.json \
        --outdir  output/ \
        [--exclude-goon]

出力ファイル（outdir 以下）:
    shang_zhuodu_candidates.tsv     全候補フラット展開（28 列）
    shang_zhuodu_tone_cross.tsv     tone_marks × shengdiao クロス集計
    shang_zhuodu_by_shengmu.tsv     声母別 tone_marks 分布
    shang_zhuodu_ambig_profile.tsv  ambiguous エントリの候補構成分類

────────────────────────────────────────────────────────────────────
shang_zhuodu_candidates.tsv の列構成:
    pronunciation_id          KRM 音注 ID
    character_headword        見出し字（KRM 側の基準字形）
    character_form            KRM 上の字形
    tone_marks                声点（KRM 声点。空欄は声点なし）
    ss_tone                   similar_sound から抽出した声点
    ss_kana                   similar_sound から抽出した仮名
    kana_phonetic_annotation  仮名注（直接記載）
    similar_sound             類音注全文
    annotation_format         音注形式（KRM 音注種別）
    is_goon                   呉音・和音フラグ（1=疑いあり, 0=対象外）
    join_status               照合状態
    candidate_rank            この候補の順番（1 始まり）
    candidate_total           候補の総数
    word_id                   sbgy.xml 親字 ID
    shengmu                   声母
    qingzhuo                  清濁
    yunmu                     韻母
    she                       攝
    deng                      等
    kaihe                     開合
    shengdiao                 声調（廣韻）
    ipa                       IPA 再構音
    onyomi                    音読み（sbgy.xml より）
    is_shang_zhuodu           上声全濁フラグ（1=該当, 0=非該当）
    match_method              照合方法
    ondigi                    廣韻 音韻地位（廣韻.csv 由来）
    xiaoyun                   小韻番号
    giyi_head                 釋義先頭 40 字

is_goon の判定基準:
    similar_sound のパターン照合のみで判定する（annotation_format は使用しない）。
    以下のパターンを含む場合に is_goon=1:
        「呉音〇〇」「和音〇〇」「呉+漢字/カタカナ」「漢字+和+漢字」
    ※ 「音呉（去）」（呉の字の音注）は除外しない
    ※ 判定は自動処理のため、similar_sound 原文で必ず確認すること

オプション:
    --exclude-goon  is_goon=1 のエントリを集計・サマリーから除外する
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path


# ──────────────────────────────────────────────────────────────────
# 定数
# ──────────────────────────────────────────────────────────────────

# 全濁声母 11 種
ZHUOMU: set[str] = {"並", "定", "澄", "從", "邪", "崇", "俟", "船", "常", "群", "匣"}

# 対象とする join_status
TARGET_STATUSES: set[str] = {"matched_1", "matched_n", "ambiguous"}

# KRM 声点の大分類
TONE_SHANG: set[str] = {"上", "上清", "上濁"}
TONE_QU:    set[str] = {"去", "去清", "去濁"}
TONE_PING:  set[str] = {"平", "平清", "平濁"}
TONE_RU:    set[str] = {"入", "入清", "入濁"}

# similar_sound からの声点・仮名抽出パターン
_PAT_RUION = re.compile(r"音[^\s（「]*（([^）]+)）(?:「([^」]+)」)?")

# ──────────────────────────────────────────────────────────────────
# 呉音・和音検出パターン
# ──────────────────────────────────────────────────────────────────
# 検出対象:
#   「呉音〇〇」「和音〇〇」
#   「呉+漢字」（呉信・呉国 等）「呉+カタカナ」（呉ー 等）
#   「漢字+和+漢字」（和頓 等）
# 非対象:
#   「音呉（去）」（呉の字の音注） → 「音」の直後の「呉」は除外しない
#   「音和（平）」（和の字の音注）

_PAT_GOON_SS = re.compile(
    r"呉音"                                           # 「呉音〇〇」
    r"|和音"                                           # 「和音〇〇」
    r"|(?<![音字])呉[\u4e00-\u9fff\u30a0-\u30ff]"     # 「呉+漢字/カタカナ」（「音呉」除外）
    r"|(?:^|[\u4e00-\u9fff])和[\u4e00-\u9fff]"        # 「漢字+和+漢字」または行頭「和+漢字」
)

def is_goon_entry(annotation_format: str, similar_sound: str) -> int:
    """
    呉音・和音フラグを返す（1=疑いあり, 0=対象外）。

    similar_sound のパターン照合のみで判定する。
    annotation_format は判定に使用しない。
    """
    if similar_sound and _PAT_GOON_SS.search(similar_sound):
        return 1
    return 0


# ──────────────────────────────────────────────────────────────────
# similar_sound の解析
# ──────────────────────────────────────────────────────────────────

def parse_similar_sound(ss: str) -> tuple[str, str]:
    """similar_sound から最初の声点・仮名を抽出する。"""
    if not ss:
        return "", ""
    m = _PAT_RUION.search(ss)
    if m:
        return m.group(1) or "", m.group(2) or ""
    return "", ""


# ──────────────────────────────────────────────────────────────────
# 判定関数
# ──────────────────────────────────────────────────────────────────

def is_shang_zhuodu(match: dict) -> bool:
    # 旧版の統合JSONに含まれることがある unmatched_sm_diff は、
    # 声母判定の信頼性が低いため除外する（例: 已 w310a1006 が邪母と誤判定される問題）。
    if match.get("match_status") == "unmatched_sm_diff":
        return False
    return (
        match.get("shengdiao") == "上声"
        and match.get("shengmu") in ZHUOMU
    )


def tone_category(tone_marks: str) -> str:
    if not tone_marks:
        return "（空欄）"
    if tone_marks in TONE_PING:
        return "平"
    if tone_marks in TONE_SHANG:
        return "上"
    if tone_marks in TONE_QU:
        return "去"
    if tone_marks in TONE_RU:
        return "入"
    return "その他"


# ──────────────────────────────────────────────────────────────────
# データ読み込み
# ──────────────────────────────────────────────────────────────────

def load_joined(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────────────────────────
# 抽出条件
# ──────────────────────────────────────────────────────────────────

def is_target_entry(entry: dict) -> bool:
    if not entry.get("is_headword_char"):
        return False
    if entry.get("join_status") not in TARGET_STATUSES:
        return False
    matches = entry.get("sbgy_matches", [])
    return any(is_shang_zhuodu(m) for m in matches)


# ──────────────────────────────────────────────────────────────────
# フラット展開
# ──────────────────────────────────────────────────────────────────

def expand_candidates(entry: dict) -> list[dict]:
    pid      = entry["pronunciation_id"]
    headword = entry.get("character_headword", "")
    form     = entry.get("character_form", "")
    tone     = entry.get("tone_marks", "")
    kana     = entry.get("kana_phonetic_annotation", "")
    ss       = entry.get("similar_sound", "")
    af       = entry.get("annotation_format", "")
    status   = entry.get("join_status", "")

    ss_tone, ss_kana = parse_similar_sound(ss)
    goon = is_goon_entry(af, ss)

    matches = entry.get("sbgy_matches", [])
    total   = len(matches)

    rows = []
    for rank, m in enumerate(matches, 1):
        gy = m.get("gy") or {}
        row = {
            "pronunciation_id":          pid,
            "character_headword":         headword,
            "character_form":             form,
            "tone_marks":                 tone,
            "ss_tone":                    ss_tone,
            "ss_kana":                    ss_kana,
            "kana_phonetic_annotation":   kana,
            "similar_sound":              ss,
            "annotation_format":          af,
            "is_goon":                    goon,
            "join_status":                status,
            "candidate_rank":             rank,
            "candidate_total":            total,
            "word_id":                    m.get("word_id", ""),
            "shengmu":                    m.get("shengmu", ""),
            "qingzhuo":                   m.get("qingzhuo", ""),
            "yunmu":                      m.get("yunmu", ""),
            "she":                        m.get("she", ""),
            "deng":                       m.get("deng", ""),
            "kaihe":                      m.get("kaihe", ""),
            "shengdiao":                  m.get("shengdiao", ""),
            "ipa":                        m.get("ipa", ""),
            "onyomi":                     m.get("onyomi", ""),
            "is_shang_zhuodu":            1 if is_shang_zhuodu(m) else 0,
            "match_method":               m.get("match_method", ""),
            "ondigi":                     gy.get("ondigi", ""),
            "xiaoyun":                    gy.get("xiaoyun", ""),
            "giyi_head":                  (gy.get("giyi") or "")[:40],
        }
        rows.append(row)
    return rows


# ──────────────────────────────────────────────────────────────────
# 集計関数
# ──────────────────────────────────────────────────────────────────

def make_tone_cross(rows: list[dict], exclude_goon: bool) -> list[dict]:
    """
    上声全濁エントリに絞り、tone_marks × shengdiao のクロス集計を作成する。
    exclude_goon=True の場合、is_goon=1 のエントリを除外する。
    集計単位は pronunciation_id（同一 ID の複数候補は1件として扱う）。
    """
    seen:    set[str] = set()
    counter: Counter  = Counter()

    for row in rows:
        if not row["is_shang_zhuodu"]:
            continue
        if exclude_goon and row["is_goon"]:
            continue
        pid = row["pronunciation_id"]
        if pid in seen:
            continue
        seen.add(pid)
        tone = row["tone_marks"]
        tcat = tone_category(tone)
        counter[(tcat, tone)] += 1

    result = []
    for (tcat, tone), cnt in sorted(counter.items(), key=lambda x: (-x[1], x[0])):
        result.append({"tone_category": tcat, "tone_marks": tone, "count": cnt})
    return result


def make_by_shengmu(rows: list[dict], exclude_goon: bool) -> list[dict]:
    """声母別・tone_marks 大分類別の集計（pronunciation_id 重複排除）。"""
    seen:    set[str] = set()
    counter: Counter  = Counter()

    for row in rows:
        if not row["is_shang_zhuodu"]:
            continue
        if exclude_goon and row["is_goon"]:
            continue
        pid = row["pronunciation_id"]
        if pid in seen:
            continue
        seen.add(pid)
        sm   = row["shengmu"]
        tcat = tone_category(row["tone_marks"])
        counter[(sm, tcat)] += 1

    sm_order   = [sm for sm, _ in Counter(
        row["shengmu"] for row in rows if row["is_shang_zhuodu"]
        and not (exclude_goon and row["is_goon"])
    ).most_common()]
    tcat_order = ["平", "上", "去", "入", "その他", "（空欄）"]

    result = []
    for sm in sm_order:
        for tcat in tcat_order:
            cnt = counter.get((sm, tcat), 0)
            if cnt:
                result.append({"shengmu": sm, "tone_category": tcat, "count": cnt})
    return result


def make_ambig_profile(joined: dict, exclude_goon: bool) -> list[dict]:
    """ambiguous エントリの候補構成を分類する。"""
    result = []
    for pid, entry in joined.items():
        if not entry.get("is_headword_char"):
            continue
        if entry.get("join_status") != "ambiguous":
            continue
        matches = entry.get("sbgy_matches", [])
        if not matches:
            continue

        # is_goon 判定
        af = entry.get("annotation_format", "")
        ss = entry.get("similar_sound", "")
        goon = is_goon_entry(af, ss)
        if exclude_goon and goon:
            continue

        n_total = len(matches)
        n_shang = sum(1 for m in matches if is_shang_zhuodu(m))
        if n_shang == 0:
            continue

        n_other  = n_total - n_shang
        profile  = "shang_only" if n_other == 0 else "shang_and_other"
        cand_sum = "; ".join(
            f'{m.get("shengdiao","")}/{m.get("shengmu","")}/{m.get("yunmu","")}'
            for m in matches
        )
        result.append({
            "pronunciation_id":   pid,
            "character_headword": entry.get("character_headword", ""),
            "tone_marks":         entry.get("tone_marks", ""),
            "is_goon":            goon,
            "candidate_total":    n_total,
            "n_shang_zhuodu":     n_shang,
            "n_other":            n_other,
            "profile":            profile,
            "candidate_summary":  cand_sum,
        })
    return result


# ──────────────────────────────────────────────────────────────────
# TSV 書き込み
# ──────────────────────────────────────────────────────────────────

def write_tsv(path: str, rows: list[dict], fieldnames: list[str]):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  → {path}  ({len(rows):,} 行)")


# ──────────────────────────────────────────────────────────────────
# メイン
# ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="上声全濁字の ambiguous 分解と声点分析"
    )
    parser.add_argument("--joined", "-j",
                        default="/mnt/user-data/outputs/sbgy_krm_joined.json")
    parser.add_argument("--outdir", "-o",
                        default="/mnt/user-data/outputs/")
    parser.add_argument("--exclude-goon", action="store_true",
                        help="呉音・和音フラグ(is_goon=1)のエントリを集計から除外する")
    args = parser.parse_args()

    if not Path(args.joined).exists():
        print(f"ERROR: {args.joined} が見つかりません", file=sys.stderr)
        sys.exit(1)

    outdir      = Path(args.outdir)
    exclude_goon = args.exclude_goon
    outdir.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] {args.joined} を読み込み中 …")
    joined = load_joined(args.joined)
    print(f"      総エントリ数: {len(joined):,} 件")
    if exclude_goon:
        print("      ※ --exclude-goon: 呉音・和音フラグ付きエントリを集計から除外")

    print("[2/5] 上声全濁関連エントリを抽出中 …")
    target_entries = {
        pid: entry for pid, entry in joined.items()
        if is_target_entry(entry)
    }
    print(f"      対象エントリ数: {len(target_entries):,} 件")

    status_dist = Counter(e["join_status"] for e in target_entries.values())
    for k, v in status_dist.most_common():
        print(f"        {k}: {v:,} 件")

    print("[3/5] 候補を展開中 …")
    all_rows: list[dict] = []
    for entry in target_entries.values():
        all_rows.extend(expand_candidates(entry))

    n_shang_rows = sum(1 for r in all_rows if r["is_shang_zhuodu"])
    n_goon_rows  = sum(1 for r in all_rows if r["is_goon"] and r["is_shang_zhuodu"])
    print(f"      展開後総行数: {len(all_rows):,} 行")
    print(f"      うち上声全濁候補: {n_shang_rows:,} 行")
    print(f"      うち呉音・和音フラグ付き（上声全濁）: {n_goon_rows:,} 行")

    print("[4/5] 集計中 …")
    tone_cross    = make_tone_cross(all_rows, exclude_goon)
    by_shengmu    = make_by_shengmu(all_rows, exclude_goon)
    ambig_profile = make_ambig_profile(joined, exclude_goon)

    print("[5/5] TSV を出力中 …")

    CAND_COLS = [
        "pronunciation_id", "character_headword", "character_form",
        "tone_marks", "ss_tone", "ss_kana",
        "kana_phonetic_annotation", "similar_sound",
        "annotation_format", "is_goon",
        "join_status", "candidate_rank", "candidate_total",
        "word_id", "shengmu", "qingzhuo", "yunmu",
        "she", "deng", "kaihe", "shengdiao", "ipa", "onyomi",
        "is_shang_zhuodu", "match_method",
        "ondigi", "xiaoyun", "giyi_head",
    ]
    write_tsv(str(outdir / "shang_zhuodu_candidates.tsv"), all_rows, CAND_COLS)
    write_tsv(str(outdir / "shang_zhuodu_tone_cross.tsv"), tone_cross,
              ["tone_category", "tone_marks", "count"])
    write_tsv(str(outdir / "shang_zhuodu_by_shengmu.tsv"), by_shengmu,
              ["shengmu", "tone_category", "count"])
    write_tsv(str(outdir / "shang_zhuodu_ambig_profile.tsv"), ambig_profile,
              ["pronunciation_id", "character_headword", "tone_marks", "is_goon",
               "candidate_total", "n_shang_zhuodu", "n_other",
               "profile", "candidate_summary"])

    # ── サマリー表示
    label = "（呉音・和音除外後）" if exclude_goon else "（呉音・和音を含む全件）"
    print()
    print("=" * 62)
    print(f"  上声全濁字 分析サマリー {label}")
    print("=" * 62)

    # 集計対象 pronunciation_id 数
    counted_pids = set()
    for r in all_rows:
        if r["is_shang_zhuodu"]:
            if not (exclude_goon and r["is_goon"]):
                counted_pids.add(r["pronunciation_id"])
    print(f"  対象 pronunciation_id 数: {len(counted_pids):,} 件")
    print()

    # 呉音・和音フラグの内訳
    goon_pids = set(r["pronunciation_id"] for r in all_rows
                    if r["is_shang_zhuodu"] and r["is_goon"])
    non_goon_pids = set(r["pronunciation_id"] for r in all_rows
                        if r["is_shang_zhuodu"] and not r["is_goon"])
    all_pids = goon_pids | non_goon_pids
    print(f"  【呉音・和音フラグ内訳】（全 {len(all_pids):,} 件）")
    print(f"  is_goon=0（漢音系）: {len(non_goon_pids):,} 件")
    print(f"  is_goon=1（呉音・和音疑い）: {len(goon_pids):,} 件")
    print()

    print(f"  【tone_marks × 上声全濁候補 クロス集計】{label}")
    print(f"  {'声点大分類':8s}  {'tone_marks':12s}  {'件数':>6s}")
    print("  " + "-" * 36)
    for r in tone_cross:
        print(f"  {r['tone_category']:8s}  {r['tone_marks']:12s}  {r['count']:6d}")
    print()

    print(f"  【ambiguous の候補構成】{label}")
    prof_cnt = Counter(r["profile"] for r in ambig_profile)
    for k in ["shang_only", "shang_and_other"]:
        print(f"  {k:20s}: {prof_cnt.get(k, 0):,} 件")
    print("=" * 62)


if __name__ == "__main__":
    main()
