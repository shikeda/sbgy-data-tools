#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project Name: Parse SBGY XML into a Character Phonology JSON Dictionary
Copyright (c) 2026 Shoju Ikeda
Released under the MIT license
https://opensource.org/licenses/mit-license.php

sbgy_parse.py
宋本廣韻 (sbgy.xml) を解析し、各漢字について
  声母・韻母・声調・攝・韻・等・開合・反切・音読み・巻・韻ID
を含む JSON 辞書を生成する。

使用方法:
    python3 sbgy_parse.py --input sbgy.xml --output sbgy_dict.json

出力形式 (JSON):
{
  "東": [
    {
      "ipa":      "tuŋ˥˩",
      "shengmu":  "端",              # 声母（漢字名）
      "wuyun":    "舌頭音",          # 五音
      "qingzhuo": "全清",            # 清濁
      "yunmu":    "東",              # 韻母（韻名）
      "she":      "通攝",            # 攝
      "deng":     "一等",            # 等
      "kaihe":    "開口",            # 開合
      "shengdiao":"平声",            # 声調
      "fanqie":   "德紅切",          # 反切（その字が反切字の場合）
      "onyomi":   "トウ",            # 音読み
      "volume":   "v1",              # 巻ID
      "rhyme_id": "sp01",            # 韻ID
      "word_id":  "w107b0601",       # 親字ID
      "is_head":  true               # 反切の代表字か
    }
  ],
  ...
}
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


# ============================================================
# Step 2A: 声母対応表
#   key: IPA先頭子音列
#   value: (声母漢字名, 五音カテゴリ, 清濁)
# ============================================================
SHENGMU_TABLE = {
    # 唇音
    "p":    ("幫", "唇音",     "全清"),
    "pʰ":   ("滂", "唇音",     "次清"),
    "bʰ":   ("並", "唇音",     "全濁"),
    "m":    ("明", "唇音",     "次濁"),
    # 舌頭音
    "t":    ("端", "舌頭音",   "全清"),
    "tʰ":   ("透", "舌頭音",   "次清"),
    "dʰ":   ("定", "舌頭音",   "全濁"),
    "n":    ("泥", "舌頭音",   "次濁"),
    # 舌上音
    "ţ":    ("知", "舌上音",   "全清"),
    "ţʰ":   ("徹", "舌上音",   "次清"),
    "ɖʰ":   ("澄", "舌上音",   "全濁"),
    "ɳ":    ("娘", "舌上音",   "次濁"),
    # 歯頭音
    "ts":   ("精", "歯頭音",   "全清"),
    "tsʰ":  ("清", "歯頭音",   "次清"),
    "dzʰ":  ("從", "歯頭音",   "全濁"),
    "s":    ("心", "歯頭音",   "全清"),
    "z":    ("邪", "歯頭音",   "全濁"),
    # 正歯音（莊組）
    "ʧ":    ("莊", "正歯音2",  "全清"),
    "ʧʰ":   ("初", "正歯音2",  "次清"),
    "dʒʰ":  ("崇", "正歯音2",  "全濁"),
    "ʃ":    ("生", "正歯音2",  "全清"),
    "dʐʰ":  ("俟", "正歯音2",  "全濁"),
    # 正歯音（章組）
    "tɕ":   ("章", "正歯音3",  "全清"),
    "tɕʰ":  ("昌", "正歯音3",  "次清"),
    "dʑʰ":  ("船", "正歯音3",  "全濁"),
    "ɕ":    ("書", "正歯音3",  "全清"),
    "ʑ":    ("常", "正歯音3",  "全濁"),
    "nʑ":   ("日", "正歯音3",  "次濁"),
    # 牙音
    "k":    ("見", "牙音",     "全清"),
    "kʰ":   ("溪", "牙音",     "次清"),
    "gʰ":   ("群", "牙音",     "全濁"),
    "ŋ":    ("疑", "牙音",     "次濁"),
    # 喉音
    "ʔ":    ("影", "喉音",     "全清"),
    "x":    ("曉", "喉音",     "全清"),
    "ɣ":    ("匣", "喉音",     "全濁"),
    "j":    ("以", "喉音",     "次濁"),
    # 半舌音・半歯音
    "l":    ("來", "半舌音",   "次濁"),
}

