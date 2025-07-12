import xlrd
import pandas as pd
import glob,os

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
    for row in data:
        # 宽松的标题行匹配（允许 "Line" 出现在任意位置）
        if row and any(isinstance(cell, str) and 'Line' in cell for cell in row):
            if current_block:
                blocks.append(current_block)
            title_cell = next(cell for cell in row if isinstance(cell, str) and 'Line' in cell)
            current_block = {
                'title': title_cell,
                'headers': [],
                'rows': []
            }
        elif current_block:
            # 列头匹配实际关键词（如 "类型"）
            if not current_block['headers'] and any('类型' in str(cell) for cell in row):
                current_block['headers'] = [str(cell).strip() for cell in row]
            else:
                # 过滤完全空的行
                if any(cell is not None for cell in row):
                    current_block['rows'].append(row)
    if current_block:
        blocks.append(current_block)
    return blocks

# 使用示例

# 读取文件（注意文件路径和编码）
bom_folder = os.path.join(os.getcwd(), '导出文件')  # 获取西门子导出文件放置的文件路径
files = glob.glob(
    os.path.join(bom_folder, '*.xls')  # 匹配模式：任意xlsx文件
)
file_path = files[0]
# file_path = 'Report_L1.xls'
data = process_merged_cells_xls(file_path, 'Sheet1')

# 打印前10行数据，验证处理结果
print("==== 前10行数据 ====")
for idx, row in enumerate(data[:10]):
    print(f"行 {idx}: {row}")

data_blocks = extract_data_blocks(data)
print("提取到的数据块数量:", len(data_blocks))

# 转换为 DataFrame
dfs = []
for block in data_blocks:
    if block.get('headers') and block.get('rows'):
        df = pd.DataFrame(block['rows'], columns=block['headers'])
        df['料台标题'] = block['title']
        dfs.append(df)
    else:
        print("跳过无效块:", block)

if dfs:
    final_df = pd.concat(dfs, ignore_index=True)
    final_df.to_csv("1.csv")
    # print(final_df.head())
else:
    print("警告: 无有效数据块可合并，请检查数据提取逻辑！")