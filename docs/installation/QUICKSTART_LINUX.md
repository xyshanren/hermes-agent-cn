# Hermes-Agent-CN Linux 快速安装指南

> 10 分钟完成安装 | 适用于 Ubuntu/Debian/CentOS/RHEL/Arch

---

## 🚀 快速安装（3 步）

### 1. 安装 Python 3.11+ 和 Git

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip git

# CentOS/RHEL
sudo dnf install -y python3.12 python3.12-pip git

# Arch
sudo pacman -S python python-pip git
```

### 2. 克隆仓库并创建虚拟环境

```bash
# 克隆 CN 分支
cd ~
git clone -b cn https://github.com/xyshanren/hermes-agent-cn.git
cd hermes-agent-cn

# 在项目目录外创建虚拟环境（推荐做法）
python3.12 -m venv ~/.venvs/hermes-agent-cn
source ~/.venvs/hermes-agent-cn/bin/activate

# 升级 pip
pip install --upgrade pip
```

> **💡 为什么在项目目录外创建虚拟环境？**
> - ✅ 避免意外提交到 Git（即使 `.gitignore` 配置正确）
> - ✅ 多个项目可以共享同一个虚拟环境（可选）
> - ✅ 项目目录更干净，只保留代码和配置
> - ✅ 符合 Python 社区最佳实践（PEP 370、Poetry、Pipenv 等工具默认行为）

### 3. 安装 Hermes

```bash
# 安装项目（editable 模式）
pip install -e .

# 验证安装
hermes --version
hermes doctor
```

---

## ⚙️ 配置

### 方法一：自动配置（推荐）

```bash
hermes quickstart
```

### 方法二：手动配置 API Key

```bash
# 运行设置向导
hermes setup

# 或者手动编辑配置文件
mkdir -p ~/.hermes
cat > ~/.hermes/.env << 'EOF'
ZHIPU_API_KEY=your-api-key-here
EOF
chmod 600 ~/.hermes/.env
```

### 方法三：使用 Ollama（本地模型）

```bash
# 安装 Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 启动 Ollama
ollama serve &

# 拉取模型
ollama pull qwen2.5:3b

# 配置 Hermes
hermes setup
# 选择 "Use Ollama (local models)"
```

---

## ✅ 验证

```bash
# 测试对话
hermes chat -q "你好"

# 运行诊断
hermes doctor
```

**期望输出：**
```
✅ Python version: 3.12.0
✅ Hermes installed: v0.12.0
✅ Config file found: /home/user/.hermes/config.yaml
✅ At least one LLM provider configured
```

---

## 📖 日常使用

### 激活虚拟环境并启动

```bash
# 激活虚拟环境（在项目目录外）
source ~/.venvs/hermes-agent-cn/bin/activate

cd ~/hermes-agent-cn
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

---

## 🔄 更新

```bash
cd ~/hermes-agent-cn
source ~/.venvs/hermes-agent-cn/bin/activate
git pull origin cn
pip install -e .
```

---

## 🐛 常见问题

### 问题 1：pip install 失败（网络问题）

```bash
# 使用国内镜像源
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 问题 2：hermes 命令找不到

```bash
# 检查虚拟环境是否激活
which hermes

# 如果没有，激活虚拟环境（在项目目录外）
source ~/.venvs/hermes-agent-cn/bin/activate
```

### 问题 3：Python 版本太低

```bash
# 检查 Python 版本
python3 --version

# 如果 < 3.11，安装 Python 3.12
sudo apt install -y python3.12 python3.12-venv
```

---

## 📚 详细文档

完整安装指南：[LINUX_INSTALL.md](LINUX_INSTALL.md)

---

**安装完成！** 🎉

现在可以运行 `hermes chat` 开始使用了。

---

**文档版本**：v1.0 | **最后更新**：2026-05-11