# 零声母（云母）: IPA が母音で始まる場合
ZERO_INITIAL = ("云", "喉音", "次濁")

# 声母抽出用: 長い順に並べてマッチング（bʰ を b より先に）
INITIALS_ORDERED = sorted(SHENGMU_TABLE.keys(), key=len, reverse=True)


# ============================================================
# Step 2B: 韻母対応表
#   key: IPAの韻母部分（声母・声調除去後）
#   value: (攝, 韻名, 等, 開合)
# ============================================================
YUNMU_TABLE = {
    # 通攝
    "uŋ":     ("通攝", "東", "一等", "開口"),
    "ĭuŋ":    ("通攝", "東", "三等", "合口"),
    "uoŋ":    ("通攝", "冬", "一等", "開口"),
    "ĭwoŋ":   ("通攝", "鍾", "三等", "合口"),
    "uk":     ("通攝", "屋", "一等", "開口"),
    "ĭuk":    ("通攝", "屋", "三等", "合口"),
    "uok":    ("通攝", "沃", "一等", "開口"),
    "ĭwok":   ("通攝", "燭", "三等", "合口"),
    # 江攝
    "ɔŋ":     ("江攝", "江", "二等", "開口"),
    "ɔk":     ("江攝", "覺", "二等", "開口"),
    # 止攝
    "ĭe":     ("止攝", "支", "三等", "開口"),
    "ĭwe":    ("止攝", "支", "三等", "合口"),
    "i":      ("止攝", "脂", "三等", "開口"),
    "wi":     ("止攝", "脂", "三等", "合口"),
    "ĭə":     ("止攝", "之", "三等", "開口"),
    "ĭwəi":   ("止攝", "微", "三等", "合口"),
    # 遇攝
    "ĭo":     ("遇攝", "魚", "三等", "開口"),
    "ĭu":     ("遇攝", "虞", "三等", "合口"),
    "u":      ("遇攝", "模", "一等", "開口"),
    # 蟹攝
    "iei":    ("蟹攝", "齊", "四等", "開口"),
    "iwei":   ("蟹攝", "齊", "四等", "合口"),
    "ĭɛi":    ("蟹攝", "祭", "三等", "開口"),
    "ĭwɛi":   ("蟹攝", "祭", "三等", "合口"),
    "ĭwɐi":   ("蟹攝", "廢", "三等", "合口"),
    "ɐi":     ("蟹攝", "咍", "一等", "開口"),
    "uɒi":    ("蟹攝", "灰", "一等", "合口"),
    "ai":     ("蟹攝", "泰", "一等", "開口"),
    "wai":    ("蟹攝", "泰", "一等", "合口"),
    "æi":     ("蟹攝", "夬", "二等", "開口"),
    "wæi":    ("蟹攝", "夬", "二等", "合口"),
    "ĭɐi":    ("蟹攝", "皆", "二等", "開口"),
    "ĭwəi":   ("蟹攝", "皆", "二等", "合口"),  # ← 微と共有の場合あり（止攝優先）
    "ɒi":     ("蟹攝", "哈", "一等", "合口"),
    # 臻攝
    "ĭĕn":    ("臻攝", "眞", "三等", "開口"),
    "ĭwĕn":   ("臻攝", "眞", "三等", "合口"),
    "ĭuĕn":   ("臻攝", "諄", "三等", "合口"),
    "ən":     ("臻攝", "痕", "一等", "開口"),
    "uən":    ("臻攝", "魂", "一等", "合口"),
    "ĭɛn":    ("臻攝", "仙", "三等", "開口"),   # 重複するので山攝を優先
    "ĭĕt":    ("臻攝", "質", "三等", "開口"),
    "ĭwĕt":   ("臻攝", "質", "三等", "合口"),
    "ĭuĕt":   ("臻攝", "術", "三等", "合口"),
    "ət":     ("臻攝", "沒", "一等", "開口"),
    "uət":    ("臻攝", "沒", "一等", "合口"),
    # 山攝
    "an":     ("山攝", "寒", "一等", "開口"),
    "wan":    ("山攝", "桓", "一等", "合口"),
    "æn":     ("山攝", "刪", "二等", "開口"),
    "wæn":    ("山攝", "山", "二等", "合口"),
    "ĭɛn":    ("山攝", "仙", "三等", "開口"),
    "ĭwɛn":   ("山攝", "仙", "三等", "合口"),
    "ien":    ("山攝", "先", "四等", "開口"),
    "iwen":   ("山攝", "先", "四等", "合口"),
    "ĭen":    ("山攝", "先", "四等", "開口"),
    "ĭan":    ("山攝", "元", "三等", "開口"),
    "ĭwan":   ("山攝", "元", "三等", "合口"),
    "ĭwɐn":   ("山攝", "元", "三等", "合口"),
    "ĭɐn":    ("山攝", "仙", "三等", "開口"),
    "at":     ("山攝", "曷", "一等", "開口"),
    "wat":    ("山攝", "末", "一等", "合口"),
    "æt":     ("山攝", "鎋", "二等", "開口"),
    "wæt":    ("山攝", "月", "三等", "合口"),
    "ĭɛt":    ("山攝", "薛", "三等", "開口"),
    "ĭwɛt":   ("山攝", "薛", "三等", "合口"),
    "iet":    ("山攝", "屑", "四等", "開口"),
    "iwet":   ("山攝", "屑", "四等", "合口"),
    "ĭɐt":    ("山攝", "月", "三等", "開口"),
    "ĭwak":   ("山攝", "藥", "三等", "合口"),
    "ĭak":    ("山攝", "藥", "三等", "開口"),  # 宕攝と共有
    # 效攝
    "au":     ("效攝", "豪", "一等", "開口"),
    "ɑu":     ("效攝", "豪", "一等", "開口"),
    "ɐŋ":     ("效攝", "肴", "二等", "開口"),  # 咸攝のɐmと区別
    "ĭɛu":    ("效攝", "宵", "三等", "開口"),
    "ieu":    ("效攝", "蕭", "四等", "開口"),
    "iəu":    ("效攝", "蕭", "四等", "開口"),
    # 果攝
    "ɑ":      ("果攝", "歌", "一等", "開口"),
    "uɑ":     ("果攝", "戈", "一等", "合口"),
    "ĭuɑ":    ("果攝", "戈", "三等", "合口"),
    "wa":     ("果攝", "戈", "一等", "合口"),
    "a":      ("果攝", "歌", "一等", "開口"),
    # 仮攝
    "ĭa":     ("仮攝", "麻", "三等", "開口"),
    "æŋ":     ("梗攝", "庚", "二等", "開口"),  # 梗攝へ
    "wæŋ":    ("梗攝", "庚", "二等", "合口"),
    # 宕攝
    "ɑŋ":     ("宕攝", "唐", "一等", "開口"),
    "uɑŋ":    ("宕攝", "唐", "一等", "合口"),
    "ĭaŋ":    ("宕攝", "陽", "三等", "開口"),
    "ĭwaŋ":   ("宕攝", "陽", "三等", "合口"),
    "ɑk":     ("宕攝", "鐸", "一等", "開口"),
    "uɑk":    ("宕攝", "鐸", "一等", "合口"),
    "ĭak":    ("宕攝", "藥", "三等", "開口"),
    # 梗攝
    "ɐŋ":     ("梗攝", "耕", "二等", "開口"),
    "wɐŋ":    ("梗攝", "耕", "二等", "合口"),
    "ĭɛŋ":    ("梗攝", "清", "三等", "開口"),
    "ĭwɛŋ":   ("梗攝", "清", "三等", "合口"),
    "ieŋ":    ("梗攝", "青", "四等", "開口"),
    "iweŋ":   ("梗攝", "青", "四等", "合口"),
    "ĭɐŋ":    ("梗攝", "庚", "三等", "開口"),
    "ĭwɐŋ":   ("梗攝", "庚", "三等", "合口"),
    "ɐk":     ("梗攝", "麥", "二等", "開口"),
    "wɐk":    ("梗攝", "麥", "二等", "合口"),
    "ĭɛk":    ("梗攝", "昔", "三等", "開口"),
    "ĭwɛk":   ("梗攝", "昔", "三等", "合口"),
    "iek":    ("梗攝", "錫", "四等", "開口"),
    "iwek":   ("梗攝", "錫", "四等", "合口"),
    "ĭɐk":    ("梗攝", "陌", "三等", "開口"),
    "ĭwɐk":   ("梗攝", "陌", "三等", "合口"),
    # 曾攝
    "ĭəŋ":    ("曾攝", "蒸", "三等", "開口"),
    "ĭwək":   ("曾攝", "職", "三等", "合口"),
    "əŋ":     ("曾攝", "登", "一等", "開口"),
    "uəŋ":    ("曾攝", "登", "一等", "合口"),
    "ĭək":    ("曾攝", "職", "三等", "開口"),
    "ək":     ("曾攝", "德", "一等", "開口"),
    "uək":    ("曾攝", "德", "一等", "合口"),
    # 流攝
    "ĭəu":    ("流攝", "尤", "三等", "開口"),
    "əu":     ("流攝", "侯", "一等", "開口"),
    "iəu":    ("流攝", "幽", "三等", "開口"),
    # 深攝
    "ĭĕm":    ("深攝", "侵", "三等", "開口"),
    "ĭĕp":    ("深攝", "緝", "三等", "開口"),
    # 咸攝
    "ɒm":     ("咸攝", "覃", "一等", "開口"),
    "ɒp":     ("咸攝", "合", "一等", "開口"),
    "ɑm":     ("咸攝", "談", "一等", "開口"),
    "ɑp":     ("咸攝", "盍", "一等", "開口"),
    "ĭɛm":    ("咸攝", "鹽", "三等", "開口"),
    "ĭɛp":    ("咸攝", "葉", "三等", "開口"),
    "iem":    ("咸攝", "添", "四等", "開口"),
    "iep":    ("咸攝", "帖", "四等", "開口"),
    "ɐm":     ("咸攝", "咸", "二等", "開口"),
    "ɐp":     ("咸攝", "洽", "二等", "開口"),
    "am":     ("咸攝", "銜", "二等", "開口"),
    "ap":     ("咸攝", "狎", "二等", "開口"),
    "ĭɐm":    ("咸攝", "嚴", "三等", "開口"),
    "ĭɐp":    ("咸攝", "業", "三等", "開口"),
    "ĭwɐm":   ("咸攝", "凡", "三等", "合口"),
    "ĭwɐp":   ("咸攝", "乏", "三等", "合口"),
    # 蟹攝（追加）
    "uɑi":    ("蟹攝", "泰", "一等", "合口"),
    "uɑn":    ("臻攝", "桓", "一等", "合口"),  # 山攝桓韻
    "uɑt":    ("山攝", "末", "一等", "合口"),
    # その他残り
    "uɑ":     ("果攝", "戈", "一等", "合口"),
    "ĭwɛi":   ("蟹攝", "祭", "三等", "合口"),
    "ĭuən":   ("臻攝", "諄", "三等", "合口"),
    "ĭuət":   ("臻攝", "術", "三等", "合口"),
    # 補完（不明韻母の追加対応）
    "ɑn":     ("山攝", "寒", "一等", "開口"),
    "ɑt":     ("山攝", "曷", "一等", "開口"),
    "ɑi":     ("蟹攝", "泰", "一等", "開口"),
    "æk":     ("梗攝", "麥", "二等", "開口"),
    "wæk":    ("梗攝", "麥", "二等", "合口"),
    "wɐi":    ("蟹攝", "皆", "二等", "合口"),
    "ĭəi":    ("止攝", "微", "三等", "開口"),
    "ĭwɐt":   ("山攝", "月", "三等", "合口"),
    "ĭən":    ("臻攝", "眞", "三等", "開口"),
    "ĭət":    ("臻攝", "質", "三等", "開口"),
    "ĭet":    ("山攝", "屑", "四等", "開口"),
    "ĭɑ":     ("仮攝", "麻", "三等", "開口"),
}

