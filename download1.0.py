import os
import time
import threading
import requests
import random
import string
from urllib.parse import urlparse
from pathlib import Path


class DownloadManager:
    def __init__(self):
        self.url = ""
        self.download_path = "D:\\"
        self.delete_time = 0
        self.active = False
        self.stop_requested = False
        self.download_thread = None
        self.delete_timer = None

    def validate_url(self, url):
        """验证URL格式是否有效"""
        parsed = urlparse(url)
        return parsed.scheme in ('http', 'https') and parsed.netloc

    def get_filename(self, url, headers=None):
        """从URL或响应头提取文件名，或生成随机文件名"""
        filename = os.path.basename(urlparse(url).path)

        # 尝试从Content-Disposition获取文件名
        if headers and 'Content-Disposition' in headers:
            content_disp = headers['Content-Disposition']
            if 'filename=' in content_disp:
                filename = content_disp.split('filename=')[1].strip('"\'')

        # 如果仍无有效文件名，生成随机文件名
        if not filename or '.' not in filename:
            ext = self.guess_extension(headers) if headers else '.bin'
            filename = f"file_{''.join(random.choices(string.ascii_letters + string.digits, k=8))}{ext}"

        return filename

    def guess_extension(self, headers):
        """根据Content-Type猜测文件扩展名"""
        content_type = headers.get('Content-Type', 'application/octet-stream')
        extensions = {
            'image/jpeg': '.jpg',
            'image/png': '.png',
            'application/pdf': '.pdf',
            'application/zip': '.zip',
            'text/plain': '.txt',
            'text/csv': '.csv',
            'application/json': '.json'
        }
        return extensions.get(content_type.split(';')[0], '.bin')

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

                # 处理文件存在的情况
                if file_path.exists():
                    print(f"\n文件已存在: {file_path}")
                    choice = input("是否删除? (y/n): ").lower()
                    if choice == 'y':
                        try:
                            file_path.unlink()
                            print("文件已删除，将重新下载")
                        except Exception as e:
                            print(f"删除失败: {str(e)}")
                            break
                    else:
                        print("停止下载任务")
                        break

                # 执行下载
                try:
                    print(f"开始下载: {self.url}")
                    with requests.get(self.url, stream=True) as r:
                        r.raise_for_status()
                        with open(file_path, 'wb') as f:
                            for chunk in r.iter_content(chunk_size=8192):
                                if self.stop_requested:
                                    break
                                if chunk:
                                    f.write(chunk)

                    if self.stop_requested:
                        print("下载已中止")
                        break

                    print(f"\n下载完成: {file_path}")

                    # 设置自动删除
                    if self.delete_time > 0:
                        print(f"文件将在 {self.delete_time} 秒后自动删除")
                        self.schedule_file_deletion(file_path)
                    else:
                        self.active = False
                        return

                except requests.RequestException as e:
                    print(f"下载失败: {str(e)}")
                    time.sleep(5)  # 等待后重试
                    continue

        finally:
            self.active = False

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
        print("等待删除", end='', flush=True)
        for _ in range(seconds):
            if self.stop_requested:
                print("\n等待已取消")
                return
            print('.', end='', flush=True)
            time.sleep(1)
        print()

    def delete_and_restart(self, file_path):
        """删除文件并重启下载"""
        try:
            if file_path.exists():
                file_path.unlink()
                print(f"文件已删除: {file_path}")
            self.download_file()  # 重新开始下载
        except Exception as e:
            print(f"删除文件时出错: {str(e)}")
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
        print("操作已停止")


def display_settings(manager):
    """显示当前设置"""
    print("\n当前设置:")
    print(f"1. 下载链接: {manager.url or '未设置'}")
    print(f"2. 下载路径: {manager.download_path}")
    print(f"3. 删除时间: {manager.delete_time} 秒")
    print("4. 开始下载")
    print("5. 停止下载")
    print("6. 退出程序")


def main():
    """主菜单系统"""
    manager = DownloadManager()

    while True:
        display_settings(manager)
        choice = input("\n请选择操作 (1-6): ")

        if choice == '1':
            url = input("请输入下载链接: ").strip()
            if manager.validate_url(url):
                manager.url = url
            else:
                print("无效的URL! 请使用有效的HTTP/HTTPS链接")

        elif choice == '2':
            path = input("请输入下载路径 (默认为D:\\): ").strip()
            if path:
                path = Path(path)
                if not path.exists():
                    try:
                        path.mkdir(parents=True, exist_ok=True)
                        manager.download_path = str(path)
                    except Exception as e:
                        print(f"创建目录失败: {str(e)}")
                else:
                    manager.download_path = str(path)

        elif choice == '3':
            try:
                time_sec = int(input("请输入删除等待时间 (秒): "))
                if 0 <= time_sec <= 3600 * 24:  # 允许最多1天
                    manager.delete_time = time_sec
                else:
                    print("时间必须在0-86400秒之间 (0表示不删除)")
            except ValueError:
                print("请输入有效的整数")

        elif choice == '4':
            if not manager.url:
                print("请先设置下载链接!")
            else:
                manager.start_download()

        elif choice == '5':
            manager.stop_download()

        elif choice == '6':
            manager.stop_download()
            print("程序退出")
            break

        else:
            print("无效选择，请重新输入")


if __name__ == "__main__":
    main()