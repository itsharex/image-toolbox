# Image Toolbox (图片工具箱)
[![Release](https://github.com/EIHRTeam/image-toolbox/actions/workflows/release.yml/badge.svg)](https://github.com/EIHRTeam/image-toolbox/actions/workflows/release.yml)
[![Build](https://github.com/EIHRTeam/image-toolbox/actions/workflows/build.yml/badge.svg)](https://github.com/EIHRTeam/image-toolbox/actions/workflows/build.yml)
![Version](https://img.shields.io/badge/version-0.1.0-blue) ![Tauri](https://img.shields.io/badge/Tauri-v2-orange) ![Vue](https://img.shields.io/badge/Vue-3-green)

基于 Tauri v2 与 Vue 3 的桌面端图片批处理软件。
该工具以内置 FFmpeg 管理与配置驱动（Profile）为核心，适合用于资源构建、静态站点素材处理及团队协作流程。

tip：善用右上角的文档索引按钮

## 下载安装

方式一：Release 版本（推荐）

前往仓库的 Releases 页面下载 exe 或 msi 安装程序：

https://github.com/EIHRTeam/image-toolbox/releases/latest

方式二：Actions 构建产物

在 GitHub Actions 页面下载最近一次成功构建的产物。

## 功能概览

Image Toolbox 提供以下主要能力：

* 批量图片处理
* 支持 PNG、JPG、WebP 等常见格式输出
* 基于 FFmpeg 实现高性能转码与缩放
* 支持固定尺寸或按比例缩放

### 两种缩放模式

#### Fixed（固定尺寸）

指定宽度与高度

支持裁剪（Crop）或留白填充（Pad）

#### Ratio（按比例）

按倍率进行缩放（如 0.5×、1.5× 等）

#### 自动化工作流

自动检测输入/输出目录是否位于 Git 仓库中

可在处理完成后自动执行：
```bash
git add .
git commit
git push
```

#### 配置驱动（Profile 系统）
使用 settings.json 管理多个处理配置

支持一次加载多个 Profile

提供执行前的确认模式（Review Mode）


#### FFmpeg 管理

自动检测系统中是否已安装 FFmpeg

提供一键下载安装向导

支持自动配置用户 PATH 环境变量

## 快速上手（GUI 使用）

以下步骤描述一次完整的图片批处理流程。

1. 准备图片输入与输出目录，如：
```
assets/
├─ input/
└─ output/
```

2. 启动应用，通过 GUI 填写参数

3. 确认并执行

## 配置文件说明（settings.json）

Image Toolbox 支持通过 JSON 文件定义处理配置。
每个 Profile 对应一个独立的处理任务。

示例配置
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

字段说明

enable
是否启用该 Profile

description
配置说明，仅用于备注

input_folder
输入图片目录（支持相对路径与绝对路径）

output_folder
输出图片目录（支持相对路径与绝对路径）

format
输出格式：png / jpg / webp

resize_method
缩放方式：fixed 或 ratio

width / height
固定尺寸模式下必填

fixed_mode
固定尺寸模式的适配方式：crop 或 pad



---

## FFmpeg 说明

Image Toolbox 依赖 FFmpeg 执行图片转码与缩放操作。

启动时会自动检测系统 PATH 中是否存在 FFmpeg

若未检测到：

应用会提示下载安装

支持官方源与镜像源

可自动配置环境变量，无需手动设置

## 开发与构建（开发者）

安装依赖

npm install

启动开发模式

npm run tauri dev

构建发布版本

npm run tauri build


## 常见问题

1. 图片未处理或失败

确认 FFmpeg 已正确安装

检查输入目录是否包含支持的图片格式


2. Git 自动提交失败

确认目录位于 Git 仓库中

检查是否已配置 Git 用户信息与远程仓库权限


3. 路径解析异常

优先使用绝对路径排查

或将 settings.json 与输入目录放在同一层级。

## 许可证
本项目采用 GNU General Public License v3.0 许可协议。<br>
详细信息请参阅仓库中的 LICENSE 文件。<br>
© Endfield Industry Human Resources Team, Some Rights Reserved.