# 声調対応
TONE_TABLE = {
    "˥˩": "平声",
    "˩":  "平声",
    "˥":  "上声",
    "˩˥": "去声",
    "":   "入声",
}


# ============================================================
# IPA解析関数
# ============================================================
def parse_ipa(ipa: str) -> dict:
    """
    IPA文字列を声母・韻母・声調に分解する。
    例: "tuŋ˥˩" -> {shengmu:"端", yunmu:"東", shengdiao:"平声", ...}
    """
    result = {
        "shengmu":   "（不明）",
        "wuyun":     "（不明）",
        "qingzhuo":  "（不明）",
        "yunmu":     "（不明）",
        "she":       "（不明）",
        "deng":      "（不明）",
        "kaihe":     "（不明）",
        "shengdiao": "（不明）",
    }

    # 1. 声調を末尾から抽出
    tone_match = re.search(r"(˥˩|˩˥|˥|˩)$", ipa)
    tone_str = tone_match.group(1) if tone_match else ""
    result["shengdiao"] = TONE_TABLE.get(tone_str, "入声")
    core = ipa[: -len(tone_str)] if tone_str else ipa

    # 2. 声母を先頭から抽出（長い順にマッチ）
    initial_str = ""
    for ini in INITIALS_ORDERED:
        if core.startswith(ini):
            initial_str = ini
            break

    if initial_str:
        sm, wy, qz = SHENGMU_TABLE[initial_str]
        result["shengmu"]  = sm
        result["wuyun"]    = wy
        result["qingzhuo"] = qz
        final_str = core[len(initial_str):]
    else:
        # 零声母（母音始まり）→ 云母
        sm, wy, qz = ZERO_INITIAL
        result["shengmu"]  = sm
        result["wuyun"]    = wy
        result["qingzhuo"] = qz
        final_str = core

    # 3. 韻母テーブルをルックアップ（長い順で試みる）
    finals_sorted = sorted(YUNMU_TABLE.keys(), key=len, reverse=True)
    for fin in finals_sorted:
        if final_str == fin:
            she, yun, deng, kaihe = YUNMU_TABLE[fin]
            result["yunmu"]   = yun
            result["she"]     = she
            result["deng"]    = deng
            result["kaihe"]   = kaihe
            break
    else:
        # テーブル未登録の韻母はそのまま記録
        result["yunmu"] = f"（{final_str}）"
        result["she"]   = f"（{final_str}）"

    return result


