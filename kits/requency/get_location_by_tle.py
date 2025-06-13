import h5py
import numpy as np
import datetime
import os
from skyfield.api import load, EarthSatellite, utc


def view_constellation_TLE_data(constellation_name):
    """
    从H5文件读取2LE格式的TLE数据

    参数:
        constellation_name: 星座名称

    返回:
        2LE格式的TLE数据列表，每个卫星包含两行数据
    """
    file_path = '/Users/bytedance/Desktop/StarPerf_Simulator/StarPerf_Simulator/config/TLE_constellation/' + constellation_name + '/tle.h5'
    with h5py.File(file_path, 'a') as file:
        current_date = datetime.datetime.now()
        formatted_date = current_date.strftime('%Y%m%d')
        TLE_group = file[formatted_date]
        TLE_2LE = np.array(TLE_group[formatted_date + '-2LE']).tolist()
        TLE_2LE = [item.decode('utf-8') for item in TLE_2LE]

    return TLE_2LE


def calculate_satellite_position(line1, line2, target_time=None):
    """
    根据2LE格式数据计算卫星在指定时刻的经纬度和高度

    参数:
        line1: TLE第一行数据
        line2: TLE第二行数据
        target_time: 目标时间，默认为当前时间

    返回:
        包含经纬度和高度的字典
    """
    # 创建卫星对象
    satellite = EarthSatellite(line1, line2)

    # 设置目标时间
    ts = load.timescale()
    if target_time is None:
        t = ts.now()
    else:
        # 确保datetime对象包含时区信息
        if target_time.tzinfo is None:
            target_time = target_time.replace(tzinfo=utc)
        t = ts.from_datetime(target_time)

    # 计算卫星位置
    geocentric = satellite.at(t)
    subpoint = geocentric.subpoint()

    # 返回结果
    return {
        'satellite_id': line2[2:7].strip(),  # 从第二行提取卫星ID
        'time': t.utc_strftime('%Y-%m-%d %H:%M:%S UTC'),
        'longitude': subpoint.longitude.degrees,
        'latitude': subpoint.latitude.degrees,
        'elevation_km': subpoint.elevation.km
    }


def process_all_satellites(constellation_name, target_time=None, output_file=None):
    """
    处理指定星座的所有卫星TLE数据，计算经纬度并保存结果

    参数:
        constellation_name: 星座名称
        target_time: 统一的目标时间，默认为当前时间
        output_file: 输出文件路径，默认为None（不保存）
    """
    # 如果没有指定目标时间，使用当前时间
    if target_time is None:
        target_time = datetime.datetime.now().replace(tzinfo=utc)

    # 获取TLE数据
    tle_lines = view_constellation_TLE_data(constellation_name)

    # 每两颗行为一组处理
    satellite_positions = []
    for i in range(0, len(tle_lines), 2):
        if i + 1 < len(tle_lines):
            line1 = tle_lines[i]
            line2 = tle_lines[i + 1]

            # 计算卫星位置（使用统一的目标时间）
            position = calculate_satellite_position(line1, line2, target_time=target_time)
            satellite_positions.append(position)

            # 打印结果
            print(f"卫星ID: {position['satellite_id']}")
            print(f"时间: {position['time']}")
            print(f"经度: {position['longitude']:.6f}°")
            print(f"纬度: {position['latitude']:.6f}°")
            print(f"高度: {position['elevation_km']:.2f} km")
            print("-" * 40)

    # 保存结果到文件
    if output_file:
        with open(output_file, 'w') as f:
            # 写入CSV表头
            f.write("卫星ID,时间,经度(度),纬度(度),高度(km)\n")

            # 写入每行数据
            for pos in satellite_positions:
                f.write(
                    f"{pos['satellite_id']},{pos['time']},{pos['longitude']:.6f},{pos['latitude']:.6f},{pos['elevation_km']:.2f}\n")

        print(f"结果已保存到: {output_file}")

    return satellite_positions


# 主函数
if __name__ == "__main__":
    # 指定星座名称
    constellation_name = "Starlink"  # 替换为你的星座名称

    # 指定统一的目标时间（例如当前时间）
    target_time = datetime.datetime.now().replace(tzinfo=utc)

    # 也可以指定特定时间
    # target_time = datetime.datetime(2023, 10, 15, 12, 0, 0, tzinfo=utc)  # 2023年10月15日12:00:00 UTC

    # 输出文件路径（可选）
    output_dir = "/Users/bytedance/Desktop/StarPerf_Simulator/StarPerf_Simulator/kits/requency/results"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir,
                               f"{constellation_name}_positions_{target_time.strftime('%Y%m%d_%H%M%S')}.csv")

    # 处理所有卫星并保存结果
    process_all_satellites(constellation_name, target_time, output_file)
