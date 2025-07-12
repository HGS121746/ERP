import sys
import datetime
import random
import sqlite3
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QComboBox, QCheckBox, QPushButton,
    QHeaderView, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor

class ProductionDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("生产数据看板")
        self.setGeometry(100, 100, 1200, 800)
        
        # 初始化数据库
        self.db_conn = self.init_database()
        
        # 初始化数据
        self.board_configs = {
            "priming": "底涂",
            "taping": "贴膜",
            "printing": "印刷",
            "rework": "返修",
            "smt": "SMT",
            "shrinkage": "涨缩"
        }
        
        self.current_board_type = "priming"  # 默认底涂看板
        self.is_shift_work = False
        
        # 创建主部件和布局
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # 添加顶部信息栏
        main_layout.addLayout(self.create_top_bar())
        
        # 添加控制面板
        main_layout.addLayout(self.create_control_panel())
        
        # 添加数据表格
        self.table = QTableWidget()
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #F0F0F0;
                gridline-color: #D0D0D0;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #E0E0E0;
                padding: 4px;
                border: 1 solid #D0D0D0;
                font-weight: bold;
            }
        """)
        self.table.verticalHeader().setVisible(False)
        main_layout.addWidget(self.table)
        
        # 设置表格横向填充铺满当前界面
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # 初始化表格（空白）
        self.setup_blank_table()
        
        # 设置定时器更新时间
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_current_time)
        self.timer.start(1000)  # 每秒更新一次
        self.update_current_time()
    
    def init_database(self):
        """初始化SQLite数据库"""
        conn = sqlite3.connect('production_data.db')
        cursor = conn.cursor()
        
        # 创建数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS board_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                board_type TEXT NOT NULL,
                time_frame TEXT NOT NULL,
                spec TEXT DEFAULT '',
                header TEXT NOT NULL,
                value TEXT NOT NULL,
                save_time DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_board_data 
            ON board_data (board_type, time_frame, spec, header)
        ''')
        
        conn.commit()
        return conn
    
    def create_top_bar(self):
        """创建顶部信息栏"""
        top_layout = QHBoxLayout()
        
        # 公司名称
        company_label = QLabel("乔芯科技有限公司")
        company_label.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        company_label.setStyleSheet("color: #303030;")
        top_layout.addWidget(company_label)
        
        # 产线名称
        self.proline_label = QLabel("底涂线")
        self.proline_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        self.proline_label.setStyleSheet("color: #204080;")
        top_layout.addWidget(self.proline_label)
        
        # 当前时间
        self.time_label = QLabel()
        self.time_label.setFont(QFont("Microsoft YaHei", 10))
        self.time_label.setStyleSheet("color: #606060;")
        top_layout.addWidget(self.time_label)
        
        top_layout.addStretch()
        
        return top_layout
    
    def create_control_panel(self):
        """创建控制面板"""
        control_layout = QHBoxLayout()
        
        # 看板类型选择
        board_layout = QHBoxLayout()
        board_layout.addWidget(QLabel("看板类型:"))
        self.board_combo = QComboBox()
        for key, value in self.board_configs.items():
            self.board_combo.addItem(value, key)
        self.board_combo.setCurrentIndex(0)
        self.board_combo.currentIndexChanged.connect(self.board_type_changed)
        board_layout.addWidget(self.board_combo)
        control_layout.addLayout(board_layout)
        
        # 班次模式
        self.shift_checkbox = QCheckBox("两班倒模式")
        self.shift_checkbox.stateChanged.connect(self.shift_work_changed)
        control_layout.addWidget(self.shift_checkbox)
        
        control_layout.addStretch()
        
        # 保存按钮
        save_button = QPushButton("保存数据")
        save_button.clicked.connect(self.save_current_data)
        control_layout.addWidget(save_button)
        
        # 加载按钮
        load_button = QPushButton("加载最新数据")
        load_button.clicked.connect(self.load_latest_data)
        control_layout.addWidget(load_button)
        
        return control_layout
    
    def update_current_time(self):
        """更新当前时间"""
        now = datetime.datetime.now()
        time_frame = self.get_time_frame_of_day(now.hour)
        weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][now.weekday()]
        
        time_str = f"{time_frame}好 {now.strftime('%Y年%m月%d日 %H:%M:%S')} {weekday}"
        self.time_label.setText(time_str)
    
    def get_time_frame_of_day(self, hour):
        """获取时间段描述"""
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
    
    def board_type_changed(self, index):
        """切换看板类型"""
        self.current_board_type = self.board_combo.currentData()
        # 清空表格并重新初始化
        self.table.clear()
        self.table.clearSpans()  # 清除所有合并的单元格
        self.setup_blank_table()
        self.proline_label.setText(self.board_combo.currentText() + "线")
    
    def shift_work_changed(self, state):
        """切换班次模式"""
        self.is_shift_work = (state == Qt.Checked)
        # 清空表格并重新初始化
        self.table.clear()
        self.table.clearSpans()  # 清除所有合并的单元格
        self.setup_blank_table()
    
    def setup_blank_table(self):
        """设置带时段的空白表格"""
        # 设置表头
        headers = self.get_headers_for_board()
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        
        # 设置行数
        row_count = self.get_row_count()
        self.table.setRowCount(row_count)
        
        # 填充时段列并合并单元格
        if self.current_board_type == "shrinkage":
            # 涨缩看板 - 每三行一个时段
            for time_idx in range(0, row_count // 3):
                start_row = time_idx * 3
                time_frame = self.generate_time_frame(time_idx)
                
                # 设置时段单元格并合并
                self.table.setItem(start_row, 0, QTableWidgetItem(time_frame))
                self.table.setSpan(start_row, 0, 3, 1)  # 合并3行1列
                
                # 设置规格
                sizes = ["±10um", "±20um", "±30um"]
                for i in range(3):
                    self.table.setItem(start_row + i, 1, QTableWidgetItem(sizes[i]))
                
                # 合并不良数列
                self.table.setItem(start_row, 3, QTableWidgetItem(""))
                self.table.setSpan(start_row, 3, 3, 1)
                
                # 合并不良率列
                self.table.setItem(start_row, 4, QTableWidgetItem(""))
                self.table.setSpan(start_row, 4, 3, 1)
                
                # 合并生产人数列
                self.table.setItem(start_row, 5, QTableWidgetItem(""))
                self.table.setSpan(start_row, 5, 3, 1)
        else:
            # 其他看板 - 每行一个时段
            for row in range(row_count):
                time_frame = self.generate_time_frame(row)
                self.table.setItem(row, 0, QTableWidgetItem(time_frame))
        
        # 调整列宽 - 确保表格横向填充铺满当前界面
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    
    def get_row_count(self):
        """获取当前看板类型的行数"""
        if self.current_board_type == "shrinkage":
            # 涨缩界面每个时间段有三行（每个规格一行）
            return (6 if self.is_shift_work else 12) * 3
        return 6 if self.is_shift_work else 12
    
    def get_headers_for_board(self):
        """根据看板类型获取表头"""
        if self.current_board_type == "rework":
            return ["时段", "点亮外观数量", "直通率", "返修数量", "一次通过率", "不良率"]
        
        elif self.current_board_type == "shrinkage":
            return ["时段", "规格", "数量", "不良数", "不良率", "生产人数"]
        
        else:  # 其他通用类型
            return ["时段", "数量", "不良数", "不良率", "生产人数"]
    
    def generate_time_frame(self, index):
        """生成时间段文本"""
        # 修复了非两班倒模式下超出预期时段的问题
        base_hour = 8
        total_rows = 6 if self.is_shift_work else 12
        
        # 确保索引在合理范围内
        if index >= total_rows:
            index = total_rows - 1
            
        if self.is_shift_work:
            if index < 6:
                base_hour = 8
            else:
                base_hour = 20
                index -= 6
        else:
            base_hour = 8
        
        # 确保开始时间在0-23点范围内
        start_hour = (base_hour + index * 2) % 24
        end_hour = (start_hour + 2) % 24
        
        # 调整24点为00点
        start_text = f"00:00" if start_hour == 0 else f"{start_hour:02d}:00"
        end_text = f"00:00" if end_hour == 0 else f"{end_hour:02d}:00"
        end_text = end_text if end_hour != 24 else "00:00"
        
        return f"{start_text}-{end_text}"
    
    def save_current_data(self):
        """保存当前表格数据到数据库"""
        try:
            cursor = self.db_conn.cursor()
            save_time = datetime.datetime.now()
            current_time_frame = ""
            total_rows = self.table.rowCount()

            # 清空当前看板的旧数据
            cursor.execute('''
                DELETE FROM board_data 
                WHERE board_type = ?
            ''', (self.current_board_type,))

            # 记录保存的行列信息（用于调试）
            saved_data = []
            
            for row in range(total_rows):
                # 获取时段（处理合并单元格）
                if self.current_board_type == "shrinkage":
                    if row % 3 == 0:
                        time_frame_item = self.table.item(row, 0)
                        current_time_frame = time_frame_item.text() if time_frame_item else ""
                    time_frame = current_time_frame
                else:
                    time_frame_item = self.table.item(row, 0)
                    time_frame = time_frame_item.text().strip() if time_frame_item else ""
                    # 确保时段格式正确（重要！）
                    if not self.is_valid_time_frame(time_frame):
                        time_frame = self.generate_time_frame(row)

                for col in range(self.table.columnCount()):
                    # 确保每个单元格都有QTableWidgetItem
                    if self.table.item(row, col) is None:
                        self.table.setItem(row, col, QTableWidgetItem(""))
                        
                    item = self.table.item(row, col)
                    value = item.text().strip() if item and item.text() else ""
                    header = self.table.horizontalHeaderItem(col).text().strip()
                    
                    # 对于规格列进行特殊处理
                    spec = ""
                    if self.current_board_type == "shrinkage" and col == 1:
                        # 规格列使用单元格的实际值
                        spec = value
                    
                    # 记录保存的信息
                    saved_data.append((row, col, value))
                    
                    # 保存所有值，包括空白
                    cursor.execute('''
                        INSERT INTO board_data 
                        (board_type, time_frame, spec, header, value, save_time)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (self.current_board_type, time_frame, spec, header, value, save_time))
            
            self.db_conn.commit()
            
            # 打印保存的行列信息（调试用）
            print(f"保存完成，共保存 {len(saved_data)} 个单元格:")
            for i, (row, col, value) in enumerate(saved_data[:10]):  # 只显示前10条
                print(f"  {row}x{col}: {value}")
            
            QMessageBox.information(self, "保存成功", 
                                f"{self.board_configs[self.current_board_type]}数据已保存！")
        
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存数据时出错: {str(e)}")
    
    def is_valid_time_frame(self, time_frame):
        """验证时段格式是否正确"""
        if not time_frame:
            return False
        parts = time_frame.split('-')
        if len(parts) != 2:
            return False
        try:
            for part in parts:
                time_parts = part.split(':')
                if len(time_parts) != 2:
                    return False
                hour = int(time_parts[0])
                minute = int(time_parts[1])
                if hour < 0 or hour > 23 or minute != 0:
                    return False
        except:
            return False
        return True
    
    def load_latest_data(self):
        """从数据库加载最新数据"""
        try:
            cursor = self.db_conn.cursor()
            self.clear_table_content()
            
            # 获取当前看板的所有数据
            cursor.execute('''
                SELECT time_frame, spec, header, value          
                FROM board_data
                WHERE board_type = ? 
                ORDER BY save_time DESC
            ''', (self.current_board_type,))
            
            # 创建数据映射：{(时段, 规格, 表头): 值}
            data_map = {}
            for row in cursor.fetchall():
                time_frame, spec, header, value = row
                key = (time_frame.strip(), spec.strip(), header.strip())
                data_map[key] = value
            
            # 填充表格
            rows_to_fill = []
            for row in range(self.table.rowCount()):
                group_start_row = (row // 3) * 3
                time_frame_item = self.table.item(group_start_row, 0)
                time_frame = time_frame_item.text().strip() if time_frame_item else ""
                
                # 对于非涨缩表，直接从当前行获取时段
                if self.current_board_type != "shrinkage":
                    time_frame_item = self.table.item(row, 0)
                    time_frame = time_frame_item.text().strip() if time_frame_item else ""
                
                for col in range(self.table.columnCount()):
                    # 确保单元格存在
                    if self.table.item(row, col) is None:
                        self.table.setItem(row, col, QTableWidgetItem(""))
                    
                    header = self.table.horizontalHeaderItem(col).text().strip()
                    
                    # 对于涨缩表，获取规格
                    spec = ""
                    if self.current_board_type == "shrinkage":
                        spec_item = self.table.item(row, 1)
                        spec = spec_item.text().strip() if spec_item else ""
                    
                    key = (time_frame, spec, header)
                    if key in data_map:
                        self.table.item(row, col).setText(data_map[key])
                        rows_to_fill.append(row)
            
            # 检查实际填充的行数
            print(f"加载完成，实际填充 {len(set(rows_to_fill))} 行数据")
            
            QMessageBox.information(self, "加载成功", "已加载最新数据!")
        
        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"加载数据时出错: {str(e)}")
    
    def clear_table_content(self):
        """清除表格内容（保留时段和规格）"""
        for row in range(self.table.rowCount()):
            for col in range(self.table.columnCount()):
                # 保留时段列和规格列（涨缩看板）
                if col == 0 or (self.current_board_type == "shrinkage" and col == 1):
                    continue
                
                # 清除其他单元格
                self.table.setItem(row, col, QTableWidgetItem(""))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ProductionDashboard()
    window.show()
    sys.exit(app.exec_())