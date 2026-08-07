# 分支发展规划与代码裁剪计划

> 创建日期：2025-07-16
> 基于 cn 分支（自 v0.10.0-cn.1 以来 4,616 次 commit）的分析

---

## 一、下一步发展计划

### 1. SmartRouter 增强 — P0

SmartRouter 的自动检测 + 国产 API 兼容特性是目前 cn 分支最核心的独立价值（上游没有），值得持续投入。

| 里程碑 | 内容 | 预估工作量 |
|--------|------|-----------|
| **M1** ✅ 国产 API 统一 failover | 云端健康检测、自动熔断 failover、熔断恢复探测 | 2-3 天 (✅ 已提交 ebbf35b) |
| **M2** ✅ Cost-aware routing | CN_MODEL_COSTS 数据库(21模型)、4 种成本策略(off/balanced/strict/quality) | 3-5 天 (✅ 已提交 ce19f4f) |
| **M3** ✅ quickstart 自动检测同步 | 让 SmartRouter 和 quickstart 的检测结果保持一致 | 1 天 (✅ 已提交 38122938) |
| **M4** 向上游提交 PR | 抽离路由通用设计，向上游提交 | 待定 |

### ✅ SmartRouter Phase 5（2026-06-03）

| 功能 | 内容 | 
|------|------|
| **跨 Provider 路由** | `RoutingRule` 支持 `provider` 字段，规则可指定目标 provider |
| **复杂度感知路由** | `complexity` 匹配条件（simple/medium/complex），`_match_rule` 自动判断 |
| **Vision fallback** | `auxiliary.vision` 支持 `fallback_provider/model/base_url`，主 vision 失败时自动降级 |

### ✅ Quickstart 增强（2026-06-02 修复批）

### ✅ Quickstart 增强（2026-06-02 修复批）

| 修复项 | 内容 | 
|--------|------|
| **模型检测统一** | 新建 `agent/model_detection.py`，quickstart 和 SmartRouter 共享一套分类逻辑 |
| **云端/本地主力选择** | 同时有云端 API 和本地模型时，让用户选择主力策略 |
| **云端视觉模型** | `auxiliary.vision` 优先检测云端 Provider 中的视觉模型，其次才是 Ollama |
| **配置自动整理** | `_cleanup_config()` 清理空段/容器默认值；`_cleanup_env()` 去重 |
| **Fallback 读配置模型** | fallback 链不再用硬编码默认值，改为读取用户实际配置的模型 |
| **model_routing 云端兼容** | 云端主力时规则只引用云端模型名，不引用 Ollama 本地模型，避免 400 错误 |

### ✅ 语义防火墙增强（2026-06-03）

| 里程碑 | 内容 | 状态 |
|--------|------|------|
| **M1** ✅ 规则热加载 | 不需重启 Agent，检测到防火墙规则变更后自动重载 | ✅ `795004b7e` |
| **M2** ✅ 审计日志 | 防火墙拦截/告警事件输出到文件，方便事后排查 | ✅ `241568159` |
| **M3** 向上游提交 PR | 抽出 5 层纵深防御设计，向上游提交 | 待定 |

### ✅ Quickstart 国产服务商扩展（2026-06-03）

| 里程碑 | 内容 | 状态 |
|--------|------|------|
| **M1** ✅ 百度千帆 | quickstart 集成百度千帆 API 检测 (QIANFAN_API_KEY) | ✅ `fe85dbb7a` |
| **M2** ✅ 阿里百炼 | quickstart 集成阿里百炼 API 检测 (DASHSCOPE_API_KEY) | ✅ `fe85dbb7a` |
| **M3** ✅ 火山引擎 | quickstart 集成火山引擎 API 检测 (ARK_API_KEY) | ✅ `fe85dbb7a` |
| **M4** ✅ 网络诊断 | quickstart 检测常见国产 API 端点可达性 | ✅ `fe85dbb7a` |

### ✅ Doctor 诊断扩展（2026-06-03）

| 里程碑 | 内容 | 状态 |
|--------|------|------|
| **D6** ✅ 网络连通性 | 常见国产 API 端点可访问性检测（8个端点）| ✅ `66d96d40f` |
| **D7** ✅ 配置兼容性 | yaml 与 .env 冲突检测（8个 Provider 一致性） | ✅ `66d96d40f` |
| **D8** ✅ GPU/CUDA | GPU 驱动/CUDA Toolkit/PyTorch GPU 检测 | ✅ `66d96d40f` |

### ✅ 浏览器工具兼容性修复（2026-06-03）

| 修复 | 内容 |
|------|------|
| **CN 网络检测** | `_check_chromium_download_available()` 检测国内防火墙阻断，跳过安装 |
| **中文提示** | 被墙时跳过 Chromium 下载并提示改为 Lightpanda 引擎 |

### 2. 语义防火墙增强 — P1

语义防火墙的 5 层纵深防御是另一个独立价值点（上游没有），已初步成型，值得增强。

