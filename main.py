import os.path
import sys
import json
import math
import re
from itertools import combinations
import numpy as np
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QFileDialog, QTextEdit, QTabWidget, QComboBox,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib
import matplotlib.pyplot as plt

# 应用基础信息
APP_TAG = "stable"
APP_VERSION = "v1.1.0"
APP_DESCRIPTION = "磁场数据加载、分析与可视化工具"

# ✅ 设置中文字体（Windows常用）
matplotlib.rcParams['font.sans-serif'] = ['SimHei']    # 黑体
matplotlib.rcParams['axes.unicode_minus'] = False      # 正常显示负号


class DataViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"磁场数据工具 [{APP_TAG}] {APP_VERSION}")
        self.resize(1200, 800)

        self.data = {}  # 存放 Hx/Hy/Hz
        self.freqs = None
        self.sorted_freqs = None
        self.sorted_idx = None
        self.current_sorted_pos = 0
        self.trace_pairs = []
        self.data_mode = None
        self.default_colormap = "jet"
        self.current_plot_items = []
        self.standalone_figures = []

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
        self.log(f"应用信息: {APP_DESCRIPTION} | tag={APP_TAG} | version={APP_VERSION}")

    @staticmethod
    def _format_frequency(freq_hz):
        """将频率格式化为易读单位：小于 1GHz 使用 MHz。"""
        if abs(freq_hz) < 1e9:
            return f"{freq_hz / 1e6:g} MHz"
        return f"{freq_hz / 1e9:g} GHz"

    @staticmethod
    def _validate_loaded_data(data_dict):
        """校验多个方向数据的列和行标签是否一致。"""
        if not data_dict:
            return True, ""

        items = list(data_dict.items())
        base_name, base_df = items[0]
        base_cols = list(base_df.columns)
        base_sample_count = max(base_df.shape[1] - 1, 0)

        base_first_col = base_df.iloc[:, 0]
        base_is_freq_rows = pd.to_numeric(base_first_col, errors="coerce").notna().all()
        base_labels = base_first_col.astype(str).tolist()

        for name, df in items[1:]:
            if df.shape[0] != base_df.shape[0]:
                return False, f"{name} 与 {base_name} 的行数不一致"

            current_first_col = df.iloc[:, 0]
            current_is_freq_rows = pd.to_numeric(current_first_col, errors="coerce").notna().all()
            if current_is_freq_rows != base_is_freq_rows:
                return False, f"{name} 与 {base_name} 的数据方向不一致"

            if base_is_freq_rows:
                current_sample_count = max(df.shape[1] - 1, 0)
                if current_sample_count != base_sample_count:
                    return False, f"{name} 与 {base_name} 的采样点个数不一致"

                base_freq = pd.to_numeric(base_first_col, errors="coerce").to_numpy(dtype=float)
                cur_freq = pd.to_numeric(current_first_col, errors="coerce").to_numpy(dtype=float)
                if not np.allclose(base_freq, cur_freq):
                    return False, f"{name} 与 {base_name} 的频率点不一致"

                if list(df.columns) != base_cols:
                    # 对扫描幅度格式放宽标签一致性要求：只要点数一致就允许合并，
                    # 坐标统一使用首个文件（通常为 Hx）的标签。
                    continue
            else:
                if list(df.columns) != base_cols:
                    return False, f"{name} 与 {base_name} 的频率列不一致"
                if current_first_col.astype(str).tolist() != base_labels:
                    return False, f"{name} 与 {base_name} 的采样标签顺序不一致"

        return True, ""

    @staticmethod
    def _get_grid_shape(labels):
        """从标签推断二维网格尺寸，兼容 x_y_z_* 与 x1_y1_z_A 格式。"""
        points = set()
        for label in labels:
            text = str(label)
            parts = text.split("_")

            if len(parts) >= 2:
                try:
                    points.add((int(parts[0]), int(parts[1])))
                    continue
                except ValueError:
                    pass

            x_match = re.search(r"(?:^|_)x(-?\d+)(?:_|$)", text, re.IGNORECASE)
            y_match = re.search(r"(?:^|_)y(-?\d+)(?:_|$)", text, re.IGNORECASE)
            if x_match and y_match:
                points.add((int(x_match.group(1)), int(y_match.group(1))))

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

    @staticmethod
    def _extract_xy(label):
        """从标签解析坐标，返回 (x, y)，失败返回 None。"""
        text = str(label)
        parts = text.split("_")

        if len(parts) >= 2:
            try:
                return int(parts[0]), int(parts[1])
            except ValueError:
                pass

        x_match = re.search(r"(?:^|_)x(-?\d+)(?:_|$)", text, re.IGNORECASE)
        y_match = re.search(r"(?:^|_)y(-?\d+)(?:_|$)", text, re.IGNORECASE)
        if x_match and y_match:
            return int(x_match.group(1)), int(y_match.group(1))
        return None

    def _values_to_grid(self, labels, values):
        """按标签中的坐标将一维值重建为二维网格，避免依赖列顺序。"""
        coords = [self._extract_xy(label) for label in labels]
        if any(c is None for c in coords):
            return None

        unique_x = sorted({x for x, _ in coords})
        unique_y = sorted({y for _, y in coords})
        x_index = {x: i for i, x in enumerate(unique_x)}
        y_index = {y: i for i, y in enumerate(unique_y)}

        if len(unique_x) * len(unique_y) != len(values):
            return None

        grid = np.full((len(unique_y), len(unique_x)), np.nan, dtype=float)
        for (x, y), val in zip(coords, values):
            yi = y_index[y]
            xi = x_index[x]
            if not np.isnan(grid[yi, xi]):
                return None
            grid[yi, xi] = val

        if np.isnan(grid).any():
            return None
        return grid

    def _get_grid_extent(self, labels):
        """根据标签坐标返回 imshow extent，用于按真实坐标比例显示。"""
        coords = [self._extract_xy(label) for label in labels]
        if any(c is None for c in coords):
            return None

        unique_x = sorted({x for x, _ in coords})
        unique_y = sorted({y for _, y in coords})
        if len(unique_x) * len(unique_y) != len(coords):
            return None

        def _axis_bounds(axis_values):
            if len(axis_values) == 1:
                v = float(axis_values[0])
                return v - 0.5, v + 0.5

            values = np.array(axis_values, dtype=float)
            diffs = np.diff(values)
            left = values[0] - diffs[0] / 2
            right = values[-1] + diffs[-1] / 2
            return float(left), float(right)

        x0, x1 = _axis_bounds(unique_x)
        y0, y1 = _axis_bounds(unique_y)
        return [x0, x1, y0, y1]

    @staticmethod
    def _apply_axis_orientation(ax, origin_mode, extent):
        """根据原点设置坐标显示样式，避免与 imshow 的 origin 逻辑重复翻转。"""
        ax.set_aspect('equal' if extent is not None else 'auto', adjustable='box')

    @staticmethod
    def _resolve_extent_by_origin(extent, origin_mode):
        """将坐标范围与 origin 协同处理，确保上下原点切换时 y 值语义正确。"""
        if extent is None:
            return None

        x0, x1, y0, y1 = extent
        if origin_mode == "upper":
            return [x0, x1, y1, y0]
        return [x0, x1, y0, y1]

    @staticmethod
    def _merge_axis_amplitudes(axis_amplitudes):
        """合并多个方向的幅度数据。

        - 若检测到负值，按 dB 量处理：先转线性功率求和，再转回 dB。
        - 否则按线性幅度处理：使用向量模值 sqrt(x^2 + y^2 + ...)。
        """
        if not axis_amplitudes:
            return None
        if len(axis_amplitudes) == 1:
            return axis_amplitudes[0]

        amp_matrix = np.vstack(axis_amplitudes)
        if np.any(amp_matrix < 0):
            power_sum = np.sum(np.power(10.0, amp_matrix / 10.0), axis=0)
            safe_power = np.maximum(power_sum, np.finfo(float).tiny)
            return 10.0 * np.log10(safe_power)

        return np.sqrt(np.sum(np.square(amp_matrix), axis=0))

    def log(self, message):
        """统一日志输出，兼容界面未完全初始化的阶段。"""
        text = str(message)
        if hasattr(self, "log_box") and self.log_box is not None:
            self.log_box.append(text)
        else:
            print(text)

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
        self.dir_combo.currentIndexChanged.connect(lambda _: self.update_plot(sync_amp_limits=True))
        dir_layout.addWidget(self.dir_combo)

        dir_layout.addWidget(QLabel("频率(GHz):"))
        self.freq_edit = QLineEdit()
        self.freq_edit.setPlaceholderText("输入频率GHz,回车更新")
        self.freq_edit.returnPressed.connect(lambda: self.update_plot(sync_amp_limits=True))
        dir_layout.addWidget(self.freq_edit)

        self.freq_up_btn = QPushButton("fre up")
        self.freq_up_btn.clicked.connect(self.move_sorted_frequency_up)
        dir_layout.addWidget(self.freq_up_btn)

        self.freq_down_btn = QPushButton("fre down")
        self.freq_down_btn.clicked.connect(self.move_sorted_frequency_down)
        dir_layout.addWidget(self.freq_down_btn)

        dir_layout.addWidget(QLabel("色带:"))
        self.cmap_combo = QComboBox()
        colormaps = ["jet", "viridis", "plasma", "inferno", "magma", "turbo", "gray"]
        self.cmap_combo.addItems(colormaps)
        self.cmap_combo.setCurrentText(self.default_colormap)
        self.cmap_combo.currentIndexChanged.connect(lambda _: self.update_plot(sync_amp_limits=False))
        dir_layout.addWidget(self.cmap_combo)

        dir_layout.addWidget(QLabel("原点位置:"))
        self.origin_combo = QComboBox()
        self.origin_combo.addItem("左上角", "upper")
        self.origin_combo.addItem("左下角", "lower")
        self.origin_combo.setCurrentIndex(0)
        self.origin_combo.currentIndexChanged.connect(lambda _: self.update_plot(sync_amp_limits=False))
        dir_layout.addWidget(self.origin_combo)

        dir_layout.addWidget(QLabel("幅值最小:"))
        self.amp_min_edit = QLineEdit()
        self.amp_min_edit.setPlaceholderText("自动")
        self.amp_min_edit.returnPressed.connect(lambda: self.update_plot(sync_amp_limits=False))
        dir_layout.addWidget(self.amp_min_edit)

        dir_layout.addWidget(QLabel("幅值最大:"))
        self.amp_max_edit = QLineEdit()
        self.amp_max_edit.setPlaceholderText("自动")
        self.amp_max_edit.returnPressed.connect(lambda: self.update_plot(sync_amp_limits=False))
        dir_layout.addWidget(self.amp_max_edit)

        self.amp_reset_btn = QPushButton("重置幅值")
        self.amp_reset_btn.clicked.connect(self.reset_amp_limits)
        dir_layout.addWidget(self.amp_reset_btn)

        dir_layout.addWidget(QLabel("独立编号:"))
        self.plot_selector = QComboBox()
        self.plot_selector.addItem("无可选子图")
        self.plot_selector.setEnabled(False)
        dir_layout.addWidget(self.plot_selector)

        self.standalone_btn = QPushButton("独立绘图")
        self.standalone_btn.clicked.connect(self.open_standalone_plot)
        dir_layout.addWidget(self.standalone_btn)

        layout.addLayout(dir_layout)

        self.amp_stats_label = QLabel("幅度统计: -")
        self.amp_stats_label.setFixedHeight(22)
        self.amp_stats_label.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.amp_stats_label)
        layout.setSpacing(4)

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

        self.refresh_direction_options()

        # 获取频率列表并识别数据模式
        first_df = next(iter(self.data.values()))
        first_col_numeric = pd.to_numeric(first_df.iloc[:, 0], errors="coerce")
        self.data_mode = "amplitude" if first_col_numeric.notna().all() else "complex"

        if self.data_mode == "amplitude":
            self.freqs = first_col_numeric.to_numpy(dtype=float)
            self.trace_pairs = []
            self.log_box.append("识别为频谱幅度格式（frequency + 点位幅度列）")
        else:
            self.freqs = np.array([round(float(f)) for f in first_df.columns[1:]], dtype=float)  # Hz

            # 提取可用的 trace 信息，兼容旧格式 trace1/trace2 与 ZNA67 格式 Trc1_S21/Trc2_S31
            self.trace_pairs = self._extract_trace_pairs(first_df.iloc[:, 0])
            if not self.trace_pairs:
                self.log_box.append("未识别到可用 trace（需要成对的 *_re/*_im）")
                return

        # 默认按幅度值排序
        self.sort_freqs_by_amp()
        self.apply_default_amp_limits()

        self.tabs.setCurrentIndex(1)
        self.update_plot()

    def apply_default_amp_limits(self):
        """使用首张图的幅度范围作为默认上下限。"""
        if self.sorted_idx is None or len(self.sorted_idx) == 0:
            return

        idx = int(self.sorted_idx[0])
        sel_dir = self.dir_combo.currentText() or "X"
        amp_min, amp_max = self._get_amplitude_limits(idx, sel_dir)
        if amp_min is None or amp_max is None:
            return

        self.amp_min_edit.setText(f"{amp_min:.6g}")
        self.amp_max_edit.setText(f"{amp_max:.6g}")

    def _get_amplitude_limits(self, idx, sel_dir):
        """获取指定频点和方向下的幅值最小/最大值。"""
        if self.data_mode == "amplitude":
            values = []
            for axis in sel_dir:
                key = f"H{axis.lower()}"
                if key not in self.data:
                    continue
                values.append(self.data[key].iloc[idx, 1:].to_numpy(dtype=float))
            if not values:
                return None, None
            merged = self._merge_axis_amplitudes(values)
            return float(np.min(merged)), float(np.max(merged))

        if sel_dir in ["X", "Y", "Z"]:
            key = f"H{sel_dir.lower()}"
            df = self.data.get(key)
        else:
            df = None
            for axis in sel_dir:
                key = f"H{axis.lower()}"
                if key not in self.data:
                    continue
                part_df = self.data[key]
                if df is None:
                    df = part_df.copy()
                else:
                    df.iloc[:, 1:] += part_df.iloc[:, 1:]

        if df is None or not self.trace_pairs:
            return None, None

        amps = []
        for trace_name in self.trace_pairs:
            trace_re = self._filter_trace_rows(df, trace_name, "re")
            trace_im = self._filter_trace_rows(df, trace_name, "im")
            if trace_re.empty or trace_im.empty:
                continue
            re_vals = trace_re.iloc[:, idx + 1].to_numpy(dtype=float)
            im_vals = trace_im.iloc[:, idx + 1].to_numpy(dtype=float)
            amps.append(np.sqrt(re_vals ** 2 + im_vals ** 2))

        if not amps:
            return None, None

        merged = np.concatenate(amps)
        return float(np.min(merged)), float(np.max(merged))

    def sort_freqs_by_amp(self):
        """计算每个频率的最大幅度并排序"""
        if "Hx" in self.data:
            df = self.data["Hx"]
        else:
            df = next(iter(self.data.values()))

        if self.data_mode == "amplitude":
            amp_matrix = df.iloc[:, 1:].to_numpy(dtype=float)
            max_amp_list = np.max(np.abs(amp_matrix), axis=1)
        else:
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
        self.current_sorted_pos = 0

    def move_sorted_frequency_up(self):
        """切到按幅度排序后更靠前（幅度更大）的频点。"""
        if self.sorted_freqs is None or len(self.sorted_freqs) == 0:
            return
        self.current_sorted_pos = max(0, self.current_sorted_pos - 1)
        self.update_plot(use_input=False, sync_amp_limits=True)

    def move_sorted_frequency_down(self):
        """切到按幅度排序后更靠后（幅度更小）的频点。"""
        if self.sorted_freqs is None or len(self.sorted_freqs) == 0:
            return
        self.current_sorted_pos = min(len(self.sorted_freqs) - 1, self.current_sorted_pos + 1)
        self.update_plot(use_input=False, sync_amp_limits=True)

    def update_plot(self, use_input=True, sync_amp_limits=True):
        if self.freqs is None:
            return

        # 从输入框取频率GHz
        if use_input:
            try:
                freq_ghz = float(self.freq_edit.text())
                freq_val = freq_ghz * 1e9
                sorted_idx = (np.abs(self.sorted_freqs - freq_val)).argmin()
                self.current_sorted_pos = int(sorted_idx)
            except ValueError:
                sorted_idx = self.current_sorted_pos
        else:
            sorted_idx = self.current_sorted_pos

        sorted_idx = min(max(0, sorted_idx), len(self.sorted_freqs) - 1)
        self.current_sorted_pos = sorted_idx

        freq_val = self.sorted_freqs[sorted_idx]
        idx = self.sorted_idx[sorted_idx]
        self.freq_edit.setText(f"{freq_val / 1e9:.6g}")
        sel_dir = self.dir_combo.currentText()
        cmap_name = self.cmap_combo.currentText() or self.default_colormap
        origin_mode = self.origin_combo.currentData() or "upper"

        # 仅在频点/方向切换时同步幅值范围，避免覆盖用户手动输入。
        if sync_amp_limits:
            self._sync_amp_limits_for_current_view(idx, sel_dir)
        amp_vmin, amp_vmax = self._parse_amp_limits()

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
            self.amp_stats_label.setText("幅度统计: -")
            return

        if self.data_mode == "amplitude":
            self.update_plot_amplitude(idx, sel_dir, freq_val, cmap_name, origin_mode, amp_vmin, amp_vmax)
            return

        if not self.trace_pairs:
            self.log_box.append("当前数据未识别到可用 trace（含 re/im）")
            self.amp_stats_label.setText("幅度统计: -")
            return

        trace_data = []
        missing_parts = []
        for trace_name in self.trace_pairs:
            trace_re = self._filter_trace_rows(df, trace_name, "re")
            trace_im = self._filter_trace_rows(df, trace_name, "im")
            if trace_re.empty or trace_im.empty:
                missing_parts.append(trace_name)
                continue

            re_vals = trace_re.iloc[:, idx + 1].to_numpy(dtype=float)
            im_vals = trace_im.iloc[:, idx + 1].to_numpy(dtype=float)
            amp = np.sqrt(re_vals ** 2 + im_vals ** 2)
            phase = np.angle(re_vals + 1j * im_vals, deg=True)
            trace_data.append({
                "name": trace_name,
                "amp": amp,
                "phase": phase,
                "labels": trace_re.iloc[:, 0].to_list()
            })

        if missing_parts:
            self.log_box.append(f"以下 trace 缺少实部或虚部，已跳过: {', '.join(missing_parts)}")

        if not trace_data:
            self.log_box.append("未找到可用于绘图的 trace 数据")
            self.amp_stats_label.setText("幅度统计: -")
            return

        self.fig.clear()
        self.current_plot_items = []
        plot_specs = []
        for item in trace_data:
            labels = item["labels"]
            amp_grid = self._values_to_grid(labels, item["amp"])
            phase_grid = self._values_to_grid(labels, item["phase"])
            grid_extent = self._get_grid_extent(labels)

            if amp_grid is None or phase_grid is None:
                grid_rows, grid_cols = self._get_grid_shape(labels)
                if grid_rows * grid_cols != len(item["amp"]):
                    self.log_box.append("无法推断网格尺寸，按单行展示")
                    grid_rows, grid_cols = 1, len(item["amp"])
                amp_grid = item["amp"].reshape(grid_rows, grid_cols)
                phase_grid = item["phase"].reshape(grid_rows, grid_cols)

            draw_amp_grid = amp_grid
            if amp_vmin is not None or amp_vmax is not None:
                draw_amp_grid = np.clip(amp_grid, amp_vmin, amp_vmax)

            plot_specs.extend([
                (f"{item['name']} 幅度", draw_amp_grid, grid_extent),
                (f"{item['name']} 相位", phase_grid, grid_extent),
            ])

        plot_count = len(plot_specs)
        rows = int(np.ceil(plot_count / 2))
        cols = 1 if plot_count == 1 else 2

        for i, (t, data, extent) in enumerate(plot_specs, 1):
            is_amp = "幅度" in t
            display_extent = self._resolve_extent_by_origin(extent, origin_mode)
            self.current_plot_items.append({
                "index": i,
                "title": t,
                "data": np.array(data, copy=True),
                "extent": display_extent,
                "cmap": cmap_name,
                "origin": origin_mode,
                "vmin": amp_vmin if is_amp else None,
                "vmax": amp_vmax if is_amp else None,
                "suptitle": f"{sel_dir}方向 @ {self._format_frequency(freq_val)}"
            })
            ax = self.fig.add_subplot(rows, cols, i)
            if is_amp:
                im = ax.imshow(
                    data,
                    cmap=cmap_name,
                    vmin=amp_vmin,
                    vmax=amp_vmax,
                    extent=display_extent,
                    origin=origin_mode
                )
            else:
                im = ax.imshow(data, cmap=cmap_name, extent=display_extent, origin=origin_mode)
            self._apply_axis_orientation(ax, origin_mode, display_extent)
            self.fig.colorbar(im, ax=ax)
            ax.set_title(t)
        self.fig.suptitle(f"{sel_dir}方向 @ {self._format_frequency(freq_val)}")
        self.canvas.draw()
        self._refresh_plot_selector()

        self.amp_stats_label.setText(
            self._format_amplitude_stats(
                [(item["name"], item["amp"]) for item in trace_data]
            )
        )

    def _sync_amp_limits_for_current_view(self, idx, sel_dir):
        """按当前频点与方向刷新幅值上下限输入框。"""
        amp_min, amp_max = self._get_amplitude_limits(idx, sel_dir)
        if amp_min is None or amp_max is None:
            self.amp_min_edit.clear()
            self.amp_max_edit.clear()
            return

        self.amp_min_edit.setText(f"{amp_min:.6g}")
        self.amp_max_edit.setText(f"{amp_max:.6g}")

    def update_plot_amplitude(self, idx, sel_dir, freq_val, cmap_name, origin_mode, amp_vmin=None, amp_vmax=None):
        """绘制频谱扫描幅度格式（frequency + 点位列）数据。"""
        axis_values = []
        for axis in sel_dir:
            key = f"H{axis.lower()}"
            if key not in self.data:
                continue
            values = self.data[key].iloc[idx, 1:].to_numpy(dtype=float)
            axis_values.append((axis, values))

        if not axis_values:
            self.log_box.append(f"未找到方向 {sel_dir} 对应的数据")
            self.amp_stats_label.setText("幅度统计: -")
            return

        labels = list(next(iter(self.data.values())).columns[1:])
        merged_amp = self._merge_axis_amplitudes([amp for _, amp in axis_values])
        grid_extent = self._get_grid_extent(labels)
        merged_grid = self._values_to_grid(labels, merged_amp)
        if merged_grid is None:
            grid_rows, grid_cols = self._get_grid_shape(labels)
            if grid_rows * grid_cols != len(merged_amp):
                self.log_box.append("无法推断网格尺寸，按单行展示")
                grid_rows, grid_cols = 1, len(merged_amp)
            merged_grid = merged_amp.reshape(grid_rows, grid_cols)

        draw_grid = merged_grid
        if amp_vmin is not None or amp_vmax is not None:
            draw_grid = np.clip(merged_grid, amp_vmin, amp_vmax)

        self.fig.clear()
        self.current_plot_items = []
        display_extent = self._resolve_extent_by_origin(grid_extent, origin_mode)
        self.current_plot_items.append({
            "index": 1,
            "title": f"{sel_dir}方向 合并幅度",
            "data": np.array(draw_grid, copy=True),
            "extent": display_extent,
            "cmap": cmap_name,
            "origin": origin_mode,
            "vmin": amp_vmin,
            "vmax": amp_vmax,
            "suptitle": f"{sel_dir}方向 @ {self._format_frequency(freq_val)}"
        })
        ax = self.fig.add_subplot(1, 1, 1)
        im = ax.imshow(
            draw_grid,
            cmap=cmap_name,
            vmin=amp_vmin,
            vmax=amp_vmax,
            extent=display_extent,
            origin=origin_mode
        )
        self._apply_axis_orientation(ax, origin_mode, display_extent)
        self.fig.colorbar(im, ax=ax)
        ax.set_title(f"{sel_dir}方向 合并幅度")
        self.fig.suptitle(f"{sel_dir}方向 @ {self._format_frequency(freq_val)}")
        self.canvas.draw()
        self._refresh_plot_selector()
        self.amp_stats_label.setText(
            self._format_amplitude_stats([
                (f"{sel_dir}方向 合并", merged_amp)
            ])
        )

    def _refresh_plot_selector(self):
        """刷新可独立绘制的子图编号列表。"""
        self.plot_selector.blockSignals(True)
        self.plot_selector.clear()

        if not self.current_plot_items:
            self.plot_selector.addItem("无可选子图")
            self.plot_selector.setEnabled(False)
            self.plot_selector.blockSignals(False)
            return

        for item in self.current_plot_items:
            self.plot_selector.addItem(f"{item['index']} - {item['title']}")
        self.plot_selector.setCurrentIndex(0)
        self.plot_selector.setEnabled(True)
        self.plot_selector.blockSignals(False)

    def open_standalone_plot(self):
        """按当前选择的编号使用 matplotlib 默认窗口独立弹出单张子图。"""
        if not self.current_plot_items:
            self.log_box.append("当前没有可独立绘制的子图")
            return

        selected_idx = self.plot_selector.currentIndex()
        if selected_idx < 0 or selected_idx >= len(self.current_plot_items):
            self.log_box.append("独立绘图编号无效")
            return

        item = self.current_plot_items[selected_idx]
        fig, ax = plt.subplots(figsize=(8, 6))
        fig.canvas.manager.set_window_title(f"独立绘图 - {item['index']} {item['title']}")
        im = ax.imshow(
            item["data"],
            cmap=item["cmap"],
            vmin=item["vmin"],
            vmax=item["vmax"],
            extent=item.get("extent"),
            origin=item.get("origin", "upper")
        )
        self._apply_axis_orientation(ax, item.get("origin", "upper"), item.get("extent"))
        fig.colorbar(im, ax=ax)
        ax.set_title(item["title"])
        fig.suptitle(item["suptitle"])
        fig.tight_layout()

        self.standalone_figures.append(fig)

        def _on_close(_event, closed_fig=fig):
            if closed_fig in self.standalone_figures:
                self.standalone_figures.remove(closed_fig)

        fig.canvas.mpl_connect("close_event", _on_close)
        plt.show(block=False)

        self.log_box.append(f"已使用 Matplotlib 默认窗口独立绘制子图: {item['index']} - {item['title']}")

    def _parse_amp_limits(self):
        """解析用户输入的幅值上下限，失败时退回自动范围。"""
        try:
            amp_vmin = float(self.amp_min_edit.text()) if self.amp_min_edit.text().strip() else None
        except ValueError:
            self.log_box.append("幅值最小输入无效，已使用自动范围")
            amp_vmin = None

        try:
            amp_vmax = float(self.amp_max_edit.text()) if self.amp_max_edit.text().strip() else None
        except ValueError:
            self.log_box.append("幅值最大输入无效，已使用自动范围")
            amp_vmax = None

        if amp_vmin is not None and amp_vmax is not None and amp_vmin > amp_vmax:
            self.log_box.append("幅值最小大于最大，已交换两者")
            amp_vmin, amp_vmax = amp_vmax, amp_vmin

        return amp_vmin, amp_vmax

    def reset_amp_limits(self):
        """重置幅值上下限为当前频点和方向下的原始范围。"""
        if self.freqs is None or self.sorted_idx is None or len(self.sorted_idx) == 0:
            self.amp_min_edit.clear()
            self.amp_max_edit.clear()
            self.log_box.append("暂无可重置的幅值范围")
            return

        idx = int(self.sorted_idx[self.current_sorted_pos])
        sel_dir = self.dir_combo.currentText() or "X"
        amp_min, amp_max = self._get_amplitude_limits(idx, sel_dir)
        if amp_min is None or amp_max is None:
            self.amp_min_edit.clear()
            self.amp_max_edit.clear()
            self.log_box.append("当前方向无法计算幅值范围，已恢复自动")
        else:
            self.amp_min_edit.setText(f"{amp_min:.6g}")
            self.amp_max_edit.setText(f"{amp_max:.6g}")
            self.log_box.append("已重置为当前频点的初始幅值范围")

        self.update_plot(use_input=False)

    def refresh_direction_options(self):
        """根据已加载方向动态更新可选场方向组合。"""
        current = self.dir_combo.currentText()
        available_axes = [axis for axis in ["X", "Y", "Z"] if f"H{axis.lower()}" in self.data]
        if not available_axes:
            return

        options = available_axes.copy()
        for size in range(2, len(available_axes) + 1):
            options.extend("".join(group) for group in combinations(available_axes, size))

        self.dir_combo.blockSignals(True)
        self.dir_combo.clear()
        self.dir_combo.addItems(options)

        restore_idx = self.dir_combo.findText(current)
        self.dir_combo.setCurrentIndex(restore_idx if restore_idx >= 0 else 0)
        self.dir_combo.blockSignals(False)

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
        target_part = str(part).lower()

        def _matched(label):
            parsed = self._parse_trace_label(label)
            if not parsed:
                return False
            parsed_trace, parsed_part = parsed
            return parsed_trace == trace_name and parsed_part == target_part

        labels = df.iloc[:, 0].astype(str)
        return df[labels.map(_matched)]

    @staticmethod
    def _format_amplitude_stats(items):
        """格式化多个幅度数据的最小值/最大值信息。"""
        stats = []
        for name, values in items:
            arr = np.asarray(values, dtype=float)
            if arr.size == 0:
                continue
            stats.append(f"{name} min={np.min(arr):.6g}, max={np.max(arr):.6g}")

        if not stats:
            return "幅度统计: -"
        return "幅度统计 | " + " | ".join(stats)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = DataViewer()
    w.show()
    sys.exit(app.exec())
