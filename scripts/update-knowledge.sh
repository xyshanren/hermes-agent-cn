#!/bin/bash
# Hermes-agent-cn 知识库自动化更新脚本
# 功能：在上游合并后自动更新 MemPalace 和 graphify 知识库
#
# 使用方法：
#   1. 手动运行：bash scripts/update-knowledge.sh
#   2. Git hook：在 .git/hooks/post-merge 中调用此脚本
#
# 作者：守一 (lixy2017@aliyun.com)
# 日期：2026-04-18

set -e

# 配置
HERMES_DIR="/mnt/f/work/workspace/qclaw/码一/hermes-agent"
VENV_PATH="$HOME/hermes-venv"
MEMPALACE_DIR="$HOME/.mempalace/palace"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 激活虚拟环境
activate_venv() {
    if [ -f "$VENV_PATH/bin/activate" ]; then
        source "$VENV_PATH/bin/activate"
        log_info "虚拟环境已激活: $VENV_PATH"
    else
        log_error "虚拟环境不存在: $VENV_PATH"
        exit 1
    fi
}

# 更新 MemPalace
update_mempalace() {
    log_info "开始更新 MemPalace..."
    cd "$HERMES_DIR"
    
    # 检查是否有 mempalace 配置
    if [ ! -f "$HERMES_DIR/mempalace.yaml" ]; then
        log_warn "MemPalace 未初始化，跳过..."
        return
    fi
    
    # Mine 新增/修改的文件（限制数量避免耗时过长）
    mempalace mine "$HERMES_DIR" --limit 50
    log_info "MemPalace 更新完成"
}

# 更新 graphify
update_graphify() {
    log_info "开始更新 graphify..."
    cd "$HERMES_DIR"
    
    # 检查是否有 graphify 输出
    if [ ! -d "$HERMES_DIR/graphify-out" ]; then
        log_warn "graphify 未初始化，跳过..."
        return
    fi
    
    # 更新图谱（无需 LLM）
    graphify update "$HERMES_DIR"
    log_info "graphify 更新完成"
}

# 生成变更摘要
generate_summary() {
    log_info "生成变更摘要..."
    cd "$HERMES_DIR"
    
    # 获取最近的 merge commit
    LAST_MERGE=$(git log --oneline -1 --merges 2>/dev/null || echo "无合并记录")
    
    # 获取最近修改的文件（只看代码文件）
    RECENT_FILES=$(git diff --name-only HEAD~5 HEAD 2>/dev/null | grep -E '\.(py|md|yaml)$' | head -20 || echo "无变更")
    
    SUMMARY_FILE="$HERMES_DIR/KNOWLEDGE_UPDATE.md"
    
    cat > "$SUMMARY_FILE" << EOF
# 知识库更新摘要

**更新时间**: $(date '+%Y-%m-%d %H:%M:%S')

## 最近合并

$LAST_MERGE

## 最近修改的文件（代码/文档）

\`\`\`
$RECENT_FILES
\`\`\`

## 知识库状态

### MemPalace
- 存储位置: $MEMPALACE_DIR
- 更新状态: $(mempalace status 2>/dev/null | grep -E 'WING|ROOM' | head -10 || echo "未知")

### graphify
- 存储位置: $HERMES_DIR/graphify-out
- 节点数: $(cat $HERMES_DIR/graphify-out/graph.json 2>/dev/null | grep -o '"nodes":\[' | wc -l || echo "未知")
- 边数: $(cat $HERMES_DIR/graphify-out/graph.json 2>/dev/null | grep -o '"edges":\[' | wc -l || echo "未知")

---
*自动生成 by update-knowledge.sh*
EOF
    
    log_info "摘要已保存到: $SUMMARY_FILE"
}

# 主流程
main() {
    log_info "=========================================="
    log_info "Hermes-agent-cn 知识库自动更新"
    log_info "=========================================="
    
    activate_venv
    update_mempalace
    update_graphify
    generate_summary
    
    log_info "=========================================="
    log_info "更新完成！"
    log_info "=========================================="
}

# 运行
main "$@"