| 里程碑 | 内容 | 预估工作量 |
|--------|------|-----------|
| **M1** 规则热加载 | 不需重启 Agent，检测到防火墙规则变更后自动重载 | 2 天 |
| **M2** 审计日志 | 防火墙拦截/告警事件输出到文件，方便事后排查 | 1 天 |
| **M3** 向上游提交 PR | 抽出 5 层纵深防御设计，向上游提交 | 待定 |

### 3. Quickstart 国产服务商扩展 — P1

扩大 quickstart 一键检测的范围，降低国内用户首次使用门槛。

| 里程碑 | 内容 | 预估工作量 |
|--------|------|-----------|
| **M1** 百度千帆一键配置 | quickstart 中集成百度千帆 API 检测 | 1 天 |
| **M2** 阿里百炼一键配置 | quickstart 中集成阿里百炼 API 检测 | 1 天 |
| **M3** 火山引擎一键配置 | 同上 | 1 天 |
| **M4** 网络诊断向导 | quickstart 中检测常见国产 API 端点可达性 | 1 天 |

### 4. Doctor 诊断扩展 — P2

扩大 doctor 诊断范围。

| 里程碑 | 内容 | 预估工作量 |
|--------|------|-----------|
| **D6** 网络连通性检测 | 常见国产 API 端点可访问性 | 1-2 天 |
| **D7** 配置兼容性检测 | yaml 与 .env 冲突检测 | 1 天 |
| **D8** GPU/CUDA 环境检测 | 本地模型运行环境检测 | 1-2 天 |

---

## 二、代码裁剪计划

### 总体策略

```
层级    策略                        文件数    预估行数
─────────────────────────────────────────────────
T1: 无条件安全删除                    16         ~2,100
T2: 轻量重构后可删（lazy import）      4         ~4,500
T3: 标记废弃不删（入侵太深）            7         ~6,000
T4: plugin 层批量清理                 22         ~2,000
─────────────────────────────────────────────────
总计                                 49        ~14,600
```

### T1: ✅ 无条件安全删除（零引用 / 死代码）

这些文件在 cn 分支中没有任何代码引用，直接删除不影响任何功能：

| 文件 | 行数 | 说明 |
|------|------|------|
| `agent/secret_sources/bitwarden.py` | ~130 | Bitwarden 密码管理，国内用不上 |
| `gateway/platforms/homeassistant.py` | ~200 | Home Assistant 智能家居网关 |
| `gateway/platforms/email.py` | ~350 | Email 消息网关 |
| `gateway/platforms/msgraph_webhook.py` | ~250 | Microsoft Graph Webhook |
| `gateway/whatsapp_identity.py` | ~150 | WhatsApp 身份验证残留 |
| `tools/neutts_synth.py` | ~50 | NEUTTS 语音合成（重写后原文件废弃） |
| `tools/neutts_synth_original.py` | ~70 | NEUTTS 语音合成原始版本 |
| `tools/microsoft_graph_auth.py` | ~245 | Microsoft Graph 认证 |
| `tools/microsoft_graph_client.py` | ~408 | Microsoft Graph 客户端 |
| `tools/osv_check.py` | ~155 | OSV 漏洞检查 |
| `tools/browser_camofox.py` | ~699 | Camofox 浏览器状态持久化 |
| `tools/browser_camofox_state.py` | ~47 | 同上 |
| `tools/binary_extensions.py` | ~50 | 二进制扩展识别 |
| `hermes_cli/azure_detect.py` | ~120 | Azure 环境检测 |
| `hermes_cli/agent_truncation.py` | ~80 | 上游专用截断逻辑 |
| **共 16 文件** | **~2,100 行** | |

**操作方法**：直接 `git rm` 即可。

### T2: ⚠️ 轻量重构后可删（需改成 lazy import + try/except）

这些文件仅在 `cli.py` 中被延迟导入（`from tools.xxx import ...` 放在函数体内），可以把导入包在 `try/except ImportError` 中，找不到就优雅降级：

| 文件 | 行数 | 被谁引用 | 重构方法 |
|------|------|----------|----------|
| `tools/tts_tool.py` | 2,369 | `cli.py` voice mode | 在 `_enable_voice_mode()` 中加 `try/except ImportError` |
| `tools/voice_mode.py` | 1,129 | `cli.py` voice mode | 同上 |
| `tools/transcription_tools.py` | 963 | `tools/voice_mode.py` | 随 voice_mode.py 级联删除 |
| `tools/homeassistant_tool.py` | 513 | `tools/browser_cdp_tool.py` | 改 browser_cdp_tool.py 为条件导入 |
| **共 4 文件** | **~4,500 行** | |

> **注意**：如果 voice mode 对中文用户有价值（语音交互场景），tts / voice / transcription 这三个文件可以保留，只删 homeassistant_tool.py。
>
> 判断标准：检查 `cli.py` 中的 `--voice` 参数是否有用户实际使用。

