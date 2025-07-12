# 运行命令
# waitress-serve --host=0.0.0.0 --port=80 app:app
# 打包运行命令（保持不变）
# pyinstaller --onefile --add-data "templates;templates" --add-data "static;static" app.py
from flask import Flask, render_template, jsonify, request, send_from_directory
import datetime
import time
import sys, os
import random
import logging
import sqlite3
from sqlite3 import connect
from contextlib import contextmanager
from urllib.parse import quote
from queue import Queue
import threading
from waitress import serve

test_flag = 1 # 1表示使用真实数据库数据，0表示模拟数据
# 配置日志系统
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)



# 动态获取模板路径
def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)



# 初始化Flask（指定模板路径）
app = Flask(
    __name__,
    template_folder=resource_path('templates')
)

# 配置信息
SITE_CONFIG = {
    "COMPANY_NAME": "乔芯科技有限公司",
    "DEFAULT_LINE_SERIAL": "一",
    "DEFAULT_DIRECTION": "",
    "DEFAULT_SHIFT_WORK": False,
}

# 看板类型配置
BOARD_CONFIGS = {
    "dieBonding": {
        "columns": [
            {"label": "PCB编码", "prop": "pcbId"},
            {"label": "机台号", "prop": "devId"},
            {"label": "要板时间", "prop": "askPcbTime", "formatter": "time"},
            {"label": "到达时间", "prop": "pcbArriveTime", "formatter": "time"},
            {"label": "出板时间", "prop": "pcbOutTime", "formatter": "time"},
            {"label": "用户名", "prop": "userName"},
            {"label": "固晶开始时间", "prop": "startTime", "formatter": "time"},
            {"label": "固晶结束时间", "prop": "finishTime", "formatter": "time"},
            {"label": "固晶速度", "prop": "speedAverage"},
            {"label": "已固数", "prop": "bondOk"},
            {"极客时间标签": "漏固数", "prop": "missBond"},
            {"label": "漏取数", "prop": "missTake"},
            {"label": "报警次数", "prop": "alarmCount"},
            {"label": "异常处理时间", "prop": "brokeTime"},
            {"label": "开机空闲时间", "prop": "freeTime"},
            {"label": "完成率", "prop": "cRate"},
        ],
        "meta": {"title": "固晶"},
    },
    "priming": {
        "columns": [
            {"label": "时段", "prop": "timeFrame"},
            {"label": "数量", "prop": "quantity"},
            {"label": "不良数", "prop": "defectQuantity"},
            {"label": "不良率", "prop": "defectRate"},
            {"label": "生产人数", "prop": "peopleNum"},
        ],
        "meta": {"title": "底涂"},
    },
    "taping": {
        "columns": [
            {"label": "时段", "prop": "timeFrame"},
            {"label": "数量", "prop": "quantity"},
            {"label": "不良数", "prop": "defectQuantity"},
            {"label": "不良率", "prop": "defectRate"},
            {"label": "生产人数", "prop": "peopleNum"},
        ],
        "meta": {"title": "贴膜"},
    },
    "printing": {
        "columns": [
            {"label": "时段", "prop": "timeFrame"},
            {"label": "数量", "prop": "quantity"},
            {"label": "不良数", "prop": "defectQuantity"},
            {"label": "不良率", "prop": "defectRate"},
            {"label": "生产人数", "prop极客时间": "peopleNum"},
        ],
        "meta": {"title": "印刷"},
    },
    "rework": {
        "columns": [
            {"label": "时段", "prop": "timeFrame"},
            {"label": "点亮外观数量", "prop": "illumeQuantity"},
            {"label": "直通率", "prop": "firstPassRate"},
            {"label": "返修数量", "prop": "reworkQuantity"},
            {"label": "一次通过率", "prop": "onetimePassRate"},
            {"label": "不良率", "prop": "defectRate"},
        ],
        "meta": {"title": "返修"},
    },
    "smt": {
        "columns": [
            {"label": "时段", "prop": "timeFrame"},
            {"label": "数量", "prop": "quantity"},
            {"label": "不良数", "prop": "defectQuantity"},
            {"label": "不良率", "prop": "defectRate"},
            {"label": "生产人数", "prop": "peopleNum"},
        ],
        "meta": {"title": "SMT"},
    },
    "shrinkage": {
        "columns": [
            {"label": "时段", "prop": "timeFrame"},
            {"label": "规格", "prop": "size", "formatter": "array"},
            {"label": "数量", "prop": "quantity", "formatter": "array"},
            {"label": "不良数", "prop": "defectQuantity"},
            {"label": "不良率", "prop": "defectRate"},
            {"label": "生产人数", "prop": "peopleNum"},
        ],
        "meta": {"title": "涨缩"},
    },
}


