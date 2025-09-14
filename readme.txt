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




