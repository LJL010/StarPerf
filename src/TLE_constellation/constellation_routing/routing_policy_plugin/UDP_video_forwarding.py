import socket
import time
import subprocess
import os
import signal
import threading
from queue import Queue
import queue

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

    # 初始化UDP套接字
    sockets = {}
    for sat in current_path:
        try:
            sat_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sat_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sat_socket.bind((sat.ip, sat.port))
            sat_socket.settimeout(10)  # 增加超时时间到10秒
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

    # 创建一个队列用于存储最后一颗卫星接收的数据包
    packet_queue = Queue(maxsize=1000)  # 限制队列大小，防止内存溢出
    queue_full_warnings = 0

    # 最后一颗卫星的处理线程
    def process_last_satellite(socket_id, ffmpeg_stdin):
        nonlocal packet_count, consecutive_empty, queue_full_warnings
        last_receive_time = time.time()

        while True:
            try:
                data, addr = sockets[socket_id].recvfrom(16384)
                if not data:
                    consecutive_empty += 1
                    if consecutive_empty > 10:  # 增加连续空包的阈值
                        print("连续多次无数据，可能传输已结束")
                        break
                    continue
                else:
                    consecutive_empty = 0
                    last_receive_time = time.time()

                # 将数据包放入队列
                try:
                    packet_queue.put(data, block=False)
                except queue.Full:
                    queue_full_warnings += 1
                    if queue_full_warnings % 10 == 0:  # 每10次满队列警告一次
                        print("警告: 数据包队列已满，可能丢包")

                    # 队列已满，丢弃最旧的数据包
                    try:
                        packet_queue.get_nowait()
                        packet_queue.put(data, block=False)
                    except:
                        pass  # 队列仍满，只能丢弃当前数据包

                # 打印接收状态
                packet_count += 1
                if packet_count % 100 == 0:
                    print(f"Sat{socket_id} 已接收 {packet_count} 个数据包")

            except socket.timeout:
                # 超时检查
                if time.time() - last_receive_time > 5:  # 30秒无数据视为结束
                    print("长时间无数据，传输可能已完成")
                    break
                continue
            except Exception as e:
                print(f"最后一颗卫星接收数据时出错: {e}")
                break

        print(f"最后一颗卫星处理线程退出，共接收 {packet_count} 个数据包")

    # 向FFmpeg写入数据的线程
    def write_to_ffmpeg(ffmpeg_stdin):
        last_write_time = time.time()
        consecutive_empty_writes = 0
        queue_check_count = 0  # 新增计数器
        while True:
            try:
                # 优先处理队列中的数据
                if not packet_queue.empty() or queue_check_count < 10:
                    if not packet_queue.empty():
                        data = packet_queue.get(timeout=1)  # 缩短超时时间
                        ffmpeg_stdin.write(data)
                        ffmpeg_stdin.flush()
                        last_write_time = time.time()
                        consecutive_empty_writes = 0
                        queue_check_count = 0  # 重置计数器
                    else:
                        queue_check_count += 1  # 记录空队列检查次数
                        time.sleep(0.1)  # 短暂休眠
                else:
                    consecutive_empty_writes += 1
                    if consecutive_empty_writes > 3:  # 进一步缩短阈值
                        print("向FFmpeg写入数据超时")
                        break
                    time.sleep(0.5)

            except Exception as e:
                print(f"向FFmpeg写入数据时出错: {e}")
                break

        print("FFmpeg写入线程退出")

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
        time.sleep(2)  # 增加启动等待时间

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
            f"udp://{first_sat_ip}:{first_sat_port}?pkt_size=1316&buffer_size=65536&fifo_size=131072"  # UDP参数优化
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
        time.sleep(2)  # 增加启动等待时间
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

    # 启动卫星间转发线程
    forward_threads = []
    for i, sat in enumerate(current_path):
        if i == len(current_path) - 1:
            # 最后一颗卫星由专门的线程处理
            continue

        next_sat = current_path[i + 1]

        def forward_data(sat_id, next_ip, next_port):
            sat_socket = sockets[sat_id]
            print(f"启动卫星 {sat_id} 的转发线程，目标: {next_ip}:{next_port}")

            while True:
                try:
                    data, addr = sat_socket.recvfrom(16384)
                    if not data:
                        continue

                    sat_socket.sendto(data, (next_ip, next_port))
                    # 减少打印频率，避免影响性能
                    print(f"{next_ip}:{next_port} 收到视频包！")
                except socket.timeout:
                    # 超时继续等待
                    continue
                except Exception as e:
                    print(f"卫星 {sat_id} 转发数据时出错: {e}")
                    break

        # 为每个卫星创建转发线程
        thread = threading.Thread(target=forward_data, args=(sat.id, next_sat.ip, next_sat.port), daemon=True)
        thread.start()
        forward_threads.append(thread)
        print(f"卫星 {sat.id} 的转发线程已启动")

    try:
        # 启动最后一颗卫星的处理线程
        last_sat_thread = threading.Thread(
            target=process_last_satellite,
            args=(last_satellite.id, ffmpeg_receive_process.stdin),
            daemon=True
        )
        last_sat_thread.start()

        # 启动向FFmpeg写入数据的线程
        write_thread = threading.Thread(
            target=write_to_ffmpeg,
            args=(ffmpeg_receive_process.stdin,),
            daemon=True
        )
        write_thread.start()

        # 主循环监控线程状态
        last_activity_time = time.time()
        while True:
            # 检查FFmpeg进程状态
            if ffmpeg_process.poll() is not None:
                print(f"FFmpeg发送进程已退出，返回码: {ffmpeg_process.returncode}")
                break

            if ffmpeg_receive_process.poll() is not None:
                print(f"FFmpeg接收进程已退出，返回码: {ffmpeg_receive_process.returncode}")
                break

            # 如果队列为空但FFmpeg还在运行，说明可能还在接收数据
            if not packet_queue.empty():
                last_activity_time = time.time()

            # 检查是否长时间没有活动
            if time.time() - last_activity_time > 10:  # 60秒无活动
                print("长时间没有数据包活动，退出主循环")
                break

            time.sleep(1)  # 每秒检查一次

    except Exception as e:
        print(f"转发过程中发生错误：{e}")
    finally:
        # 清理资源
        signal.alarm(0)  # 确保闹钟被关闭

        # 先停止数据写入，再关闭进程
        if ffmpeg_receive_process and ffmpeg_receive_process.stdin:
            try:
                # 发送EOF信号而非直接关闭stdin
                ffmpeg_receive_process.stdin.write(b'')
                ffmpeg_receive_process.stdin.flush()
                # 增加等待时间确保数据写入
                time.sleep(5)  # 延长至5秒
                ffmpeg_receive_process.stdin.close()
            except Exception:
                pass

        # 等待所有线程结束
        print("等待所有线程结束...")
        time.sleep(5)  # 给线程一些时间完成

        for sock in sockets.values():
            sock.close()

        # 等待FFmpeg进程结束并获取输出
        if ffmpeg_process and ffmpeg_process.poll() is None:
            print("等待FFmpeg发送进程结束...")
            ffmpeg_process.terminate()
            try:
                stdout, stderr = ffmpeg_process.communicate(timeout=10)
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
                stdout, stderr = ffmpeg_receive_process.communicate(timeout=20)
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