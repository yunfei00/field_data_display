版本信息:
- Tag: stable
- Version: v1.1.0
- 说明: 磁场数据加载、分析与可视化工具，支持多方向合并显示、兼容多种输入格式，并新增 Hx/Hy 坐标偏移场景下的图片合成功能。

v1.1.0 更新说明:
- 新增：兼容 Hx 与 Hy 的坐标标签不完全一致、但数据个数一致时的合并显示。
  - 适用场景：扫描数据中 Hx 与 Hy 采样点数量一致，但列名（坐标标签）存在偏移或命名差异。
  - 合并规则：在保证频率轴与采样点数量一致的前提下，允许按首个方向文件（通常为 Hx）坐标标签进行对齐并生成合并图片。
  - 结果表现：XY（及包含 XY 的组合方向）仍按向量模值 `sqrt(Hx^2 + Hy^2 + ...)` 合成，不因标签差异中断绘图流程。
- 优化：README 补充了新增兼容能力的触发条件与行为说明，便于发布与使用。

新增工具：CST 导出转 CAT 导入格式（GUI）
- 在“加载数据”页新增转换区域，支持选择 `e.txt`、`h.txt`。
- 自动忽略前两行，从第三行开始按一个或多个空格解析数据列。
- E 场支持列：`x y z ex_re ex_im ey_re ey_im ez_re ez_im`。
- H 场支持列：`x y z hx_re hx_im hy_re hy_im hz_re hz_im`。
- 频率由用户手动输入（Hz）。
- 输出目录可手动选择；若留空，默认输出到输入文件同目录下 `out_xml_dat`。
- 生成 `.dat` 与 `.xml` 文件：
  - E 场：`ex/ey/ez.dat` + `ex/ey/ez.xml`
  - H 场：`hx/hy/hz.dat` + `hx/hy/hz.xml`
- `.dat` 每行格式：`x y z re im`，坐标单位从 mm 转换为 m。

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

v1.1.0 兼容增强（Hx/Hy 坐标偏移）:
- 当数据属于“频谱扫描”模式时，方向文件之间只要满足以下条件即可合并：
  1) 行数一致；
  2) 首列频率点一致；
  3) 采样点个数一致（即除首列外的数据列数量一致）。
- 若 Hx/Hy（或其他方向）列名不一致，程序不再强制报错，而是继续允许多方向合图。
- 绘图时坐标标签以首个加载方向文件为基准（推荐先加载 Hx），从而支持“坐标偏移但点数一致”场景的图片合成。

---

自动化打包 EXE（GitHub Actions）:
- 已添加 `.github/workflows/build-windows-exe.yml`。
- 当推送 tag（格式 `v*`，例如 `v1.1.0`）时会自动执行：
  1) 安装依赖（含 pyinstaller）
  2) 使用 `pyinstaller --onefile --windowed` 打包 `main.py`
  3) 上传构建产物到 Actions Artifacts
  4) 若为 tag 触发，同时把 `dist/field_data_display.exe` 上传到对应 GitHub Release

发布建议：
- 建议为本次发布创建并推送 tag：`v1.1.0`。
- 若同名 tag 早于当前提交，请删除并重新推送该 tag，或改用新 tag 触发自动打包。
