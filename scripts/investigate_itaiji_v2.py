import os
import json
import pandas as pd

def main():
    # 1. ファイルパスの設定
    unmatch_file = 'unmatch.md'
    tsv_file = '異体漢字対応テーブル111220版_TSV221111.txt'
    json_file = 'itaiji_20240922.json'
    
    # ファイルの存在確認
    for f in [unmatch_file, tsv_file, json_file]:
        if not os.path.exists(f):
            print(f"エラー: '{f}' が見つかりません。スクリプトと同じディレクトリに配置してください。")
            return

    # 2. unmatch.md の読み込みとクレンジング
    print(f"1/3. '{unmatch_file}' を読み込んでいます...")
    unmatch_chars = []
    with open(unmatch_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # 空行、Markdownのコードブロック記号(```)、見出し(#)などを除外
            if not line or line.startswith('```') or line.startswith('#'):
                continue
            unmatch_chars.append(line)
    print(f"   -> 調査対象文字数: {len(unmatch_chars)} 件")

    # 3. 異体漢字対応テーブル(TSV)の読み込み
    print(f"2/3. '{tsv_file}' を読み込んでいます...")
    try:
        df_tsv = pd.read_csv(tsv_file, sep='\t', dtype=str)
        if not any('異体' in col for col in df_tsv.columns):
            raise ValueError
    except Exception:
        df_tsv = pd.read_csv(tsv_file, sep=r'\s+', dtype=str)

    tsv_variants = set()
    for col in df_tsv.columns:
        if '異体' in col:
            valid_chars = df_tsv[col].dropna().astype(str).str.strip()
            tsv_variants.update(valid_chars)
    print(f"   -> テーブルから抽出された異体字（ユニーク）: {len(tsv_variants)} 種")

    # 4. itaiji_20240922.json の読み込み
    print(f"3/3. '{json_file}' を読み込んでいます...")
    with open(json_file, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
    
    json_variants = set()
    for item in json_data:
        if isinstance(item, dict):
            for key in ['c1', 'c2']:
                if key in item and item[key]:
                    json_variants.add(str(item[key]).strip())
    print(f"   -> JSONから抽出された異体字（ユニーク）: {len(json_variants)} 種")

    # 5. 5つのタイプへの分類・抽出
    type1 = []  # 1. テーブルのみに対応を求められるもの
    type2 = []  # 2. JSONのみに対応を求められるもの
    type3 = []  # 3. 双方に対応をもとめられるもの
    type4 = []  # 4. 双方に対応をもとめられないもの
    type5 = []  # 5. いずれかに対応をもとめられるもの（1, 2, 3 の合計）

    for char in unmatch_chars:
        in_tsv = char in tsv_variants
        in_json = char in json_variants
        
        # 排他的な分類（1〜4）
        if in_tsv and not in_json:
            type1.append(char)
        elif not in_tsv and in_json:
            type2.append(char)
        elif in_tsv and in_json:
            type3.append(char)
        else:
            type4.append(char)
        
        # 5. いずれかに対応（TSVまたはJSONのどちらか一方にでもあれば登録）
        if in_tsv or in_json:
            type5.append(char)

    # 6. 結果のテキストファイル書き出し
    print("\n詳細結果をファイルに書き出しています...")
    output_files = {
        "result_type1_tsv_only.txt": type1,
        "result_type2_json_only.txt": type2,
        "result_type3_both.txt": type3,
        "result_type4_neither.txt": type4,
        "result_type5_either.txt": type5
    }
    for filename, char_list in output_files.items():
        with open(filename, 'w', encoding='utf-8') as out_f:
            out_f.write('\n'.join(char_list) + '\n')
        print(f"   -> {filename} に {len(char_list)} 件を保存しました。")

    # 7. 改良版まとめ（サマリーレポート）の出力
    print("\n" + "="*55)
    print(" 【異体字調査結果・詳細サマリー】")
    print("="*55)
    total = len(unmatch_chars)
    print(f" 調査対象の総文字（行）数: {total} 件\n")
    
    print(" [A] 基本の4分類（重複なし・足すと合計100%になります）")
    print(f"  ・1. テーブルのみ対応あり  : {len(type1):>5} 件 ({len(type1)/total*100:6.2f}%)")
    print(f"  ・2. JSONのみ対応あり      : {len(type2):>5} 件 ({len(type2)/total*100:6.2f}%)")
    print(f"  ・3. 双方に対応あり        : {len(type3):>5} 件 ({len(type3)/total*100:6.2f}%)")
    print(f"  ・4. どちらも対応なし      : {len(type4):>5} 件 ({len(type4)/total*100:6.2f}%)")
    print("-"*55)
    
    print(" [B] 追加されたパターン（いずれかに対応）")
    print(f"  ★5. いずれかに対応あり    : {len(type5):>5} 件 ({len(type5)/total*100:6.2f}%)")
    print("      (※タイプ1 + タイプ2 + タイプ3 の合算値です)")
    print("-"*55)
    
    print(" [C] 各ソースごとのカバー総数（参考値・重複を含む）")
    total_tsv = len(type1) + len(type3)
    total_json = len(type2) + len(type3)
    print(f"  ・テーブルに対応あり（総数）: {total_tsv:>5} 件 ({total_tsv/total*100:6.2f}%)")
    print(f"  ・JSONに対応あり（総数）    : {total_json:>5} 件 ({total_json/total*100:6.2f}%)")
    print("="*55)

if __name__ == '__main__':
    main()
