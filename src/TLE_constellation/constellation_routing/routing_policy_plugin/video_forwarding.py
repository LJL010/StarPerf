import socket
import time
import subprocess
import os
import signal

from samples.TLE_constellation.positive_Grid.least_hop_path import least_hop_path


class TimeoutError(Exception):
    pass


def timeout_handler(signum, frame):
    raise TimeoutError("接收超时")


def video_forwarding(constellation_name, source, target, sh, t):
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

    # 初始化UDP套接字
    sockets = {}
    for sat in current_path:
        try:
            sat_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sat_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sat_socket.bind((sat.ip, sat.port))
            sat_socket.settimeout(5)  # 设置15秒超时
            sockets[sat.id] = sat_socket
            print(f"成功绑定卫星 {sat.id} 到 {sat.ip}:{sat.port}")
        except OSError as e:
            print(f"绑定失败 - 卫星ID: {sat.id}, IP: {sat.ip}, 端口: {sat.port}")
            print(f"错误详情: {e}")
            return []

    # 获取最后一颗卫星信息
    if current_path:
        last_satellite = current_path[-1]
        last_sat_ip = last_satellite.ip
        last_sat_port = last_satellite.port
        print(f"最后一颗卫星: {last_satellite.id}, IP: {last_sat_ip}, 端口: {last_sat_port}")
    else:
        print("路径为空，无法确定最后一颗卫星")
        return []

    print(f"开始沿路径转发视频流：{[sat.id for sat in current_path]}")
    packet_count = 0
    consecutive_empty = 0
    signal.signal(signal.SIGALRM, timeout_handler)

    output_file_name = f"received_video_{time.time()}.ts"
    current_dir = os.getcwd()
    output_file_path = os.path.join(current_dir, output_file_name)
    print(f"输出文件路径: {output_file_path}")

    # 检查目录是否可写
    try:
        test_file = os.path.join(current_dir, "test_write.txt")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        print("当前目录可写")
    except Exception as e:
        print(f"错误: 当前目录不可写 - {e}")
        return []

    # 创建一个管道用于将数据从最后一颗卫星的套接字传输到FFmpeg
    ffmpeg_process = None
    ffmpeg_receive_process = None

    try:
        # 1. 首先启动FFmpeg接收进程，从stdin读取数据
        ffmpeg_receive_cmd = [
            'ffmpeg',
            '-i', '-',  # 从标准输入读取数据
            '-c:v', 'copy',  # 直接复制视频流，不重新编码
            '-c:a', 'aac',  # 使用AAC音频编码，兼容性更好
            '-f', 'mp4',  # 使用MP4容器
            '-movflags', 'frag_keyframe+empty_moov',  # 适合流媒体的MP4选项
            output_file_path
        ]
        print(f"执行命令: {' '.join(ffmpeg_receive_cmd)}")
        ffmpeg_receive_process = subprocess.Popen(
            ffmpeg_receive_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            # 移除universal_newlines=True参数，以二进制模式处理输入输出
        )
        print(f"FFmpeg接收进程已启动，输出文件: {output_file_path}")

        # 给接收进程足够的时间启动
        print("等待FFmpeg接收进程准备就绪...")
        time.sleep(1)

        # 检查FFmpeg接收进程是否立即退出
        if ffmpeg_receive_process.poll() is not None:
            # 使用communicate()获取输出
            stdout, stderr = ffmpeg_receive_process.communicate()
            print(f"FFmpeg接收进程异常退出，返回码: {ffmpeg_receive_process.returncode}")
            print(f"标准输出:\n{stdout.decode('utf-8', errors='ignore')}")
            print(f"标准错误:\n{stderr.decode('utf-8', errors='ignore')}")
            return []

    except Exception as e:
        print(f"启动FFmpeg接收进程失败: {e}")
        # 清理资源
        for sock in sockets.values():
            sock.close()
        return []

    # 2. 然后启动FFmpeg发送进程
    try:
        ffmpeg_cmd = [
            'ffmpeg',
            '-re',  # 以本地帧率发送，避免一次性发送所有帧
            '-i', 'short.mp4',
            '-c:v', 'libx264',  # 视频编码
            '-preset', 'ultrafast',  # 使用最快的编码预设，减少延迟
            '-tune', 'zerolatency',  # 优化零延迟
            '-b:v', '2000k',  # 设置视频比特率
            '-maxrate', '2500k',  # 设置最大比特率
            '-bufsize', '4000k',  # 设置缓冲区大小
            '-c:a', 'aac',  # 音频编码为AAC
            '-b:a', '128k',  # 音频比特率
            '-f', 'mpegts',  # 容器格式
            f"udp://{first_sat_ip}:{first_sat_port}?pkt_size=1316&buffer_size=65536"  # UDP参数优化
        ]
        print(f"执行命令: {' '.join(ffmpeg_cmd)}")
        ffmpeg_process = subprocess.Popen(ffmpeg_cmd,
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE,
                                          # 移除universal_newlines=True参数
                                          )
        print(f"视频流已启动，目标卫星：{first_satellite}，IP: {first_sat_ip}:{first_sat_port}")
        print(f"视频流沿路径 {satellite_ids} 转发")

        # 检查FFmpeg是否立即退出
        time.sleep(1)
        if ffmpeg_process.poll() is not None:
            # 使用communicate()获取输出
            stdout, stderr = ffmpeg_process.communicate()
            print(f"FFmpeg发送进程异常退出，返回码: {ffmpeg_process.returncode}")
            print(f"标准输出:\n{stdout.decode('utf-8', errors='ignore')}")
            print(f"标准错误:\n{stderr.decode('utf-8', errors='ignore')}")
            return []

    except Exception as e:
        print(f"启动FFmpeg失败: {e}")
        # 清理资源
        if ffmpeg_receive_process:
            ffmpeg_receive_process.terminate()
        for sock in sockets.values():
            sock.close()
        return []

    try:
        # 记录最后一次收到数据的时间
        last_receive_time = time.time()
        while True:
            try:
                # 设置全局超时，如30秒内没有任何数据，认为传输完成
                signal.alarm(50)

                data_received = False  # 标记本轮是否收到数据

                for i, sat in enumerate(current_path):
                    if i == 0:
                        try:
                            # 第一颗卫星接收FFmpeg流
                            data, addr = sockets[sat.id].recvfrom(16384)  # 增大缓冲区
                            data_received = True
                            last_receive_time = time.time()
                            print(f"Sat{sat.id} 接收视频包，大小：{len(data)}字节")
                        except socket.timeout:
                            print(f"Sat{sat.id} 接收超时")
                            continue
                    else:
                        # 后续卫星从上游卫星接收数据
                        prev_sat = current_path[i - 1]
                        try:
                            data, _ = sockets[prev_sat.id].recvfrom(16384)
                            if not data:
                                consecutive_empty += 1
                                if consecutive_empty > 5:  # 如果连续5次没有数据，认为传输结束
                                    raise TimeoutError("连续多次无数据，传输可能已完成")
                                continue
                            else:
                                consecutive_empty = 0
                                data_received = True
                                last_receive_time = time.time()
                        except socket.timeout:
                            print(f"Sat{sat.id} 接收超时")
                            continue

                    if i < len(current_path) - 1:
                        # 转发到下一颗卫星
                        next_sat = current_path[i + 1]
                        sockets[sat.id].sendto(data, (next_sat.ip, next_sat.port))
                        print(f"Sat{sat.id} → Sat{next_sat.id} 转发视频包")
                    else:
                        # 最后一颗卫星：将数据写入FFmpeg进程的stdin
                        if ffmpeg_receive_process.stdin:
                            try:
                                ffmpeg_receive_process.stdin.write(data)
                                ffmpeg_receive_process.stdin.flush()
                                packet_count += 1
                                if packet_count % 100 == 0:
                                    print(f"Sat{sat.id} 已向FFmpeg写入 {packet_count} 个数据包")
                            except Exception as e:
                                print(f"向FFmpeg写入数据时出错: {e}")
                                raise

                if not data_received:
                    if time.time() - last_receive_time > 45:
                        raise TimeoutError("长时间无数据，传输已完成！")

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

        # 关闭FFmpeg接收进程的stdin
        if ffmpeg_receive_process and ffmpeg_receive_process.stdin:
            try:
                ffmpeg_receive_process.stdin.close()
            except Exception:
                pass

        for sock in sockets.values():
            sock.close()

        # 等待FFmpeg进程结束并获取输出
        if ffmpeg_process and ffmpeg_process.poll() is None:
            print("等待FFmpeg发送进程结束...")
            ffmpeg_process.terminate()
            try:
                stdout, stderr = ffmpeg_process.communicate(timeout=5)
                print(f"FFmpeg发送进程已终止，返回码: {ffmpeg_process.returncode}")
                print(f"标准输出:\n{stdout.decode('utf-8', errors='ignore')}")
                print(f"标准错误:\n{stderr.decode('utf-8', errors='ignore')}")
            except subprocess.TimeoutExpired:
                print("FFmpeg发送进程超时，强制终止")
                ffmpeg_process.kill()

        if ffmpeg_receive_process and ffmpeg_receive_process.poll() is None:
            print("等待FFmpeg接收进程结束...")
            ffmpeg_receive_process.terminate()
            try:
                stdout, stderr = ffmpeg_receive_process.communicate(timeout=10)
                print(f"FFmpeg接收进程已终止，返回码: {ffmpeg_receive_process.returncode}")
                print(f"标准输出:\n{stdout.decode('utf-8', errors='ignore')}")
                print(f"标准错误:\n{stderr.decode('utf-8', errors='ignore')}")
            except subprocess.TimeoutExpired:
                print("FFmpeg接收进程超时，强制终止")
                ffmpeg_receive_process.kill()

        # 验证文件大小
        try:
            if os.path.exists(output_file_path):
                file_size = os.path.getsize(output_file_path) / 1024 / 1024
                print(f"视频下载完成，共转发 {packet_count} 个数据包，文件大小：{file_size:.2f} MB")
            else:
                print(f"错误: 文件未生成 - {output_file_path}")
        except Exception as e:
            print(f"验证文件时出错: {e}")

    return current_path