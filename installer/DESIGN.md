---
name: "攀岩助手中文安装器"
description: "沿用 App 的黄色与灰白，为首次安装提供简洁的中文原生窗口。"
colors:
  primary: "#edcb52"
  background: "#f7f7f7"
  text: "#202020"
  secondary-text: "#464646"
typography:
  title:
    fontFamily: "Microsoft YaHei UI"
    fontSize: "22pt"
    fontWeight: 700
  body:
    fontFamily: "Microsoft YaHei UI"
    fontSize: "9pt"
    fontWeight: 400
  step:
    fontFamily: "Microsoft YaHei UI"
    fontSize: "10pt"
    fontWeight: 700
rounded:
  button: "0px"
spacing:
  page: "30px"
components:
  window:
    backgroundColor: "{colors.background}"
    textColor: "{colors.text}"
    typography: "{typography.body}"
    width: "520px"
    height: "340px"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.text}"
    typography: "{typography.body}"
    rounded: "{rounded.button}"
    width: "140px"
    height: "38px"
  link-secondary:
    textColor: "{colors.secondary-text}"
    typography: "{typography.body}"
  progress:
    height: "8px"
---

# Design System: 攀岩助手中文安装器

## Overview

**Creative North Star: "一次安装，直接打开"**

以现有 App 的黄色主按钮、灰白背景与深色文字保持产品连续性。窗口采用 Windows 原生控件，让用户按中文提示开始安装、了解当前进展，再打开 App。文字少，主要操作清楚，详细信息通过次要入口展开。

本记录由 `WindowsApp.cs` 的实际实现提取，合并原有中文设计约束；不新增视觉方向。原生控件的系统外观、键盘焦点与状态绘制仍由 Windows 处理。

**Key Characteristics:**

- 单列、短文案、一个黄色主要操作。
- 当前步骤与简短说明分开，进度条细而明确。
- 失败说明和重试留在原窗口，详细日志另行打开。

## Colors

一个暖黄色强调色搭配灰白底色；具体色值以 frontmatter 为准。

### Primary

- **App 黄色**：主要按钮背景，提示开始、重试或打开 App 的下一步操作。

### Neutral

- **灰白底色**：整个安装窗口背景。
- **深色正文**：产品名、当前步骤、详细说明及主要按钮文字。
- **次要灰色**：两行用途简介与次要说明/日志链接。

**The Text Status Rule.** 状态必须有中文文字与原生进度控件表达，颜色不能成为唯一信号。

## Typography

全窗口使用 Microsoft YaHei UI；标题和步骤为粗体，正文及按钮为常规字重。字号、字体与字重以 frontmatter 为准；不设自定义字距或行高。

- **Title**：只用于“攀岩助手”产品名。
- **Body**：用途、联网与空间说明、失败处理、链接及按钮文案。
- **Step**：当前阶段与已用时间，帮助用户判断安装仍在进行。

## Layout

逻辑客户区为窗口 token 的尺寸。居中打开，单列 TableLayoutPanel 填满客户区，内边距使用 page token。七行依次承载产品名、两行用途、当前步骤、进度条、简短说明、次要链接和右对齐主按钮。各行逻辑高度依次为 50、45、32、25、剩余空间、25、44 px；简短说明行随窗口高度扩展。

实现读取系统 DPI，相对 96 DPI 缩放所有以 px 声明的尺寸并向上取整；字体保持 pt 单位。清单声明系统 DPI 感知，代码未实现切换显示器时的动态 DPI 重排。窗口可调整大小，主按钮保持右对齐。

**The Current Step Rule.** 首屏不排列五步长文本；安装开始后只显示当前阶段、必要说明及已用时间。

## Elevation & Depth

界面不添加自定义阴影、渐变或悬浮卡片。层级由字号、字重、留白和黄色主按钮建立；窗口边框及原生进度条的系统外观由 Windows 提供。

## Shapes

主按钮为无边框的平直矩形，使用 FlatStyle.Flat；其圆角值记录于 frontmatter。没有卡片、胶囊按钮或自绘输入框。链接与进度条保持原生控件形态。

## Components

### Primary Button

主要按钮在最后一行右侧，以 App 黄色配深色文字。默认“开始安装”，安装期间禁用，失败后“重试安装”，成功后“打开攀岩助手”。Enter 通过 AcceptButton 触发当前可用操作，保留原生键盘焦点。实现没有自定义悬停色、焦点动画或转场。

### Current Step and Progress

当前步骤采用 step 字体；运行时每秒附加已用分钟和秒数。细进度条显示安装引擎提供的阶段进度，值限制在 0–100。下载说明以实际收到的 MB 数量及可获得的总量呈现；整个安装的进度值不是总下载百分比。

### Detail and Secondary Link

简短说明允许换行，失败时同一位置显示原因与可执行处理方式，技术详情进入日志。次要入口初始为“安装说明”，开始后为“查看日志”；后者打开安装缓存/日志目录，包括失败后。重试保留已验证下载，个人资料与程序分开。

初始空间说明沿用当前实测并取整的界面文案。测量依据见 `../docs/VALIDATION.md` 的“空间实测”：现有结果不含新安装微软窗口组件和个人资料空间。该数字属于产品事实，不作为视觉 token。

## Do's and Don'ts

### Do:

- **Do** 沿用 App 黄色、灰白底色、深色正文及原生中文字体。
- **Do** 使用系统 DPI 缩放逻辑尺寸，保留原生键盘焦点。
- **Do** 将当前步骤、失败原因及下一步操作写成简短中文。
- **Do** 保持一个右侧主要操作，并将详细日志放在次要入口。

### Don't:

- **Don't** 在首屏展开五步长说明或技术配置选项。
- **Don't** 用颜色单独表达状态，或把阶段进度冒充总下载百分比。
- **Don't** 为现有原生界面添加无依据的阴影、圆角、悬停动画或新强调色。
- **Don't** 将当前空间实测数字变成适用于所有电脑的固定承诺。
