import xlrd
import pandas as pd
import glob,os

def process_merged_cells_xls(file_path, sheet_name):
    """使用 xlrd 处理 .xls 合并单元格"""
    workbook = xlrd.open_workbook(file_path)
    sheet = workbook.sheet_by_name(sheet_name)
    
    # 获取合并单元格信息 (xlrd行/列从0开始)
    merged_regions = []
    for merged_range in sheet.merged_cells:
        min_row, max_row, min_col, max_col = merged_range
        value = sheet.cell_value(min_row, min_col)
        merged_regions.append((min_row, max_row, min_col, max_col, value))
    
    # 填充合并值到所有单元格
    data = []
    for row_idx in range(sheet.nrows):
        row_data = []
        for col_idx in range(sheet.ncols):
            cell_value = sheet.cell_value(row_idx, col_idx)
            # 检查是否在合并区域中
            for (m_min_row, m_max_row, m_min_col, m_max_col, m_value) in merged_regions:
                if (m_min_row <= row_idx < m_max_row) and (m_min_col <= col_idx < m_max_col):
                    cell_value = m_value
                    break
            row_data.append(cell_value)
        data.append(row_data)
    return data

def extract_data_blocks(data):
    """提取数据块（与之前代码逻辑一致）"""
    blocks = []
    current_block = None
    headers = []
    for row in data:
        if row and isinstance(row[0], str) and row[0].startswith('Line'):
            if current_block:
                blocks.append(current_block)
            current_block = {
                'title': row[0],
                'headers': [],
                'rows': []
            }
            headers = []
        elif current_block:
            if not current_block['headers'] and any('供料器' in str(cell) for cell in row):
                current_block['headers'] = [str(cell).strip() for cell in row]
            else:
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
data_blocks = extract_data_blocks(data)

# 转换为 DataFrame
dfs = []
for block in data_blocks:
    if block['headers'] and block['rows']:
        df = pd.DataFrame(block['rows'], columns=block['headers'])
        df['料台标题'] = block['title']
        dfs.append(df)

final_df = pd.concat(dfs, ignore_index=True)
print(final_df.head())