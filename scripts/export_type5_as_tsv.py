import os
import json
import pandas as pd

def main():
    # 1. ファイルパスの設定
    unmatch_file = 'unmatch.md'
    tsv_file = '異体漢字対応テーブル111220版_TSV221111.txt'
    json_file = 'itaiji_20240922.json'
    
    for f in [unmatch_file, tsv_file, json_file]:
        if not os.path.exists(f):
            print(f"エラー: '{f}' が見つかりません。")
            return

    # 2. unmatch.md の読み込み
    unmatch_chars = []
    with open(unmatch_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('```') or line.startswith('#'):
                continue
            unmatch_chars.append(line)

    # 3. 異体漢字対応テーブル(TSV)の読み込みとマッピング構築
    try:
        df_tsv = pd.read_csv(tsv_file, sep='\t', dtype=str)
        if not any('異体' in col for col in df_tsv.columns):
            raise ValueError
    except Exception:
        df_tsv = pd.read_csv(tsv_file, sep=r'\s+', dtype=str)

    # 後で元の行を高速に引き出せるよう、文字から行データ（Series）への辞書を作る
    tsv_row_map = {}
    tsv_variants = set()
    for idx, row in df_tsv.iterrows():
        for col in df_tsv.columns:
            if '異体' in col and pd.notna(row[col]):
                char = str(row[col]).strip()
                tsv_variants.add(char)
                # その文字が含まれる元の行を記憶（重複時は最初の行を優先）
                if char not in tsv_row_map:
                    tsv_row_map[char] = row

    # 4. itaiji_20240922.json の読み込みとマッピング構築
    with open(json_file, 'r', encoding='utf-8') as f:
        json_data = json.load(f)
    
    json_pair_map = {}
    json_variants = set()
    for item in json_data:
        if isinstance(item, dict) and 'c1' in item and 'c2' in item:
            c1, c2 = str(item['c1']).strip(), str(item['c2']).strip()
            if c1: json_variants.add(c1)
            if c2: json_variants.add(c2)
            # 文字から相方のペアを引けるようにする
            json_pair_map[c1] = c2
            json_pair_map[c2] = c1

    # 5. 分類およびフォーマットデータの生成
    type1, type2, type3, type4 = [], [], [], []
    
    # タイプ5用のTSV行データを格納するリスト
    type5_rows = []
    json_dummy_id = 1  # JSONのみで見つかった文字用のダミー整理番号カウンター

    # 出力TSVの基本カラム定義
    tsv_columns = ['整理番号', '異体1', 'Unicode1', '異体2', 'Unicode2', '異体3', 'Unicode3', '異体4', 'Unicode4']

    for char in unmatch_chars:
        in_tsv = char in tsv_variants
        in_json = char in json_variants
        
        # 4分類の仕分け
        if in_tsv and not in_json:
            type1.append(char)
        elif not in_tsv and in_json:
            type2.append(char)
        elif in_tsv and in_json:
            type3.append(char)
        else:
            type4.append(char)
        
        # 5. いずれかに対応（TSVフォーマットへの成形処理）
        if in_tsv:
            # 元のTSVに対応行があるので、その行データをそのままコピー
            orig_row = tsv_row_map[char]
            # カラム順を統一して辞書化
            row_dict = {col: orig_row.get(col, '') for col in tsv_columns}
            type5_rows.append(row_dict)
        elif in_json:
            # JSONにしか対応がない場合、TSVの構造に似せて新規作成
            pair_char = json_pair_map.get(char, '')
            c1_uni = f"{ord(char):04X}" if char else ''
            c2_uni = f"{ord(pair_char):04X}" if pair_char else ''
            
            row_dict = {
                '整理番号': f'JSON_{json_dummy_id:05d}',
                '異体1': char,
                'Unicode1': c1_uni,
                '異体2': pair_char,
                'Unicode2': c2_uni,
                '異体3': '', 'Unicode3': '',
                '異体4': '', 'Unicode4': ''
            }
            type5_rows.append(row_dict)
            json_dummy_id += 1

    # 6. 通常のテキストファイル書き出し
    print("通常のリストファイルを書き出しています...")
    output_files = {
        "result_type1_tsv_only.txt": type1,
        "result_type2_json_only.txt": type2,
        "result_type3_both.txt": type3,
        "result_type4_neither.txt": type4,
        "result_type5_either.txt": list(set(type1 + type2 + type3)) # 重複排除した文字リスト
    }
    for filename, char_list in output_files.items():
        with open(filename, 'w', encoding='utf-8') as out_f:
            out_f.write('\n'.join(char_list) + '\n')

    # 7. ★ タイプ5のデータをTSVフォーマットで書き出し ★
    print("タイプ5を元のTSVフォーマットに変換して保存しています...")
    df_type5 = pd.DataFrame(type5_rows, columns=tsv_columns)
    # 重複する行（同じ元の行が何度も引っかかった場合）をクリーンアップ
    df_type5 = df_type5.drop_duplicates(subset=['整理番号', '異体1', '異体2'])
    
    output_tsv_name = "result_type5_formatted_table.txt"
    df_type5.to_csv(output_tsv_name, sep='\t', index=False, na_rep='')
    print(f"   -> {output_tsv_name} （{len(df_type5)}行）の出力を完了しました。")

    # サマリー表示
    total = len(unmatch_chars)
    print("\n" + "="*55)
    print(f" 調査対象総数: {total} 件")
    print(f" ・タイプ5 (いずれかに対応あり) 判定数 : {len(type1)+len(type2)+len(type3)} 件")
    print(f" ・生成されたTSVテーブルの総行数     : {len(df_type5)} 行")
    print("="*55)

if __name__ == '__main__':
    main()