# 时间框架定义
TIME_FRAME = [
    "08:00-10:00", "10:00-12:00", "12:00-14:00", "14:00-16:00", 
    "16:00-18:00", "18:00-20:00", "20:00-22:00", "22:00-00:00",
    "00:00-02:00", "02:00-04:00", "04:00-06:00", "06:00-08:00"
]

# ============== SQLite连接池 (关键优化) ==============
class SQLiteConnectionPool:
    def __init__(self, max_connections=5):
        self.pool = Queue(maxsize=max_connections)
        for _ in range(max_connections):
            conn = connect('production_data.db', check_same_thread=False)
            self.pool.put(conn)

    @contextmanager
    def get_conn(self):
        conn = self.pool.get()
        try:
            yield conn
        finally:
            self.pool.put(conn)

# 全局连接池实例
DB_POOL = SQLiteConnectionPool(max_connections=10)

# ============== 远程数据库连接管理 ==============
def encoded_path(lujing):
    encoded_path = quote(lujing.replace('\\', '/'), safe='')
    return f"file:{encoded_path}?mode=ro"

# 线体与数据库映射配置
LINE_DB_MAPPING = {
    "固晶一线": (r"\\DESKTOP-REFU2A1\db\ldbPd.db", [f"{i:02d}-L" for i in range(1, 14)]),
    "固晶二线": (r"\\DESKTOP-REFU2A1\db\ldbPd.db", [f"{i:02d}-R" for i in range(1, 14)]),
    "固晶三线": (r"\\DESKTOP-REFU2A0\asmade_messerver\ldbPd.db", [f"{i:02d}-L" for i in range(1, 14)]),
    "固晶四线": (r"\\DESKTOP-REFU2A0\asmade_messerver\ldbPd.db", [f"{i:02d}-R" for i in range(1, 14)]),
    "固晶五线": (r"\\DESKTOP-I17GN86\asmade_messerver\ldbPd.db", [f"{i:02d}-L" for i in range(1, 14)]),
    "固晶六线": (r"\\DESKTOP-I17GN86\asmade_messerver\ldbPd.db", [f"{i:02d}-R" for i in range(1, 14)]),
}

