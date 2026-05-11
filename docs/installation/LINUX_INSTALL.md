# Hermes-Agent-CN Linux 安装指南

> 适用于所有 Linux 发行版（Ubuntu/Debian/CentOS/RHEL/Arch 等）  
> 版本：v0.12.0-cn.1 | 最后更新：2026-05-11

---

## 📋 目录

1. [系统要求](#1-系统要求)
2. [安装 Python 3.11+](#2-安装-python-311)
3. [创建专属虚拟环境](#3-创建专属虚拟环境)
4. [克隆 hermes-agent-cn 仓库](#4-克隆-hermes-agent-cn-仓库)
5. [安装依赖](#5-安装依赖)
6. [配置 Hermes](#6-配置-hermes)
7. [验证安装](#7-验证安装)
8. [日常使用](#8-日常使用)
9. [更新 Hermes](#9-更新-hermes)
10. [常见问题排查](#10-常见问题排查)

---

## 1. 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|----------|----------|
| **操作系统** | Linux 内核 3.10+ | 任意现代发行版 |
| **Python** | 3.11+ | 3.11 或 3.12 |
| **Git** | 2.0+ | 最新稳定版 |
| **磁盘空间** | 2 GB | 5 GB（含虚拟环境） |
| **内存** | 2 GB | 4 GB+（运行本地模型需要更多） |
| **网络** | 能访问 GitHub| 能访问 GitHub + API 端点 |

### 可选依赖

| 功能 | 所需组件 |
|------|----------|
| 本地模型（Ollama） | [Ollama](https://ollama.com) |
| 浏览器工具 | Node.js 20+ |
| 语音功能 | sounddevice、faster-whisper |

---

## 2. 安装 Python 3.11+

### 检查当前 Python 版本

```bash
python3 --version
```

如果版本 ≥ 3.11，跳过此步骤。

### Ubuntu/Debian 安装 Python 3.11+

```bash
# 更新软件包列表
sudo apt update

# 安装 Python 3.12（或 3.11）
sudo apt install -y python3.12 python3.12-venv python3.12-dev python3-pip

# 验证安装
python3.12 --version
```

### CentOS/RHEL 8+ 安装 Python 3.11+

```bash
# 启用 AppStream 仓库
sudo dnf install -y python3.12 python3.12-pip

# 或者使用 pyenv（推荐）
curl https://pyenv.run | bash
pyenv install 3.12.0
pyenv global 3.12.0
```

### Arch Linux 安装 Python

```bash
# Arch 默认 Python 版本通常是最新的
sudo pacman -S python python-pip

# 验证
python --version
```

### 使用 pyenv 安装（通用方法）

```bash
# 安装依赖（Ubuntu/Debian）
sudo apt install -y make build-essential libssl-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
  libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
  libffi-dev liblzma-dev

# 安装 pyenv
curl https://pyenv.run | bash

# 配置环境变量（添加到 ~/.bashrc 或 ~/.zshrc）
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init -)"

# 重新加载 shell 配置
source ~/.bashrc  # 或 source ~/.zshrc

# 安装 Python 3.12
pyenv install 3.12.0

# 设置全局版本
pyenv global 3.12.0

# 验证
python --version
```

---

## 3. 创建专属虚拟环境

### 为什么需要虚拟环境？

- ✅ **隔离依赖**：避免与系统 Python 包冲突
- ✅ **版本管理**：为每个项目使用不同的依赖版本
- ✅ **便于维护**：更新/删除项目不会影响系统

### 方法一：使用 venv（推荐）

```bash
# 创建项目目录
mkdir -p ~/projects
cd ~/projects

# 克隆仓库（先跳过，后面会做）
# 创建虚拟环境
python3.12 -m venv hermes-venv

# 验证虚拟环境
ls -la hermes-venv/
# 应该看到 bin/ include/ lib/ 等目录

# 激活虚拟环境
source ~/projects/hermes-venv/bin/activate

# 升级 pip（在虚拟环境中）
pip install --upgrade pip setuptools wheel

# 验证虚拟环境激活成功
which python    # 应该显示 ~/projects/hermes-venv/bin/python
which pip       # 应该显示 ~/projects/hermes-venv/bin/pip
```

### 方法二：使用 virtualenv

```bash
# 安装 virtualenv
pip install --user virtualenv

# 创建虚拟环境
virtualenv -p python3.12 ~/projects/hermes-venv

# 激活
source ~/projects/hermes-venv/bin/activate
```

### 方法三：使用 conda/mamba

```bash
# 创建 conda 环境
conda create -n hermes python=3.12

# 激活环境
conda activate hermes

# 验证
which python    # 应该显示 ~/miniconda3/envs/hermes/bin/python
```

### 虚拟环境管理命令

```bash
# 激活虚拟环境
source ~/projects/hermes-venv/bin/activate

# 退出虚拟环境
deactivate

# 查看已安装的包
pip list

# 删除虚拟环境（如果需要）
deactivate
rm -rf ~/projects/hermes-venv
```

---

## 4. 克隆 hermes-agent-cn 仓库

### 安装 Git（如果没有）

```bash
# Ubuntu/Debian
sudo apt install -y git

# CentOS/RHEL
sudo dnf install -y git

# Arch
sudo pacman -S git
```

### 克隆仓库

```bash
# 进入项目目录
cd ~/projects

# 克隆 CN 分支
git clone -b cn https://github.com/xyshanren/hermes-agent-cn.git

# 进入项目目录
cd hermes-agent-cn

# 验证分支
git branch
# 应该显示 * cn

# 查看最新提交
git log --oneline -5
```

### 配置 Git（首次使用）

```bash
# 配置用户信息（可选，仅用于提交）
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

---

## 5. 安装依赖

### 激活虚拟环境

```bash
# 进入项目目录
cd ~/projects/hermes-agent-cn

# 激活虚拟环境
source ~/projects/hermes-venv/bin/activate

# 确认虚拟环境已激活（提示符前应该有 (hermes-venv)）
```

### 方法一：使用 pip 安装（推荐）

```bash
# 安装项目（editable 模式）
pip install -e .

# 安装开发依赖（可选，用于开发/测试）
pip install -e ".[dev]"

# 验证安装
pip list | grep hermes
# 应该显示 hermes-agent 0.12.0
```

### 方法二：使用 uv 安装（更快）

```bash
# 安装 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或者使用 pip
pip install uv

# 创建虚拟环境并安装
uv venv venv --python 3.12
source venv/bin/activate

# 使用 uv 安装（速度快 10-100 倍）
uv pip install -e ".[dev]"

# 验证
hermes --version
```

### 安装可选依赖

```bash
# 安装所有可选依赖（完整功能）
pip install -e ".[all]"

# 或者按需安装特定功能
pip install -e ".[messaging]"    # 消息平台集成
pip install -e ".[cli]"          # 交互式 CLI 菜单
pip install -e ".[voice]"        # 语音功能
pip install -e ".[web]"          # Web 仪表板
```

### 验证依赖安装

```bash
# 检查核心依赖
python -c "import openai; import anthropic; import rich; print('✅ 核心依赖正常')"

# 检查 hermes 命令是否可用
which hermes
# 应该显示 ~/projects/hermes-venv/bin/hermes

# 查看版本
hermes --version
```

---

## 6. 配置 Hermes

### 方法一：交互式配置（推荐）

```bash
# 运行快速启动向导
hermes quickstart
```

**向导会引导你完成：**
1. 检测现有 API Key
2. 检测 Ollama 本地模型
3. 自动选择合适的 Provider
4. 无需手动选择

### 方法二：手动配置 API Key

```bash
# 运行设置向导
hermes setup
```

**支持的 Provider：**
- ✅ 智谱 GLM（ZHIPU_API_KEY）
- ✅ 文心一言（WENXIN_API_KEY）
- ✅ 通义千问（DASHSCOPE_API_KEY）
- ✅ 腾讯混元（HUNYUAN_API_KEY）
- ✅ OpenAI（OPENAI_API_KEY）
- ✅ OpenRouter（OPENROUTER_API_KEY）
- ✅ Ollama（本地模型，无需 API Key）
- ✅ 其他 OpenAI 兼容接口

### 方法三：直接编辑配置文件

```bash
# 创建配置目录
mkdir -p ~/.hermes

# 创建配置文件
cat > ~/.hermes/config.yaml << 'EOF'
# Hermes Agent 配置文件
llm:
  provider: zhipu            # 可选：zhipu, wenxin, qwen, hunyuan, openai, ollama
  model: glm-4-flash          # 模型名称
  temperature: 0.7            # 温度参数
  max_tokens: 4096            # 最大 token 数

# 其他配置...
EOF

# 创建环境变量文件（用于存储 API Key）
cat > ~/.hermes/.env << 'EOF'
ZHIPU_API_KEY=your-api-key-here
EOF

# 设置权限（重要！）
chmod 600 ~/.hermes/.env
```

### 安装本地模型（Ollama）

```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 启动 Ollama 服务
ollama serve &

# 拉取推荐模型
ollama pull qwen2.5:3b        # 快速，适合日常使用
ollama pull qwen2.5:7b        # 更好，需要更多资源

# 验证 Ollama 运行
curl http://localhost:11434/api/tags

# 在 hermes 中配置 Ollama
hermes setup
# 选择 "Use Ollama (local models)"
```

---

## 7. 验证安装

### 运行诊断工具

```bash
# 运行 hermes doctor（自动诊断）
hermes doctor
```

**期望输出：**
```
✅ Python version: 3.12.0
✅ Hermes installed: v0.12.0
✅ Config file found: /home/user/.hermes/config.yaml
✅ At least one LLM provider configured
✅ Dependencies check passed
```

### 测试对话功能

```bash
# 测试非交互模式
hermes chat -q "你好，请介绍一下你自己"

# 测试交互模式
hermes chat
```

**在交互模式中：**
1. 输入 `/help` 查看可用命令
2. 输入 `/status` 查看当前状态
3. 输入 `/exit` 退出

### 运行测试套件（可选）

```bash
# 安装测试依赖
pip install pytest

# 运行测试
pytest tests/ -v

# 或者运行快速测试（不依赖外部服务）
pytest tests/ -v -m "not integration"
```

---

## 8. 日常使用

### 激活虚拟环境并启动 Hermes

```bash
# 方法一：每次手动激活
source ~/projects/hermes-venv/bin/activate
hermes chat

# 方法二：创建别名（推荐）
echo 'alias hermes="source ~/projects/hermes-venv/bin/activate && hermes"' >> ~/.bashrc
source ~/.bashrc
hermes chat
```

### 创建全局命令（推荐）

```bash
# 创建符号链接
sudo ln -s ~/projects/hermes-venv/bin/hermes /usr/local/bin/hermes

# 或者复制到用户 bin 目录
mkdir -p ~/.local/bin
ln -s ~/projects/hermes-venv/bin/hermes ~/.local/bin/hermes

# 确保 ~/.local/bin 在 PATH 中
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# 现在可以在任何地方运行 hermes
hermes chat
```

### 常用命令

```bash
# 查看帮助
hermes --help

# 快速配置
hermes quickstart

# 手动配置
hermes setup

# 模型管理
hermes model

# 本地模型管理
hermes local-models status
hermes local-models setup --yes

# 诊断
hermes doctor

# 技能管理
hermes skills browse
hermes skills install <skill-name>

# 查看版本
hermes --version
```

---

## 9. 更新 Hermes

### 拉取最新代码

```bash
# 进入项目目录
cd ~/projects/hermes-agent-cn

# 激活虚拟环境
source ~/projects/hermes-venv/bin/activate

# 保存本地修改（如果有）
git stash

# 拉取最新代码
git pull origin cn

# 重新安装（editable 模式会自动更新）
pip install -e .

# 如果有新的依赖，会自动安装
```

### 一键更新脚本（推荐）

```bash
# 创建更新脚本
cat > ~/update-hermes.sh << 'EOF'
#!/bin/bash
set -e

HERMES_DIR=~/projects/hermes-agent-cn
VENV_DIR=~/projects/hermes-venv

echo "📦 更新 Hermes Agent CN..."

# 进入项目目录
cd "$HERMES_DIR"

# 激活虚拟环境
source "$VENV_DIR/bin/activate"

# 保存本地修改
git stash

# 拉取最新代码
git pull origin cn

# 重新安装
pip install -e .

# 验证
hermes --version
hermes doctor

echo "✅ 更新完成！"
EOF

# 设置可执行权限
chmod +x ~/update-hermes.sh

# 运行更新
~/update-hermes.sh
```

---

## 10. 常见问题排查

### 问题 1：Python 版本太低

**错误信息：**
```
ERROR: Package requires Python >=3.11
```

**解决方法：**
```bash
# 安装 Python 3.12
sudo apt install -y python3.12 python3.12-venv

# 使用 Python 3.12 创建虚拟环境
python3.12 -m venv hermes-venv
```

---

### 问题 2：pip install 失败（网络问题）

**错误信息：**
```
Connection timeout / Read timed out
```

**解决方法：**
```bash
# 使用国内镜像源
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或者配置永久镜像
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 然后重新安装
pip install -e .
```

**常用国内镜像：**
- 清华：`https://pypi.tuna.tsinghua.edu.cn/simple`
- 阿里：`https://mirrors.aliyun.com/pypi/simple`
- 豆瓣：`https://pypi.douban.com/simple`

---

### 问题 3：hermes 命令找不到

**错误信息：**
```
hermes: command not found
```

**解决方法：**
```bash
# 检查虚拟环境是否激活
which hermes

# 如果没有，激活虚拟环境
source ~/projects/hermes-venv/bin/activate

# 或者创建符号链接
sudo ln -s ~/projects/hermes-venv/bin/hermes /usr/local/bin/hermes

# 验证
which hermes
```

---

### 问题 4：API Key 配置错误

**错误信息：**
```
ERROR: No LLM provider configured
```

**解决方法：**
```bash
# 运行配置向导
hermes setup

# 或者手动编辑配置文件
nano ~/.hermes/.env

# 添加 API Key（示例：智谱 GLM）
ZHIPU_API_KEY=your-api-key-here

# 保存后设置权限
chmod 600 ~/.hermes/.env

# 验证配置
hermes doctor
```

---

### 问题 5：Ollama 连接失败

**错误信息：**
```
ERROR: Cannot connect to Ollama at localhost:11434
```

**解决方法：**
```bash
# 检查 Ollama 是否运行
ps aux | grep ollama

# 如果没有，启动 Ollama
ollama serve &

# 或者作为服务启动（systemd）
sudo systemctl enable ollama
sudo systemctl start ollama

# 验证 Ollama 运行
curl http://localhost:11434/api/tags

# 拉取模型
ollama pull qwen2.5:3b
```

---

### 问题 6：权限错误

**错误信息：**
```
Permission denied: ~/.hermes/config.yaml
```

**解决方法：**
```bash
# 修复权限
chmod 755 ~/.hermes
chmod 644 ~/.hermes/config.yaml
chmod 600 ~/.hermes/.env

# 或者删除重新配置
rm -rf ~/.hermes
hermes setup
```

---

### 问题 7：虚拟环境损坏

**错误信息：**
```
Error: No module named 'hermes_cli'
```

**解决方法：**
```bash
# 删除旧的虚拟环境
deactivate
rm -rf ~/projects/hermes-venv

# 重新创建
python3.12 -m venv ~/projects/hermes-venv
source ~/projects/hermes-venv/bin/activate

# 重新安装
cd ~/projects/hermes-agent-cn
pip install -e .
```

---

### 问题 8：端口被占用（Gateway 模式）

**错误信息：**
```
ERROR: Port 8000 already in use
```

**解决方法：**
```bash
# 查找占用端口的进程
sudo lsof -i :8000

# 杀死进程（替换 PID）
kill -9 <PID>

# 或者修改 Hermes 使用其他端口
hermes gateway --port 8001
```

---

## 📚 附加资源

- **项目仓库**：https://github.com/xyshanren/hermes-agent-cn
- **上游仓库**：https://github.com/NousResearch/hermes-agent
- **问题反馈**：https://github.com/xyshanren/hermes-agent-cn/issues
- **讨论区**：https://github.com/xyshanren/hermes-agent-cn/discussions

---

## 📝 快速参考表

| 任务 | 命令 |
|------|------|
| 激活虚拟环境 | `source ~/projects/hermes-venv/bin/activate` |
| 启动对话 | `hermes chat` |
| 快速配置 | `hermes quickstart` |
| 手动配置 | `hermes setup` |
| 诊断问题 | `hermes doctor` |
| 查看版本 | `hermes --version` |
| 更新代码 | `cd ~/projects/hermes-agent-cn && git pull origin cn` |
| 重新安装 | `pip install -e .` |
| 退出虚拟环境 | `deactivate` |

---

## 🎉 安装完成！

现在你可以开始使用 Hermes Agent CN 了！

**下一步：**
1. 运行 `hermes chat` 开始对话
2. 运行 `hermes --help` 查看所有命令
3. 查看 [README.md](../README.md) 了解更多功能

---

**文档版本**：v1.0 | **最后更新**：2026-05-11  
**作者**：xyshanren | **维护**：Hermes Agent CN 社区
