# from sqlite3 import connect
# from contextlib import contextmanager

# @contextmanager
# def db_connection():
#     conn = connect('ldbPd.db')
#     try:
#         yield conn
#     finally:
#         conn.close()

# # 使用示例
# # with db_connection() as conn:
# #     cursor = conn.cursor()
# #     board_type = "shrinkage"
# #     i = "08:00-10:00"
# #     row = cursor.execute(
# #                         'SELECT value FROM board_data WHERE board_type=?  and header=? and time_frame=? ORDER BY save_time DESC limit 3;',
# #                     (board_type, "数量", i)
# #                 ).fetchall()
    
# #     print(row[0][0],row[1][0],row[2][0])
# with db_connection() as conn:
#     cursor = conn.cursor()

#     for i in [f"{i:02d}-R" for i in range(1, 14)]:
#         row = cursor.execute(
#                             'SELECT * FROM ldbPd WHERE devId = ? ORDER BY id DESC LIMIT 1;',
#                         (i,)
#                     ).fetchone()
#         print(row)
    


# # print([f"{i:02d}-L" for i in range(1, 14)])

import os
from sqlite3 import connect
from contextlib import contextmanager
from urllib.parse import quote
lujing = r'\\DESKTOP-REFU2A1\db\ldbPd.db'
print(os.path.abspath(lujing))  # 打印绝对路径
print(os.path.exists(lujing))    # 检查文件是否存在
encoded_path = quote(lujing.replace('\\', '/'), safe='')
uri = f"file:{encoded_path}?mode=ro"


def encoded_path(lujing):
    # lujing = r'\\DESKTOP-REFU2A1\db\ldbPd.db'
    encoded_path = quote(lujing.replace('\\', '/'), safe='')
    return f"file:{encoded_path}?mode=ro"

@contextmanager
def db_die_connection(uri1):
    conn = connect(uri1, uri=True)
    try:
        yield conn
    finally:
        conn.close()

if __name__ == '__main__':
    xLine = [f"{i:02d}-R" for i in range(1, 14)]
    with db_die_connection(encoded_path(r'\\DESKTOP-REFU2A1\db\ldbPd.db')) as conn:
        cursor = conn.cursor()
        for dev_id in xLine:  # 直接遍历 xLine 中的设备ID
            row = cursor.execute(
                'SELECT * FROM ldbPd WHERE devId = ? ORDER BY id DESC LIMIT 1;',
                (dev_id,)  # 传入设备ID如 "01-L"
            ).fetchone()
            print(row)