import h3
import pandas as pd
import os


def convert_latlng_to_h3(latitude, longitude, resolution=9):
    """
    将经纬度转换为 H3 单元格 ID

    Args:
        latitude: 纬度
        longitude: 经度
        resolution: H3 分辨率 (0-15), 默认为 9

    Returns:
        H3 单元格 ID 字符串
    """
    # 检查输入范围
    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        raise ValueError("经纬度超出范围")

    if not (0 <= resolution <= 15):
        raise ValueError("H3 分辨率必须在 0-15 之间")

    # 转换为 H3 单元格
    h3_cell = h3.latlng_to_cell(latitude, longitude, resolution)

    # 验证转换结果
    cell_lat, cell_lng = h3.cell_to_latlng(h3_cell)
    print(f"输入经纬度: ({latitude:.6f}, {longitude:.6f})")
    print(f"H3 单元格 ID: {h3_cell} (分辨率 {resolution})")
    print(f"单元格中心点: ({cell_lat:.6f}, {cell_lng:.6f})")

    return h3_cell


def process_satellite_csv(input_file, output_file, resolution=9):
    """
    处理卫星CSV文件，添加H3 ID列并保存结果

    Args:
        input_file: 输入CSV文件路径
        output_file: 输出CSV文件路径
        resolution: H3 分辨率
    """
    # 读取输入CSV文件
    print(f"正在读取文件: {input_file}")
    df = pd.read_csv(input_file)

    # 检查必要的列是否存在
    required_columns = ['卫星ID', '经度(度)', '纬度(度)']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"输入文件缺少必要的列: {', '.join(missing_columns)}")

    # 转换经纬度为H3 ID
    print(f"正在转换经纬度为H3 ID (分辨率: {resolution})...")
    h3_ids = []
    for index, row in df.iterrows():
        try:
            h3_id = convert_latlng_to_h3(row['纬度(度)'], row['经度(度)'], resolution)
            h3_ids.append(h3_id)
        except Exception as e:
            print(f"处理行 {index + 1} 时出错: {e}")
            h3_ids.append(None)

    # 创建新的DataFrame，只包含卫星ID和H3 ID
    result_df = pd.DataFrame({
        '卫星ID': df['卫星ID'],
        'H3_ID': h3_ids
    })

    # 保存结果到CSV文件
    print(f"正在保存结果到: {output_file}")
    result_df.to_csv(output_file, index=False)
    print(f"处理完成! 共处理 {len(df)} 条记录。")

    return result_df


def main():
    # 设置固定的文件路径和H3分辨率
    input_file = "/Users/bytedance/Desktop/StarPerf_Simulator/StarPerf_Simulator/kits/requency/results/Starlink_positions_20250612_130255.csv"  # 替换为您的输入文件路径
    output_file = "/Users/bytedance/Desktop/StarPerf_Simulator/StarPerf_Simulator/kits/requency/results/geo_h3.csv"  # 替换为您想要的输出文件路径
    resolution = 2  # H3分辨率，范围0-15

    # 确保输出目录存在
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 处理CSV文件
    process_satellite_csv(input_file, output_file, resolution)


if __name__ == "__main__":
    main()
