import socket
import time
from typing import Any
import subprocess
import os
import signal
import sys

from samples.TLE_constellation.positive_Grid.least_hop_path import least_hop_path


class TimeoutError(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutError("接收超时")


def UDP_video_forwarding(constellation_name, source, target, sh, t):
    """
    插件入口函数：沿指定路径转发FFmpeg视频流，并在终点保存文件
    """
    current_path = least_hop_path(constellation_name, source, target, sh, t)
    satellite_ids = [sat.id for sat in current_path]
    print("\t\t\tThe least hop path from ", source.user_name, " to ", target.user_name, " is ", satellite_ids)

    # 4. 从路由路径中提取第一颗卫星作为FFmpeg流的目标
    if not current_path:
        print("未获取到有效路由路径，无法启动FFmpeg流")
        return []

    first_satellite = current_path[0]
    first_sat_ip = first_satellite.ip
    first_sat_port = first_satellite.port

    # 5. 启动FFmpeg流，目标为路径中的第一颗卫星
    try:
        ffmpeg_cmd = [
            'ffmpeg',
            '-re',  # 以本地帧率发送，避免一次性发送所有帧
            '-i', 'video.mp4',
            '-c:v', 'libx264',
            '-f', 'mpegts',
            f"udp://{first_sat_ip}:{first_sat_port}"
        ]
        ffmpeg_process = subprocess.Popen(ffmpeg_cmd)
        print(f"视频流已启动，目标卫星：{first_satellite}，IP: {first_sat_ip}:{first_sat_port}")
        print(f"视频流沿路径 {satellite_ids} 转发")
    except Exception as e:
        print(f"启动FFmpeg失败: {e}")
        return []

    # 初始化UDP套接字
    sockets = {}
    for sat in current_path:
        try:
            sat_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sat_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sat_socket.bind((sat.ip, sat.port))
            sat_socket.settimeout(10)  # 设置10秒超时
            sockets[sat.id] = sat_socket
            print(f"成功绑定卫星 {sat.id} 到 {sat.ip}:{sat.port}")
        except OSError as e:
            print(f"绑定失败 - 卫星ID: {sat.id}, IP: {sat.ip}, 端口: {sat.port}")
            print(f"错误详情: {e}")
            ffmpeg_process.terminate()
            return []

    # 在最后一颗卫星创建文件对象以保存数据
    output_file = open(f"received_video_{time.time()}.ts", 'wb')
    print(f"开始沿路径转发视频流：{[sat.id for sat in current_path]}")
    packet_count = 0
    consecutive_empty = 0
    signal.signal(signal.SIGALRM, timeout_handler)

    try:
        while True:
            try:
                # 设置全局超时，如果15秒内没有任何数据，认为传输完成
                signal.alarm(15)

                for i, sat in enumerate(current_path):
                    if i == 0:
                        # 第一颗卫星接收FFmpeg流
                        data, addr = sockets[sat.id].recvfrom(8192)  # 增大缓冲区
                        print(f"Sat{sat.id} 接收视频包，大小：{len(data)}字节")
                    else:
                        # 后续卫星从上游卫星接收数据
                        prev_sat = current_path[i - 1]
                        data, _ = sockets[prev_sat.id].recvfrom(8192)
                        if not data:
                            consecutive_empty += 1
                            if consecutive_empty > 5:  # 如果连续5次没有数据，认为传输结束
                                raise TimeoutError("连续多次无数据，传输可能已完成")
                            continue
                        else:
                            consecutive_empty = 0

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

                signal.alarm(0)  # 重置闹钟
            except TimeoutError:
                print("接收超时，视频传输可能已完成")
                break
            except socket.timeout:
                print("单个套接字接收超时，继续等待")
                continue

    except Exception as e:
        print(f"转发过程中发生错误：{e}")
    finally:
        # 清理资源
        signal.alarm(0)  # 确保闹钟被关闭
        for sock in sockets.values():
            sock.close()
        output_file.close()

        # 等待FFmpeg进程结束
        if ffmpeg_process.poll() is None:
            ffmpeg_process.terminate()
            try:
                ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ffmpeg_process.kill()

        # 验证文件大小
        try:
            file_size = os.path.getsize(output_file.name) / 1024 / 1024
            print(f"视频下载完成，共接收 {packet_count} 个数据包，文件大小：{file_size:.2f} MB")
        except Exception:
            print(f"视频下载完成，共接收 {packet_count} 个数据包")

    return current_path