#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Name: Integrate SBGY XML, SGY Fanqie CSV, and Guangyun CSV
Copyright (c) 2026 Shoju Ikeda
Released under the MIT license
https://opensource.org/licenses/mit-license.php

sbgy_integrate.py
─────────────────────────────────────────────────────────────────
宋本廣韻 (sbgy.xml) ・ SGY_fanqie.csv ・ 廣韻.csv の 3 データを
結合し、各漢字エントリに以下の情報を統合した JSON 辞書を生成する。

  sbgy.xml    → IPA・声母・韻母・声調・攝・等・開合・反切・音読み
  SGY_fanqie  → 三十六字母声母・攝開合等・清濁・校勘注（首字のみ）
  廣韻.csv    → 音韻地位（正式記法）・小韻號・釋義・直音

使用方法:
    python3 sbgy_integrate.py \
        --sbgy   /path/to/sbgy.xml \
        --sgy    /path/to/SGY_fanqie.csv \
        --gy     /path/to/廣韻.csv \
        --output /path/to/sbgy_integrated.json [--pretty]

出力 JSON の構造（漢字をキー、エントリのリストを値）:
{
  "東": [
    {
      // ── sbgy.xml 由来 ──────────────────────────────────────
      "ipa":        "tuŋ˥˩",
      "shengmu":    "端",
      "wuyun":      "舌頭音",
      "qingzhuo":   "全清",
      "yunmu":      "東",
      "she":        "通攝",
      "deng":       "一等",
      "kaihe":      "開口",
      "shengdiao":  "平声",
      "fanqie":     "德紅切",
      "onyomi":     "トウ",
      "volume":     "v1",
      "rhyme_id":   "sp01",
      "word_id":    "w107b0601",
      "is_head":    true,
      // ── SGY_fanqie.csv 由来（is_head=true のみ付与）─────────
      "sgy": {
        "shengmu":            "端",
        "shengmu_deng":       "端1",
        "qingzhuo":           "全清",
        "wuyun":              "舌音",
        "she_kaihe_deng":     "通中1",
        "fanqie":             "徳紅",
        "fanqie_note":        "切2 王2 王3 P2016 P2017 広/...",
        "entry_no":           "1",
        "rhyme_id":           "01東01",
        "volume_rhyme_yunmu": "1:01:東"
      },
      // ── 廣韻.csv 由来（照合できたエントリに付与）──────────
      "gy": {
        "ondigi":     "端一東平",
        "xiaoyun":    "1",
        "xiaoyun_no": "1",
        "yunmu_raw":  "東",
        "fanqie":     "德紅",
        "zhiyin":     "",
        "giyi":       "春方也說文曰動也…",
        "giyi_ref":   "",
        "match_via":  "ondigi"
      },
      "match_status": "matched"
    }
  ]
}

match_status の値:
  "matched"   sbgy + GY の両方に対応エントリあり（sgy も付与済みの場合あり）
  "unmatched_no_gy_char" sbgy の漢字自体が GY に収録されていない
  "unmatched" sbgy の漢字は GY にあるが、音韻地位・反切で結合できなかった
