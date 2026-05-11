# Hermes-Agent-CN macOS 安装指南

> 适用于 macOS Catalina 及以上版本（Intel + Apple Silicon）  
> 版本：v0.12.0-cn.1 | 最后更新：2026-05-12

---

## 📋 目录

1. [系统要求](#1-系统要求)
2. [安装 Homebrew](#2-安装-homebrew)
3. [安装 Git](#3-安装-git)
4. [安装 Python 3.11+](#4-安装-python-311)
5. [创建专属虚拟环境](#5-创建专属虚拟环境)
6. [克隆 hermes-agent-cn 仓库](#6-克隆-hermes-agent-cn-仓库)
7. [安装依赖](#7-安装依赖)
8. [配置 Hermes](#8-配置-hermes)
9. [验证安装](#9-验证安装)
10. [日常使用](#10-日常使用)
11. [更新 Hermes](#11-更新-hermes)
12. [常见问题排查](#12-常见问题排查)

---

## 1. 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|----------|----------|
| **操作系统** | macOS Catalina (10.15) | macOS Sonoma (14.0) + |
| **架构** | Intel x86_64 | Apple Silicon (M1/M2/M3) |
| **Python** | 3.11+ | 3.12 |
| **Homebrew** | 必需 | 最新稳定版 |
| **磁盘空间** | 3 GB | 6 GB（含虚拟环境） |
| **内存** | 4 GB | 8 GB+（运行本地模型需要更多） |
| **网络** | 能访问 GitHub | 能访问 GitHub + API 端点 |

### 可选依赖

| 功能 | 所需组件 |
|------|----------|
| 本地模型（Ollama） | [Ollama](https://ollama.com)（macOS 原生支持） |
| 浏览器工具 | Node.js 20+ |
| 语音功能 | sounddevice、faster-whisper |
| GPU 加速 | Apple Silicon (M1/M2/M3) 内置 GPU |

---

## 2. 安装 Homebrew

**Homebrew 是 macOS 的包管理器，必需安装。**

### 安装 Homebrew

```bash
# 安装 Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 按照提示配置环境变量
```

### 配置环境变量（重要）

**Apple Silicon (M1/M2/M3)：**

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
source ~/.zshrc
```

**Intel Mac：**

```bash
echo 'eval "$(/usr/local/bin/brew shellenv)"' >> ~/.zshrc
source ~/.zshrc
```

### 验证安装

```bash
# 验证 Homebrew 安装
brew --version

# 更新 Homebrew
brew update
```

---

## 3. 安装 Git

```bash
# 使用 Homebrew 安装 Git
brew install git

# 验证安装
git --version
```

### 配置 Git（可选但推荐）

```bash
# 配置用户名和邮箱
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# 配置换行符（macOS 特有）
git config --global core.autocrlf input
```

---

## 4. 安装 Python 3.11+

### 方法一：使用 Homebrew 安装（推荐）

```bash
# 安装 Python 3.12
brew install python@3.12

# 链接 Python 3.12
brew link python@3.12

# 验证安装
python3.12 --version
```

### 方法二：使用 pyenv 安装（多版本管理）

```bash
# 安装 pyenv
brew install pyenv

# 配置环境变量
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.zshrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(pyenv init -)"' >> ~/.zshrc
source ~/.zshrc

# 安装 Python 3.12.0
pyenv install 3.12.0

# 设置为全局默认版本
pyenv global 3.12.0

# 验证
python --version
```

### 方法三：使用官方安装包

1. 访问：https://www.python.org/downloads/macos/
2. 下载 **Python 3.12.x** 安装包（.pkg 文件）
3. 运行安装程序
4. 验证安装：
   ```bash
   python3 --version
   ```

---

## 5. 创建专属虚拟环境

### 为什么要在项目目录外创建虚拟环境？

✅ **避免意外提交到 Git**（即使 `.gitignore` 配置正确）  
✅ **项目目录更干净**，只保留代码和配置  
✅ **符合 Python 社区最佳实践**（PEP 370、Poetry、Pipenv 等工具默认行为）  
✅ **多个项目可以共享同一个虚拟环境**（可选）

### 创建虚拟环境

```bash
# 在项目目录外创建虚拟环境（推荐路径）
python3.12 -m venv ~/.venvs/hermes-agent-cn

# 激活虚拟环境
source ~/.venvs/hermes-agent-cn/bin/activate
```

**验证虚拟环境：**

```bash
# 应该显示虚拟环境路径
which python

# 输出应该类似：
# /Users/yourname/.venvs/hermes-agent-cn/bin/python
```

### 虚拟环境管理

```bash
# 激活虚拟环境
source ~/.venvs/hermes-agent-cn/bin/activate

# 退出虚拟环境
deactivate

# 删除虚拟环境（如果需要）
rm -rf ~/.venvs/hermes-agent-cn
```

---

## 6. 克隆 hermes-agent-cn 仓库

```bash
# 切换到用户主目录
cd ~

# 克隆 CN 分支
git clone -b cn https://github.com/xyshanren/hermes-agent-cn.git

# 进入项目目录
cd hermes-agent-cn

# 查看分支
git branch -a
```

**预期输出：**

```

* cn
  remotes/origin/cn
```

### 如果遇到克隆失败（SSL 证书错误）

```bash
# 临时禁用 SSL 验证（仅测试环境）
git config --global http.sslVerify false

# 或者配置代理
git config --global http.proxy http://proxy.example.com:8080

# 然后重新克隆
git clone -b cn https://github.com/xyshanren/hermes-agent-cn.git
```

---

## 7. 安装依赖

### 激活虚拟环境

```bash
source ~/.venvs/hermes-agent-cn/bin/activate
```

**提示：** 激活后，命令提示符前会显示 `(hermes-agent-cn)`。

### 升级 pip

```bash
pip install --upgrade pip
```

### 安装项目（editable 模式）

```bash
# 进入项目目录
cd ~/hermes-agent-cn

# 安装项目（editable 模式，修改代码后无需重装）
pip install -e .
```

**使用国内镜像源（如果网络不好）：**

```bash
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 安装可选依赖

```bash
# 安装浏览器工具（需要 Node.js）
pip install -e ".[browser]"

# 安装所有可选依赖
pip install -e ".[all]"
```

### 安装额外依赖（macOS 特有）

```bash
# 安装 ripgrep（代码搜索工具）
brew install ripgrep

# 安装 ffmpeg（音视频处理）
brew install ffmpeg

# 验证安装
which rg
which ffmpeg
```

---

## 8. 配置 Hermes

### 方法一：自动配置（推荐）

```bash
hermes quickstart
```

按照提示选择：

1. **选择 LLM 提供商**（智谱 AI、OpenAI、Ollama 等）
2. **输入 API Key**（如果使用云服务）
3. **选择默认模型**

### 方法二：手动配置

```bash
# 运行设置向导
hermes setup
```

或者手动编辑配置文件：

```bash
# 创建配置目录
mkdir -p ~/.hermes

# 创建 .env 文件
cat > ~/.hermes/.env << 'EOF'
ZHIPU_API_KEY=your-zhipu-api-key-here
OPENAI_API_KEY=your-openai-api-key-here
EOF

chmod 600 ~/.hermes/.env
```

### 方法三：使用 Ollama（本地模型）

1. **安装 Ollama（macOS 原生支持）**
   ```bash
   brew install ollama
   ```
2. **启动 Ollama**
   ```bash
   # 方法一：后台启动
   ollama serve &
   
   # 方法二：使用 Homebrew services
   brew services start ollama
   ```
3. **拉取模型**
   ```bash
   ollama pull qwen2.5:3b
   ```
4. **配置 Hermes**
   ```bash
   hermes setup
   ```
   - 选择 **"Use Ollama (local models)"**
   - 输入 Ollama 地址（默认：`http://localhost:11434`）

---

## 9. 验证安装

### 运行诊断工具

```bash
hermes doctor
```

**预期输出：**

```
✅ Python version: 3.12.0
✅ Hermes installed: v0.12.0
✅ Config file found: /Users/yourname/.hermes/config.yaml
✅ At least one LLM provider configured
✅ Virtual environment active: .venvs/hermes-agent-cn
```

### ⚠️ macOS 特有步骤：激活环境变量

**macOS Catalina 及以上版本默认使用 zsh：**

```bash
# 激活环境变量
source ~/.zshrc

# 如果使用 bash（Mojave 及更早版本）
source ~/.bashrc
```

### 测试对话

```bash
hermes chat -q "你好，请介绍一下你自己"
```

**预期输出：**

```
你好！我是 Hermes Agent，一个强大的 AI 助手。
我可以帮助你完成各种任务，包括...
```

---

## 10. 日常使用

### 激活虚拟环境并启动

```bash
# 激活虚拟环境
source ~/.venvs/hermes-agent-cn/bin/activate

# 进入项目目录
cd ~/hermes-agent-cn

# 启动 Hermes
hermes chat
```

### 创建全局命令（推荐）

```bash
# 创建符号链接（指向虚拟环境中的 hermes 命令）
mkdir -p ~/.local/bin
ln -s ~/.venvs/hermes-agent-cn/bin/hermes ~/.local/bin/hermes

# 添加到 PATH（如果还没有）
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc

# 现在可以在任何地方运行
hermes chat
```

**如果使用 bash（Mojave 及更早版本）：**

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

---

## 11. 更新 Hermes

```bash
# 激活虚拟环境
source ~/.venvs/hermes-agent-cn/bin/activate

# 进入项目目录
cd ~/hermes-agent-cn

# 拉取最新代码
git pull origin cn

# 重新安装（如果有依赖变更）
pip install -e .
```

---

## 12. 常见问题排查

### 问题 1：pip install 失败（网络问题）

**解决方法一：使用国内镜像源**

```bash
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**解决方法二：配置 pip 镜像（永久生效）**

```bash
# 创建 pip 配置文件
mkdir -p ~/.pip
cat > ~/.pip/pip.conf << 'EOF'
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
trusted-host = pypi.tuna.tsinghua.edu.cn
EOF
```

### 问题 2：hermes 命令找不到

**原因：** macOS 默认使用 zsh，需要 source `~/.zshrc`

```bash
# 检查虚拟环境是否激活
which hermes

# 如果没有，激活虚拟环境
source ~/.venvs/hermes-agent-cn/bin/activate

# 激活环境变量（macOS 特有）
source ~/.zshrc
```

### 问题 3：Python 版本太低

```bash
# 检查 Python 版本
python3 --version

# 如果 < 3.11，安装 Python 3.12
brew install python@3.12

# 链接 Python 3.12
brew link python@3.12

# 验证
python3.12 --version
```

### 问题 4：ripgrep 或 ffmpeg 缺失

```bash
# 使用 Homebrew 安装依赖
brew install ripgrep ffmpeg

# 验证安装
which rg
which ffmpeg
```

### 问题 5：Ollama 无法启动（Apple Silicon）

```bash
# Apple Silicon (M1/M2/M3) 需要安装原生版本
brew install ollama

# 检查是否正常运行
ps aux | grep ollama

# 或者使用 Homebrew services 启动
brew services start ollama
```

### 问题 6：虚拟环境激活后包找不到

**原因：** 可能有多个 Python 版本冲突

```bash
# 检查当前 Python 路径
which python3

# 应该显示虚拟环境中的 Python
# 如果不是，删除虚拟环境并重新创建
deactivate
rm -rf ~/.venvs/hermes-agent-cn
python3.12 -m venv ~/.venvs/hermes-agent-cn
source ~/.venvs/hermes-agent-cn/bin/activate
```

### 问题 7：Git 克隆失败（SSL 证书错误）

**解决方法：**

```bash
# 临时禁用 SSL 验证（仅测试环境）
git config --global http.sslVerify false

# 重新克隆
git clone -b cn https://github.com/xyshanren/hermes-agent-cn.git
```

### 问题 8：Homebrew 安装缓慢（国内网络问题）

**解决方法：使用国内镜像源**

```bash
# 使用清华大学镜像源
export HOMEBREW_BOTTLE_DOMAIN=https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles

# 安装 Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 配置环境变量（按照安装后的提示）
```

---

## 📚 相关文档

- [macOS 快速安装](QUICKSTART_MACOS.md)
- [Linux 安装指南](LINUX_INSTALL.md)
- [Linux 快速安装](QUICKSTART_LINUX.md)
- [WSL2 安装指南](WSL2_INSTALL.md)

---

## 🔗 相关链接

- **Homebrew 官方文档**：https://brew.sh/
- **Python 官方文档**：https://www.python.org/doc/
- **Hermes 官方文档**：https://hermes.xaapi.ai/guide/installation
- **项目主页**：https://github.com/xyshanren/hermes-agent-cn
- **上游仓库**：https://github.com/NousResearch/hermes-agent
- **问题反馈**：https://github.com/xyshanren/hermes-agent-cn/issues
- **讨论区**：https://github.com/xyshanren/hermes-agent-cn/discussions

---

**安装完成！** 🎉

现在可以运行 `hermes chat` 开始使用了。

---

**文档版本**：v1.0 | **最后更新**：2026-05-12
