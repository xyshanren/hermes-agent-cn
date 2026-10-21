#!/bin/bash
# hermes-update.sh - 一键更新 Hermes 智能体 (CN 分支)
#
# 部署位置：WSL 的 ~/hermes-update.sh（从本仓库拷贝：
#   cp /root/hermes-agent-cn/scripts/deploy/hermes-update.sh ~/hermes-update.sh）
#
# 更新方式（2026-10-21 重写）：venv 由 uv 管理（uv venv 无 pip，裸 pip 会落到
# 系统 pip3 被 PEP 668 拦下），项目有 uv.lock —— 所以更新 = git pull + 按锁
# uv sync，不做重新解析（依赖版本与 CI/开发环境一致）。

set -e

echo "=== 开始更新 Hermes 智能体 ==="

VENV_PATH="$HOME/hermes-venv"
PROJECT_PATH="$HOME/hermes-agent-cn"

# 1. 找 uv（venv 由 uv 管理，没有 pip 可用）
UV_BIN="/root/.local/bin/uv"
if [ ! -x "$UV_BIN" ]; then
    UV_BIN="$(command -v uv || true)"
fi
if [ -z "$UV_BIN" ]; then
    echo "错误：找不到 uv。安装方法见 docs.astral.sh/uv（或把 uv 装进一个不随更新重建的稳定位置）"
    exit 1
fi

# 2. 检查目录
[ -d "$VENV_PATH" ] || { echo "错误：虚拟环境目录不存在 ($VENV_PATH)"; exit 1; }
[ -d "$PROJECT_PATH" ] || { echo "错误：项目目录不存在 ($PROJECT_PATH)"; exit 1; }

# 3. 拉取最新代码（先弃掉本地 uv.lock 的改动：sync 的重解析产物，仓库锁是权威，
#    留着会挡 pull）
cd "$PROJECT_PATH"
echo "拉取最新代码 (origin/cn)..."
git checkout -- uv.lock 2>/dev/null || true
git pull origin cn

# 4. 按锁安装依赖（含 [all] 特性集 + dev 组；Python 版本按 .python-version）
echo "按 uv.lock 安装依赖..."
UV_PROJECT_ENVIRONMENT="$VENV_PATH" "$UV_BIN" sync --frozen --extra all --group dev

# 5. 验证
echo "验证安装："
"$VENV_PATH/bin/hermes" --version
"$VENV_PATH/bin/python" -c "import hermes_cli.config, agent.chat_completion_helpers; print('核心导入 OK')"

# 6. 网关在跑就重启它加载新代码（一键更新的收尾；没有服务则跳过）
if systemctl --user is-active --quiet hermes-gateway 2>/dev/null; then
    echo "重启网关加载新代码..."
    systemctl --user restart hermes-gateway
    sleep 12
    systemctl --user is-active hermes-gateway && echo "网关已重启 OK"
fi

echo "=== 更新完成 ==="
