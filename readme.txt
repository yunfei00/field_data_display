将matplotlib后台界面嵌入pyside6中。

需求说明:
展示磁场数据和合并磁场数据的各种图。
原始数据格式:
有磁场数据Hx Hy Hz, 第一行是频率数据，单位是Hz，共有两条trace数据，每条trace对应数据的实部和虚部，后面每行数据的格式为:
x_y_z_trace1/2_re/im

如下:
fre,1,2,3,4
0_0_0_trace1_re 1.2 1.3
0_0_0_trace1_im
0_0_0_trace2_re
0_0_0_trace2_im

1_0_0_trace1_re
1_0_0_trace1_im
1_0_0_trace2_re
1_0_0_trace2_im

直接打开就是全屏显示，或者指定大小，左侧放
指定频率，展示对应的数据，可以是Hx，Hy，Hz，HxHy，HxHz,HyHz,HXHyHz
默认按照幅度值大小进行排序 按钮有up down
频率可以自己手动指定


界面说明:
分两个页面，第一个页面负责加载数据和日志显示，第二个页面负责展示数据和相关过滤信息。
页面1:
    X方向场文件: LineEdit browser_button
    Y方向场文件: LineEdit browser_button
    Z方向场文件: LineEdit browser_button
    button_view
    日志显示框

页面2:
    场方向: X, Y, Z, XY, XZ, YZ, XYZ     频率: 选择框,同时支持输入,单位GHz
    画图区域






新增兼容格式说明:
支持 ZNA67 仪表格式标签（示例）：
0_0_0_Trc1_S21_re
0_0_0_Trc1_S21_im
0_0_0_Trc2_S31_re
0_0_0_Trc2_S31_im

程序会自动识别 trace 名（如 Trc1_S21、Trc2_S31），并兼容原有 trace1/trace2。


新增兼容格式说明(频谱扫描):
支持仅幅度的频谱扫描数据，示例表头:
frequency,x1_y1_z_A,x2_y1_z_A,x3_y1_z_A,x1_y2_z_A,...
其中每一行代表一个频率点，程序会自动识别并按频率维度排序后显示。
多方向合并规则:
- 单方向(X/Y/Z): 直接显示该方向幅度
- 组合方向(XY/XZ/YZ/XYZ): 按向量模值合并 sqrt(Hx^2 + Hy^2 + ...)
该兼容逻辑对后续频谱列名变化保持容错（优先识别 x*_y* 坐标，否则降级单行显示）。
