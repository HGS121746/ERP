import pandas as pd
import re

def diagnose_group(group):
    """诊断分组数据结构"""
    print(f"{'='*30} 诊断分组 {group.name} {'='*30}")
    print("前3行数据:")
    print(group.head(3))
    print("唯一值统计 (第0列):")
    print(group[0].unique())
    print("是否存在'料槽'行:", '料槽' in group[0].values)
    print("="*60)

def process_groups(df):
    groups = []
    for key, group in df.groupby('group_key'):
        try:
            # 诊断分组结构
            print(f"Processing Group {key}")
            print(group.head(3))
            
            # 修复点：改用 contains + 正则表达式
            header_mask = group[0].str.contains(r'^料槽$', regex=True, na=False)
            
            if header_mask.sum() == 0:
                print(f"跳过分组 {key}: 无有效表头")
                continue
                
            header_row = group[header_mask].index[0]
            
            # 表头标准化处理
            headers = group.iloc[header_row].astype(str).str.strip().tolist()
            required_headers = ['料槽', '供料器类型', '元件']
            
            if not all(h in headers for h in required_headers):
                print(f"跳过分组 {key}: 表头不完整")
                continue
                
            # 数据行提取优化
            data_rows = group.iloc[header_row+1:header_row+6]  # 最多取5行数据
            block_data = []
            
            for _, row in data_rows.iterrows():
                row_dict = {}
                for idx, value in enumerate(row):
                    if idx < len(headers) and pd.notna(value):
                        # 参数字段特殊处理
                        if headers[idx] == '参数':
                            row_dict[headers[idx]] = parse_parameters(str(value))
                        else:
                            row_dict[headers[idx]] = str(value).strip()
                if row_dict:
                    block_data.append(row_dict)
            
            # 构建区块元数据
            groups.append({
                '区块名称': group.iloc[0,0],
                '设备类型': group.iloc[1,0],
                '供料器配置': block_data
            })
            
        except Exception as e:
            print(f"处理分组 {key} 时发生错误: {str(e)}")
            continue
            
    return groups

def enhanced_preprocess(df):
    """增强数据预处理"""
    # 智能填充策略
    for col in df.columns:
        if df[col].dtype == object:
            # 文本列用前向填充
            df[col] = df[col].fillna(method='ffill')
        else:
            # 数值列用序列填充
            df[col] = df[col].fillna(pd.Series(range(1, len(df)+1)))
    
    # 合并跨行文本
    df[0] = df[0].fillna(method='ffill').astype(str)
    return df


def parse_parameters(param_str):
    """参数字段解析增强"""
    try:
        # 示例参数格式: "2 0 0 0 0 1 27"
        return [int(x) for x in param_str.split()]
    except:
        return param_str  # 保留原始值作为fallback
    

# 主程序
# 主程序
try:
    df = pd.read_excel('test.xlsx', header=None)
    
    # 关键修复：使用 contains + 正则表达式
    line_pattern = r'^Line\d+-\d+$'  # 匹配 Line1-1 格式
    df['group_key'] = (
        df[0].str.contains(line_pattern, regex=True, na=False)).cumsum()
    
    
    # 4. 处理分组
    result = process_groups(df)
    
    # 5. 结果验证
    print(f"共发现 {len(result)} 个有效区块")
    print("首个区块示例:")
    print(result[0])
    
except Exception as e:
    print(f"主流程错误: {str(e)}")


def test_regex_patterns():
    test_cases = [
        ("Line1-1", True),
        ("Line2-3", True),
        ("LineX-Y", False),
        ("Line1_2", False)
    ]
    
    for text, expected in test_cases:
        result = bool(re.match(r'^Line\d+-\d+$', text))
        print(f"Test '{text}': {'Pass' if result == expected else 'Fail'}")

test_regex_patterns()