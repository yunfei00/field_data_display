"""
创建测试数据
"""
import os.path

import numpy as np
import pandas as pd


def generate_magnetic_data(nx=80, ny=50,
                           freq_start=1e9, freq_end=1.3e9, freq_num=1001,
                           z=0, seed=None, filepath=None, trace_names=None):
    """
    生成模拟磁场数据 CSV 文件。

    每个 (x,y,z) 点会按 trace_names 生成两行分量数据：<trace_name>_re 与 <trace_name>_im。

    第一列是 "fre"，后面列是频率点对应的值。

    参数:
        nx (int): x方向点数
        ny (int): y方向点数
        freq_start (float): 起始频率 (Hz)
        freq_end (float): 终止频率 (Hz)
        freq_num (int): 频率点个数
        z (int/float): z坐标
        seed (int): 随机种子，保证可重复
        filepath (str): 如果提供则保存CSV到此路径
        trace_names (list[str]): trace名称列表，默认 ["trace1", "trace2"]

    返回:
        pandas.DataFrame: 生成的数据表
    """
    if seed is not None:
        np.random.seed(seed)

    if trace_names is None:
        trace_names = ["trace1", "trace2"]

    # 频率数组
    freqs = np.linspace(freq_start, freq_end, freq_num)
    n_freq = len(freqs)

    # 列名
    columns = ["fre"] + [str(round(f)) for f in freqs]

    # 按行生成
    rows = []
    for y in range(nx):
        for x in range(ny):
            for trace_name in trace_names:
                for part in ["re", "im"]:
                    label = f"{x}_{y}_{z}_{trace_name}_{part}"
                    values = np.random.randn(n_freq)  # 模拟随机数据
                    rows.append([label] + list(values))

    df = pd.DataFrame(rows, columns=columns)

    # 如果指定路径则保存
    if filepath:
        df.to_csv(filepath, index=False)

    return df


def generate_zna67_data(nx=80, ny=50,
                        freq_start=1e9, freq_end=1.3e9, freq_num=1001,
                        z=0, seed=None, filepath=None):
    """生成 ZNA67 风格测试数据（Trc1_S21、Trc2_S31）。"""
    return generate_magnetic_data(
        nx=nx,
        ny=ny,
        freq_start=freq_start,
        freq_end=freq_end,
        freq_num=freq_num,
        z=z,
        seed=seed,
        filepath=filepath,
        trace_names=["Trc1_S21", "Trc2_S31"]
    )


if __name__ == '__main__':
    # 使用示例
    _nx = 151
    _ny = 151
    _freq_start = 1e9
    _freq_end = 1.3e9
    _freq_num = 201
    _z = 0
    _file_dir = os.path.join(os.getcwd(), 'test_data', f'{_nx}X{_ny}')
    _legacy_dir = os.path.join(_file_dir, 'legacy_trace')
    _zna67_dir = os.path.join(_file_dir, 'zna67_trace')

    os.makedirs(_legacy_dir, exist_ok=True)
    os.makedirs(_zna67_dir, exist_ok=True)

    for _file in ['hx.csv', 'hy.csv', 'hz.csv']:
        _legacy_path = os.path.join(_legacy_dir, _file)
        generate_magnetic_data(
            nx=_nx,
            ny=_ny,
            freq_start=_freq_start,
            freq_end=_freq_end,
            freq_num=_freq_num,
            z=_z,
            seed=None,
            filepath=_legacy_path,
            trace_names=['trace1', 'trace2']
        )
        print(f'create file {_legacy_path}')

        _zna67_path = os.path.join(_zna67_dir, _file)
        generate_zna67_data(
            nx=_nx,
            ny=_ny,
            freq_start=_freq_start,
            freq_end=_freq_end,
            freq_num=_freq_num,
            z=_z,
            seed=None,
            filepath=_zna67_path
        )
        print(f'create file {_zna67_path}')
