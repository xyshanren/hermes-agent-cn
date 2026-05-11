# Hermes-Agent-CN Windows 安装指南

> 适用于 Windows 10/11（所有版本）  
> 版本：v0.12.0-cn.1 | 最后更新：2026-05-12

---

## 📋 目录

1. [系统要求](#1-系统要求)
2. [安装 Python 3.11+](#2-安装-python-311)
3. [安装 Git](#3-安装-git)
4. [创建专属虚拟环境](#4-创建专属虚拟环境)
5. [克隆 hermes-agent-cn 仓库](#5-克隆-hermes-agent-cn-仓库)
6. [安装依赖](#6-安装依赖)
7. [配置 Hermes](#7-配置-hermes)
8. [验证安装](#8-验证安装)
9. [日常使用](#9-日常使用)
10. [更新 Hermes](#10-更新-hermes)
11. [常见问题排查](#11-常见问题排查)

---

## 1. 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|----------|----------|
| **操作系统** | Windows 10 版本 19041+ | Windows 11 |
| **Python** | 3.11+ | 3.12 |
| **Git** | 2.30+ | 最新稳定版 |
| **磁盘空间** | 2 GB | 5 GB（含虚拟环境） |
| **内存** | 4 GB | 8 GB+（运行本地模型需要更多） |
| **网络** | 能访问 GitHub | 能访问 GitHub + API 端点 |

### 可选依赖

| 功能 | 所需组件 |
|------|----------|
| 本地模型（Ollama） | [Ollama for Windows](https://ollama.com/download/windows) |
| 浏览器工具 | Node.js 20+ |
| 语音功能 | sounddevice、faster-whisper |
| GPU 加速 | NVIDIA GPU + CUDA 12.1+ |

---

## 2. 安装 Python 3.11+

### 方法一：官方安装包（推荐）

1. **下载 Python 3.12**
   - 访问：https://www.python.org/downloads/
   - 点击 **"Download Python 3.12.x"**

2. **运行安装程序**
   - ✅ **重要**：勾选 **"Add Python to PATH"**（添加到 PATH）
   - 选择 **"Customize installation"**（自定义安装）
   - ✅ 勾选 **"pip"**、**"pylauncher"**
   - 点击 **"Install"**

3. **验证安装**
   ```cmd
   python --version
   pip --version
   ```

### 方法二：Microsoft Store（简化安装）

1. 打开 **Microsoft Store**
2. 搜索 **"Python 3.12"**
3. 点击 **"获取"**（会自动添加到 PATH）
4. 验证安装：
   ```cmd
   python --version
   ```

### 方法三：使用 Chocolatey（高级用户）

```cmd
:: 安装 Chocolatey（如果还没有）
:: 以管理员身份运行 PowerShell，执行：
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

:: 安装 Python 3.12
choco install python312 -y

:: 验证
python --version
```

### 方法四：使用 winget（Windows 10/11 内置）

```cmd
:: 安装 Python 3.12
winget install Python.Python.3.12

:: 验证
python --version
```

---

## 3. 安装 Git

### 方法一：官方安装包（推荐）

1. **下载 Git**
   - 访问：https://git-scm.com/download/win
   - 下载 **64-bit Git for Windows Setup**

2. **运行安装程序**
   - ✅ 选择 **"Use Git from the command line and also from 3rd-party software"**
   - ✅ 选择 **"Checkout as-is, commit Unix-style line endings"**
   - 其他使用默认选项

3. **验证安装**
   ```cmd
   git --version
   ```

### 方法二：使用 Chocolatey

```cmd
choco install git -y
```

### 方法三：使用 winget

```cmd
winget install Git.Git
```

---

## 4. 创建专属虚拟环境

### 为什么要在项目目录外创建虚拟环境？

✅ **避免意外提交到 Git**（即使 `.gitignore` 配置正确）  
✅ **项目目录更干净**，只保留代码和配置  
✅ **符合 Python 社区最佳实践**（PEP 370、Poetry、Pipenv 等工具默认行为）  
✅ **多个项目可以共享同一个虚拟环境**（可选）

### 创建虚拟环境

```cmd
:: 在项目目录外创建虚拟环境（推荐路径）
python -m venv %USERPROFILE%\.venvs\hermes-agent-cn

:: 激活虚拟环境
%USERPROFILE%\.venvs\hermes-agent-cn\Scripts\activate.bat
```

**验证虚拟环境：**
```cmd
:: 应该显示虚拟环境路径
where python

:: 输出应该类似：
:: C:\Users\YourName\.venvs\hermes-agent-cn\Scripts\python.exe
```

### 虚拟环境管理

```cmd
:: 激活虚拟环境
%USERPROFILE%\.venvs\hermes-agent-cn\Scripts\activate.bat

:: 退出虚拟环境
deactivate

:: 删除虚拟环境（如果需要）
rmdir /s /q %USERPROFILE%\.venvs\hermes-agent-cn
```

---

## 5. 克隆 hermes-agent-cn 仓库

```cmd
:: 切换到用户主目录
cd %USERPROFILE%

:: 克隆 CN 分支
git clone -b cn https://github.com/xyshanren/hermes-agent-cn.git

:: 进入项目目录
cd hermes-agent-cn

:: 查看分支
git branch -a
```

**预期输出：**
```
* cn
  remotes/origin/cn
```

### 如果遇到克隆失败（SSL 证书错误）

```cmd
:: 临时禁用 SSL 验证（仅测试环境）
git config --global http.sslVerify false

:: 或者配置代理
git config --global http.proxy http://proxy.example.com:8080

:: 然后重新克隆
git clone -b cn https://github.com/xyshanren/hermes-agent-cn.git
```

---

## 6. 安装依赖

### 激活虚拟环境

```cmd
%USERPROFILE%\.venvs\hermes-agent-cn\Scripts\activate.bat
```

**提示：** 激活后，命令提示符前会显示 `(hermes-agent-cn)`。

### 升级 pip

```cmd
pip install --upgrade pip
```

### 安装项目（editable 模式）

```cmd
:: 进入项目目录
cd %USERPROFILE%\hermes-agent-cn

:: 安装项目（editable 模式，修改代码后无需重装）
pip install -e .
```

**使用国内镜像源（如果网络不好）：**
```cmd
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 安装可选依赖

```cmd
:: 安装浏览器工具（需要 Node.js）
pip install -e ".[browser]"

:: 安装所有可选依赖
pip install -e ".[all]"
```

---

## 7. 配置 Hermes

### 方法一：自动配置（推荐）

```cmd
hermes quickstart
```

按照提示选择：
1. **选择 LLM 提供商**（智谱 AI、OpenAI、Ollama 等）
2. **输入 API Key**（如果使用云服务）
3. **选择默认模型**

### 方法二：手动配置

```cmd
:: 运行设置向导
hermes setup
```

或者手动编辑配置文件：

```cmd
:: 创建配置目录
mkdir %USERPROFILE%\.hermes

:: 创建 .env 文件
notepad %USERPROFILE%\.hermes\.env
```

**.env 文件内容示例：**
```
ZHIPU_API_KEY=your-zhipu-api-key-here
OPENAI_API_KEY=your-openai-api-key-here
```

### 方法三：使用 Ollama（本地模型）

1. **安装 Ollama**
   - 下载：https://ollama.com/download/windows
   - 运行安装程序
   - Ollama 会自动启动

2. **拉取模型**
   ```cmd
   ollama pull qwen2.5:3b
   ```

3. **配置 Hermes**
   ```cmd
   hermes setup
   ```
   - 选择 **"Use Ollama (local models)"**
   - 输入 Ollama 地址（默认：`http://localhost:11434`）

---

## 8. 验证安装

### 运行诊断工具

```cmd
hermes doctor
```

**预期输出：**
```
✅ Python version: 3.12.0
✅ Hermes installed: v0.12.0
✅ Config file found: C:\Users\YourName\.hermes\config.yaml
✅ At least one LLM provider configured
✅ Virtual environment active: .venvs\hermes-agent-cn
```

### 测试对话

```cmd
hermes chat -q "你好，请介绍一下你自己"
```

**预期输出：**
```
你好！我是 Hermes Agent，一个强大的 AI 助手。
我可以帮助你完成各种任务，包括...
```

---

## 9. 日常使用

### 激活虚拟环境并启动

```cmd
:: 激活虚拟环境
%USERPROFILE%\.venvs\hermes-agent-cn\Scripts\activate.bat

:: 进入项目目录
cd %USERPROFILE%\hermes-agent-cn

:: 启动 Hermes
hermes chat
```

### 创建全局命令（推荐）

**方法一：添加到 PATH（永久生效）**

```cmd
:: 将虚拟环境的 Scripts 目录添加到 PATH
setx PATH "%PATH%;%USERPROFILE%\.venvs\hermes-agent-cn\Scripts"

:: 重新打开 CMD，现在可以在任何地方运行
hermes chat
```

**方法二：创建批处理文件**

```cmd
:: 创建 hermes.bat
echo @echo off > %USERPROFILE%\hermes.bat
echo call %USERPROFILE%\.venvs\hermes-agent-cn\Scripts\activate.bat >> %USERPROFILE%\hermes.bat
echo cd %USERPROFILE%\hermes-agent-cn >> %USERPROFILE%\hermes.bat
echo hermes chat >> %USERPROFILE%\hermes.bat

:: 运行
%USERPROFILE%\hermes.bat
```

**方法三：创建 PowerShell 配置文件（高级用户）**

```powershell
:: 创建 PowerShell 配置文件
New-Item -Path $PROFILE -ItemType File -Force

:: 编辑配置文件
notepad $PROFILE
```

**添加以下内容到 $PROFILE：**
```powershell
function hermes {
    & "$env:USERPROFILE\.venvs\hermes-agent-cn\Scripts\Activate.ps1"
    Set-Location "$env:USERPROFILE\hermes-agent-cn"
    & hermes chat
}
```

---

## 10. 更新 Hermes

```cmd
:: 激活虚拟环境
%USERPROFILE%\.venvs\hermes-agent-cn\Scripts\activate.bat

:: 进入项目目录
cd %USERPROFILE%\hermes-agent-cn

:: 拉取最新代码
git pull origin cn

:: 重新安装（如果有依赖变更）
pip install -e .
```

---

## 11. 常见问题排查

### 问题 1：Python 不是内部或外部命令

**原因：** Python 没有添加到 PATH

**解决方法：**
```cmd
:: 查找 Python 安装路径
where python

:: 如果找不到，手动添加到 PATH
:: 控制面板 → 系统和安全 → 系统 → 高级系统设置 → 环境变量
:: 在 "用户变量" 中找到 "Path"，点击 "编辑"
:: 添加 Python 安装路径（例如：C:\Python312\）
```

### 问题 2：pip install 失败（网络问题）

**解决方法一：使用国内镜像源**
```cmd
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**解决方法二：配置 pip 镜像（永久生效）**
```cmd
:: 创建 pip 配置文件
mkdir %APPDATA%\pip
notepad %APPDATA%\pip\pip.ini
```

**pip.ini 内容：**
```ini
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
trusted-host = pypi.tuna.tsinghua.edu.cn
```

### 问题 3：hermes 命令找不到

**原因：** 虚拟环境没有激活，或者安装失败

**解决方法：**
```cmd
:: 检查虚拟环境是否激活
where hermes

:: 如果没有，激活虚拟环境
%USERPROFILE%\.venvs\hermes-agent-cn\Scripts\activate.bat

:: 检查是否安装成功
pip list | findstr hermes
```

### 问题 4：PowerShell 执行策略阻止脚本运行

**错误信息：**
```
.\activate.ps1 : 无法加载，因为在此系统上禁止运行脚本。
```

**解决方法：**
```powershell
:: 以管理员身份运行 PowerShell，然后执行：
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

:: 验证
Get-ExecutionPolicy -List
```

### 问题 5：Git 克隆失败（SSL 证书错误）

**解决方法：**
```cmd
:: 临时禁用 SSL 验证（仅测试环境）
git config --global http.sslVerify false

:: 重新克隆
git clone -b cn https://github.com/xyshanren/hermes-agent-cn.git
```

### 问题 6：Ollama 无法启动

**解决方法：**
1. 检查 Ollama 是否安装成功：
   ```cmd
   where ollama
   ```

2. 手动启动 Ollama：
   ```cmd
   ollama serve
   ```

3. 检查防火墙设置（确保 11434 端口未被阻止）

### 问题 7：虚拟环境激活后，pip 安装的包找不到

**原因：** 可能有多个 Python 版本冲突

**解决方法：**
```cmd
:: 检查当前 Python 路径
where python

:: 应该显示虚拟环境中的 Python
:: 如果不是，删除虚拟环境并重新创建
rmdir /s /q %USERPROFILE%\.venvs\hermes-agent-cn
python -m venv %USERPROFILE%\.venvs\hermes-agent-cn
```

### 问题 8：Windows 长路径限制

**错误信息：**
```
The specified path, file name, or both are too long.
```

**解决方法：**
```cmd
:: 以管理员身份运行 PowerShell，启用长路径支持
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
  -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

或者在 **组策略编辑器** 中启用：
1. 运行 `gpedit.msc`
2. 导航到：**计算机配置 → 管理模板 → 系统 → 文件系统**
3. 启用 **"启用 Win32 长路径"**

---

## 📚 相关文档

- [快速安装指南](QUICKSTART_WINDOWS.md)
- [Linux 安装指南](LINUX_INSTALL.md)
- [Linux 快速安装](QUICKSTART_LINUX.md)

---

## 🔗 相关链接

- **项目主页**：https://github.com/xyshanren/hermes-agent-cn
- **上游仓库**：https://github.com/NousResearch/hermes-agent
- **问题反馈**：https://github.com/xyshanren/hermes-agent-cn/issues
- **讨论区**：https://github.com/xyshanren/hermes-agent-cn/discussions

---

**安装完成！** 🎉

现在可以运行 `hermes chat` 开始使用了。

---

**文档版本**：v1.0 | **最后更新**：2026-05-12