@contextmanager
def db_die_connection(uri):
    """上下文管理器用于安全处理远程数据库连接"""
    conn = None
    try:
        conn = sqlite3.connect(uri, timeout=10, uri=True)
        # conn.execute("PRAGMA journal_mode=WAL;")
        # conn.execute("PRAGMA busy_timeout=5000;")
        yield conn
    except sqlite3.Error as e:
        logger.error(f"数据库连接错误: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()



# 生成固晶数据 - 修复时间格式, 增加线号支持
def generate_die_bonding_data(line_serial="一", count=13):
    data = []
    for i in range(1, count+1):
        # 创建随机偏移时间
        time_offset = random.randint(0, 120)  # 随机时间偏移0-120分钟
        base_time = datetime.datetime.now() - datetime.timedelta(minutes=time_offset)
        pcb_prefix = "QKBM"
        
        data.append({
            "pcbId": f"{pcb_prefix}5101G125052100{str(i).zfill(3)}",
            "devId": f"{str(i).zfill(2)}-L",
            "askPcbTime": base_time.strftime("%Y-%m-%d %H:%M:%S"),
            "pcbArriveTime": (base_time + datetime.timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S"),
            "pcbOutTime": (base_time + datetime.timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S"),
            "userName": f"操作员{random.randint(1, 5)}",
            "startTime": (base_time + datetime.timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S"),
            "finishTime": (base_time + datetime.timedelta(minutes=28)).strftime("%Y-%m-%d %H:%M:%S"),
            "speedAverage": str(random.randint(90, 120)),
            "bondOk": random.randint(20, 30),
            "missBond": random.randint(0, 2),
            "missTake": random.randint(0, 1),
            "alarmCount": random.randint(0, 5),
            "brokeTime": f"00:{str(random.randint(0,10)).zfill(2)}:00",
            "freeTime": f"00:{str(random.randint(0,5)).zfill(2)}:00",
            "cRate": f"{random.randint(95, 100)}%",
            "dutyId": f"DUTY{str(random.randint(1,3)).zfill(3)}",
            "lineSerial": line_serial,  # 添加线号信息
        })
    return data
# # 生成通用数据 - 修复格式错误
def generate_test_data(count=12, board_type="priming"):
    data = []
    for i in range(count):
        if board_type == "shrinkage":
            # 涨缩线体的特殊数据结构
            item = {
                "timeFrame": TIME_FRAME[i],
                "size": ["±10um", "±20um", "±30um"],
                "quantity": [
                    random.randint(50, 100),
                    random.randint(100, 150),
                    random.randint(150, 200)
                ],
                "defectQuantity": random.randint(0, 10),
                "defectRate": f"{random.uniform(0.5, 5.0):.1f}%",
                "peopleNum": random.randint(1, 5)
            }
        elif board_type == "rework":
            # 返修线体的特殊数据结构
            item = {
                "timeFrame": TIME_FRAME[i],
                "illumeQuantity": random.randint(180, 220),
                "firstPassRate": f"{random.uniform(90.0, 99.9):.1f}%",
                "reworkQuantity": random.randint(1, 15),
                "onetimePassRate": f"{random.uniform(85.0, 95.0):.1f}%",
                "defectRate": f"{random.uniform(0.5, 5.0):.1f}%",
            }
        else:
            # 其他通用线体的数据结构
            item = {
                "timeFrame": TIME_FRAME[i],
                "quantity": random.randint(150, 250), 
                "defectQuantity": random.randint(0, 10),
                "defectRate": f"{random.uniform(0.5, 5.0):.1f}%",
                "peopleNum": random.randint(1, 5)
            }
            
        data.append(item)
    return data


# ============== 固晶线体数据获取函数 ==============
def generate_die_bonding_True_data(line_serial="一"):
    """从远程数据库获取固晶线体实时数据"""
    if line_serial not in LINE_DB_MAPPING:
        logger.error(f"未知线体配置: {line_serial}")
        return []

    db_path, devices = LINE_DB_MAPPING[line_serial]
    uri = encoded_path(db_path)
    data = []
    
    try:
        with db_die_connection(uri) as conn:
            cursor = conn.cursor()
            for dev_id in devices:
                try:
                    cursor.execute(
                        'SELECT pcbId, devId, askPcbTime, pcbArriveTime, pcbOutTime, userName, '
                        'startTime, finishTime, speedAverage, bondOk, missBond, missTake, '
                        'alarmCount, brokeTime, freeTime, cRate, dutyId '
                        'FROM ldbPd WHERE devId = ? ORDER BY id DESC LIMIT 1;',
                        (dev_id,)
                    )
                    row = cursor.fetchone()
                    if row:
                        data.append({
                            "pcbId": row[0], "devId": row[1], "askPcbTime": row[2],
                            "pcbArriveTime": row[3], "pcbOutTime": row[4], "userName": row[5],
                            "startTime": row[6], "finishTime": row[7], "speedAverage": row[8],
                            "bondOk": row[9], "missBond": row[10], "missTake": row[11],
                            "alarmCount": row[12], "brokeTime": row[13], "freeTime": row[14],
                            "cRate": row[15], "dutyId": row[16], "lineSerial": line_serial
                        })
                    else:
                        # 无数据时返回空记录
                        data.append(create_empty_die_bonding_record(dev_id, line_serial))
                except sqlite3.Error as e:
                    logger.error(f"设备 {dev_id} 查询失败: {str(e)}")
                    data.append(create_empty_die_bonding_record(dev_id, line_serial))
    except Exception as e:
        logger.error(f"固晶线体数据获取失败: {str(e)}")
        # 返回所有设备的空记录
        for dev_id in devices:
            data.append(create_empty_die_bonding_record(dev_id, line_serial))
    
    return data

def create_empty_die_bonding_record(dev_id, line_serial):
    """创建空数据记录模板"""
    return {
        "pcbId": '', "devId": dev_id, "askPcbTime": '',
        "pcbArriveTime": '', "pcbOutTime": '', "userName": '',
        "startTime": '', "finishTime": '', "speedAverage": '',
        "bondOk": '', "missBond": '', "missTake": '',
        "alarmCount": '', "brokeTime": '', "freeTime": '',
        "cRate": '', "dutyId": '', "lineSerial": line_serial
    }


def generate_general_data(count=12, board_type="priming"):
    # 定义各板型的数据字段配置 [1,5](@ref)
    BOARD_CONFIG = {
        "shrinkage": {
            "fields": [
                ("数量", "quantity", 3),  # (表头, 数据键, 查询条数)
                ("不良数", "defectQuantity", 1),
                ("不良率", "defectRate", 1),
                ("生产人数", "peopleNum", 1)
            ],
            "post_process": lambda item: {
                "timeFrame": item["timeFrame"],
                "size": ["±10um", "±20um", "±30um"],
                "quantity": item["quantity"],
                "defectQuantity": item["defectQuantity"][0] if item["defectQuantity"] else 0,
                "defectRate": item["defectRate"][0] if item["defectRate"] else 0,
                "peopleNum": item["peopleNum"][0] if item["peopleNum"] else 0
            }
        },
        "rework": {
            "fields": [
                ("点亮外观数量", "illumeQuantity", 1),
                ("直通率", "firstPassRate", 1),
                ("返修数量", "reworkQuantity", 1),
                ("一次通过率", "onetimePassRate", 1),
                ("不良率", "defectRate", 1)
            ],
            "post_process": lambda item: {**item, "timeFrame": item["timeFrame"]}
        },
        "default": {
            "fields": [
                ("数量", "quantity", 1),
                ("不良数", "defectQuantity", 1),
                ("不良率", "defectRate", 1),
                ("生产人数", "peopleNum", 1)
            ],
            "post_process": lambda item: {**item, "timeFrame": item["timeFrame"]}
        }
    }

    config = BOARD_CONFIG.get(board_type, BOARD_CONFIG["default"])
    data = []

    with DB_POOL.get_conn() as conn:
        cursor = conn.cursor()
        for time_frame in TIME_FRAME[:count]:  # 只处理指定数量的时段
            item = {"timeFrame": time_frame}
            
            # 统一查询所有字段 [5,8](@ref)
            for header, key, limit in config["fields"]:
                cursor.execute(
                    'SELECT value FROM board_data '
                    'WHERE board_type=? AND header=? AND time_frame=? '
                    'ORDER BY save_time DESC LIMIT ?',
                    (board_type, header, time_frame, limit)
                )
                result = [row[0] for row in cursor.fetchall()]
                item[key] = result if limit > 1 else (result[0] if result else 0)
            
            # 特殊数据结构后处理
            processed_item = config["post_process"](item)
            data.append(processed_item)
    
    return data
  

# ============== 心跳监控线程 (新增) ==============
def heartbeat_monitor():
    """监控应用健康状态，每分钟记录心跳"""
    while True:
        logger.info("心跳检测: 服务运行正常")
        time.sleep(60)

# 启动心跳线程
threading.Thread(target=heartbeat_monitor, daemon=True).start()

# ============== 页面渲染函数 ==============
def render_board_page(board_type, line_serial=None, direction=None, is_shift_work=None, template_name='index.html'):
    config = BOARD_CONFIGS[board_type]
    
    # 设置页面标题和内容
    title = f"{config['meta']['title']} — {SITE_CONFIG['COMPANY_NAME']}"
    
    # 固晶看板单独处理线号显示
    if board_type == "dieBonding":
        line_display = "一" if line_serial == "一" else line_serial
        proline_name = f"{config['meta']['title']}{line_display}线"
    else:
        proline_name = f"{config['meta']['title']}线"
    
    # 当前时间
    now = datetime.datetime.now()
    current_time = {
        "time_frame": get_time_frame_of_day(now.hour),
        "date": now.strftime("%Y年%m月%d日"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": get_day_of_week()
    }
    return render_template(
        template_name,
        company_name=SITE_CONFIG['COMPANY_NAME'],
        title=title,
        proline_name=proline_name,
        current_time=current_time,
        board_type=board_type,
        is_shift_work=is_shift_work,
        line_serial=line_serial
    )

# ============== 路由定义 ==============
@app.route('/')
def index():
    return render_board_page('dieBonding', line_serial='一')

# 固晶线路由组
@app.route('/die-bonding')
def die_bonding():
    """固晶一线默认页面"""
    return render_board_page('dieBonding', line_serial='一')

@app.route('/die-bonding/second')
def die_bonding_second():
    """固晶二线页面"""
    return render_board_page('dieBonding', line_serial='二')

@app.route('/die-bonding/third')
def die_bonding_third():
    """固晶三线页面"""
    return render_board_page('dieBonding', line_serial='三')

@app.route('/die-bonding/fourth')
def die_bonding_fourth():
    """固晶四线页面"""
    return render_board_page('dieBonding', line_serial='四')

@app.route('/die-bonding/fifth')
def die_bonding_fifth():
    """固晶五线页面"""
    return render_board_page('dieBonding', line_serial='五')

@app.route('/die-bonding/sixth')
def die_bonding_sixth():
    """固晶六线页面"""
    return render_board_page('dieBonding', line_serial='六')

# 底涂看板路由
@app.route('/priming')
def priming():
    return render_board_page('priming')

# 贴膜看板路由
@app.route('/taping')
def taping():
    return render_board_page('taping')

# 印刷看板路由
@app.route('/printing')
def printing():
    return render_board_page('printing')

# 返修看板路由
@app.route('/rework')
def rework():
    return render_board_page('rework')

# SMT看板路由
@app.route('/smt')
def smt():
    return render_board_page('smt')

# 涨缩看板路由 - 使用专用模板
@app.route('/shrinkage')
def shrinkage():
    return render_board_page('shrinkage', template_name='shrinkage.html')

# ============== API接口 (添加超时检测) ==============
@app.route('/api/board-data')
def board_data():
    start_time = time.time()
    board_type = request.args.get('boardType', 'dieBonding')
    is_shift_work = request.args.get('isShiftWork', 'false') == 'true'
    line_serial = request.args.get('boardName', '')
    
    try:
        if board_type == "dieBonding":
            data = generate_die_bonding_True_data(line_serial) if test_flag else generate_die_bonding_data(line_serial)
        else:
            if test_flag:
                data = generate_general_data(count=6 if is_shift_work else 12, board_type=board_type)
            else:
                data = generate_test_data(count=6 if is_shift_work else 12, board_type=board_type)
    except Exception as e:
        logger.error(f"数据生成失败: {str(e)}")
        data = []  # 返回空数据避免前端卡死
    
    # 记录慢查询
    if time.time() - start_time > 2:  # 超过2秒视为慢查询
        logger.warning(f"API响应缓慢: {time.time()-start_time:.2f}s, 板型={board_type}")
    
    return jsonify(data)

@app.route('/current_time')
def current_time():
    now = datetime.datetime.now()
    return jsonify({
        "time_frame": get_time_frame_of_day(now.hour),
        "date": now.strftime("%Y年%m月%d日"),
        "time": now.strftime("%H:%M"),
        "weekday": get_day_of_week()
    })

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

# 图片组数据 (5组，每组3张图片)
IMAGE_GROUPS = {
    'zoulang1': ['6s1.jpg', 'pro1.png', 'qua1.png'],
    'zoulang2': ['6s2.jpg', 'pro2.png', 'qua2.png'],
    'zoulang3': ['6s3.jpg', 'pro3.png', 'qua3.png'],
    'zoulang4': ['6s4.jpg', 'pro4.png', 'qua4.png'],
    'zoulang5': ['6s5.jpg', 'pro5.png', 'qua5.png']
}
# 图片模板路由
@app.route('/<group_name>')
def show_images(group_name):
    if group_name not in IMAGE_GROUPS:
        return "Invalid group name", 404
    
    # 添加时间戳参数防止缓存问题
    timestamp = int(datetime.datetime.now().timestamp())
    images = [f"/static/img/{img}?v={timestamp}" for img in IMAGE_GROUPS[group_name]]
    
    return render_template('carousel.html', images=images)



# ============== 辅助函数 ==============
def get_time_frame_of_day(hour):
    if 0 <= hour < 6:
        return "凌晨"
    elif 6 <= hour < 8:
        return "早上"
    elif 8 <= hour < 12:
        return "上午"
    elif 12 <= hour < 14:
        return "中午"
    elif 14 <= hour < 19:
        return "下午"
    else:
        return "晚上"
# 获取星期几
def get_day_of_week():
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    return weekdays[datetime.datetime.today().weekday()]

if __name__ == '__main__':
    serve(
        app,
        host="0.0.0.0",
        port=80,
        threads=16,          # 增加工作线程
        channel_timeout=60,  # 超时设置
        connection_limit=1000, # 最大连接数
        asyncore_use_poll=True # 使用高效poll
    )