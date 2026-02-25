import os.path
import sys
import json
import math
import re
import numpy as np
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QFileDialog, QTextEdit, QTabWidget, QComboBox
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib

# ✅ 设置中文字体（Windows常用）
matplotlib.rcParams['font.sans-serif'] = ['SimHei']    # 黑体
matplotlib.rcParams['axes.unicode_minus'] = False      # 正常显示负号


class DataViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("磁场数据工具")
        self.resize(1200, 800)

        self.data = {}  # 存放 Hx/Hy/Hz
        self.freqs = None
        self.sorted_freqs = None
        self.sorted_idx = None
        self.trace_pairs = []

        self.tabs = QTabWidget()
        self.tab1 = QWidget()  # 数据加载
        self.tab2 = QWidget()  # 数据展示
        self.tabs.addTab(self.tab1, "加载数据")
        self.tabs.addTab(self.tab2, "查看数据")

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.tabs)

        self.init_tab1()
        self.init_tab2()

        self.conf_file = os.path.join(os.getcwd(), 'conf.json')
        self.load_config()

    @staticmethod
    def _validate_loaded_data(data_dict):
        """校验多个方向数据的列和行标签是否一致。"""
        if not data_dict:
            return True, ""

        items = list(data_dict.items())
        base_name, base_df = items[0]
        base_cols = list(base_df.columns)
        base_labels = base_df.iloc[:, 0].astype(str).tolist()

        for name, df in items[1:]:
            if list(df.columns) != base_cols:
                return False, f"{name} 与 {base_name} 的频率列不一致"
            if df.shape[0] != base_df.shape[0]:
                return False, f"{name} 与 {base_name} 的行数不一致"
            if df.iloc[:, 0].astype(str).tolist() != base_labels:
                return False, f"{name} 与 {base_name} 的采样标签顺序不一致"

        return True, ""

    @staticmethod
    def _get_grid_shape(labels):
        """从标签 x_y_z_trace*_*(形如 10_3_0_trace1_re) 推断二维网格尺寸。"""
        points = set()
        for label in labels:
            parts = str(label).split("_")
            if len(parts) < 5:
                continue
            try:
                x = int(parts[0])
                y = int(parts[1])
                points.add((x, y))
            except ValueError:
                continue

        if points:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            nx = max(xs) - min(xs) + 1
            ny = max(ys) - min(ys) + 1
            if nx * ny == len(points):
                return ny, nx

        n = len(labels)
        side = int(math.sqrt(n))
        if side * side == n:
            return side, side
        return 1, n

    def init_tab1(self):
        layout = QVBoxLayout()

        # X方向文件
        hx_layout = QHBoxLayout()
        self.xfile_edit = QLineEdit()
        hx_btn = QPushButton("浏览")
        hx_btn.clicked.connect(lambda: self.browse_file(self.xfile_edit))
        hx_layout.addWidget(QLabel("X方向场文件:"))
        hx_layout.addWidget(self.xfile_edit)
        hx_layout.addWidget(hx_btn)
        layout.addLayout(hx_layout)

        # Y方向文件
        hy_layout = QHBoxLayout()
        self.yfile_edit = QLineEdit()
        hy_btn = QPushButton("浏览")
        hy_btn.clicked.connect(lambda: self.browse_file(self.yfile_edit))
        hy_layout.addWidget(QLabel("Y方向场文件:"))
        hy_layout.addWidget(self.yfile_edit)
        hy_layout.addWidget(hy_btn)
        layout.addLayout(hy_layout)

        # Z方向文件
        hz_layout = QHBoxLayout()
        self.zfile_edit = QLineEdit()
        hz_btn = QPushButton("浏览")
        hz_btn.clicked.connect(lambda: self.browse_file(self.zfile_edit))
        hz_layout.addWidget(QLabel("Z方向场文件:"))
        hz_layout.addWidget(self.zfile_edit)
        hz_layout.addWidget(hz_btn)
        layout.addLayout(hz_layout)

        # view 按钮
        self.view_btn = QPushButton("加载并查看")
        self.view_btn.clicked.connect(self.load_all_data)
        layout.addWidget(self.view_btn)

        # 日志
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        layout.addWidget(QLabel("日志:"))
        layout.addWidget(self.log_box)

        self.tab1.setLayout(layout)

    def init_tab2(self):
        layout = QVBoxLayout()

        # 场方向选择 + 频率输入
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("场方向:"))
        self.dir_combo = QComboBox()
        self.dir_combo.addItems(["X", "Y", "Z", "XY", "XZ", "YZ", "XYZ"])
        self.dir_combo.currentIndexChanged.connect(self.update_plot)
        dir_layout.addWidget(self.dir_combo)

        dir_layout.addWidget(QLabel("频率(GHz):"))
        self.freq_edit = QLineEdit()
        self.freq_edit.setPlaceholderText("输入频率GHz,回车更新")
        self.freq_edit.returnPressed.connect(self.update_plot)
        dir_layout.addWidget(self.freq_edit)

        layout.addLayout(dir_layout)

        # Matplotlib画布
        self.fig = Figure(figsize=(10, 8))
        self.canvas = FigureCanvas(self.fig)
        layout.addWidget(self.canvas)

        self.tab2.setLayout(layout)

    def browse_file(self, lineedit):
        file, _ = QFileDialog.getOpenFileName(self, "选择CSV文件", "", "CSV Files (*.csv)")
        if file:
            lineedit.setText(file)
            self.save_config()

    def save_config(self):

        cfg = {
            "xfile": self.xfile_edit.text(),
            "yfile": self.yfile_edit.text(),
            "zfile": self.zfile_edit.text()
        }
        with open(self.conf_file, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=4)

    def load_config(self):
        if os.path.exists(self.conf_file):
            with open(self.conf_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.xfile_edit.setText(cfg.get("xfile", ""))
            self.yfile_edit.setText(cfg.get("yfile", ""))
            self.zfile_edit.setText(cfg.get("zfile", ""))

    def load_all_data(self):
        self.data.clear()
        try:
            if self.xfile_edit.text():
                self.data["Hx"] = pd.read_csv(self.xfile_edit.text(), encoding='utf-8-sig')
                self.log_box.append(f"加载 X方向数据: {self.xfile_edit.text()}")
            if self.yfile_edit.text():
                self.data["Hy"] = pd.read_csv(self.yfile_edit.text(), encoding='utf-8-sig')
                self.log_box.append(f"加载 Y方向数据: {self.yfile_edit.text()}")
            if self.zfile_edit.text():
                self.data["Hz"] = pd.read_csv(self.zfile_edit.text(), encoding='utf-8-sig')
                self.log_box.append(f"加载 Z方向数据: {self.zfile_edit.text()}")
        except Exception as e:
            self.log_box.append(f"加载数据出错: {e}")
            return

        if not self.data:
            self.log_box.append("没有加载任何数据")
            return

        valid, message = self._validate_loaded_data(self.data)
        if not valid:
            self.log_box.append(f"数据校验失败: {message}")
            return

        # 获取频率列表
        first_df = next(iter(self.data.values()))
        self.freqs = [round(float(f)) for f in first_df.columns[1:]]  # Hz
        self.freqs = np.array(self.freqs)

        # 提取可用的 trace 信息，兼容旧格式 trace1/trace2 与 ZNA67 格式 Trc1_S21/Trc2_S31
        self.trace_pairs = self._extract_trace_pairs(first_df.iloc[:, 0])
        if not self.trace_pairs:
            self.log_box.append("未识别到可用 trace（需要成对的 *_re/*_im）")
            return

        # 默认按幅度值排序
        self.sort_freqs_by_amp()

        self.tabs.setCurrentIndex(1)
        self.update_plot()

    def sort_freqs_by_amp(self):
        """计算每个频率的最大幅度并排序"""
        if "Hx" in self.data:
            df = self.data["Hx"]
        else:
            df = next(iter(self.data.values()))
        trace_name = self.trace_pairs[0]
        trace_re = self._filter_trace_rows(df, trace_name, "re")
        trace_im = self._filter_trace_rows(df, trace_name, "im")
        if trace_re.empty or trace_im.empty:
            self.log_box.append(f"用于排序的 trace({trace_name}) 数据不完整")
            return

        max_amp_list = []
        for idx in range(len(self.freqs)):
            re_vals = trace_re.iloc[:, idx + 1].to_numpy()
            im_vals = trace_im.iloc[:, idx + 1].to_numpy()
            amp = np.sqrt(re_vals ** 2 + im_vals ** 2)
            max_amp_list.append(np.max(amp))
        max_amp_list = np.array(max_amp_list)

        self.sorted_idx = np.argsort(max_amp_list)[::-1]
        self.sorted_freqs = self.freqs[self.sorted_idx]
        print(self.sorted_freqs)

    def update_plot(self):
        if self.freqs is None:
            return

        # 从输入框取频率GHz
        try:
            freq_ghz = float(self.freq_edit.text())
            freq_val = freq_ghz * 1e9
            idx = (np.abs(self.sorted_freqs - freq_val)).argmin()
        except ValueError:
            idx = 0  # 默认最大幅度的频率

        freq_val = self.sorted_freqs[idx]
        sel_dir = self.dir_combo.currentText()

        # 组装数据
        df = None
        if sel_dir in ["X", "Y", "Z"]:
            key = f"H{sel_dir.lower()}"
            df = self.data.get(key)
        else:
            combined = None
            for d in sel_dir:
                part_key = f"H{d.lower()}"
                if d in ["X", "Y", "Z"] and part_key in self.data:
                    part = self.data[part_key]
                    if combined is None:
                        combined = part.copy()
                    else:
                        combined.iloc[:, 1:] += part.iloc[:, 1:]
            df = combined
        if df is None:
            self.log_box.append(f"未找到方向 {sel_dir} 对应的数据")
            return

        if len(self.trace_pairs) < 2:
            self.log_box.append("当前数据至少需要两组 trace（含 re/im）")
            return

        trace1_name = self.trace_pairs[0]
        trace2_name = self.trace_pairs[1]
        trace1_re = self._filter_trace_rows(df, trace1_name, "re")
        trace1_im = self._filter_trace_rows(df, trace1_name, "im")
        trace2_re = self._filter_trace_rows(df, trace2_name, "re")
        trace2_im = self._filter_trace_rows(df, trace2_name, "im")

        if trace1_re.empty or trace1_im.empty or trace2_re.empty or trace2_im.empty:
            self.log_box.append(f"数据缺少 {trace1_name}/{trace2_name} 的实部或虚部")
            return

        re1 = trace1_re.iloc[:, idx + 1].to_numpy()
        im1 = trace1_im.iloc[:, idx + 1].to_numpy()
        re2 = trace2_re.iloc[:, idx + 1].to_numpy()
        im2 = trace2_im.iloc[:, idx + 1].to_numpy()

        amp1 = np.sqrt(re1 ** 2 + im1 ** 2)
        amp2 = np.sqrt(re2 ** 2 + im2 ** 2)
        ph1 = np.angle(re1 + 1j * im1, deg=True)
        ph2 = np.angle(re2 + 1j * im2, deg=True)

        grid_rows, grid_cols = self._get_grid_shape(trace1_re.iloc[:, 0].to_list())
        if grid_rows * grid_cols != len(amp1):
            self.log_box.append("无法推断网格尺寸，按单行展示")
            grid_rows, grid_cols = 1, len(amp1)

        amp1 = amp1.reshape(grid_rows, grid_cols)
        amp2 = amp2.reshape(grid_rows, grid_cols)
        ph1 = ph1.reshape(grid_rows, grid_cols)
        ph2 = ph2.reshape(grid_rows, grid_cols)

        self.fig.clear()
        titles = [
            f"{trace1_name} 幅度",
            f"{trace1_name} 相位",
            f"{trace2_name} 幅度",
            f"{trace2_name} 相位"
        ]
        datas = [amp1, ph1, amp2, ph2]
        for i, (data, t) in enumerate(zip(datas, titles), 1):
            ax = self.fig.add_subplot(2, 2, i)
            im = ax.imshow(data, aspect='auto')
            self.fig.colorbar(im, ax=ax)
            ax.set_title(t)
        self.fig.suptitle(f"{sel_dir}方向 @ {freq_val/1e9:.3f} GHz")
        self.canvas.draw()

    @staticmethod
    def _parse_trace_label(label):
        """解析 x_y_z_<trace_name>_<re/im> 格式，返回 (trace_name, part)。"""
        parts = str(label).split("_")
        if len(parts) < 5:
            return None
        part = parts[-1].lower()
        if part not in {"re", "im"}:
            return None
        trace_name = "_".join(parts[3:-1])
        if not trace_name:
            return None
        return trace_name, part

    def _extract_trace_pairs(self, labels):
        """提取同时具备 re/im 的 trace 名称，并优先返回常见顺序。"""
        parts_map = {}
        for label in labels.astype(str):
            parsed = self._parse_trace_label(label)
            if not parsed:
                continue
            trace_name, part = parsed
            parts_map.setdefault(trace_name, set()).add(part)

        available = [name for name, parts in parts_map.items() if {"re", "im"}.issubset(parts)]
        if not available:
            return []

        # 兼容常见命名，优先用户关注的 Trc1_S21/Trc2_S31 以及历史 trace1/trace2
        preferred = ["Trc1_S21", "Trc2_S31", "trace1", "trace2"]
        ordered = [name for name in preferred if name in available]
        ordered.extend(sorted([name for name in available if name not in ordered]))
        return ordered

    def _filter_trace_rows(self, df, trace_name, part):
        """按 trace 名和分量(re/im)精确过滤行。"""
        pattern = re.compile(rf"^\\d+_\\d+_[^_]+_{re.escape(trace_name)}_{part}$", re.IGNORECASE)
        labels = df.iloc[:, 0].astype(str)
        return df[labels.map(lambda x: bool(pattern.match(x)))]


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = DataViewer()
    w.show()
    sys.exit(app.exec())