# ============================================================
# Step 1: XML解析
# ============================================================
def get_char(element) -> str:
    """word_head / added_word から漢字テキストを取得する。"""
    orig = element.find("original_word")
    if orig is not None:
        text = orig.text or ""
    else:
        text = element.text or ""
    return text.strip()


def get_fanqie(element) -> str:
    """note要素内の fanqie テキストを取得する。"""
    note = element.find("note")
    if note is None:
        return ""
    fq = note.find("fanqie")
    if fq is None:
        return ""
    return (fq.text or "").strip()


def parse_xml(xml_path: str) -> dict:
    """
    sbgy.xml をパースし、漢字をキーとする辞書を返す。
    {
      "漢字": [ {entry_dict}, ... ],
      ...
    }
    同一漢字が複数の voice_part に属する場合はリストに追加。
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    result = defaultdict(list)
    stats = {"total_chars": 0, "unknown_yunmu": 0, "voices": 0}

    for vol in root.findall("volume"):
        vol_id = vol.get("id", "")

        for rhyme in vol.findall("rhyme"):
            rhyme_id  = rhyme.get("id", "")
            rhyme_num = rhyme.findtext("rhyme_num", "")

            for vp in rhyme.findall("voice_part"):
                ipa    = vp.get("ipa", "")
                onyomi = vp.get("onyomi", "")
                stats["voices"] += 1

                # IPA解析（Step 2）
                ipa_info = parse_ipa(ipa)

                # 先頭word_headが代表字（反切字）
                children = [c for c in list(vp) if c.tag in ("word_head", "added_word")]
                for idx, elem in enumerate(children):
                    char = get_char(elem)
                    if not char:
                        continue

                    fanqie = get_fanqie(elem)
                    word_id = elem.get("id", "")
                    is_head = (idx == 0)  # 最初のword_headが反切代表字

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
                    }

                    result[char].append(entry)
                    stats["total_chars"] += 1

                    if "不明" in ipa_info["yunmu"] or ipa_info["yunmu"].startswith("（"):
                        stats["unknown_yunmu"] += 1

    return dict(result), stats


# ============================================================
# メイン
# ============================================================
def main():
    parser = argparse.ArgumentParser(
        description="宋本廣韻XMLから声母・韻母・声調JSON辞書を生成"
    )
    parser.add_argument(
        "--input",  "-i",
        default="/mnt/project/sbgy.xml",
        help="入力XMLファイルパス（デフォルト: /mnt/project/sbgy.xml）"
    )
    parser.add_argument(
        "--output", "-o",
        default="/mnt/user-data/outputs/sbgy_dict.json",
        help="出力JSONファイルパス"
    )
    parser.add_argument(
        "--pretty", "-p",
        action="store_true",
        help="JSON出力をインデント整形する"
    )
    args = parser.parse_args()

    print(f"[1/3] XMLを読み込み中: {args.input}")
    if not Path(args.input).exists():
        print(f"ERROR: ファイルが見つかりません: {args.input}", file=sys.stderr)
        sys.exit(1)

    print(f"[2/3] 解析中（全{63384}行）...")
    result, stats = parse_xml(args.input)

    print(f"[3/3] JSONを書き出し中: {args.output}")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    indent = 2 if args.pretty else None
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=indent)

    # 統計表示
    print()
    print("=" * 50)
    print("  完了統計")
    print("=" * 50)
    print(f"  ユニーク漢字数    : {len(result):,} 字")
    print(f"  総エントリ数      : {stats['total_chars']:,} 件")
    print(f"  voice_part 数     : {stats['voices']:,} 個")
    print(f"  韻母マッチ不明    : {stats['unknown_yunmu']:,} 件")
    print(f"  出力ファイル      : {args.output}")
    print("=" * 50)

    # 検証：「凍」の例
    if "凍" in result:
        print()
        print("【検証】「凍」のエントリ:")
        for e in result["凍"]:
            print(f"  IPA={e['ipa']}")
            print(f"  声母={e['shengmu']} ({e['wuyun']}・{e['qingzhuo']})")
            print(f"  韻母={e['yunmu']} ({e['she']}・{e['deng']}・{e['kaihe']})")
            print(f"  声調={e['shengdiao']}")
            print(f"  反切={e['fanqie'] or '（なし）'}")
            print(f"  音読み={e['onyomi']}")


if __name__ == "__main__":
    main()
