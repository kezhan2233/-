# 多线程下载管理器

这个 Python 程序是一个功能强大的多线程下载管理器，支持自动文件删除、断点续传、多线程下载等功能，并提供了直观的图形用户界面（GUI）。

此项目的最大作用是提高自己宽带的下载量确保不会被3大运营商给标记PCDN，本方法只能降低风险。且本程序仅供学习参考。

再说一点，本程序全由ai协助完成。如有其他需要的功能可以提出，我尝试着添加

## 功能特点

### 📥 核心下载功能

- 支持 HTTP/HTTPS 下载
- 自动识别文件名（从 URL 或 Content-Disposition 头）
- 自动识别文件扩展名（基于 Content-Type）
- 支持单线程和多线程下载模式
- 自动检测服务器是否支持多线程下载（Range 请求）
- 大文件（>1MB）自动启用多线程下载

### ⚙️ 多线程下载

- 可配置线程数量（1-32 个线程）
- 动态分块下载
- 智能合并下载块
- 失败分块自动重试机制

### 🗑️ 自动文件管理

- 可设置文件自动删除时间（0-3600 秒）
- 文件占用检测和自动解锁
- 文件存在检测和用户确认删除
- 带重试机制的文件删除功能

### 📊 进度监控

- 实时下载进度显示
- 下载速度计算
- 已下载大小和总大小显示
- 百分比进度条

### 🪟 用户友好界面

- 直观的下载设置面板
- 详细的日志记录
- 重启次数计数器
- 线程状态显示

## 使用方法

### 基本操作

1. 输入下载 URL
2. 设置下载路径（默认为 D:\）
3. 设置自动删除时间（0 表示不自动删除）
4. 选择线程数量和是否启用多线程
5. 点击 "开始下载" 按钮

### 高级功能

- 解锁文件：当文件被锁定时尝试解锁
- 停止下载：随时中断下载过程
- 浏览目录：选择自定义下载路径

### 文件存在处理

当下载路径已存在同名文件时：

- 程序会提示用户是否删除
- 用户确认后会尝试多次删除（最多 5 次）
- 删除成功后自动开始下载

## 技术栈

- Python 3.x
- GUI 框架：Tkinter
- 网络请求：Requests 库
- 多线程处理：Threading, concurrent.futures
- 文件操作：Pathlib, shutil
- 进度显示：ttk.Progressbar

## 安装与运行

### 依赖安装

```bash
pip install requests
```

### 运行程序

```bash
python download_manager.py
```

## 应用场景

- 定期下载需要自动清理的文件
- 需要高速下载大文件
- 需要稳定下载支持断点续传
- 需要管理下载文件的生命周期
- 需要详细日志记录的下载任务

## 程序截图

![屏幕截图 2025-06-27 203247.png](https://lsky.photo.crhtdg.com/imgs/2025/06/kdtrjorg.png)

## 贡献指南

欢迎提交问题和拉取请求！请确保：

- 在提交 PR 前运行测试
- 遵循现有的代码风格
- 为重大更改添加适当的文档

## 许可证

本项目采用 MIT 许可证 - 详见 LICENSE 文件。