"""

import argparse
import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


# ──────────────────────────────────────────────────────────────
# 定数・対応表
# ──────────────────────────────────────────────────────────────

# sbgy IPA 先頭子音 → 声母（漢字名, 五音, 清濁）
SHENGMU_TABLE = {
    "p":   ("幫", "唇音",     "全清"),
    "pʰ":  ("滂", "唇音",     "次清"),
    "bʰ":  ("並", "唇音",     "全濁"),
    "m":   ("明", "唇音",     "次濁"),
    "t":   ("端", "舌頭音",   "全清"),
    "tʰ":  ("透", "舌頭音",   "次清"),
    "dʰ":  ("定", "舌頭音",   "全濁"),
    "n":   ("泥", "舌頭音",   "次濁"),
    "ţ":   ("知", "舌上音",   "全清"),
    "ţʰ":  ("徹", "舌上音",   "次清"),
    "ɖʰ":  ("澄", "舌上音",   "全濁"),
    "ɳ":   ("娘", "舌上音",   "次濁"),
    "ts":  ("精", "歯頭音",   "全清"),
    "tsʰ": ("清", "歯頭音",   "次清"),
    "dzʰ": ("從", "歯頭音",   "全濁"),
    "s":   ("心", "歯頭音",   "全清"),
    "z":   ("邪", "歯頭音",   "全濁"),
    "ʧ":   ("莊", "正歯音2",  "全清"),
    "ʧʰ":  ("初", "正歯音2",  "次清"),
    "dʒʰ": ("崇", "正歯音2",  "全濁"),
    "ʃ":   ("生", "正歯音2",  "全清"),
    "dʐʰ": ("俟", "正歯音2",  "全濁"),
    "tɕ":  ("章", "正歯音3",  "全清"),
    "tɕʰ": ("昌", "正歯音3",  "次清"),
    "dʑʰ": ("船", "正歯音3",  "全濁"),
    "ɕ":   ("書", "正歯音3",  "全清"),
    "ʑ":   ("常", "正歯音3",  "全濁"),
    "nʑ":  ("日", "正歯音3",  "次濁"),
    "k":   ("見", "牙音",     "全清"),
    "kʰ":  ("溪", "牙音",     "次清"),
    "gʰ":  ("群", "牙音",     "全濁"),
    "ŋ":   ("疑", "牙音",     "次濁"),
    "ʔ":   ("影", "喉音",     "全清"),
    "x":   ("曉", "喉音",     "全清"),
    "ɣ":   ("匣", "喉音",     "全濁"),
    "j":   ("以", "喉音",     "次濁"),
    "l":   ("來", "半舌音",   "次濁"),
}
ZERO_INITIAL = ("云", "喉音", "次濁")
INITIALS_ORDERED = sorted(SHENGMU_TABLE.keys(), key=len, reverse=True)

# sbgy IPA 韻母部分 → (攝, 韻名, 等, 開合)
YUNMU_TABLE = {
    "uŋ":    ("通攝","東","一等","開口"), "ĭuŋ":   ("通攝","東","三等","合口"),
    "uoŋ":   ("通攝","冬","一等","開口"), "ĭwoŋ":  ("通攝","鍾","三等","合口"),
    "uk":    ("通攝","屋","一等","開口"), "ĭuk":   ("通攝","屋","三等","合口"),
    "uok":   ("通攝","沃","一等","開口"), "ĭwok":  ("通攝","燭","三等","合口"),
    "ɔŋ":    ("江攝","江","二等","開口"), "ɔk":    ("江攝","覺","二等","開口"),
    "ĭe":    ("止攝","支","三等","開口"), "ĭwe":   ("止攝","支","三等","合口"),
    "i":     ("止攝","脂","三等","開口"), "wi":    ("止攝","脂","三等","合口"),
    "ĭə":    ("止攝","之","三等","開口"), "ĭwəi":  ("止攝","微","三等","合口"),
    "ĭəi":   ("止攝","微","三等","開口"),
    "ĭo":    ("遇攝","魚","三等","開口"), "ĭu":    ("遇攝","虞","三等","合口"),
    "u":     ("遇攝","模","一等","開口"),
    "iei":   ("蟹攝","齊","四等","開口"), "iwei":  ("蟹攝","齊","四等","合口"),
    "ĭɛi":   ("蟹攝","祭","三等","開口"), "ĭwɛi":  ("蟹攝","祭","三等","合口"),
    "ĭwɐi":  ("蟹攝","廢","三等","合口"),
    "ɐi":    ("蟹攝","咍","一等","開口"), "uɒi":   ("蟹攝","灰","一等","合口"),
    "ai":    ("蟹攝","泰","一等","開口"), "wai":   ("蟹攝","泰","一等","合口"),
    "uɑi":   ("蟹攝","泰","一等","合口"),
    "æi":    ("蟹攝","夬","二等","開口"), "wæi":   ("蟹攝","夬","二等","合口"),
    "ĭɐi":   ("蟹攝","皆","二等","開口"), "wɐi":   ("蟹攝","皆","二等","合口"),
    "ɒi":    ("蟹攝","哈","一等","合口"), "ɑi":    ("蟹攝","泰","一等","開口"),
    "ĭĕn":   ("臻攝","眞","三等","開口"), "ĭwĕn":  ("臻攝","眞","三等","合口"),
    "ĭuĕn":  ("臻攝","諄","三等","合口"), "ĭuən":  ("臻攝","諄","三等","合口"),
    "ən":    ("臻攝","痕","一等","開口"), "uən":   ("臻攝","魂","一等","合口"),
    "ĭĕt":   ("臻攝","質","三等","開口"), "ĭwĕt":  ("臻攝","質","三等","合口"),
    "ĭuĕt":  ("臻攝","術","三等","合口"), "ĭuət":  ("臻攝","術","三等","合口"),
    "ĭən":   ("臻攝","眞","三等","開口"), "ĭət":   ("臻攝","質","三等","開口"),
    "ət":    ("臻攝","沒","一等","開口"), "uət":   ("臻攝","沒","一等","合口"),
    "an":    ("山攝","寒","一等","開口"), "wan":   ("山攝","桓","一等","合口"),
    "ɑn":    ("山攝","寒","一等","開口"), "ɑt":    ("山攝","曷","一等","開口"),
    "æn":    ("山攝","刪","二等","開口"), "wæn":   ("山攝","山","二等","合口"),
    "ĭɛn":   ("山攝","仙","三等","開口"), "ĭwɛn":  ("山攝","仙","三等","合口"),
    "ien":   ("山攝","先","四等","開口"), "iwen":  ("山攝","先","四等","合口"),
    "ĭen":   ("山攝","先","四等","開口"), "ĭan":   ("山攝","元","三等","開口"),
    "ĭwɐn":  ("山攝","元","三等","合口"), "ĭɐn":   ("山攝","仙","三等","開口"),
    "at":    ("山攝","曷","一等","開口"), "wat":   ("山攝","末","一等","合口"),
    "æt":    ("山攝","鎋","二等","開口"), "wæt":   ("山攝","月","三等","合口"),
    "ĭɛt":   ("山攝","薛","三等","開口"), "ĭwɛt":  ("山攝","薛","三等","合口"),
    "iet":   ("山攝","屑","四等","開口"), "iwet":  ("山攝","屑","四等","合口"),
    "ĭet":   ("山攝","屑","四等","開口"), "ĭɐt":   ("山攝","月","三等","開口"),
    "ĭwɐt":  ("山攝","月","三等","合口"), "ĭwak":  ("山攝","藥","三等","合口"),
    "au":    ("效攝","豪","一等","開口"), "ɑu":    ("效攝","豪","一等","開口"),
    "ĭɛu":   ("效攝","宵","三等","開口"), "ieu":   ("效攝","蕭","四等","開口"),
    "iəu":   ("流攝","幽","三等","開口"),
    "ɑ":     ("果攝","歌","一等","開口"), "uɑ":    ("果攝","戈","一等","合口"),
    "ĭuɑ":   ("果攝","戈","三等","合口"), "wa":    ("果攝","戈","一等","合口"),
    "a":     ("果攝","歌","一等","開口"),
    "ĭa":    ("仮攝","麻","三等","開口"), "ĭɑ":    ("仮攝","麻","三等","開口"),
    "ɑŋ":    ("宕攝","唐","一等","開口"), "uɑŋ":   ("宕攝","唐","一等","合口"),
    "ĭaŋ":   ("宕攝","陽","三等","開口"), "ĭwaŋ":  ("宕攝","陽","三等","合口"),
    "ɑk":    ("宕攝","鐸","一等","開口"), "uɑk":   ("宕攝","鐸","一等","合口"),
    "ĭak":   ("宕攝","藥","三等","開口"),
    "æŋ":    ("梗攝","庚","二等","開口"), "wæŋ":   ("梗攝","庚","二等","合口"),
    "ɐŋ":    ("梗攝","耕","二等","開口"), "wɐŋ":   ("梗攝","耕","二等","合口"),
    "ĭɛŋ":   ("梗攝","清","三等","開口"), "ĭwɛŋ":  ("梗攝","清","三等","合口"),
    "ieŋ":   ("梗攝","青","四等","開口"), "iweŋ":  ("梗攝","青","四等","合口"),
    "ĭɐŋ":   ("梗攝","庚","三等","開口"), "ĭwɐŋ":  ("梗攝","庚","三等","合口"),
    "ɐk":    ("梗攝","麥","二等","開口"), "wɐk":   ("梗攝","麥","二等","合口"),
    "æk":    ("梗攝","麥","二等","開口"), "wæk":   ("梗攝","麥","二等","合口"),
    "ĭɛk":   ("梗攝","昔","三等","開口"), "ĭwɛk":  ("梗攝","昔","三等","合口"),
    "iek":   ("梗攝","錫","四等","開口"), "iwek":  ("梗攝","錫","四等","合口"),
    "ĭɐk":   ("梗攝","陌","三等","開口"), "ĭwɐk":  ("梗攝","陌","三等","合口"),
    "ĭəŋ":   ("曾攝","蒸","三等","開口"), "ĭwək":  ("曾攝","職","三等","合口"),
    "əŋ":    ("曾攝","登","一等","開口"), "uəŋ":   ("曾攝","登","一等","合口"),
    "ĭək":   ("曾攝","職","三等","開口"), "ək":    ("曾攝","德","一等","開口"),
    "uək":   ("曾攝","德","一等","合口"),
    "ĭəu":   ("流攝","尤","三等","開口"), "əu":    ("流攝","侯","一等","開口"),
    "ĭĕm":   ("深攝","侵","三等","開口"), "ĭĕp":   ("深攝","緝","三等","開口"),
    "ɒm":    ("咸攝","覃","一等","開口"), "ɒp":    ("咸攝","合","一等","開口"),
    "ɑm":    ("咸攝","談","一等","開口"), "ɑp":    ("咸攝","盍","一等","開口"),
    "ĭɛm":   ("咸攝","鹽","三等","開口"), "ĭɛp":   ("咸攝","葉","三等","開口"),
    "iem":   ("咸攝","添","四等","開口"), "iep":   ("咸攝","帖","四等","開口"),
    "ɐm":    ("咸攝","咸","二等","開口"), "ɐp":    ("咸攝","洽","二等","開口"),
    "am":    ("咸攝","銜","二等","開口"), "ap":    ("咸攝","狎","二等","開口"),
    "ĭɐm":   ("咸攝","嚴","三等","開口"), "ĭɐp":   ("咸攝","業","三等","開口"),
    "ĭwɐm":  ("咸攝","凡","三等","合口"), "ĭwɐp":  ("咸攝","乏","三等","合口"),
    "uɑn":   ("臻攝","桓","一等","合口"), "uɑt":   ("山攝","末","一等","合口"),
}
TONE_TABLE = {"˥˩": "平声", "˩": "平声", "˥": "上声", "˩˥": "去声", "": "入声"}

# 廣韻.csv の音韻地位照合用：sbgy 韻名 → GY 韻名
YUN_NORM = {
    "屋":"東","沃":"冬","燭":"鍾","覺":"江","質":"真","術":"真",
    "諄":"真","沒":"魂","月":"元","曷":"寒","末":"寒","黠":"刪",
    "鎋":"刪","薛":"仙","屑":"先","職":"蒸","德":"登","緝":"侵",
    "合":"覃","盍":"談","葉":"鹽","帖":"添","洽":"咸","狎":"銜",
    "業":"嚴","乏":"凡","藥":"陽","鐸":"唐","陌":"庚","麥":"耕",
    "昔":"清","錫":"青","眞":"真","桓":"寒","戈":"歌","哈":"咍",
    "耕":"庚","刪":"山",
}
# sbgy 声母 → GY 声母（字体差補正）
SM_NORM = {"群": "羣", "娘": "孃"}

# SGY → GY 反切の字体差補正
FANQIE_NORM = {
    "徳":"德","戸":"戶","鋤":"鉏","茲":"玆","倶":"俱","兪":"俞",
    "隹":"佳","弐":"二","台":"臺","眞":"真","鄰":"隣","顔":"顏",
    "間":"閒","顛":"顚","𦵔":"莖","吹":"炊","姉":"姊","呉":"吳",
    "縁":"緣","歩":"步","妳":"汝","頼":"賴","遥":"遙","悦":"悅",
    "虚":"虛",
}

def norm_fanqie(fq: str) -> str:
    return "".join(FANQIE_NORM.get(c, c) for c in fq)

def clean_gy_fanqie(fq: str) -> str:
    """GY.csv の反切から注記記号（〈〉〘〙【】（）｟｠）を除去"""
    fq = re.sub(r"[〈〘〖【（(｟].*?[〉〙〗】）｠]", "", fq)
    return fq.strip()


# ──────────────────────────────────────────────────────────────
# IPA 解析
# ──────────────────────────────────────────────────────────────

def parse_ipa(ipa: str) -> dict:
    result = {
        "shengmu": "（不明）", "wuyun": "（不明）", "qingzhuo": "（不明）",
        "yunmu": "（不明）", "she": "（不明）", "deng": "（不明）",
        "kaihe": "（不明）", "shengdiao": "（不明）",
    }
    tone_m = re.search(r"(˥˩|˩˥|˥|˩)$", ipa)
    tone_str = tone_m.group(1) if tone_m else ""
    result["shengdiao"] = TONE_TABLE.get(tone_str, "入声")
    core = ipa[: -len(tone_str)] if tone_str else ipa

    initial_str = ""
    for ini in INITIALS_ORDERED:
        if core.startswith(ini):
            initial_str = ini
            break
    if initial_str:
        sm, wy, qz = SHENGMU_TABLE[initial_str]
        result["shengmu"] = sm
        result["wuyun"] = wy
        result["qingzhuo"] = qz
        final_str = core[len(initial_str):]
    else:
        result["shengmu"], result["wuyun"], result["qingzhuo"] = ZERO_INITIAL
        final_str = core

    finals_sorted = sorted(YUNMU_TABLE.keys(), key=len, reverse=True)
    for fin in finals_sorted:
        if final_str == fin:
            she, yun, deng, kaihe = YUNMU_TABLE[fin]
            result["yunmu"] = yun
            result["she"] = she
            result["deng"] = deng
            result["kaihe"] = kaihe
            break
    else:
        result["yunmu"] = f"（{final_str}）"
        result["she"] = f"（{final_str}）"
    return result


# ──────────────────────────────────────────────────────────────
# Step 1: sbgy.xml の解析
# ──────────────────────────────────────────────────────────────

def get_char(element) -> str:
    orig = element.find("original_word")
    text = (orig.text if orig is not None else element.text) or ""
    return text.strip()

def get_fanqie(element) -> str:
    note = element.find("note")
    if note is None:
        return ""
    fq = note.find("fanqie")
    return (fq.text or "").strip() if fq is not None else ""

def parse_sbgy(xml_path: str) -> tuple[dict, dict]:
    """
    Returns:
        entries:  { char: [ entry_dict, ... ] }
        wid_map:  { word_id: entry_dict }  ← SGY 結合用
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    entries = defaultdict(list)
    wid_map = {}

    for vol in root.findall("volume"):
        vol_id = vol.get("id", "")
        for rhyme in vol.findall("rhyme"):
            rhyme_id  = rhyme.get("id", "")
            rhyme_num = rhyme.findtext("rhyme_num", "")
            for vp in rhyme.findall("voice_part"):
                ipa    = vp.get("ipa", "")
                onyomi = vp.get("onyomi", "")
                ipa_info = parse_ipa(ipa)
                children = [c for c in list(vp) if c.tag in ("word_head", "added_word")]
                for idx, elem in enumerate(children):
                    char = get_char(elem)
                    if not char:
                        continue
                    fanqie  = get_fanqie(elem)
                    word_id = "w" + elem.get("id", "").lstrip("w")
                    is_head = (idx == 0)
                    entry = {
                        "ipa":       ipa,
                        "shengmu":   ipa_info["shengmu"],
                        "wuyun":     ipa_info["wuyun"],
                        "qingzhuo":  ipa_info["qingzhuo"],
                        "yunmu":     ipa_info["yunmu"],
                        "she":       ipa_info["she"],
                        "deng":      ipa_info["deng"],
                        "kaihe":     ipa_info["kaihe"],
                        "shengdiao": ipa_info["shengdiao"],
                        "fanqie":    fanqie,
                        "onyomi":    onyomi,
                        "volume":    vol_id,
                        "rhyme_id":  rhyme_id,
                        "rhyme_num": rhyme_num,
                        "word_id":   word_id,
                        "is_head":   is_head,
                        "sgy":       None,
                        "gy":        None,
                        "match_status": "unmatched",
                    }
                    entries[char].append(entry)
                    if is_head and word_id:
                        wid_map[word_id] = entry
    return dict(entries), wid_map


