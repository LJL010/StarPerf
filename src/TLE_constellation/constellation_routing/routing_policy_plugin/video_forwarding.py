import socket
import time
from typing import Any

from samples.TLE_constellation.positive_Grid.least_hop_path import least_hop_path
import os


def video_forwarding(constellation_name, source, target, sh, t):
    """
    插件入口函数：沿指定路径转发FFmpeg视频流，并在终点保存文件
    """
    current_path = least_hop_path(constellation_name, source, target, sh, t)
    satellite_ids = [sat.id for sat in current_path]
    print("\t\t\tThe least hop path from ", source.user_name, " to ", target.user_name, " is ", satellite_ids)

    # 4. 从路由路径中提取第一颗卫星作为FFmpeg流的目标
    if current_path:
        first_satellite = current_path[0]  # 假设route存储的是卫星ID或对象
        # 根据卫星ID获取IP和端口（需确保卫星对象包含这些属性）
        first_sat_ip = first_satellite.ip  # 示例获取方式
        first_sat_port = first_satellite.port

        # 5. 启动FFmpeg流，目标为路径中的第一颗卫星
        import subprocess

        ffmpeg_cmd = [
            'ffmpeg',
            '-i', 'video.mp4',
            '-c:v', 'libx264',
            '-f', 'mpegts',
            f"udp://{first_sat_ip}:{first_sat_port}"
        ]
        ffmpeg_process = subprocess.Popen(ffmpeg_cmd)
        print(f"视频流已启动，目标卫星：{first_satellite}，IP: {first_sat_ip}:{first_sat_port}")
        print(f"视频流沿路径 {satellite_ids} 转发完成")
    else:
        print("未获取到有效路由路径，无法启动FFmpeg流")

    # 初始化UDP套接字
    sockets = {}
    for sat in current_path:
        try:
            sat_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # 允许地址重用，避免调试时的端口占用问题
            sat_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sat_socket.bind((sat.ip, sat.port))
            sockets[sat.id] = sat_socket
            print(f"成功绑定卫星 {sat.id} 到 {sat.ip}:{sat.port}")
        except OSError as e:
            print(f"绑定失败 - 卫星ID: {sat.id}, IP: {sat.ip}, 端口: {sat.port}")
            print(f"错误详情: {e}")
            raise  # 可选：继续抛出错误或处理异常

    # 在最后一颗卫星创建文件对象以保存数据
    output_file = open(f"received_video_{time.time()}.ts", 'wb')  # 创建TS文件

    print(f"开始沿路径转发视频流：{[sat.id for sat in current_path]}")
    packet_count = 0

    try:
        for timeslot in range(3000):  # 假设转发100个时间片
            for i, sat in enumerate(current_path):
                if i == 0:
                    # 第一颗卫星接收FFmpeg流
                    data, addr = sockets[sat.id].recvfrom(4096)  # 增大缓冲区
                    if not data:
                        break
                    print(f"Sat{sat.id} 接收视频包，大小：{len(data)}字节")
                else:
                    # 后续卫星从上游卫星接收数据
                    prev_sat = current_path[i - 1]
                    data, _ = sockets[prev_sat.id].recvfrom(4096)
                    if not data:
                        break

                # # 模拟ISL延迟
                # isl_delay = get_isl_delay(constellation_name, sat.id, current_path[i + 1].id, t)
                # time.sleep(isl_delay)  # 延迟转发

                if i < len(current_path) - 1:
                    # 转发到下一颗卫星
                    next_sat = current_path[i + 1]
                    sockets[sat.id].sendto(data, (next_sat.ip, next_sat.port))
                    print(f"Sat{sat.id} → Sat{next_sat.id} 转发视频包")
                else:
                    # 最后一颗卫星：写入文件而非转发
                    output_file.write(data)
                    packet_count += 1
                    if packet_count % 100 == 0:
                        print(f"Sat{sat.id} 已写入 {packet_count} 个数据包")

    except Exception as e:
        print(f"转发过程中发生错误：{e}")
    finally:
        # 关闭所有套接字和文件
        for sock in sockets.values():
            sock.close()
        output_file.close()
        print(
            f"视频下载完成，共接收 {packet_count} 个数据包，文件大小：{os.path.getsize(output_file.name) / 1024 / 1024:.2f} MB")

    return current_path


# def get_isl_delay(constellation_name, sat1_id, sat2_id, timeslot):
#     """从StarPerf的delay矩阵中获取卫星间延迟（单位：秒）"""
#     import h5py
#     delay_h5_path = f"data/{'TLE_constellation' if 'TLE' in constellation_name else 'XML_constellation'}/{constellation_name}.h5"
#     with h5py.File(delay_h5_path, 'r') as f:
#         delay_group = f[f'delay/timeslot{timeslot}']
#         delay_key = f"{sat1_id}_{sat2_id}"
#         if delay_key in delay_group:
#             return delay_group[delay_key][()] / 1000  # 转换为秒
#         return 0.01  # 默认延迟10ms