# Nekro Plugin - memU.so 长期记忆（memu_memory）

一个为 NekroAgent 设计的长期记忆插件，集成 memU.so 官方云服务，为 AI 代理提供稳定的“记忆-回忆”能力。

- 项目地址：`https://github.com/johntime2005/memu_memory`

## ✨ 功能特性

- 自动回忆注入：在回复前自动检索最近对话的相关记忆，拼接为提示词注入。
- 主动回忆工具：提供可调用的工具函数，基于语义搜索主动回忆历史信息。
- 写入长期记忆：将重要事实与偏好写入长期记忆库，支持多人设（agent）调用。
- 可视化配置：在 NekroAgent 的插件设置页面配置 API Key、服务地址及回忆数量。

## 🚀 安装

```powershell
pip install -e .
```

## ⚙️ 配置项

- MEMU_API_KEY：memu.so 的 API Key（必填）
- BASE_URL：memu.so API 地址（默认 https://api.memu.so）
- AGENT_ID：默认助理 ID
- AGENT_NAME：默认助理名称
- RECALL_TOP_K：自动回忆条目数（0 关闭自动回忆）

## 🧩 接口一览

- 提示注入：`relevant_memories_from_memu_so`
- 工具（行为）：`记忆对话`
- 工具（Tool）：`回忆信息`

## 🏗️ 结构

```
memu_memory/
  └── __init__.py
pyproject.toml
README.md
```

## 📦 依赖声明

依赖在 `pyproject.toml` 中声明，安装插件时会自动安装：

```toml
[tool.poetry.dependencies]
python = ">=3.10,<3.13"
nekro-agent = "*"
memu-py = "*"
pydantic = ">=2.3"
```

## 📄 许可证

本项目采用 AGPL-3.0-or-later 开源协议。详见仓库中的 `LICENSE` 文件。
