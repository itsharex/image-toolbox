# Image Toolbox (图片工具箱)
[![Release](https://github.com/EIHRTeam/image-toolbox/actions/workflows/release.yml/badge.svg)](https://github.com/EIHRTeam/image-toolbox/actions/workflows/release.yml)
[![Build](https://github.com/EIHRTeam/image-toolbox/actions/workflows/build.yml/badge.svg)](https://github.com/EIHRTeam/image-toolbox/actions/workflows/build.yml)
![Version](https://img.shields.io/badge/version-0.1.0-blue) ![Tauri](https://img.shields.io/badge/Tauri-v2-orange) ![Vue](https://img.shields.io/badge/Vue-3-green)

基于 **Tauri v2** 与 **Vue 3** 开发的桌面端图片批处理软件。

该工具以内置 **FFmpeg** 管理与配置驱动（Profile）为核心，专为资源构建、静态站点素材处理及团队协作流程设计。

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

* **高性能处理**：基于 FFmpeg 实现高性能图片转码与缩放。
* **多格式支持**：支持输出 PNG、JPG、WebP 等常见格式。
* **灵活缩放**：支持固定尺寸或按比例倍数缩放。
* **自动化流**：自动检测 Git 仓库，支持处理后自动 `git push`。
* **配置驱动**：支持加载多个 Profile 配置，并提供执行前的预览模式（Review Mode）。
* **环境向导**：内置 FFmpeg 下载向导及自动环境变量配置。

### 缩放模式说明

* **Fixed（固定尺寸）**
* 指定精确的宽度与高度。
* 支持 **裁剪（Crop）** 或 **留白填充（Pad）** 以适配比例。

* **Ratio（按比例）**
* 按倍率进行缩放（例如 `0.5x`、`1.5x` 等）。

## 📖 快速上手（GUI）

以下是完成一次图片批处理的标准流程：

1. **准备目录结构**：
```text
assets/
├── input/   # 存放原图
└── output/  # 处理后的输出目录

```


2. **启动应用**：在 GUI 界面填写路径及处理参数。
3. **执行任务**：确认配置后点击执行。

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

### 字段详细说明

| 字段 | 说明 | 备注 |
| --- | --- | --- |
| `enable` | 是否启用该配置 | `true` / `false` |
| `description` | 配置描述 | 仅用于备注识别 |
| `input_folder` | 输入目录 | 支持相对或绝对路径 |
| `output_folder` | 输出目录 | 处理后的存放位置 |
| `format` | 输出格式 | `png` / `jpg` / `webp` |
| `resize_method` | 缩放方式 | `fixed` (固定) / `ratio` (比例) |
| `width` / `height` | 目标尺寸 | 仅在 `fixed` 模式下生效 |
| `fixed_mode` | 适配方式 | `crop` (裁剪) / `pad` (填充) |

## 📽️ FFmpeg 环境

应用核心依赖 **FFmpeg**：

* **自动检测**：启动时检测系统 PATH。
* **一键安装**：若缺失，应用提供安装向导。
* **源支持**：支持从官方源或国内镜像源下载。

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

1. **图片处理失败？**
* 请确认 FFmpeg 已正确安装且在 PATH 中可用。
* 检查输入文件格式是否受支持。

2. **Git 自动提交失败？**
* 确保输入/输出目录位于有效的 Git 仓库内。
* 检查本地是否已配置 Git 用户信息 (`user.name`, `user.email`)。

3. **路径找不到？**
* 建议先使用绝对路径进行测试。
* 相对路径默认相对于 `settings.json` 所在位置。

## 📜 许可证

本项目采用 **GNU General Public License v3.0** 许可协议。

详细信息请参阅 [LICENSE](https://www.google.com/search?q=./LICENSE) 文件。

© **Endfield Industry Human Resources Team**, Some Rights Reserved.
