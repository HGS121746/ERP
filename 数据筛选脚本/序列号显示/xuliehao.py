import re


# 生成序列号列表（补零3位）
start = input("输入开始字符串：")
end = input("输入结束字符串：")


def split_letters_numbers(s):
    # 匹配末尾的连续数字，其余作为前段
    match = re.match(r'^(.*?)(\d*)$', s)
    letters = match.group(1) if match else s
    numbers = match.group(2) if match else ''
    return letters, numbers

letters1, numbers1 = split_letters_numbers(start)
letters2, numbers2 = split_letters_numbers(end)




serial_numbers = [str(letters1)+f"{i}" for i in range(int(numbers1), int(numbers2)+1)]

# 用逗号连接所有序列号
output_str = ",".join(serial_numbers)

# 写入到txt文件（路径可自定义）
with open("output.txt", "w") as file:
    file.write(output_str)

print("序列号已保存到 output.txt")