# ──────────────────────────────────────────────────────────────
# Step 2: SGY_fanqie.csv の読み込み・索引化
# ──────────────────────────────────────────────────────────────

def load_sgy(sgy_path: str) -> dict:
    """Returns { 'w' + word_id: sgy_row }"""
    sgy_map = {}
    with open(sgy_path, encoding="utf-8-sig") as f:
        data_lines = (line for line in f if line.strip() and not line.lstrip().startswith("#"))
        for row in csv.DictReader(data_lines):
            wid = row.get("word_id", "").strip()
            if wid:
                sgy_map["w" + wid] = row
    return sgy_map


# ──────────────────────────────────────────────────────────────
# Step 3: 廣韻.csv の読み込み・索引化
# ──────────────────────────────────────────────────────────────

def load_gy(gy_path: str) -> tuple[dict, dict]:
    """
    Returns:
        gy_by_char:   { char: [ row, ... ] }  ← 漢字→行（異体字対応）
        gy_by_fanqie: { cleaned_fanqie: [ row, ... ] }  ← 反切→行
    """
    gy_by_char   = defaultdict(list)
    gy_by_fanqie = defaultdict(list)

    with open(gy_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            char_raw = row["字頭"].strip()
            # 異体字記法 「主〈異〉」を分離
            m = re.match(r"^(.+?)〈(.+?)〉$", char_raw)
            if m:
                gy_by_char[m.group(1)].append(row)
                gy_by_char[m.group(2)].append(row)
            else:
                gy_by_char[char_raw].append(row)
            # 反切索引（注記除去 + クリーン版）
            fq_raw   = row["反切"].strip()
            fq_clean = clean_gy_fanqie(fq_raw)
            if fq_clean:
                gy_by_fanqie[fq_clean].append(row)

    return dict(gy_by_char), dict(gy_by_fanqie)


# ──────────────────────────────────────────────────────────────
# GY 照合ロジック
# ──────────────────────────────────────────────────────────────

_PAT_ONDIGI = re.compile(r"^(.+?)([一二三四])([A-C])?([\u4e00-\u9fff]+)(平|上|去|入)$")

def normalize_ondigi(od: str) -> str:
    """開/合・A/B/C を除去した基本形に変換"""
    od = re.sub(r"(開|合)", "", od)
    od = re.sub(r"[ABC]", "", od)
    return od

def make_ondigi(entry: dict, use_yun_norm: bool = True) -> str:
    sd = {"平声": "平", "上声": "上", "去声": "去", "入声": "入"}.get(entry["shengdiao"], "")
    ym = (YUN_NORM.get(entry["yunmu"], entry["yunmu"]) if use_yun_norm else entry["yunmu"])
    sm = SM_NORM.get(entry["shengmu"], entry["shengmu"])
    return f'{sm}{entry["deng"][0]}{ym}{sd}'

def find_gy_row(entry: dict, gy_by_char: dict, gy_by_fanqie: dict) -> tuple[dict | None, str]:
    """
    sbgy エントリに対応する GY 行を探す。
    Returns: (matched_row_or_None, match_method)
    match_method: 'fanqie' | 'ondigi' | 'ondigi_raw' | ''
    """
    char = None
    # char は呼び出し元から渡されないので GY の検索は ondigi ベース
    od_mapped = make_ondigi(entry, use_yun_norm=True)
    od_raw    = make_ondigi(entry, use_yun_norm=False)

    # 反切が存在する場合は反切で先に検索
    fq = entry["fanqie"].rstrip("切").strip()
    if fq:
        fq_n = norm_fanqie(fq)
        candidates = gy_by_fanqie.get(fq) or gy_by_fanqie.get(fq_n)
        if candidates:
            return candidates[0], "fanqie"

    return None, ""

def find_gy_row_for_char(char: str, entry: dict,
                          gy_by_char: dict) -> tuple[dict | None, str]:
    """漢字 + 音韻地位で GY 行を探す"""
    gy_rows = gy_by_char.get(char, [])
    if not gy_rows:
        return None, ""

    od_mapped = make_ondigi(entry, True)
    od_raw    = make_ondigi(entry, False)

    for method, od in [("ondigi", od_mapped), ("ondigi_raw", od_raw)]:
        for row in gy_rows:
            if normalize_ondigi(row["音韻地位"]) == od:
                return row, method

    # フォールバック：同韻・同声調で候補が 1 件のみ
    sd = {"平声": "平", "上声": "上", "去声": "去", "入声": "入"}.get(entry["shengdiao"], "")
    sm = SM_NORM.get(entry["shengmu"], entry["shengmu"])
    fallback = [r for r in gy_rows
                if normalize_ondigi(r["音韻地位"]).startswith(sm)
                and normalize_ondigi(r["音韻地位"]).endswith(sd)]
    if len(fallback) == 1:
        return fallback[0], "fallback"

    return None, ""


def make_gy_block(row: dict, method: str) -> dict:
    return {
        "ondigi":     row["音韻地位"],
        "xiaoyun":    row["小韻號"],
        "xiaoyun_no": row["小韻字號"],
        "yunmu_raw":  row["韻目原貌"],
        "fanqie":     row["反切"],
        "zhiyin":     row["直音"],
        "giyi":       row["釋義"],
        "giyi_ref":   row["釋義參照"],
        "match_via":  method,
    }


# ──────────────────────────────────────────────────────────────
# Step 4: SGY ブロック生成
# ──────────────────────────────────────────────────────────────

def make_sgy_block(row: dict) -> dict:
    return {
        "shengmu":            row["shengmu"],
        "shengmu_deng":       row["shengmu_deng"],
        "qingzhuo":           row["qingzhuo"],
        "wuyun":              row["wuyun"],
        "she_kaihe_deng":     row["she_kaihe_deng"],
        "fanqie":             row["fanqie"],
        "fanqie_alt":         row["fanqie_alt"],
        "fanqie_note":        row["fanqie_note"],
        "entry_no":           row["entry_no"],
        "rhyme_id":           row["rhyme_id"],
        "volume_rhyme_yunmu": row["volume_rhyme_yunmu"],
    }


# ──────────────────────────────────────────────────────────────
# メイン結合処理
# ──────────────────────────────────────────────────────────────

def integrate(sbgy_path, sgy_path, gy_path) -> tuple[dict, dict]:
    print("[1/4] sbgy.xml を解析中 …")
    entries, wid_map = parse_sbgy(sbgy_path)

    print("[2/4] SGY_fanqie.csv を読み込み中 …")
    sgy_map = load_sgy(sgy_path)

    print("[3/4] 廣韻.csv を読み込み中 …")
    gy_by_char, gy_by_fanqie = load_gy(gy_path)

    print("[4/4] 3データを結合中 …")

    stats = {
        "total": 0,
        "sgy_attached": 0,
        "gy_matched": 0,
        "gy_fanqie": 0,
        "gy_ondigi": 0,
        "gy_ondigi_raw": 0,
        "gy_fallback": 0,
        "unmatched_no_gy_char": 0,
        "unmatched": 0,
    }

    for char, char_entries in entries.items():
        for entry in char_entries:
            stats["total"] += 1

            # ── SGY 付与（is_head のみ）
            if entry["is_head"] and entry["word_id"] in sgy_map:
                entry["sgy"] = make_sgy_block(sgy_map[entry["word_id"]])
                stats["sgy_attached"] += 1

            # ── GY 照合（全エントリ）
            # 1. 反切ベース（sbgy 側の反切を使用）
            row, method = find_gy_row(entry, gy_by_char, gy_by_fanqie)
            # 2. 漢字 + 音韻地位ベース
            if row is None:
                row, method = find_gy_row_for_char(char, entry, gy_by_char)

            if row is not None:
                entry["gy"] = make_gy_block(row, method)
                entry["match_status"] = "matched"
                stats["gy_matched"] += 1
                if method == "fanqie":
                    stats["gy_fanqie"] += 1
                elif method == "ondigi":
                    stats["gy_ondigi"] += 1
                elif method == "ondigi_raw":
                    stats["gy_ondigi_raw"] += 1
                elif method == "fallback":
                    stats["gy_fallback"] += 1
            else:
                if char not in gy_by_char:
                    entry["match_status"] = "unmatched_no_gy_char"
                    stats["unmatched_no_gy_char"] += 1
                else:
                    entry["match_status"] = "unmatched"
                    stats["unmatched"] += 1

    return entries, stats


# ──────────────────────────────────────────────────────────────
# 検証出力
# ──────────────────────────────────────────────────────────────

def verify(entries: dict):
    """「凍」「行」「中」「樂」で結合結果を確認"""
    tests = ["凍", "東", "行", "中", "樂", "明"]
    for char in tests:
        if char not in entries:
            continue
        print(f"\n【{char}】")
        for e in entries[char]:
            print(f"  IPA={e['ipa']:20s} {e['shengmu']:3s} {e['yunmu']:3s} {e['shengdiao']}"
                  f"  status={e['match_status']}")
            if e["sgy"]:
                s = e["sgy"]
                print(f"    SGY: {s['shengmu']:6s} {s['she_kaihe_deng']:8s}"
                      f" fq={s['fanqie']}")
            if e["gy"]:
                g = e["gy"]
                print(f"    GY:  ondigi={g['ondigi']:10s} via={g['match_via']}"
                      f" giyi={g['giyi'][:25]}…")


# ──────────────────────────────────────────────────────────────
# エントリーポイント
# ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="sbgy.xml + SGY_fanqie.csv + 廣韻.csv を統合した JSON を生成"
    )
    parser.add_argument("--sbgy",   default="/mnt/project/sbgy.xml")
    parser.add_argument("--sgy",    default="/mnt/project/SGY_fanqie.csv")
    parser.add_argument("--gy",     default="/mnt/project/廣韻.csv")
    parser.add_argument("--output", default="/mnt/user-data/outputs/sbgy_integrated.json")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    for path, label in [(args.sbgy, "sbgy.xml"), (args.sgy, "SGY_fanqie.csv"),
                         (args.gy, "廣韻.csv")]:
        if not Path(path).exists():
            print(f"ERROR: {label} が見つかりません: {path}", file=sys.stderr)
            sys.exit(1)

    entries, stats = integrate(args.sbgy, args.sgy, args.gy)

    print(f"\n出力中: {args.output}")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2 if args.pretty else None)

    # ── 統計表示
    print()
    print("=" * 55)
    print("  統合統計")
    print("=" * 55)
    t = stats["total"]
    print(f"  ユニーク漢字数          : {len(entries):,} 字")
    print(f"  総エントリ数            : {t:,} 件")
    print(f"  SGY 付与（首字）        : {stats['sgy_attached']:,} 件")
    print(f"  GY 照合成功             : {stats['gy_matched']:,} 件  ({stats['gy_matched']/t*100:.1f}%)")
    print(f"    うち 反切一致         : {stats['gy_fanqie']:,} 件")
    print(f"    うち 音韻地位一致     : {stats['gy_ondigi']:,} 件")
    print(f"    うち 音韻地位(raw)    : {stats['gy_ondigi_raw']:,} 件")
    print(f"    うち フォールバック   : {stats['gy_fallback']:,} 件")
    unmatched_total = stats["unmatched"] + stats["unmatched_no_gy_char"]
    print(f"  GY 未照合               : {unmatched_total:,} 件  ({unmatched_total/t*100:.1f}%)")
    print(f"    うち GY 字頭未収録    : {stats['unmatched_no_gy_char']:,} 件")
    print(f"    うち 照合不能         : {stats['unmatched']:,} 件")
    print(f"  出力ファイルサイズ      : {Path(args.output).stat().st_size / 1e6:.1f} MB")
    print("=" * 55)

    verify(entries)


if __name__ == "__main__":
    main()
