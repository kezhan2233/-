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
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import sys


class DownloadManager:
    def __init__(self, gui_callback=None):
        self.url = ""
        self.download_path = "D:\\"
        self.delete_time = 0
        self.active = False
        self.stop_requested = False
        self.download_thread = None
        self.delete_timer = None
        self.download_progress = {"percent": 0, "downloaded": 0, "total": 0, "speed": 0}
        self.last_update_time = 0
        self.last_downloaded = 0
        self.gui_callback = gui_callback
        self.current_file = None
        self.is_restarting = False  # 新增：标记是否在重启过程中
        self.download_completed = False  # 新增：标记下载是否完成

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
            'application/vnd.android.package-archive': '.apk'
        }
        return extensions.get(content_type, '.bin')

    def download_file(self):
        """执行文件下载操作"""
        self.active = True
        self.stop_requested = False
        self.is_restarting = False
        self.download_completed = False

        try:
            while not self.stop_requested:
                # 获取文件信息
                with requests.head(self.url, allow_redirects=True) as response:
                    response.raise_for_status()
                    filename = self.get_filename(self.url, response.headers)
                    file_path = Path(self.download_path) / filename
                    content_length = int(response.headers.get('Content-Length', 0))
                    self.current_file = file_path

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
                if file_path.exists() and not self.is_restarting:
                    self.log_message(f"文件已存在: {file_path}")
                    if self.gui_callback:
                        choice = self.gui_callback("file_exists", f"文件已存在: {file_path}\n是否删除?")
                    else:
                        choice = input("是否删除? (y/n): ").lower()

                    if choice == 'y':
                        try:
                            # 尝试删除前关闭可能打开的文件句柄
                            if self.is_file_locked(file_path):
                                self.log_message(f"文件被占用，无法删除: {file_path}")
                                self.log_message("请关闭使用此文件的程序后重试")
                                break

                            file_path.unlink()
                            self.log_message("文件已删除，将重新下载")
                        except OSError as e:
                            self.log_message(f"删除失败: {str(e)}")
                            break
                    else:
                        self.log_message("停止下载任务")
                        break

                # 执行下载
                try:
                    self.log_message(f"开始下载: {self.url}")
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
                        self.log_message("\n下载已中止")
                        try:
                            temp_file.unlink()
                        except OSError:
                            pass
                        break

                    # 重命名临时文件为最终文件
                    self.rename_with_retry(temp_file, file_path)

                    download_time = time.time() - start_time
                    self.log_message(f"\n下载完成: {file_path}")
                    self.log_message(f"文件大小: {self.format_bytes(self.download_progress['downloaded'])}")
                    self.log_message(f"下载耗时: {download_time:.1f}秒")

                    if download_time > 0:
                        avg_speed = self.download_progress['downloaded'] / download_time
                        self.log_message(f"平均速度: {self.format_bytes(avg_speed)}/s")

                    # 标记下载完成
                    self.download_completed = True

                    # 设置自动删除
                    if self.delete_time > 0:
                        self.log_message(f"文件将在 {self.delete_time} 秒后自动删除")
                        self.schedule_file_deletion(file_path)
                        break  # 退出下载循环，等待删除完成
                    else:
                        self.active = False
                        return

                except requests.RequestException as e:
                    self.log_message(f"\n下载失败: {str(e)}")
                    time.sleep(5)  # 等待后重试
                    continue

        finally:
            self.active = False
            self.current_file = None

    def rename_with_retry(self, src, dst, max_retries=5, retry_delay=1):
        """重命名文件，带重试机制解决文件占用问题"""
        for i in range(max_retries):
            try:
                # 尝试直接重命名
                src.rename(dst)
                return True
            except (PermissionError, OSError) as e:
                if i < max_retries - 1:
                    self.log_message(f"文件占用，等待重试 ({i + 1}/{max_retries})...")
                    time.sleep(retry_delay)
                else:
                    # 最后一次尝试
                    try:
                        # 尝试复制后删除源文件
                        shutil.copy2(src, dst)
                        src.unlink()
                        self.log_message("使用复制方式完成文件移动")
                        return True
                    except Exception as e:
                        self.log_message(f"文件移动失败: {str(e)}")
                        raise e

        return False

    @staticmethod
    def is_file_locked(filepath):
        """检查文件是否被其他进程锁定"""
        if not filepath.exists():
            return False

        try:
            # 尝试以写入模式打开文件
            with open(filepath, 'a') as f:
                pass
            return False
        except IOError:
            return True

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

            # 更新GUI进度
            if self.gui_callback:
                self.gui_callback("progress_update", self.download_progress)

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
        self.log_message(f"\n等待删除 ({seconds}秒):")
        for i in range(seconds):
            if self.stop_requested:
                self.log_message("\n等待已取消")
                return
            # 每10秒显示一次剩余时间
            if i % 10 == 0:
                remaining = seconds - i
                self.log_message(f"\n剩余时间: {remaining}秒")
            time.sleep(1)
        self.log_message("\n")

    def delete_and_restart(self, file_path):
        """删除文件并重启下载"""
        try:
            if file_path.exists():
                # 检查文件是否被占用
                if self.is_file_locked(file_path):
                    self.log_message(f"\n文件被占用，无法删除: {file_path}")
                    self.log_message("请关闭使用此文件的程序后重试")
                else:
                    file_path.unlink()
                    self.log_message(f"\n文件已删除: {file_path}")

            # 标记正在重启
            self.is_restarting = True

            # 重新开始下载
            self.start_download()
        except OSError as e:
            self.log_message(f"\n删除文件时出错: {str(e)}")
            self.active = False

    def start_download(self):
        """启动下载线程"""
        # 如果已有下载线程在运行，先停止它
        if self.download_thread and self.download_thread.is_alive():
            self.log_message("停止当前下载任务...")
            self.stop_download()
            time.sleep(1)  # 等待线程停止

        # 创建新的下载线程
        self.download_thread = threading.Thread(target=self.download_file, daemon=True)
        self.download_thread.start()
        self.log_message("下载任务已启动")

    def stop_download(self):
        """停止所有下载和删除任务"""
        self.stop_requested = True
        if self.delete_timer and self.delete_timer.is_alive():
            self.delete_timer.cancel()
        self.log_message("\n操作已停止")

    def log_message(self, message):
        """记录消息，并通过回调发送到GUI"""
        if self.gui_callback:
            self.gui_callback("log", message)


class DownloadManagerGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("下载管理器")
        self.geometry("800x600")
        self.resizable(True, True)

        # 创建下载管理器实例
        self.download_manager = DownloadManager(gui_callback=self.gui_callback)

        # 设置UI
        self.create_widgets()

        # 用于更新进度的定时器
        self.progress_update_timer = None

    def create_widgets(self):
        # 创建主框架
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 下载链接部分
        url_frame = ttk.LabelFrame(main_frame, text="下载设置", padding="10")
        url_frame.pack(fill=tk.X, pady=5)

        ttk.Label(url_frame, text="下载链接:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.url_entry = ttk.Entry(url_frame, width=60)
        self.url_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=5)

        # 下载路径部分
        ttk.Label(url_frame, text="下载路径:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.path_entry = ttk.Entry(url_frame, width=50)
        self.path_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=5)
        self.path_entry.insert(0, "D:\\")

        browse_btn = ttk.Button(url_frame, text="浏览...", command=self.browse_directory)
        browse_btn.grid(row=1, column=2, padx=5, pady=5)

        # 删除时间部分
        ttk.Label(url_frame, text="删除时间(秒):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.delete_time_var = tk.StringVar()
        self.delete_time_entry = ttk.Entry(url_frame, width=10, textvariable=self.delete_time_var)
        self.delete_time_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        self.delete_time_var.set("0")
        ttk.Label(url_frame, text="0=不删除, 1-3600秒").grid(row=2, column=2, sticky=tk.W, padx=5, pady=5)

        # 按钮部分
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)

        self.start_btn = ttk.Button(button_frame, text="开始下载", command=self.start_download)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(button_frame, text="停止下载", command=self.stop_download, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        self.unlock_btn = ttk.Button(button_frame, text="解锁文件", command=self.unlock_file, state=tk.DISABLED)
        self.unlock_btn.pack(side=tk.LEFT, padx=5)

        exit_btn = ttk.Button(button_frame, text="退出程序", command=self.destroy)
        exit_btn.pack(side=tk.RIGHT, padx=5)

        # 进度条部分
        progress_frame = ttk.LabelFrame(main_frame, text="下载进度", padding="10")
        progress_frame.pack(fill=tk.X, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var,
                                            maximum=100, length=700, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=5)

        # 状态标签
        status_frame = ttk.Frame(progress_frame)
        status_frame.pack(fill=tk.X, pady=5)

        ttk.Label(status_frame, text="进度:").pack(side=tk.LEFT, padx=5)
        self.percent_label = ttk.Label(status_frame, text="0%")
        self.percent_label.pack(side=tk.LEFT, padx=5)

        ttk.Label(status_frame, text="已下载:").pack(side=tk.LEFT, padx=5)
        self.downloaded_label = ttk.Label(status_frame, text="0B")
        self.downloaded_label.pack(side=tk.LEFT, padx=5)

        ttk.Label(status_frame, text="总大小:").pack(side=tk.LEFT, padx=5)
        self.total_label = ttk.Label(status_frame, text="0B")
        self.total_label.pack(side=tk.LEFT, padx=5)

        ttk.Label(status_frame, text="速度:").pack(side=tk.LEFT, padx=5)
        self.speed_label = ttk.Label(status_frame, text="0B/s")
        self.speed_label.pack(side=tk.LEFT, padx=5)

        # 日志区域
        log_frame = ttk.LabelFrame(main_frame, text="日志信息", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)

        # 配置网格列权重
        url_frame.columnconfigure(1, weight=1)
        main_frame.columnconfigure(0, weight=1)

    def browse_directory(self):
        """打开文件夹选择对话框"""
        directory = filedialog.askdirectory()
        if directory:
            self.path_entry.delete(0, tk.END)
            self.path_entry.insert(0, directory)

    def start_download(self):
        """开始下载任务"""
        # 获取用户输入
        self.download_manager.url = self.url_entry.get()
        self.download_manager.download_path = self.path_entry.get()

        try:
            self.download_manager.delete_time = int(self.delete_time_var.get())
            if not (0 <= self.download_manager.delete_time <= 3600):
                messagebox.showerror("错误", "删除时间必须在0-3600秒之间")
                return
        except ValueError:
            messagebox.showerror("错误", "请输入有效的整数")
            return

        # 验证下载路径
        if not os.path.exists(self.download_manager.download_path):
            try:
                os.makedirs(self.download_manager.download_path, exist_ok=True)
            except OSError as e:
                messagebox.showerror("错误", f"创建目录失败: {str(e)}")
                return

        # 验证URL
        if not self.download_manager.validate_url(self.download_manager.url):
            messagebox.showerror("错误", "无效的URL格式，请使用HTTP/HTTPS链接")
            return

        # 更新按钮状态
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.unlock_btn.config(state=tk.NORMAL)

        # 启动下载
        self.download_manager.start_download()

        # 开始更新进度
        self.update_progress()

    def stop_download(self):
        """停止下载任务"""
        self.download_manager.stop_download()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)

        # 停止进度更新
        if self.progress_update_timer:
            self.after_cancel(self.progress_update_timer)
            self.progress_update_timer = None

    def unlock_file(self):
        """尝试解锁当前文件"""
        if self.download_manager.current_file:
            file_path = self.download_manager.current_file
            try:
                # 尝试重命名文件以解锁
                temp_path = file_path.with_suffix('.unlock')
                file_path.rename(temp_path)
                temp_path.rename(file_path)
                self.log_message(f"已尝试解锁文件: {file_path}")
            except Exception as e:
                self.log_message(f"解锁失败: {str(e)}")
        else:
            self.log_message("没有正在处理的文件")

    def gui_callback(self, event_type, data):
        """处理来自下载管理器的回调"""
        if event_type == "log":
            self.log_message(data)
        elif event_type == "progress_update":
            # 更新进度信息
            self.progress_var.set(data["percent"])
            self.percent_label.config(text=f"{data['percent']:.1f}%")
            self.downloaded_label.config(text=self.download_manager.format_bytes(data["downloaded"]))
            self.total_label.config(text=self.download_manager.format_bytes(data["total"]))
            self.speed_label.config(text=f"{self.download_manager.format_bytes(data['speed'])}/s")
        elif event_type == "file_exists":
            # 文件存在确认对话框
            return messagebox.askyesno("文件已存在", data)

    def log_message(self, message):
        """向日志区域添加消息"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)  # 滚动到底部
        self.log_text.config(state=tk.DISABLED)

    def update_progress(self):
        """定期更新进度条"""
        # 更新进度信息
        progress = self.download_manager.download_progress
        self.progress_var.set(progress["percent"])
        self.percent_label.config(text=f"{progress['percent']:.1f}%")
        self.downloaded_label.config(text=self.download_manager.format_bytes(progress["downloaded"]))
        self.total_label.config(text=self.download_manager.format_bytes(progress["total"]))
        self.speed_label.config(text=f"{self.download_manager.format_bytes(progress['speed'])}/s")

        # 如果下载结束，恢复按钮状态
        if not self.download_manager.active:
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)

        # 继续更新进度
        self.progress_update_timer = self.after(1000, self.update_progress)

    def on_closing(self):
        """窗口关闭事件处理"""
        if self.download_manager.active:
            if messagebox.askokcancel("退出", "下载任务仍在运行中，确定要退出吗?"):
                self.download_manager.stop_download()
                self.destroy()
        else:
            self.destroy()


if __name__ == "__main__":
    app = DownloadManagerGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()