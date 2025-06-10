import h3


def convert_latlng_to_h3(latitude, longitude, resolution=0):
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
    print(f"输入经纬度: ({latitude}, {longitude})")
    print(f"H3 单元格 ID: {h3_cell} (分辨率 {resolution})")
    print(f"单元格中心点: ({cell_lat}, {cell_lng})")

    return h3_cell


# 示例：北京市中心
if __name__ == "__main__":
    try:
        h3_id = convert_latlng_to_h3(39.9042, 116.4074, 0)
        print(f"转换成功: {h3_id}")
    except Exception as e:
        print(f"错误: {e}")