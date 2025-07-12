import pandas as pd
import glob,os

# 读取文件（注意文件路径和编码）
bom_folder = os.path.join(os.getcwd(), '导出文件')  # 获取西门子导出文件放置的文件路径
files = glob.glob(
    os.path.join(bom_folder, '*.xls')  # 匹配模式：任意xlsx文件
)
file_path = files[0]
# 读取Excel文件（假设文件路径正确）
df = pd.read_excel(file_path, sheet_name='Sheet1', header=None)
# 定义两个条件
condition_cols = df.iloc[:, 0].isna() & df.iloc[:, 1].isna()  # 第0、1列同时为空
condition_ratio = df.notna().sum(axis=1) / df.shape[1] < 0.1  # 非空占比 < 0.1

# 组合条件：同时满足则删除
mask = condition_cols & condition_ratio
df_filtered = df[~mask]  # 取反保留不满足条件的行

# 步骤2：删除全为空值的列
df_cleaned = df_filtered.dropna(axis=1, how='all')



# import pandas as pd

# # 读取Excel文件（假设文件名为test.xlsx，数据在Sheet1）
# df = pd.read_excel('test.xlsx', sheet_name='Sheet1', header=None)

df = df_cleaned.copy()

# 预处理：按行填充空白单元格（axis=0，默认值）
df.fillna(method='ffill', axis=0, inplace=True)

# 新增逻辑：用递增数字填充剩余空白（仅限数值列）
for col in df.columns:
    if pd.api.types.is_numeric_dtype(df[col]):
        df[col] = df[col].fillna(lambda x: range(1, len(x)+1))

# 创建区块分组键（遇到Line行时键值递增）
df['group_key'] = df[0].str.startswith('Line').cumsum()

# 分组处理
groups = []
for key, group in df.groupby('group_key'):
    # 找到料槽行（表头）
    header_row = group[group[0] == '料槽'].index[0]
    
    # 提取表头（需处理多级表头）
    headers = group.iloc[header_row].tolist()
    headers = [str(h) for h in headers if str(h) != 'nan']
    
    # 提取数据行
    data_rows = group.iloc[header_row+1:, :len(headers)]
    
    # 构建结构化数据
    block_data = []
    for _, row in data_rows.iterrows():
        row_data = {}
        for i, value in enumerate(row):
            if pd.notna(value):
                row_data[headers[i]] = str(value).strip()
        block_data.append(row_data)
    
    # 提取区块元信息
    block_meta = {
        '区块名称': group.iloc[0, 0],
        '设备类型': group.iloc[1, 0],
        '供料器配置': block_data
    }
    
    groups.append(block_meta)

# 输出结果
print(groups)
