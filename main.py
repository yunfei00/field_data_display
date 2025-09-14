import os.path
import sys
import json
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

        # 获取频率列表
        first_df = next(iter(self.data.values()))
        self.freqs = [round(float(f)) for f in first_df.columns[1:]]  # Hz
        self.freqs = np.array(self.freqs)

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
        trace1_re = df[df.iloc[:, 0].str.contains("trace1_re")]
        trace1_im = df[df.iloc[:, 0].str.contains("trace1_im")]
        max_amp_list = []
        for idx in range(len(self.freqs)):
            re_vals = trace1_re.iloc[:, idx + 1].to_numpy()
            im_vals = trace1_im.iloc[:, idx + 1].to_numpy()
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

            print(f'freq_ghz is {freq_val}, ids is {idx}')
        except:
            idx = 0  # 默认最大幅度的频率

        freq_val = self.sorted_freqs[idx]
        sel_dir = self.dir_combo.currentText()

        # 组装数据
        df = None
        if sel_dir in ["X", "Y", "Z"]:
            key = f"H{sel_dir.lower()}"
            df = self.data.get(key)
            # print(f'get df is {df.head()}')
        else:
            combined = None
            for d in sel_dir:
                if d in ["X", "Y", "Z"] and f"H{d}" in self.data:
                    part = self.data[f"H{d}"]
                    if combined is None:
                        combined = part.copy()
                    else:
                        combined.iloc[:, 1:] += part.iloc[:, 1:]
            df = combined
        if df is None:
            return

        trace1_re = df[df.iloc[:, 0].str.contains("trace1_re")]
        trace1_im = df[df.iloc[:, 0].str.contains("trace1_im")]
        trace2_re = df[df.iloc[:, 0].str.contains("trace2_re")]
        trace2_im = df[df.iloc[:, 0].str.contains("trace2_im")]

        print(f'trace1_re.head() is {trace1_re.head()}')

        re1 = trace1_re.iloc[:, idx + 1].to_numpy()
        im1 = trace1_im.iloc[:, idx + 1].to_numpy()
        re2 = trace2_re.iloc[:, idx + 1].to_numpy()
        im2 = trace2_im.iloc[:, idx + 1].to_numpy()

        print(f're1 shape is {re1.shape}')
        amp1 = np.sqrt(re1 ** 2 + im1 ** 2)
        amp2 = np.sqrt(re2 ** 2 + im2 ** 2)
        ph1 = np.angle(re1 + 1j * im1, deg=True)
        ph2 = np.angle(re2 + 1j * im2, deg=True)

        nx = int(np.sqrt(len(amp1)))
        nx = 151
        print(f'nx is {nx}')
        amp1 = amp1.reshape(nx, -1)
        amp2 = amp2.reshape(nx, -1)
        ph1 = ph1.reshape(nx, -1)
        ph2 = ph2.reshape(nx, -1)

        self.fig.clear()
        titles = [f"Trace1 幅度", f"Trace1 相位", f"Trace2 幅度", f"Trace2 相位"]
        datas = [amp1, ph1, amp2, ph2]
        for i, (data, t) in enumerate(zip(datas, titles), 1):
            ax = self.fig.add_subplot(2, 2, i)
            im = ax.imshow(data, aspect='auto')
            self.fig.colorbar(im, ax=ax)
            ax.set_title(t)
        self.fig.suptitle(f"{sel_dir}方向 @ {freq_val/1e9:.3f} GHz")
        self.canvas.draw()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = DataViewer()
    w.show()
    sys.exit(app.exec())
