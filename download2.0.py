import os
import time
import threading
import requests
import random
import string
import math
from urllib.parse import urlparse
from pathlib import Path
import shutil
import sys
import ctypes

# Windows控制台标题设置
if os.name == 'nt':
    ctypes.windll.kernel32.SetConsoleTitleW("下载管理器")


class DownloadManager:
    def __init__(self):
        self.url = ""
        self.download_path = os.path.join(os.path.expanduser("~"), "Downloads")
        self.delete_time = 0
        self.active = False
        self.stop_requested = False
        self.download_thread = None
        self.delete_timer = None
        self.download_progress = {"percent": 0, "downloaded": 0, "total": 0, "speed": 0}
        self.last_update_time = 0
        self.last_downloaded = 0

    @staticmethod
    def validate_url(url):
        """验证URL格式是否有效"""
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https') and parsed.netloc

    @staticmethod
    def get_filename(url, headers=None):
        """从URL或响应头提取文件名，或生成随机文件名"""
        filename = os.path.basename(urlparse(url).path)

        # 尝试从Content-Disposition获取文件名
        if headers and 'Content-Disposition' in headers:
            content_disposition = headers['Content-Disposition']
            if 'filename=' in content_disposition:
                filename = content_disposition.split('filename=')[1].strip('"\'')

        # 如果仍无有效文件名，生成随机文件名
        if not filename or '.' not in filename:
            ext = DownloadManager.guess_extension(headers) if headers else '.bin'
            filename = f"file_{''.join(random.choices(string.ascii_letters + string.digits, k=8))}{ext}"

        return filename

    @staticmethod
    def guess_extension(headers):
        """根据Content-Type猜测文件扩展名"""
        content_type = headers.get('Content-Type',
                                   'application/octet-stream') if headers else 'application/octet-stream'
        content_type = content_type.split(';')[0]

        extensions = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'application/pdf': '.pdf',
            'application/zip': '.zip',
            'text/plain': '.txt',
            'text/csv': '.csv',
            'application/json': '.json',
            'video/mp4': '.mp4',
            'audio/mpeg': '.mp3',
            'application/msword': '.doc',
            'application/vnd.ms-excel': '.xls',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx'
        }
        return extensions.get(content_type, '.bin')

    def download_file(self):
        """执行文件下载操作"""
        self.active = True
        self.stop_requested = False

        try:
            while not self.stop_requested:
                # 获取文件信息
                with requests.head(self.url, allow_redirects=True) as response:
                    response.raise_for_status()
                    filename = self.get_filename(self.url, response.headers)
                    file_path = Path(self.download_path) / filename
                    content_length = int(response.headers.get('Content-Length', 0))

                # 确保下载目录存在
                os.makedirs(self.download_path, exist_ok=True)

                # 重置进度信息
                self.download_progress = {
                    "percent": 0,
                    "downloaded": 0,
                    "total": content_length,
                    "speed": 0
                }
                self.last_update_time = time.time()
                self.last_downloaded = 0

                # 处理文件存在的情况
                if file_path.exists():
                    print(f"\n文件已存在: {file_path}")
                    choice = input("是否删除? (y/n): ").lower()
                    if choice == 'y':
                        try:
                            file_path.unlink()
                            print("文件已删除，将重新下载")
                        except OSError as e:
                            print(f"删除失败: {str(e)}")
                            break
                    else:
                        print("停止下载任务")
                        break

                # 执行下载
                try:
                    print(f"开始下载: {self.url}")
                    start_time = time.time()

                    with requests.get(self.url, stream=True) as r:
                        r.raise_for_status()

                        # 创建临时文件
                        temp_file = file_path.with_suffix('.part')

                        with open(temp_file, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if self.stop_requested:
                                    break
                                if chunk:
                                    f.write(chunk)
                                    # 更新下载进度
                                    self.update_progress(len(chunk))

                    if self.stop_requested:
                        print("\n下载已中止")
                        try:
                            temp_file.unlink()
                        except OSError:
                            pass
                        break

                    # 重命名临时文件为最终文件
                    shutil.move(temp_file, file_path)

                    download_time = time.time() - start_time
                    print(f"\n下载完成: {file_path}")
                    print(f"文件大小: {self.format_bytes(self.download_progress['downloaded'])}")
                    print(f"下载耗时: {download_time:.1f}秒")

                    if download_time > 0:
                        avg_speed = self.download_progress['downloaded'] / download_time
                        print(f"平均速度: {self.format_bytes(avg_speed)}/s")

                    # 设置自动删除
                    if self.delete_time > 0:
                        print(f"文件将在 {self.delete_time} 秒后自动删除")
                        self.schedule_file_deletion(file_path)
                    else:
                        self.active = False
                        return

                except requests.RequestException as e:
                    print(f"\n下载失败: {str(e)}")
                    time.sleep(5)  # 等待后重试
                    continue

        finally:
            self.active = False

    def update_progress(self, chunk_size):
        """更新下载进度信息"""
        # 更新下载量
        self.download_progress["downloaded"] += chunk_size

        # 计算百分比
        if self.download_progress["total"] > 0:
            percent = self.download_progress["downloaded"] / self.download_progress["total"] * 100
            self.download_progress["percent"] = min(100.0, percent)

        # 计算下载速度
        now = time.time()
        elapsed = now - self.last_update_time

        if elapsed >= 1.0:  # 每秒更新一次速度
            downloaded_since_last = self.download_progress["downloaded"] - self.last_downloaded
            self.download_progress["speed"] = downloaded_since_last / elapsed
            self.last_downloaded = self.download_progress["downloaded"]
            self.last_update_time = now

            # 显示进度
            self.display_progress()

    def display_progress(self):
        """显示下载进度条"""
        percent = self.download_progress["percent"]
        downloaded = self.download_progress["downloaded"]
        total = self.download_progress["total"]
        speed = self.download_progress["speed"]

        # 进度条长度
        bar_length = 50
        filled_length = int(bar_length * percent / 100)
        bar = '█' * filled_length + '-' * (bar_length - filled_length)

        # 文件大小显示
        size_info = f"{self.format_bytes(downloaded)}"
        if total > 0:
            size_info += f"/{self.format_bytes(total)}"

        # 速度显示
        speed_info = f"{self.format_bytes(speed)}/s" if speed > 0 else "等待中..."

        # 百分比显示
        percent_info = f"{percent:.1f}%" if percent < 100 else "100%"

        # 组合显示
        progress_info = f"\r[{bar}] {percent_info} | {size_info} | {speed_info}"

        # 清除当前行并输出
        try:
            # 获取终端宽度
            if os.name == 'nt':
                # Windows获取终端宽度
                from ctypes import windll, create_string_buffer
                h = windll.kernel32.GetStdHandle(-11)
                csbi = create_string_buffer(22)
                res = windll.kernel32.GetConsoleScreenBufferInfo(h, csbi)
                if res:
                    width = csbi.ix
                else:
                    width = 80
            else:
                # 非Windows系统
                width = os.get_terminal_size().columns

            print(progress_info.ljust(width - 1), end='', flush=True)
        except:
            # 回退方案
            print(progress_info, end='', flush=True)

    @staticmethod
    def format_bytes(size_bytes):
        """格式化字节大小为易读格式"""
        if size_bytes <= 0:
            return "0B"

        size_units = ("B", "KB", "MB", "GB", "TB")
        exponent = int(math.floor(math.log(size_bytes, 1024)))
        divisor = math.pow(1024, exponent)
        size_value = round(size_bytes / divisor, 2)
        return f"{size_value} {size_units[exponent]}"

    def schedule_file_deletion(self, file_path):
        """安排文件删除任务"""
        if self.delete_timer and self.delete_timer.is_alive():
            self.delete_timer.cancel()

        self.delete_timer = threading.Timer(self.delete_time, self.delete_and_restart, [file_path])
        self.delete_timer.daemon = True
        self.delete_timer.start()

        # 显示等待进度
        self.show_progress(self.delete_time)

    def show_progress(self, seconds):
        """显示点状进度动画"""
        print(f"\n等待删除 ({seconds}秒):", end='', flush=True)
        for i in range(seconds):
            if self.stop_requested:
                print("\n等待已取消")
                return
            # 每10秒显示一次剩余时间
            if i % 10 == 0:
                remaining = seconds - i
                print(f"\n剩余时间: {remaining}秒", end='', flush=True)
            print('.', end='', flush=True)
            time.sleep(1)
        print()

    def delete_and_restart(self, file_path):
        """删除文件并重启下载"""
        try:
            if file_path.exists():
                file_path.unlink()
                print(f"\n文件已删除: {file_path}")
            self.download_file()  # 重新开始下载
        except OSError as e:
            print(f"\n删除文件时出错: {str(e)}")
            self.active = False

    def start_download(self):
        """启动下载线程"""
        if self.download_thread and self.download_thread.is_alive():
            print("下载已在运行中")
            return

        if not self.validate_url(self.url):
            print("无效的URL格式，请使用HTTP/HTTPS链接")
            return

        self.download_thread = threading.Thread(target=self.download_file, daemon=True)
        self.download_thread.start()
        print("下载任务已启动")

    def stop_download(self):
        """停止所有下载和删除任务"""
        self.stop_requested = True
        if self.delete_timer and self.delete_timer.is_alive():
            self.delete_timer.cancel()
        print("\n操作已停止")


def display_settings(manager):
    """显示当前设置"""
    print("\n" + "=" * 50)
    print("下载管理器".center(50))
    print("=" * 50)
    print(f"1. 下载链接: {manager.url or '未设置'}")
    print(f"2. 下载路径: {manager.download_path}")
    print(f"3. 删除时间: {manager.delete_time} 秒 (0=不删除)")
    print("4. 开始下载")
    print("5. 停止下载")
    print("6. 退出程序")
    print("=" * 50)

    # 显示下载进度（如果正在下载）
    if manager.active and manager.download_progress["downloaded"] > 0:
        progress = manager.download_progress
        if progress["total"] > 0:
            print(f"下载进度: {progress['percent']:.1f}%")
        else:
            print(f"已下载: {manager.format_bytes(progress['downloaded'])}")

        if progress["speed"] > 0:
            print(f"下载速度: {manager.format_bytes(progress['speed'])}/s")


def clear_screen():
    """清屏函数，兼容Windows和类Unix系统"""
    if os.name == 'nt':
        os.system('cls')
    else:
        os.system('clear')


def main_menu(manager):
    """主菜单系统"""
    while True:
        clear_screen()
        display_settings(manager)

        try:
            choice = input("\n请选择操作 (1-6): ")
        except KeyboardInterrupt:
            return True

        if choice == '1':
            url = input("请输入下载链接: ").strip()
            if manager.validate_url(url):
                manager.url = url
            else:
                print("无效的URL! 请使用有效的HTTP/HTTPS链接")
                time.sleep(1.5)

        elif choice == '2':
            path = input(f"请输入下载路径 (默认为{manager.download_path}): ").strip()
            if path:
                path = Path(path)
                if not path.exists():
                    try:
                        path.mkdir(parents=True, exist_ok=True)
                        manager.download_path = str(path)
                        print(f"已创建目录: {path}")
                    except OSError as e:
                        print(f"创建目录失败: {str(e)}")
                        time.sleep(1.5)
                else:
                    manager.download_path = str(path)

        elif choice == '3':
            try:
                time_sec = int(input("请输入删除等待时间 (秒): "))
                if 0 <= time_sec <= 3600 * 24:  # 允许最多1天
                    manager.delete_time = time_sec
                else:
                    print("时间必须在0-86400秒之间 (0表示不删除)")
                    time.sleep(1.5)
            except ValueError:
                print("请输入有效的整数")
                time.sleep(1.5)

        elif choice == '4':
            if not manager.url:
                print("请先设置下载链接!")
                time.sleep(1.5)
            else:
                manager.start_download()
                # 等待下载启动
                time.sleep(1)

        elif choice == '5':
            manager.stop_download()
            time.sleep(1.5)

        elif choice == '6':
            manager.stop_download()
            print("程序退出")
            return False

        else:
            print("无效选择，请重新输入")
            time.sleep(1.0)

        return True


def main():
    """程序主入口"""
    # Windows控制台支持UTF-8编码
    if os.name == 'nt':
        os.system("chcp 65001 > nul")

    print("正在启动下载管理器...")
    time.sleep(0.5)

    manager = DownloadManager()

    while True:
        try:
            if not main_menu(manager):
                break
        except KeyboardInterrupt:
            print("\n检测到中断请求...")
            manager.stop_download()
            choice = input("是否要退出程序? (y/n): ").lower()
            if choice == 'y':
                print("程序退出")
                break


if __name__ == "__main__":
    main()