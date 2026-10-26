#!/bin/bash
# hermes-update.sh - 一键更新 Hermes 智能体 (CN 分支)
#
# 部署位置：WSL 的 ~/hermes-update.sh（从本仓库拷贝：
#   cp /root/hermes-agent-cn/scripts/deploy/hermes-update.sh ~/hermes-update.sh）
#
# 更新方式（2026-10-22 改订：统一 PM 栈）：运行环境由 PM 托管（Python 与依赖
# venv 都在 ~/.hermes 下），gateway 的 systemd 单元经 .hermes/bin/hermes 启动——
# 更新 = git pull + hermes pm install（默认同步 [all] 特性集，按锁安装不重新
# 解析），不再维护独立的 /root/hermes-venv（当日已退役删除）。

set -e

echo "=== 开始更新 Hermes 智能体 ==="

PROJECT_PATH="$HOME/hermes-agent-cn"
HERMES_BIN="$PROJECT_PATH/.hermes/bin/hermes"

# 1. 检查目录与入口
[ -d "$PROJECT_PATH" ] || { echo "错误：项目目录不存在 ($PROJECT_PATH)"; exit 1; }
[ -x "$HERMES_BIN" ] || { echo "错误：PM 启动器不存在 ($HERMES_BIN)"; exit 1; }

# 2. 拉取最新代码（先弃掉本地 uv.lock 的改动：sync 的重解析产物，仓库锁是权威，
#    留着会挡 pull）。fetch 显式带 --tags --force：pull 的分支 refspec 不会可靠地
#    跟进 tag（tag 重打过时本地旧 tag 还会挡住更新），而版本号显示依赖 merged tag。
cd "$PROJECT_PATH"
echo "拉取最新代码 (origin/cn)..."
git checkout -- uv.lock 2>/dev/null || true
git fetch origin cn --tags --force
git merge --ff-only FETCH_HEAD

# 3. 依赖与工具按锁装进 PM 环境（[all] 特性集；pm install 事务式，
#    新环境提交前旧环境原样保留，中途失败不影响在跑的 gateway）
echo "同步依赖到 PM 环境 ([all])..."
"$HERMES_BIN" pm install

# 4. 网关在跑就重启它加载新代码与新环境
if systemctl --user is-active --quiet hermes-gateway 2>/dev/null; then
    echo "重启网关加载新代码..."
    systemctl --user restart hermes-gateway
    sleep 12
    systemctl --user is-active hermes-gateway && echo "网关已重启 OK"
fi

# 5. 验证
"$HERMES_BIN" --version

echo "=== 更新完成 ==="
