# Hermes Agent CN 常见问题

> 收集自安装指南、用户反馈和测试过程  
> 最后更新: 2026-05-13

---

## 📂 如何选择文档？

| 你的需求 | 看这个 |
|---------|--------|
| 还没安装，想快速上手 | [QUICKSTART_LINUX.md](./installation/QUICKSTART_LINUX.md) |
| 想了解完整安装步骤 | [LINUX_INSTALL.md](./installation/LINUX_INSTALL.md) |
| 用 macOS | [MACOS_INSTALL.md](./installation/MACOS_INSTALL.md) |
| 用 Windows (WSL2) | [WSL2_INSTALL.md](./installation/WSL2_INSTALL.md) |
| 遇到具体报错 | 👇 往下看 |

---

## 📦 安装相关问题

### Q1: pip install 失败，网络超时

```
ERROR: Connection timeout / Read timed out
```

**原因**: 默认连接 PyPI 官方源，国内网络不稳定。

**解决**: 使用国内镜像源：

```bash
# 临时使用
pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple

# 永久配置
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

**常用镜像源**：
- 清华：`https://pypi.tuna.tsinghua.edu.cn/simple`
- 阿里：`https://mirrors.aliyun.com/pypi/simple`
- 豆瓣：`https://pypi.douban.com/simple`

---

### Q2: Python 版本太低

```
ERROR: Package requires Python >=3.11
```

**解决**:
```bash
# 安装 Python 3.12
sudo apt install -y python3.12 python3.12-venv

# 用 Python 3.12 重新创建虚拟环境
python3.12 -m venv ~/.venvs/hermes-agent-cn
```

---

### Q3: `hermes: command not found`

**原因**: 虚拟环境未激活，或安装失败。

**解决**:
```bash
# 激活虚拟环境
source ~/.venvs/hermes-agent-cn/bin/activate

# 验证
which hermes

# 如果 still not found，重新安装
pip install -e .
```

---

### Q4: `No module named 'hermes_cli'`

**原因**: 虚拟环境损坏或未正确安装。

**解决**:
```bash
deactivate
rm -rf ~/.venvs/hermes-agent-cn
python3.12 -m venv ~/.venvs/hermes-agent-cn
source ~/.venvs/hermes-agent-cn/bin/activate
pip install -e .
```

---

## 🔑 配置相关问题

### Q5: `ERROR: No LLM provider configured`

**原因**: 未配置 API Key 或本地模型。

**解决**:
```bash
# 方式一：自动检测（推荐）
hermes quickstart

# 方式二：手动配置向导
hermes setup

# 方式三：手动编辑 .env 文件
nano ~/.hermes/.env
# 添加你的 API Key，例如：
# DEEPSEEK_API_KEY=sk-xxxx
```

---

### Q6: `Provider resolver returned an empty API key`

**原因**: `hermes setup` 保存的 API Key 未被正确读取。

**修复方法**（v0.12.0-cn.3 已修复此 Bug）：
```bash
# 升级到最新版本
git pull origin cn
pip install -e .

# 重新配置
hermes setup
```

如果仍出现此问题，检查 `.env` 文件是否为空或格式错误：
```bash
cat ~/.hermes/.env
# 正确的格式：
# DEEPSEEK_API_KEY=sk-xxxx
# 错误的格式（不要有 export 前缀或多余空格）：
# export DEEPSEEK_API_KEY=sk-xxxx  ← 不需要 export
# DEEPSEEK_API_KEY = sk-xxxx       ← 等号两边不要空格
```

---

### Q7: `Permission denied: ~/.hermes/config.yaml`

**解决**:
```bash
chmod 755 ~/.hermes
chmod 644 ~/.hermes/config.yaml
chmod 600 ~/.hermes/.env
```

---

## 🖥️ 运行时问题

### Q8: Ollama 连接失败

```
ERROR: Cannot connect to Ollama at localhost:11434
```

**解决**:
```bash
# 检查 Ollama 是否运行
ps aux | grep ollama

# 启动 Ollama
ollama serve &

# 验证可用
curl http://localhost:11434/api/tags
```

---

