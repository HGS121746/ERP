import os
import glob
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO)

# 配置路径和关键词
bom_folder = os.path.join(os.getcwd(), 'BOM')
files = glob.glob(os.path.join(bom_folder, '*[Bb][Oo][Mm]*.xlsx'))
required_columns = {'编码', '描述', '位号'}
keyword_map = {'编码': '物料编码', '描述': '物料描述', '位号': '位号', '用量': '用量'}

data_frames = []

for file in files:
    try:
        xls = pd.ExcelFile(file)
    except Exception as e:
        logging.error(f"读取文件失败: {file}, 错误: {e}")
        continue
    
    for sheet_name in xls.sheet_names:
        try:
            # 动态寻找表头行（前10行内）
            header_row = None
            for skiprows in range(0, 10):
                df_temp = pd.read_excel(xls, sheet_name, skiprows=skiprows, nrows=1)
                row_columns = df_temp.columns.str.lower().tolist()
                # 检查是否包含所有必需列的关键词
                found = all(any(kw in col for col in row_columns) for kw in required_columns)
                if found:
                    header_row = skiprows
                    break
            
            if header_row is None:
                logging.info(f"跳过 {file} 的 {sheet_name}: 未找到表头")
                continue
            
            # 读取数据
            df = pd.read_excel(xls, sheet_name, skiprows=header_row)
            if df.empty:
                logging.info(f"文件 {file} 的 {sheet_name} 无数据")
                continue
            
            # 添加来源信息
            df['来源文件'] = os.path.basename(file)
            df['来源Sheet'] = sheet_name
            # --- 修改后的合并位号列代码 ---
            ref_cols = [col for col in df.columns if '位号' in col]  # 改为包含"位号"的列名
            if len(ref_cols) > 0:
                def merge_ref_des(row):
                    refs = []
                    for col in ref_cols:
                        val = row[col]
                        if pd.notna(val):
                            # 处理可能的换行符和多个空格
                            parts = str(val).replace('\n', ' ').split()  # 自动处理连续空格和换行
                            refs.extend([p.strip() for p in parts if p.strip()])
                    # 按原始顺序去重（替代set的无序性）
                    seen = set()
                    ordered_refs = []
                    for ref in refs:
                        if ref not in seen:
                            seen.add(ref)
                            ordered_refs.append(ref)
                    return ' '.join(ordered_refs) if ordered_refs else ''
                
                df['位号'] = df.apply(merge_ref_des, axis=1)
                df.drop(ref_cols, axis=1, inplace=True)
            data_frames.append(df)
                   
            # --- 列名重命名（确保唯一性）---
            sorted_keywords = sorted(keyword_map.keys(), key=lambda x: -len(x))
            new_columns = []
            seen = set()
            for col in df.columns:
                col_str = str(col)
                col_lower = col_str.lower()
                matched = False
                for kw in sorted_keywords:
                    if kw in col_lower:
                        base_name = keyword_map[kw]
                        if base_name in seen:
                            suffix = 1
                            while f"{base_name}.{suffix}" in seen:
                                suffix += 1
                            new_name = f"{base_name}.{suffix}"
                        else:
                            new_name = base_name
                        new_columns.append(new_name)
                        seen.add(new_name)
                        matched = True
                        break
                if not matched:
                    new_columns.append(col_str)
                    seen.add(col_str)
            df.columns = new_columns
            

        except Exception as e:
            logging.warning(f"处理 {file} 的 {sheet_name} 出错: {e}")

# 合并和清洗数据
if data_frames:
    combined_df = pd.concat(data_frames, ignore_index=True)
    combined_df = combined_df.dropna(axis=1, how='all')
    final_columns = list(keyword_map.values()) + ['来源文件', '来源Sheet']
    final_df = combined_df.reindex(columns=final_columns, fill_value='')
    
    final_df['位号'] = (
    final_df['位号']
    .astype(str)
    .replace(['nan', '', ' '], pd.NA)  # 统一替换为 Pandas 空值
)
    final_df['位号'] = final_df['位号'].fillna(method='ffill')
    print("合并后的数据样例：")
    print(final_df.head())
    final_df.to_excel("excel.xlsx")
else:
    print("未找到有效数据")