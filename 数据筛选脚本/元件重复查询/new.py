import pandas as pd
import re

# 匹配项数
key1 = 0

# 读取 Excel 文件
file_path = '待查.xlsx'
sheet_name = 'Sheet1'
file_path_sum = '总表.xlsx'
sheet_name_sum = 'Sheet1'

# 读取数据
# data = pd.read_excel(file_path, sheet_name=sheet_name, usecols='C:E', skiprows=0, nrows=13)
data = pd.read_excel(file_path, sheet_name=sheet_name)
data_sum = pd.read_excel(file_path_sum, sheet_name=sheet_name_sum)


# 分割列（正则表达式包含+匹配连续分隔符）
split_columns = data['物料描述'].str.split(r'[,/， =]+', expand=True)

# 处理空值并清理空格
split_columns = split_columns.replace({'': pd.NA}).apply(lambda col: col.str.strip())

# 动态添加非空列
for i, col in enumerate(split_columns.columns):
    if not split_columns[col].isna().all():
        data[f'物料描述_分列_{i+1}'] = split_columns[col]



# 获取分列后的列名
list1 = data.columns.tolist()[2:]
data = data.fillna("")


def is_pure_chinese(text):
    """检查字符串是否为纯中文字符（包含中文标点）"""
    pattern = re.compile(r'^[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]+$')
    return bool(pattern.fullmatch(text))

def hang_str(text, compare_list):
    compare_list = compare_list[1:]  # 跳过第一个元素
    if pd.isna(text):
        return False
    
    # 需要忽略的元器件类型关键字
    ignore_keywords = {
        'smd', 'smt', 'mlcc', 'res', 'cap', 'ind', 'led', 
        'ic', 'crystal', 'diode', 'transistor', 'chipr'
    }
    
    # 统一处理文本：小写+去空格+去±
    text_clean = str(text).lower().strip().replace('±', '')
    
    # 处理比较项
    valid_items = []
    for item in compare_list:
        if pd.notna(item) and str(item).strip():
            processed_parts = []
            # 拆分并处理每个部分
            for part in re.split(r'[\s\-_]+', str(item).lower()):
                # 过滤忽略词
                if part in ignore_keywords:
                    continue
                
                # 处理C/R前缀
                if re.match(r'^[cr]\d+$', part):
                    part = part[1:]  # 去掉首字母
                
                # 去除±符号
                part = part.replace('±', '')
                
                processed_parts.append(part)
            
            if processed_parts:
                processed_item = ''.join(processed_parts)
                # 新增：过滤纯中文项
                if not is_pure_chinese(processed_item):
                    valid_items.append(processed_item)
    
    if not valid_items:
        return False
    
    # 电容单位换算表（保持不变）
    unit_map = { 
        'μ': 1e-6, 'u': 1e-6, 'n': 1e-9, 
        'p': 1e-12, 'm': 1e-3, '': 1, 'f': 1
    }

    # 从文本提取所有电容值并转换（全小写处理）
    def extract_capacitance_values(s):
        # 模式1：三位数编码（如104p）
        pattern_code = re.compile(r'\b(\d{2})(\d)\s*([μunpm]?)f?\b', re.IGNORECASE)
        # 模式2：常规数值（如10uF）
        pattern_normal = re.compile(r'(\d+\.?\d*)\s*([μunpm]?)f?\b', re.IGNORECASE)
        
        matches = []
        
        # 匹配三位数编码（如104p）
        for match in pattern_code.finditer(s):
            first_digits, multiplier_digit, unit = match.groups()
            try:
                base = float(first_digits)
                exponent = int(multiplier_digit)
                val = base * (10 ** exponent)
                unit = unit.lower() if unit else 'p'  # 默认pF
                matches.append((val, unit))
            except:
                continue
        
        # 匹配常规数值（如10uF）
        for match in pattern_normal.finditer(s):
            val, unit = match.groups()
            try:
                matches.append((float(val), unit.lower()))
            except:
                continue
        
        # 转换为标准单位（法拉）
        converted = []
        for val, unit in matches:
            multiplier = unit_map.get(unit.lower(), 1e-12)
            converted_val = val * multiplier
            converted.append(converted_val)
        
        return converted
    
    text_cap_values = extract_capacitance_values(text_clean)
    
    matched_count = 0
    
    for item in valid_items:
        # 电容值匹配逻辑（全小写处理）
        is_capacitance = False
        item_value = None
        
        # 尝试三位数编码解析（如104p）
        code_match = re.match(r'^(\d{2})(\d)([μunpm]?)f?$', item)
        if code_match:
            first_digits, multiplier_digit, unit = code_match.groups()
            try:
                base = float(first_digits)
                exponent = int(multiplier_digit)
                val = base * (10 ** exponent)
                unit = unit.lower() if unit else 'p'  # 默认pF
                item_value = val * unit_map.get(unit, 1e-12)
                is_capacitance = True
            except:
                pass
        else:
            # 常规数值解析（如10uF）
            normal_match = re.match(r'^(\d+\.?\d*)([μunpm]?)f?$', item)
            if normal_match:
                val, unit = normal_match.groups()
                try:
                    item_value = float(val) * unit_map.get(unit.lower(), 1e-12)
                    is_capacitance = True
                except:
                    pass
        
        # 电容值匹配
        if is_capacitance and item_value is not None:
            # 允许1%的误差范围
            if any(abs(item_value - text_value) < item_value*0.01 
               for text_value in text_cap_values):
                matched_count += 1
                continue
        
        # 普通字符串匹配（全小写处理）
        if item in text_clean:
            matched_count += 1
    
    # 允许多少项不匹配
    return matched_count >= len(valid_items) - key1
# 收集所有匹配结果
all_matched = []

for i in range(len(data)):
    list2 = data.loc[i, list1].tolist()
    list2 = [item for item in list2 if item]  # 过滤空值
    
    if list2:  # 只有比较列表不为空时才进行匹配
        matched = data_sum[data_sum['描述'].apply(hang_str, compare_list=list2)]
        # 在matched中添加新列，值为list2的第一个有效元素
        if not matched.empty and len(list2) > 0:
            first_valid_item = next((item for item in list2 if item), None)  # 获取第一个非空元素
            matched = matched.assign(匹配项=first_valid_item)  # 添加新列
        if not matched.empty:
            all_matched.append(matched)

# 合并所有匹配结果
if all_matched:
    matched_data = pd.concat(all_matched).drop_duplicates()
else:
    matched_data = pd.DataFrame(columns=['描述'])  # 创建空DataFrame

# 保存结果
matched_output_file_path = 'matched_data.xlsx'
matched_data.to_excel(matched_output_file_path, index=False)

print(f"匹配结果已成功保存至 {matched_output_file_path}")