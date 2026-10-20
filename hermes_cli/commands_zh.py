"""CN: Simplified-Chinese overlay for the slash-command registry.

The upstream registry (``hermes_cli/commands.py``) keeps command
descriptions as plain English strings and localizes only the category
labels through the i18n catalog. CN's users read Chinese, so the
descriptions and argument hints live here instead of being patched into
the upstream file — which keeps ``commands.py`` clean for the next base
bump (the file is upstream's, unmodified).

Applied at import time by ``hermes_cli/commands.py``:

    COMMAND_REGISTRY = apply_zh_overlay(COMMAND_REGISTRY)

Mapping: command name -> (中文描述, 参数提示). The category identifier
stays English on purpose: upstream renders it through
``category_label`` -> ``t("slash.category.<slug>")``, so the Chinese
category label comes from the bundled ``locales/zh.yaml`` catalog.
"""

from __future__ import annotations

from typing import Dict, Tuple

# command name -> (description, args_hint)
ZH_COMMAND_TEXT: Dict[str, Tuple[str, str]] = {
    "history": ("显示对话历史", ""),
    "save": ("保存当前对话", ""),
    "retry": ("重试上一条消息（重新发送给 AI）", ""),
    "undo": ("删除最后一轮用户/AI 交换", ""),
    "title": ("设置当前会话标题", "[名称]"),
    "branch": ("创建分支会话（探索不同路径）", "[名称]"),
    "compress": ("手动压缩对话上下文", "[聚焦主题]"),
    "rollback": ("列出或恢复文件系统检查点", "[编号]"),
    "snapshot": ("创建或恢复 Hermes 配置/状态快照", "[create|restore <id>|prune]"),
    "stop": ("终止所有运行中的后台进程", ""),
    "approve": ("批准待处理危险命令", "[session|always]"),
    "deny": ("拒绝待处理危险命令", ""),
    "bg": ("在后台运行提示词", "<提示词>"),
    "btw": ("利用当前上下文临时提问（不使用工具，不保存）", "<问题>"),
    "queue": ("将提示词加入队列（不会打断当前对话）", "<提示词>"),
    "status": ("显示会话信息", ""),
    "egress": ("显示 Docker egress proxy 状态", "[状态]"),
    "profile": ("显示当前配置名称和主目录", ""),
    "sethome": ("将此聊天设为主频道", ""),
    "resume": ("恢复之前命名的会话", "[名称]"),
    "config": ("显示当前配置", ""),
    "model": ("查看当前模型（启动时绑定，会话中不可切换）", ""),
    "personality": ("设置预定义人格", "[名称]"),
    "statusbar": ("切换上下文/模型状态栏", ""),
    "verbose": ("循环切换工具输出详细程度：off -> new -> all -> verbose", ""),
    "yolo": ("切换 YOLO 模式（跳过所有危险命令确认）", ""),
    "reasoning": ("管理推理强度和显示", "[级别|show|hide]"),
    "fast": ("切换极速模式 — OpenAI 优先处理 / Anthropic 快速模式", "[normal|fast|status]"),
    "skin": ("显示或切换界面主题/皮肤", "[名称]"),
    "voice": ("切换语音模式", "[on|off|tts|status]"),
    "tools": ("管理工具： /tools [list|disable|enable] [名称...]", "[list|disable|enable] [名称...]"),
    "toolsets": ("列出可用工具集", ""),
    "skills": ("搜索、安装、查看或管理技能", ""),
    "bundles": ("列出已安装的技能包（用 /<名称> 调用整个包）", ""),
    "cron": ("管理定时任务", "[子命令]"),
    "reload": ("重新加载 .env 变量到当前会话", ""),
    "browser": ("将浏览器工具连接到你的 Chrome（CDP）", "[connect|disconnect|status]"),
    "plugins": ("列出已安装插件及其状态", ""),
    "commands": ("浏览所有命令和技能（分页）", "[页码]"),
    "help": ("显示可用命令", ""),
    "restart": ("在现有任务结束后优雅重启网关", ""),
    "usage": ("显示当前会话的 Token 用量和速率限制", ""),
    "insights": ("显示用量洞察和分析", "[天数]"),
    "platforms": ("显示网关/消息平台状态", ""),
    "paste": ("检查剪贴板中的图片并附加到输入", ""),
    "image": ("附加本地图片文件到下一条输入", "<路径>"),
    "update": ("更新 Hermes Agent 至最新版本", ""),
    "version": ("显示 Hermes Agent 版本", ""),
    "debug": ("上传调试报告（系统信息 + 日志）并获取分享链接", ""),
    "quit": ("退出 CLI", ""),
    # ── 上游 0.21/0.22 新增命令（CN 旧版无对应，中文补齐 2026-10-20）──────
    "start": ("确认平台启动 ping（不回复消息）", ""),
    "new": ("开启新会话（新会话 ID + 全新历史）", "[名称]"),
    "topic": ("启用/查看 Telegram 私聊话题会话", "[off|help|session-id]"),
    "clear": ("清屏并开启新会话", ""),
    "redraw": ("强制重绘界面（终端错位时恢复）", ""),
    "prompt": ("在 $EDITOR 里编辑下一条提示词（markdown）后发送", "[初始文本]"),
    "handoff": ("把当前会话移交给消息平台（Telegram、Discord 等）", "<平台>"),
    "worktree": ("查看/列出/创建/清理隔离的 git worktree", "[new [名称]|list|prune [--dry-run]]"),
    "export": ("导出配置档案（配置、技能、主题）为可分享压缩包", "[档案] [-o output.tar.gz]"),
    "import": ("导入分享的配置档案包为一个新配置档案", "<archive.tar.gz> [--name <名称>]"),
    "discard": ("丢弃 Hermes 重启时丢失的一轮，让本会话队列重新执行", ""),
    "pause": ("全局暂停新工作（紧急停止）；'/pause off' 恢复", "[原因 | off]"),
    "agents": ("查看活跃 agent 与运行中的任务", ""),
    "journey": ("打开学习旅程时间线", "[list|delete <id>|edit <id>]"),
    "steer": ("在下次工具调用后注入一条消息（不打断当前回合）", "<提示词>"),
    "goal": ("设定 Hermes 跨回合持续推进的目标",
             "[文本 | -- <文本> | draft <文本> | show | gate add <命令> | pause | resume | clear | status | wait <pid> | unwait]"),
    "heartbeat": ("设置周期性提示，空闲时重新进入本会话",
                  "[every <间隔> <提示词> | status | pause | resume | clear]"),
    "refine": ("立即复盘当前对话，把经验沉淀到 memory/skills", "[聚焦说明]"),
    "review": ("派出独立子 agent 复审刚讨论过的工作（PR、代码、文档）", "[复审说明]"),
    "loop": ("在本会话按固定间隔重复执行一条提示",
             "[间隔] <提示词> [--times N] [--until <条件>] | status | pause | resume | stop"),
    "plan": ("写一份 markdown 实施计划到 .hermes/plans/（不执行）", "[任务]"),
    "moa": ("用默认 Mixture of Agents 预设跑一条提示，之后恢复原模型", "<提示词>"),
    "subgoal": ("为当前目标增删附加达成条件", "[文本 | remove N | clear]"),
    "context": ("显示详细的上下文窗口视图（用量、分类占比、压缩统计、吞吐）", "[all]"),
    "whoami": ("查看当前斜杠命令权限（管理员 / 普通用户）", ""),
    "sessions": ("浏览并恢复历史会话", ""),
    "codex-runtime": ("切换 OpenAI/Codex 模型的 codex app-server 运行时", "[auto|codex_app_server]"),
    "battery": ("开关状态栏上的颜色电量指示", "[on|off|status]"),
    "timestamps": ("开关消息与 /history 上的 [HH:MM] 时间戳", "[on|off|status]"),
    "diff": ("显示工作区的 git 变更", "[staged|all|session] [--stat] [路径...]"),
    "focus": ("开关专注视图——只显示你的提示与最终回复", "[on|off|status]"),
    "footer": ("开关最终回复底部的网关运行时元信息", "[on|off|status]"),
    "approvals": ("查看或设置危险命令的常驻审批模式", "[manual|smart|off]"),
    "indicator": ("选择 TUI 忙碌指示器样式", ""),
    "wake": ("开关 'Hey Hermes' 唤醒词监听", "[on|off|status]"),
    "busy": ("设置 Hermes 忙碌时消息的处理方式", "[queue|steer|interrupt|status]"),
    "autoprune": ("开关旧会话自动清理", "[on|off|later|status]"),
    "memory": ("查看待写入的记忆 / 开关审批闸", "[pending|approve|reject|approval] [id|on|off]"),
    "pet": ("开关或领养 petdex 吉祥物（/pet、/pet list、/pet <slug>）", "[toggle|list|scale <n>|<slug>]"),
    "hatch": ("按描述生成一只 petdex 宠物", "[描述]"),
    "learn": ("从你描述的任意内容学习可复用技能（目录、URL、本对话、笔记）", "<要学习的内容>"),
    "init": ("扫描仓库生成或更新 AGENTS.md 项目说明", "[备注]"),
    "suggestions": ("审阅推荐的自动化建议（接受/忽略）", "[accept|dismiss N | catalog]"),
    "blueprint": ("用蓝图模板搭建一个自动化", "[名称] [槽位=值 ...]"),
    "curator": ("后台技能维护（状态、运行、置顶、归档、查看已归档）", "[子命令]"),
    "kanban": ("多 profile 协作看板（任务、关联、评论）", "[子命令]"),
    "reload-mcp": ("从配置重新加载 MCP 服务器", ""),
    "reload-skills": ("重新扫描 ~/.hermes/skills/ 下的新增/移除技能", ""),
    "palette": ("打开模糊命令面板（也可 Ctrl+P）", ""),
    "subscription": ("查看 Nous 订阅并在浏览器中变更", ""),
    "login": ("登录 Nous 账号（保留已连接的账号）", ""),
    "topup": ("查看 Nous 余额并在门户中充值", ""),
    "platform": ("暂停/恢复/列出故障的网关平台", "<pause|resume|list> [名称]"),
    "copy": ("复制上一条助手回复到剪贴板", "[编号]"),
}
