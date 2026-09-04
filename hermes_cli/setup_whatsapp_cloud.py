"""
WhatsApp Cloud API setup wizard — CN 减法 stub.

Sprint 16 档 A.1 (跟 8-12 P3 拍 A "Cat 1 减法" 1:1 配对):
- WhatsApp Cloud API (海外平台) 不在 CN 路线, 改 stub
- 推荐 CN 替代: feishu (飞书) / dingtalk (钉钉) / wecom (企业微信)
- 整个 wizard (495 行) 替换为 stub entry point
- Sprint 16 档 A.2 跟 11 个海外平台文件一起 `git rm`

原 wizard 由 6 步 walkthrough + 12 个 validator 函数组成 (495 行), 详见 git history
(commit `<sprint16-a1-stub>` revert 时找回). Sprint 16 档 A.1 收尾时这个 stub
跟 `cmd_whatsapp_cloud` stub 1:1 配对 (见 hermes_cli/main.py).
"""

from __future__ import annotations


def run_whatsapp_cloud_setup() -> int:
    """Sprint 16 档 A.1 CN 减法 stub.

    Returns 0 保持原有 entry point 协议 (main.py 不需改 import path).
    """
    print()
    print("⚠  WhatsApp Business Cloud API 不在 CN 分支支持范围")
    print("=" * 55)
    print()
    print("CN 减法决策: 跟 8-12 P3 拍 A 'Cat 1 减法' 1:1 配对,")
    print("上游 WhatsApp Cloud API 适配器在 CN 端已停用。")
    print()
    print("推荐 CN 替代平台 (国内官方 API 渠道):")
    print("  • 飞书 (Feishu) Open API    - 跨平台 bot + 审批 + 多维表格")
    print("  • 钉钉 (DingTalk) Open API  - 企业内 bot + 工作通知")
    print("  • 企业微信 (WeCom) API      - 内部协作 + 客户消息")
    print("  • 微信 (Weixin) iLink Bot   - 客服 + C 端用户")
    print()
    print("详情: docs/cn-divergences.md (Cat 1 减法) + cross-pollination/2026-09-03-sprint16-implementation-plan.md")
    print()
    return 0