### Q9: 端口被占用（Gateway 模式）

```
ERROR: Port 8000 already in use
```

**解决**:
```bash
# 查找占用端口的进程
sudo lsof -i :8000

# 杀死进程
kill -9 <PID>

# 或使用其他端口
hermes gateway --port 8001
```

---

### Q10: `hermes doctor` 报 `.env file missing` 但已配好 Ollama

**原因**: Doctor 的 .env 检测是硬性检查，即使只用本地模型也会报错。

**临时解决**：创建空的 `.env` 文件
```bash
touch ~/.hermes/.env
```

**永久修复**：已在 PROPOSAL-doctor-improvements.md 中规划优化（D1）。

---

### Q11: `hermes doctor` 报 `Not in virtual environment`（已使用 Conda）

**原因**: Doctor 只检测 `sys.prefix != sys.base_prefix`，不识别 Conda 环境变量。

**状态**: 已知问题，已在 PROPOSAL-doctor-improvements.md 中规划优化（D2）。

---

### Q12: `hermes chat` 中 `/model` 列表显示过多国外 Provider

**原因**: CN 分支已按国内用户常用场景做了过滤。

**当前列表（11 个）**：
- **国产**: deepseek, kimi-coding, kimi-coding-cn, minimax-cn, zai, alibaba, xiaomi, qwen-oauth, siliconflow
- **本地**: ollama
- **可选**: nous

国际版 Provider（anthropic、gemini、openrouter 等）默认不显示，如需要可在配置中手动添加。

---

## 🪟 WSL2 专属问题

### Q13: WSL2 无法启动

```
WSL2 is not installed or the component is missing.
```

**解决**:
```powershell
# 管理员身份运行 PowerShell
wsl --install
# 重启电脑
```

---

### Q14: WSL2 文件系统性能慢

**原因**: 在 `/mnt/c/`（Windows 文件系统）下运行 Python。

**解决**: 使用 WSL2 原生文件系统
```bash
# ❌ 不要这样做（慢）
cd /mnt/c/Users/YourName/hermes-agent-cn

# ✅ 应该这样做（快）
cd ~/hermes-agent-cn
```

---

### Q15: WSL2 内存占用过高

**解决**: 限制 WSL2 内存

在 Windows 中创建 `%USERPROFILE%\.wslconfig`：
```ini
[wsl2]
memory=8GB
swap=2GB
localhostForwarding=true
```

重启 WSL2：
```powershell
wsl --shutdown
```

---

### Q16: Git 克隆失败（SSL 证书错误）

**解决**:
```bash
# 临时禁用 SSL 验证
git config --global http.sslVerify false
git clone -b cn https://github.com/xyshanren/hermes-agent-cn.git
```

---

## 🍎 macOS 专属问题

### Q17: macOS 上 `hermes` 命令签名被阻止

**解决**: 在「系统设置 → 隐私与安全性」中允许运行，或在终端执行：
```bash
xattr -d com.apple.quarantine $(which hermes)
```

---

## 🔍 诊断与调试

### 如何获取诊断信息？

```bash
# 运行诊断工具
hermes doctor

# 查看版本信息
hermes --version
cat ~/.hermes/config.yaml

# 查看 API Key 配置（不输出实际 key，只检测是否存在）
test -f ~/.hermes/.env && wc -l ~/.hermes/.env

# 查看 Python 环境
which python3
python3 --version
```

### 如何获取更多日志？

```bash
# 设置调试日志
export HERMES_LOG_LEVEL=debug
hermes chat

# 查看日志文件
cat ~/.hermes/logs/*.log
```

---

## 📬 寻求帮助

如果以上 FAQ 未解决你的问题：

1. 运行 `hermes doctor` 收集诊断信息
2. 到 [GitHub Issues](https://github.com/xyshanren/hermes-agent-cn/issues) 提交问题报告
3. 在 [Discussions](https://github.com/xyshanren/hermes-agent-cn/discussions) 讨论区提问

提交 Issue 时请提供：
- 操作系统和版本
- Python 版本（`python3 --version`）
- Hermes 版本（`hermes --version`）
- `hermes doctor` 完整输出
- 错误日志
