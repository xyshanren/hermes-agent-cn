# Hermes-Agent-CN WSL2 安装指南

> 适用于 Windows 10/11 + WSL2（Ubuntu 22.04）  
> 版本：v0.12.0-cn.1 | 最后更新：2026-05-12

---

## ⚠️ 重要说明

**Hermes Agent 不支持 Windows 原生环境。**

Windows 用户**必须**通过 WSL2（Windows Subsystem for Linux 2）运行 Hermes。本指南将指导你在 WSL2 中完整安装 Hermes-Agent-CN。

---

## 📋 目录

1. [WSL2 安装前提](#1-wsl2-安装前提)
2. [系统要求](#2-系统要求)
3. [安装 Python 3.11+](#3-安装-python-311)
4. [安装 Git](#4-安装-git)
5. [创建专属虚拟环境](#5-创建专属虚拟环境)
6. [克隆 hermes-agent-cn 仓库](#6-克隆-hermes-agent-cn-仓库)
7. [安装依赖](#7-安装依赖)
8. [配置 Hermes](#8-配置-hermes)
9. [验证安装](#9-验证安装)
10. [日常使用](#10-日常使用)
11. [更新 Hermes](#11-更新-hermes)
12. [常见问题排查](#12-常见问题排查)

---

## 1. WSL2 安装前提

### 检查 WSL2 是否已安装

**在 PowerShell 中运行：**
```powershell
wsl --list --verbose
```

**如果显示 "适用于 Linux 的 Windows 子系统没有已安装的分发版"，则需要安装。**

### 安装 WSL2（如果还没有）

**方法一：自动安装（推荐）**

```powershell
# 以管理员身份打开 PowerShell，执行：
wsl --install

# 重启电脑
```

- 默认安装 **Ubuntu 22.04**（推荐）
- 重启后，系统会自动启动 Ubuntu 安装向导
- 设置用户名和密码

**方法二：手动安装特定版本**

```powershell
# 列出可用的 Linux 发行版
wsl --list --online

# 安装 Ubuntu 22.04
wsl --install -d Ubuntu-22.04

# 重启电脑
```

### 启动 WSL2

**安装完成后：**

1. 打开 **Windows Terminal**（推荐）或搜索 **Ubuntu**
2. 首次启动会要求设置用户名和密码
3. 进入 Linux 终端后，所有后续步骤都在 WSL2 中完成

**详细 WSL2 安装指南**：https://learn.microsoft.com/windows/wsl/install

---

## 2. 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|----------|----------|
| **WSL2** | Windows 10 版本 19041+ | Windows 11 |
| **Linux 发行版** | Ubuntu 20.04+ | Ubuntu 22.04 LTS |
| **Python（WSL2 内）** | 3.11+ | 3.12 |
| **内存（宿主机）** | 8 GB | 16 GB+ |
| **磁盘空间（WSL2）** | 5 GB | 10 GB |
| **网络** | 能访问 GitHub | 能访问 GitHub + API 端点 |

### 可选依赖

| 功能 | 所需组件 |
|------|----------|
| 本地模型（Ollama） | [Ollama](https://ollama.com)（在 WSL2 内安装） |
| 浏览器工具 | Node.js 20+（在 WSL2 内安装） |
| GPU 加速 | WSL2 GPU 支持 + NVIDIA CUDA |

---

## 3. 安装 Python 3.11+

### 检查当前 Python 版本

```bash
python3 --version
```

如果版本 ≥ 3.11，跳过此步骤。

### Ubuntu/Debian 安装 Python 3.12

```bash
# 更新软件包列表
sudo apt update

# 安装 Python 3.12（或 3.11）
sudo apt install -y python3.12 python3.12-venv python3.12-dev python3-pip

# 验证安装
python3.12 --version
```

### 使用 pyenv 安装（推荐，多版本管理）

```bash
# 安装依赖
sudo apt install -y make build-essential libssl-dev zlib1g-dev \
  libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm \
  libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev \
  liblzma-dev

# 安装 pyenv
curl https://pyenv.run | bash

# 配置环境变量（添加到 ~/.bashrc）
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo 'command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init -)"' >> ~/.bashrc
source ~/.bashrc

# 安装 Python 3.12.0
pyenv install 3.12.0

# 设置为全局默认版本
pyenv global 3.12.0

# 验证
python --version
```

---

## 4. 安装 Git

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y git

# 验证安装
git --version
```

### 配置 Git（可选但推荐）

```bash
# 配置用户名和邮箱
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# 配置换行符（Windows + WSL2 跨平台开发重要）
git config --global core.autocrlf input
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
# /home/yourname/.venvs/hermes-agent-cn/bin/python
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

1. **在 WSL2 中安装 Ollama**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. **启动 Ollama**
   ```bash
   # 方法一：后台启动
   ollama serve &
   
   # 方法二：使用 systemd（Ubuntu 22.04+）
   sudo systemctl enable ollama
   sudo systemctl start ollama
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
✅ Config file found: /home/yourname/.hermes/config.yaml
✅ At least one LLM provider configured
✅ Virtual environment active: .venvs/hermes-agent-cn
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
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# 现在可以在任何地方运行
hermes chat
```

### 在 Windows 和 WSL2 之间共享文件

```bash
# 在 WSL2 中访问 Windows 文件
cd /mnt/c/Users/YourName/Documents

# 但建议在 WSL2 的 Linux 文件系统中工作（性能更好）
# 例如：~/hermes-agent-cn

# 在 Windows 中访问 WSL2 文件
# 文件资源管理器地址栏输入：\\wsl$\Ubuntu\home\yourname
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

### 问题 1：WSL2 无法启动

**错误信息：**
```
WSL2 is not installed or the component is missing.
```

**解决方法：**
```powershell
# 以管理员身份打开 PowerShell，执行：
wsl --install

# 重启电脑
```

### 问题 2：pip install 失败（网络问题）

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

### 问题 3：hermes 命令找不到

**原因：** 虚拟环境没有激活，或者安装失败

**解决方法：**
```bash
# 检查虚拟环境是否激活
which hermes

# 如果没有，激活虚拟环境
source ~/.venvs/hermes-agent-cn/bin/activate

# 检查是否安装成功
pip list | grep hermes
```

### 问题 4：Ollama 在 WSL2 中无法启动

**解决方法一：手动启动 Ollama**
```bash
ollama serve &
```

**解决方法二：检查 systemd 是否启用**
```bash
# 检查 WSL2 是否支持 systemd
ps -p 1 -o comm=

# 如果不支持，编辑 WSL2 配置文件
# 在 Windows 中编辑：C:\Users\YourName\.wslconfig
# 添加：
# [boot]
# systemd=true

# 然后重启 WSL2
# 在 PowerShell 中：wsl --shutdown
```

### 问题 5：WSL2 文件系统性能问题

**建议：**
- ✅ **在 WSL2 文件系统中工作**（`~/.venvs/`、`~/hermes-agent-cn`）
- ❌ **避免在 `/mnt/c/` 下运行 Python 项目**（性能差）

```bash
# 正确：在 WSL2 文件系统中工作
cd ~/hermes-agent-cn
pip install -e .

# 错误：在 Windows 文件系统中工作（慢）
cd /mnt/c/Users/YourName/hermes-agent-cn
pip install -e .
```

### 问题 6：WSL2 内存占用过高

**解决方法：限制 WSL2 内存使用**

**在 Windows 中创建/编辑 `%USERPROFILE%\.wslconfig`：**
```ini
[wsl2]
memory=8GB
swap=2GB
localhostForwarding=true
```

**然后重启 WSL2：**
```powershell
wsl --shutdown
```

### 问题 7：Git 克隆失败（SSL 证书错误）

**解决方法：**
```bash
# 临时禁用 SSL 验证（仅测试环境）
git config --global http.sslVerify false

# 重新克隆
git clone -b cn https://github.com/xyshanren/hermes-agent-cn.git
```

### 问题 8：Python 版本冲突

**解决方法：**
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

---

## 📚 相关文档

- [WSL2 快速安装](QUICKSTART_WSL2.md)
- [Linux 安装指南](LINUX_INSTALL.md)
- [Linux 快速安装](QUICKSTART_LINUX.md)

---

## 🔗 相关链接

- **WSL2 官方安装指南**：https://learn.microsoft.com/windows/wsl/install
- **Hermes 官方文档**：https://hermes.xaapi.ai/guide/installation
- **项目主页**：https://github.com/xyshanren/hermes-agent-cn
- **上游仓库**：https://github.com/NousResearch/hermes-agent
- **问题反馈**：https://github.com/xyshanren/hermes-agent-cn/issues
- **讨论区**：https://github.com/xyshanren/hermes-agent-cn/discussions

---

**安装完成！** 🎉

现在可以在 WSL2 终端中运行 `hermes chat` 开始使用了。

---

**文档版本**：v1.0 | **最后更新**：2026-05-12