### T3: 🔴 标记废弃但不删（入侵太深，删除成本高）

这些文件被 5-15+ 个核心模块深度引用，删除需要在每个引用处改 import 并处理抽象类型接口。行数 / 收益比太低：

| 文件 | 行数 | 引用文件数 | 核心原因 |
|------|------|-----------|----------|
| `agent/anthropic_adapter.py` | 2,244 | ~15 | 核心适配器，被 auxiliary_client, conversation_loop, credential_pool 等深度引用 |
| `agent/bedrock_adapter.py` | 1,289 | ~6 | 同上 |
| `agent/gemini_native_adapter.py` | 971 | ~10 | 被 models_dev, curator, auxiliary_client 引用 |
| `agent/gemini_cloudcode_adapter.py` | 909 | ~8 | 同上 |
| `agent/google_oauth.py` | 1,059 | ~8 | OAuth 流程深度嵌入 |
| `agent/azure_identity_adapter.py` | 555 | ~5 | Azure 身份适配 |
| `agent/copilot_acp_client.py` | 686 | ~3 | Copilot 集成 |
| `agent/google_code_assist.py` | 452 | ~3 | Google Code Assist |
| `tools/checkpoint_manager.py` | 1,638 | cli.py, run_agent.py, agent_init.py | 检查点系统，深度嵌入启动流程 |
| `tools/process_registry.py` | 1,544 | terminal_tool.py 等 | 进程注册表 |
| `tools/computer_use/`（目录） | — | 与 anthropic_adapter 深度绑定 | 计算机使用功能 |
| **共 11 项** | **~11,000 行** | | |

**建议处理方式**：
- 在 `CHANGELOG_CN.md` 中标记为「不活跃代码（保留但不维护）」
- 在这些文件头部加注释 `# DEPRECATED: 仅为了保持 cn 分支与上游合并兼容性，不再主动维护`
- 等上游大版本重构时看能否一并处理

### T4: 🧹 Plugin 层外国 Provider / Platform 清理

外国模型提供商插件（国内用户基本用不上）：

| 目录 | 尺寸 | 说明 |
|------|------|------|
| `plugins/model-providers/anthropic/` | 8K | Anthropic |
| `plugins/model-providers/bedrock/` | 8K | AWS Bedrock |
| `plugins/model-providers/gemini/` | 8K | Google Gemini |
| `plugins/model-providers/google/` | 8K | Google |
| `plugins/model-providers/openai-codex/` | 1K | OpenAI Codex |
| `plugins/model-providers/openrouter/` | 16K | OpenRouter |
| `plugins/model-providers/nvidia/` | 5K | NVIDIA |
| `plugins/model-providers/novita/` | 8K | Novita |
| `plugins/model-providers/xai/` | 1K | xAI |
| `plugins/model-providers/arcee/` | 0 | Arcee（空目录） |
| `plugins/model-providers/huggingface/` | 5K | HuggingFace |
| `plugins/model-providers/copilot/` | 8K | GitHub Copilot |
| `plugins/model-providers/copilot-acp/` | 8K | Copilot ACP |
| `plugins/model-providers/azure-foundry/` | 5K | Azure Foundry |
| `plugins/model-providers/kilocode/` | 1K | KiloCode |
| `plugins/model-providers/nous/` | 8K | NousResearch |
| `plugins/model-providers/gmi/` | 8K | GMI |

外国消息平台插件：

| 目录 | 尺寸 | 说明 |
|------|------|------|
| `plugins/platforms/google_chat/` | 336K | Google Chat |
| `plugins/platforms/irc/` | 92K | IRC |
| `plugins/platforms/line/` | 148K | Line |
| `plugins/platforms/simplex/` | 72K | Simplex |
| `plugins/platforms/teams/` | 108K | Microsoft Teams |

**共 22 目录，~1.5MB，建议批量清理。**

> 注意：删除 plugin 目录后，需要检查 `plugins/__init__.py` 或相关加载代码中是否有硬编码引用，去除对应的注册逻辑。

---

## 三、裁剪执行顺序

```
第一刀：T1 + T4 —— 安全清理无副作用
  ↓ git commit
第二刀：T2 —— 需改 4 个导入点
  ↓ 验证编译通过 + voice mode 降级行为正确
第三刀：T3 —— 不删，只加 DEPRECATED 注释 + CHANGELOG 记录
  ↓ git commit
第四刀：运行完整测试套件
```

### 风险提示

1. **T4 删除后 plugin 配置不兼容**：用户如果以前配了 foreign provider 的 yaml 文件，删除后需要手动切换。建议在 CHANGELOG 中写清迁移说明。
2. **T2 voice mode 用户**：如果内部有用户依赖语音功能，需与他们确认后再删。
3. **T3 保留决策**：约 11,000 行代码会保留在代码库中，不占编译/运行资源，但占认知负担。这个权衡是合理的——删除成本远高于维护成本。
