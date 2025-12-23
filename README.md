# Image Toolbox (图片工具箱)
[![Release](https://github.com/EIHRTeam/image-toolbox/actions/workflows/release.yml/badge.svg)](https://github.com/EIHRTeam/image-toolbox/actions/workflows/release.yml)
[![Build](https://github.com/EIHRTeam/image-toolbox/actions/workflows/build.yml/badge.svg)](https://github.com/EIHRTeam/image-toolbox/actions/workflows/build.yml)
![Version](https://img.shields.io/badge/version-0.1.1-blue) ![Tauri](https://img.shields.io/badge/Tauri-v2-orange) ![Vue](https://img.shields.io/badge/Vue-3-green)

基于 **Tauri v2** 与 **Vue 3** 开发的桌面端图片批处理软件。

> [!TIP]
> 善用右上角的文档索引按钮以快速跳转章节。

## 🚀 下载安装

### 方式一：Release 版本（推荐）

前往仓库的 Releases 页面下载 `.exe` 或 `.msi` 安装程序：

🔗 [Latest Releases](https://github.com/EIHRTeam/image-toolbox/releases/latest)

### 方式二：Actions 构建产物

在 GitHub Actions 页面下载最近一次成功构建的开发版产物。

## ✨ 功能概览

Image Toolbox 提供以下核心能力：

### 1. 图片批量压缩 (Image Compressor)
* **高性能处理**：基于 FFmpeg 实现高性能图片转码与缩放。
* **多格式支持**：支持输出 PNG、JPG、WebP 等常见格式。
* **灵活缩放**：支持固定尺寸或按比例倍数缩放。
* **配置驱动**：支持加载多个 Profile 配置，并提供执行前的预览模式（Review Mode）。

### 2. 智能裁剪 (Smart Crop)
* **视觉算法**：基于 **OpenCV + SIFT** 特征匹配算法。
* **自动定位**：根据模版图片自动在目标图片中定位并裁剪相同区域。
* **双模输出**：支持同时输出高清原图裁剪和固定尺寸缩略图。

### 3. 工作流集成
* **Git 自动化**：自动检测输入/输出目录的 Git 仓库状态，支持处理后自动 Commit & Push。
* **环境向导**：内置 FFmpeg 与 Python 环境（pip 依赖）检测与一键安装向导。

## 📖 快速上手

### 图片压缩
1. **启动应用**：选择“图片压缩”标签页。
2. **配置参数**：设置输入输出目录、目标格式和尺寸。
3. **执行任务**：点击开始按钮。

### 智能裁剪
1. **准备模版**：准备包含目标特征的小图作为模版。
2. **配置路径**：
   - **Templates Folder**：存放模版图片的文件夹。
   - **Source Input**：需要被裁剪的原始大图文件夹。
3. **选择模式**：勾选“高清裁剪”或“固定尺寸”。
4. **执行**：点击 "Start Cropping"。

## 🛠️ 配置文件说明 (`settings.json`)

Image Toolbox 支持通过 JSON 定义复杂的处理任务。每个键值对代表一个独立的 Profile。

### 示例配置

```json
{
  "resize_webp_1920x1080": {
    "enable": true,
    "description": "Convert images to webp and resize to 1920x1080",
    "input_folder": "./input",
    "output_folder": "./output",
    "format": "webp",
    "resize_method": "fixed",
    "width": 1920,
    "height": 1080,
    "fixed_mode": "crop"
  }
}
```

## 📦 环境依赖

应用运行依赖以下外部环境：

### 1. FFmpeg
* **用途**：图片压缩、格式转换、缩放。
* **安装**：应用内“设置”页面提供一键安装向导。

### 2. Python
* **用途**：智能裁剪。
* **要求**：Python 3.x，并安装 `opencv-python` 和 `numpy` 库。
* **配置**：应用内“设置”页面提供依赖检查与 `pip` 一键安装功能。

## 💻 开发者指南

如果您希望自行构建或参与开发：

1. **安装依赖**：
```bash
npm install
```

2. **启动开发模式**：
```bash
npm run tauri dev
```

3. **构建发布版本**：
```bash
npm run tauri build
```

## ❓ 常见问题

1. **智能裁剪无法运行？**
* 请确保已安装 Python，并且在“设置”页中检查 `opencv-python` 和 `numpy` 是否已安装。

2. **Git 自动提交失败？**
* 确保输入/输出目录位于有效的 Git 仓库内。
* 检查本地是否已配置 Git 用户信息 (`user.name`, `user.email`)。

## 📜 许可证

本项目采用 **GNU General Public License v3.0** 许可协议。

详细信息请参阅 [LICENSE](./LICENSE.txt) 文件。

© **Endfield Industry Human Resources Team**, Some Rights Reserved.