import xlrd
import pandas as pd
import glob
import os
import re

def process_merged_cells_xls(file_path, sheet_name):
    workbook = xlrd.open_workbook(file_path)
    sheet = workbook.sheet_by_name(sheet_name)
    
    merged_regions = []
    for merged_range in sheet.merged_cells:
        min_row, max_row, min_col, max_col = merged_range
        value = sheet.cell(min_row, min_col).value
        merged_regions.append((min_row, max_row, min_col, max_col, value))
    
    data = []
    for row_idx in range(sheet.nrows):
        row_data = []
        for col_idx in range(sheet.ncols):
            cell_value = sheet.cell(row_idx, col_idx).value
            for (m_min_row, m_max_row, m_min_col, m_max_col, m_value) in merged_regions:
                if (m_min_row <= row_idx < m_max_row) and (m_min_col <= col_idx < m_max_col):
                    cell_value = m_value
                    break
            row_data.append(cell_value)
        data.append(row_data)
    return data

def extract_data_blocks(data):
    blocks = []
    current_block = None
    direction_search_range = 3  # 在标题行后最多搜索3行寻找方向

    for i, row in enumerate(data):
        # 匹配包含 Line 的标题行
        line_cells = [cell for cell in row if isinstance(cell, str) and 'Line' in cell]

        if line_cells:
            # 保存前一个区块
            if current_block:
                blocks.append(current_block)
            
            # 初始化新区块
            title_cell = line_cells[0]
            current_block = {
                'title': title_cell,
                'direction': None,  # 初始化为空
                'headers': [],
                'rows': [],
                'direction_found': False  # 方向是否已找到的标记
            }

            # 在后续行中搜索方向信息（最多检查3行）
            for j in range(i+1, min(i+1 + direction_search_range, len(data))):
                direction_row = data[j]
                # 匹配独立的方向单元格（纯"左"或"右"）
                direction_cells = [
                    cell for cell in direction_row 
                    if isinstance(cell, str) and re.fullmatch(r'\s*[左右]\s*', str(cell))
                ]
                if direction_cells:
                    current_block['direction'] = direction_cells[0].strip()
                    current_block['direction_found'] = True
                    break  # 找到后停止搜索

        elif current_block:
            # 优先处理方向未找到的情况
            if not current_block['direction_found']:
                # 尝试在本行匹配复合方向信息（如"方向：左"）
                for cell in row:
                    if isinstance(cell, str):
                        match = re.search(r'([左右])', cell)
                        if match:
                            current_block['direction'] = match.group(1)
                            current_block['direction_found'] = True
                            break

            # 列头识别逻辑（仅在方向处理后执行）
            if not current_block['headers']:
                if any('供料器' in str(cell) for cell in row):
                    current_block['headers'] = [str(cell).strip() for cell in row]
                    continue  # 跳过本行后续处理

            # 数据行收集（排除空行）
            if any(cell is not None for cell in row):
                current_block['rows'].append(row)

    # 添加最后一个区块
    if current_block:
        blocks.append(current_block)
    
    return blocks

# 主流程
bom_folder = os.path.join(os.getcwd(), '导出文件')
files = glob.glob(os.path.join(bom_folder, '*.xls'))
if not files:
    print("未找到 .xls 文件，请检查路径！")
    exit()

file_path = files[0]
data = process_merged_cells_xls(file_path, 'Sheet1')

# 调试数据
# print("==== 前10行数据 ====")
# for idx, row in enumerate(data[:10]):
#     print(f"行 {idx}: {row}")

data_blocks = extract_data_blocks(data)
print("提取到的数据块数量:", len(data_blocks))

# 转换为 DataFrame
dfs = []
for block in data_blocks:
    if block.get('headers') and block.get('rows'):
        df = pd.DataFrame(block['rows'], columns=block['headers'])
        df['料台标题'] = block['title']
        df['料台左右'] = block['direction']
        dfs.append(df)
    else:
        print("跳过无效块:", block)

if dfs:
    final_df = pd.concat(dfs, ignore_index=True)
    
    # --------------------------
    # 新增输出结果处理逻辑
    # --------------------------
    # 1. B列（供料器列）向下填充空值
    if '供料器' in final_df.columns:
        final_df['供料器'] = final_df['供料器'].fillna(method='ffill')
    else:
        print("警告: 未找到B列（供料器列）")
    
    target_column = '元件'  # 根据实际列名修改

    # 2. 空值预处理（处理多种空值表现形式）
    null_values = ['', 'NA', 'NaN', 'NULL', 'None', ' ']
    final_df[target_column] = final_df[target_column].replace(null_values, pd.NA)

    # 3. 统计空值情况（调试用）
    # print(f"删除前数据量: {len(final_df)} 行")
    # print(f"'{target_column}'列空值数量: {final_df[target_column].isna().sum()}")

    # 4. 执行删除操作（保留有数据的行）
    if target_column in final_df.columns:
        # 方法一：直接删除空值行（严格模式）
        final_df.dropna(
            subset=[target_column],
            how='any',
            inplace=True
        )
        
        
        # print(f"删除后数据量: {len(final_df)} 行")
        
        # 二次验证
        if final_df[target_column].isna().sum() > 0:
            print("警告: 仍存在空值，请检查数据源")
    else:
        print(f"关键列 '{target_column}' 不存在，可用列：{list(final_df.columns)}")

    # 自动填充空白列名（优化版）
    new_columns = []
    counter = 0
    for col in final_df.columns:
        # 处理空值或默认生成的 Unnamed 列
        if pd.isna(col) or str(col).strip() in ('', 'Unnamed: 0'):
            new_col = f"column_{counter}"
            counter += 1
        else:
            new_col = col
        
        # 统一中文列名（示例：包含 "Line" 的列重命名为 "料台标题"）
        if 'Line' in str(new_col):
            new_col = '料台标题'
        
        new_columns.append(new_col)

    final_df.columns = new_columns

    # 验证列名是否存在（若缺失则动态创建空列）
    required_columns = ["料台标题", "料台左右", "料槽", "供料器类型", "column_8", "元件", "间距"]
    for col in required_columns:
        if col not in final_df.columns:
            final_df[col] = None  # 创建空列或填充默认值

    # 正确选择多列（使用列表语法）
    end_df = final_df[required_columns]

    # 打印结果验证
    # print("\n最终列名:", end_df.columns.tolist())
    # print(end_df.head())



    
    # 保存结果
    end_df.to_csv("output.csv", index=False, encoding='utf-8-sig')
    print("处理完成，已保存到 output.csv")
else:
    print("警告: 无有效数据块可合并！")