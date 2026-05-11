# Hermes-Agent-CN Windows 快速安装指南

> 10 分钟完成安装 | 适用于 Windows 10/11

---

## 🚀 快速安装（3 步）

### 1. 安装 Python 3.11+ 和 Git

**方法一：官方安装包（推荐）**

1. 下载 Python：https://www.python.org/downloads/
   - 选择 **Python 3.12.x**（或更新版本）
   - 安装时勾选 **"Add Python to PATH"**

2. 下载 Git：https://git-scm.com/download/win
   - 使用默认选项安装即可

**验证安装：**
```cmd
python --version
git --version
```

### 2. 克隆仓库并创建虚拟环境

```cmd
:: 克隆 CN 分支
cd %USERPROFILE%
git clone -b cn https://github.com/xyshanren/hermes-agent-cn.git
cd hermes-agent-cn

:: 在项目目录外创建虚拟环境（推荐做法）
python -m venv %USERPROFILE%\.venvs\hermes-agent-cn
%USERPROFILE%\.venvs\hermes-agent-cn\Scripts\activate.bat

:: 升级 pip
pip install --upgrade pip
```

> **💡 为什么在项目目录外创建虚拟环境？**
> - ✅ 避免意外提交到 Git（即使 `.gitignore` 配置正确）
> - ✅ 多个项目可以共享同一个虚拟环境（可选）
> - ✅ 项目目录更干净，只保留代码和配置
> - ✅ 符合 Python 社区最佳实践（PEP 370、Poetry、Pipenv 等工具默认行为）

### 3. 安装 Hermes

```cmd
:: 安装项目（editable 模式）
pip install -e .

:: 验证安装
hermes --version
hermes doctor
```

---

## ⚙️ 配置

### 方法一：自动配置（推荐）

```cmd
hermes quickstart
```

### 方法二：手动配置 API Key

```cmd
:: 运行设置向导
hermes setup

:: 或者手动编辑配置文件
mkdir %USERPROFILE%\.hermes
notepad %USERPROFILE%\.hermes\.env
```

**.env 文件内容示例：**
```
ZHIPU_API_KEY=your-api-key-here
```

### 方法三：使用 Ollama（本地模型）

```cmd
:: 下载并安装 Ollama：https://ollama.com/download/windows
:: 启动 Ollama（安装后会自动启动）

:: 拉取模型
ollama pull qwen2.5:3b

:: 配置 Hermes
hermes setup
:: 选择 "Use Ollama (local models)"
```

---

## ✅ 验证

```cmd
:: 测试对话
hermes chat -q "你好"

:: 运行诊断
hermes doctor
```

**期望输出：**
```
✅ Python version: 3.12.0
✅ Hermes installed: v0.12.0
✅ Config file found: C:\Users\YourName\.hermes\config.yaml
✅ At least one LLM provider configured
```

---

## 📖 日常使用

### 激活虚拟环境并启动

```cmd
:: 激活虚拟环境（在项目目录外）
%USERPROFILE%\.venvs\hermes-agent-cn\Scripts\activate.bat

cd %USERPROFILE%\hermes-agent-cn
hermes chat
```

### 创建全局命令（推荐）

```cmd
:: 添加到 PATH（永久生效）
setx PATH "%PATH%;%USERPROFILE%\.venvs\hermes-agent-cn\Scripts"

:: 现在可以在任何地方运行
hermes chat
```

**或者直接创建批处理文件：**
```cmd
echo %USERPROFILE%\.venvs\hermes-agent-cn\Scripts\activate.bat > %USERPROFILE%\hermes.bat
echo cd %USERPROFILE%\hermes-agent-cn >> %USERPROFILE%\hermes.bat
echo hermes chat >> %USERPROFILE%\hermes.bat

:: 运行
%USERPROFILE%\hermes.bat
```

---

## 🔄 更新

```cmd
cd %USERPROFILE%\hermes-agent-cn
git pull origin cn
pip install -e .
```

---

## 🐛 常见问题

### 问题 1：pip install 失败（网络问题）

```cmd
:: 使用国内镜像源
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 问题 2：hermes 命令找不到

```cmd
:: 检查虚拟环境是否激活
where hermes

:: 如果没有，激活虚拟环境（在项目目录外）
%USERPROFILE%\.venvs\hermes-agent-cn\Scripts\activate.bat
```

### 问题 3：Python 版本太低

```cmd
:: 检查 Python 版本
python --version

:: 如果 < 3.11，下载并安装 Python 3.12
:: https://www.python.org/downloads/
```

### 问题 4：PowerShell 执行策略阻止脚本运行

```powershell
:: 以管理员身份运行 PowerShell，然后执行：
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 问题 5：Git 克隆失败（SSL 证书错误）

```cmd
:: 临时禁用 SSL 验证（仅测试环境）
git config --global http.sslVerify false

:: 或者配置代理
git config --global http.proxy http://proxy.example.com:8080
```

---

## 📚 详细文档

完整安装指南：[WINDOWS_INSTALL.md](WINDOWS_INSTALL.md)

---

**安装完成！** 🎉

现在可以运行 `hermes chat` 开始使用了。

---

**文档版本**：v1.0 | **最后更新**：2026-05-12
