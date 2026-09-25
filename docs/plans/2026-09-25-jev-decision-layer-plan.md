# Jev 决策层引入规划（NeoHorse-Jev-4B → SmartRouter 及多消费者）

> **状态**：规划完成，未动手（2026-09-25）。
> **决策类型**：defer（评估路径已定，动手令未下；upstream-decisions.md 有对应条目）。
> **依据**：三篇剪藏（TypeSafe Jev 分析 / NeoHorse-Jev-4B 发布 / OpenSquilla 路由实测）+ 仓库实检 + GGUF runtime 实检。
> **执行模式**：Linux 环境与开发环境网络隔离——本仓库是唯一交付介质（Linux 侧 `git pull` 后按 §5b runbook 执行），验证结果回传开发会话。

---

## 1. 背景

用户原设想"智能路由模型（需微调）"，与 Jev 范式（prefill-only 决策模型：收状态 + 结构化问题，返回类型化概率决策）不谋而合。

当前 SmartRouter 形态（`agent/zhineng_luyou.py`，1922 行）：
- 决策核心 = 关键词/长度启发式（`analyze_complexity`）+ `RoutingRule` 规则表 + 参数量推断估能力 + `HealthTracker` 熔断；
- 调用点 `agent/chat_completion_helpers.py`，每轮请求前 `route_with_rules()`；
- 属于"规则太死 ↔ 大模型太重"轴线的最左端，缺语义判断。

Jev 适用三条件（高频 / 选项有限 / 错了能兜住）逐条满足：每轮一次决策、`BackendHub` 探测的模型清单即天然 Choice 候选集、现有 rules/成本表/熔断即现成兜底。

## 2. 选型结论

| 候选 | 结论 | 理由 |
|---|---|---|
| TypeSafe Jev API | **reject** | 路由状态=用户消息原文打第三方 API，数据驻留/训练用途未公开（CN 用户群生死线）；远程 API 每轮 ~820ms 不可接受 |
| **NeoHorse-Jev-4B（GGUF）** | **主候选** | 官方 GGUF、Apache-2.0、ModelScope 直达、决策训练开箱即用（微调从必经之路降级为可选优化）；Q4_K_M 3.39GB 三项均值 83.77% 反超 BF16 |
| 基元律动 0.95M 路由器 | **watch item** | MS 无权重，已向官方核实（答复未回）；不影响架构，只影响 `decision_backend` 指向 |
| SemIf / daseinlabs open-jev | 范式参照 | 证明范式一周即可被消费级硬件复现——不抢跑、锁定风险低 |

**微调路线不被替代，被重新定位**：Jev 类 = 现在就拿到语义路由并积累 trace；自研小路由器（0.95M 级）= trace 积累后的长期终点。可抄配方：基元律动的"虚拟环境构造任务 + 三模型独立判断取中位数标注 + 一致性加权"。

## 3. 架构决策（已拍板）

1. **独立 System-1 决策服务 + 多消费者**，不是"升级 SmartRouter"——SmartRouter 只是 consumer #1。各消费者状态构造/阈值/兜底政策不同，共享的只有端点，不是模块。
2. **决策逻辑在 hermes 侧**：路由状态（tier 语境、调用方身份、HealthTracker、`RouteResult.reason` 审计）在 hermes 进程内；guardrail 与决策同进程。
3. **hermes 自己拿选定模型调 AIMC**；Jev 不进 AIMC 请求路径；**AIMC 保持透明网关不动**（已服务多客户端：hermes/zcode/dsh/RAG/db-center，语义改写对所有客户端是 breaking change）。决策服务不需要能访问 AIMC。
4. 决策服务无状态 → dsh/RAG 等项目可 opt-in 直连端点（能力集中、行为不劫持）。

**红线（不做清单）**：
- ❌ per-turn 工具 schema 过滤——toolset 必须 conversation 全程稳定（prompt cache 神圣性）；
- ❌ 主模型绕行（部分轮次跳过大模型）——deferred，strict alternation + cache 风险，等 #1/#2 消费者跑稳后另议。

## 4. 部署拓扑

```
WSL ───────── hermes           SmartRouter 每轮调决策服务（fail-open 回规则层）
            ├─ 决策服务(:8001)  NeoHorse-Jev-4B Q4_K_M + 随包 GGUF runtime + 薄 HTTP 包装（单实例加锁）——与 hermes 同机，localhost 直连
            └─ 拿选定模型调 AIMC
Windows ───── Ollama(:11434)   补全模型（minicpm5 等），现状不动；不跑决策服务（见下）
aliy-hy ───── AIMC(隧道:8080)  云端模型透明网关，多客户端，不动
```

**部署环境定案（2026-09-25 更新）**：决策服务落**本机 WSL**（与 hermes 同机，CUDA 经 Windows 驱动旁路直通：`/dev/dxg` + `/usr/lib/wsl/lib/libcuda.so`；驱动留 Windows 侧，toolkit 装 WSL 内）。原隔离内网 Linux 机方案搁置（取件/回传循环成本高），保留为备选。

**为什么 Windows 环境不跑决策服务**：`build.py` 是纯 Linux 构建流程（g++/`.so`/nvcc 路径硬编码），原生 Windows 需要整套移植，不值得——决策服务集中一个端点，Windows 侧 fail-open 已覆盖 Linux 环境宕机场景。**零改动路径 = Linux 环境。** 若未来真需要本地冗余，正确的跨平台姿势是**在 WSL 内跑同一套 Linux 构建**（CUDA 直通或纯 CPU），而不是做原生 Windows 移植。

**为什么 Ollama 跑不了**：统一 GGUF 的决策头在独立 tensor 命名空间（Ollama loader 不读）；prefill-only 概率读出是随包 Python 决策接口的能力，Ollama API 面给不了 Choice/Noul/Score 概率（logprobs 支持长期不全）。没有概率就没有置信度，guardrail 阈值否决失效。

## 5. runtime 落地要点（2026-09-25 实检 `E:\LLMs\NeoHorse-Jev`）

- **权重**：换用 **Q4_K_M**（83.77%，官方推荐档；当前下载的 Q3_K_M 建议替换）。
- **pin**：llama.cpp commit `9425611`（**2026-09-23**，极新）→ 近两年各代 GPU 架构均已覆盖，兼容性无忧；前置条件 CUDA toolkit ≥12.8（build.py 查 `/usr/local/cuda/bin/nvcc`）。
- **build.py 流程**（全自动）：clone llama.cpp → checkout pin → 打 unified-tensor 补丁（跳过 `v.*/mm.*/neohorse.pointer.*` tensor）→ 编译 mtmd + `libnh_vision.so`/`libnh_hidden.so` 两桥。**纯 Linux 流程**。
- **接口**（example.py 已确认）：
  ```python
  model = NeoHorseGGUF(gguf_path)
  result = model.predict({'state': '<≤384 tokens>',
                          'questions': {'q1': {'type': 'choice|noul|score',
                                               'instructions': ..., 'criteria': {...}}}})
  model.close()   # 返回 JSON 可序列化的概率分布
  ```
- **限制**：文本 state ≤ **384 tokens**（单问题 packed branch 1k / 总输入 2k）→ 状态压缩策略是设计前提；单实例一次一调用（多问题逐个处理）→ HTTP 包装需加锁串行，每轮一次 predict 多问题正好匹配。
- **别用 vanilla llama-cli/llama-server 冒烟**：未打补丁的 loader 会在统一 GGUF 的重复 tensor 名上 abort；`E:\llama.cpp`（b9437 Windows 版）runtime 用不上。
- 依赖：`requirements.txt` = torch 2.8.0（选 cu128/cu130 wheel）/ transformers 5.17 / numpy / pydantic / Pillow。

### 5b. Linux 环境验证 runbook（✅ 已于本机 WSL 完成全链路验证，见 §5c；隔离内网 Linux 机路径保留为备选）

Linux 机器在隔离内网，开发侧无法直连。执行方式：提交本仓库至 origin/cn → Linux 侧 `git pull` → 按以下步骤执行 → 结果（一致率 / 延迟 / 概率分布样本）回传开发会话。

```bash
# ① 前置检查
nvcc --version                 # CUDA toolkit ≥ 12.8（build.py 硬编码查 /usr/local/cuda/bin/nvcc）
g++ --version && cmake --version && git --version
python3 --version              # 3.12 推荐（与官方已测环境一致）

# ② 取件（二选一）
#   在线：git clone https://github.com/TokenRhythm/NeoHorse.git
#         + ModelScope 下载 NeoHorse-Jev-4B-Q4_K_M.gguf（~3.39GB）
#   离线（内网推荐）：从 Windows 拷贝 runtime/ 目录 + Q4_K_M GGUF
#     （注意：Windows 已有的是 Q3_K_M，取件前先在 Windows 补下 Q4_K_M）

# ③ Python 环境
python3 -m venv ~/neohorse/.venv && source ~/neohorse/.venv/bin/activate
pip install -r ~/neohorse/runtime/requirements.txt
# 若启动报 GPU 架构不支持，改装 cu128 wheel：
#   pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cu128

# ④ 构建（自动：clone llama.cpp → checkout pin → 打补丁 → 编译 mtmd + 两桥）
cd ~/neohorse/runtime && python build.py

# ⑤ 冒烟（自带 refund 判例，应输出 JSON 概率分布）
python example.py --model ~/neohorse/NeoHorse-Jev-4B-Q4_K_M.gguf

# ⑥ 服务化（本仓库自带参考实现，stdlib-only，单实例锁串行）
python scripts/neohorse_decision_server.py \
  --model ~/neohorse/NeoHorse-Jev-4B-Q4_K_M.gguf \
  --runtime-dir ~/neohorse/runtime --port 8001
curl -s http://127.0.0.1:8001/health        # {"ok": true, ...}

# ⑦ 20 条验证（Step 1 门检数据）
#    WSL 侧导 20 条历史 turn（state + 当时启发式决策 + tier 真值）为 JSON，拷入 Linux：
curl -s http://127.0.0.1:8001/predict -d @turn_001.json
#    逐条比对 tier 建议与真值；记录一致率、置信度分布、延迟 → 回传
```

**跨平台结论**：验证效果好也**不做原生 Windows 版**。理由：① 决策服务按架构就是集中单端点多消费者，Windows 侧再造一个是重复部署；② fail-open 已覆盖可用性；③ 原生移植（编译器/库格式/flags 全套重写 + 长期维护分叉）成本与收益不成比例。真需要本地冗余时走 **WSL 内同一套 Linux 构建**（零移植成本），该结论随本规划归档，重估条件见 §10。

### 5c. WSL 全链路验证结果（2026-09-25 实测）

| 项 | 结果 |
|---|---|
| 构建 | ✅ `build.py` 一次通过（patch + mtmd + `libnh_hidden.so`/`libnh_vision.so`），CUDA toolkit 12.8 + sm_120（Windows 驱动旁路直通） |
| 权重 | Q4_K_M 3.2G；CUDA 计算缓冲 ~1988 MiB，4060 8GB 容纳无压力 |
| example.py 冒烟 | ✅ refund 判例 → `probabilities {false: 0.996, true: 0.004}`，正确且置信度分离清晰 |
| 热态决策延迟（10 发） | **mean 91.0ms / p95 115.9ms** —— Step 1 门检（<500ms）大幅通过 |
| 服务化 | ✅ `scripts/neohorse_decision_server.py`：`/health` 200；POST `/predict`（Choice 型）端到端 **113ms** |
| Choice 决策正确性 | 路由形态冒烟题（"修一行 typo"三档候选）→ `local`（0.927 / confidence 0.890），判断正确 |

环境备注：WSL 侧 Python 依赖经清华镜像安装（PyPI 直连会断流卡死）；模型权重可经 `/mnt/e` 直读（首次加载 ~16s，热态推理不受影响）；`wsl.exe -e` 会话退出会带走普通后台子进程，常驻服务需 `setsid nohup ... & disown`。

**下一步（Step 0/1 续）**：从 WSL 侧 session store 导 20 条历史 turn（state + 当时启发式决策 + tier 真值）打 `/predict`，验证真实分布下的一致率与置信度可用性 → 进影子模式。

## 6. 分步计划（每步带准入门检，建议值可调）

**Step 0 —— 回放集（纯离线，不花钱不碰架构）**
- 从 session store 导出历史 turn + 当时 `RouteResult.reason` 的实际决策；标 tier 真值，几百条起步。
- 双重价值：NeoHorse-Jev 的考卷 + 未来自研小路由器的种子训练集（投入不白费）。
- 同时设计 state 压缩策略（384-token 上限逼出来的）。

**Step 1 —— Linux 环境部署 + 概率验证**
- 按 §5b runbook 执行：取件 → 前置检查 → 构建 → 冒烟 → 服务化 → 20 条验证。
- 验证目标：概率/置信度信号可用且能区分对错（整条 guardrail 链的命门）。
- **门检（→Step 2）**：决策服务延迟 p95 可接受（建议 <500ms）且 20 条验证一致率不低于现有启发式。

#### Step 0/1 回放结果（2026-09-25，18 条真实 turn）

样本：近 21 天去重后全部真实 cli 用户 turn（目标 20，库存 18）；`scripts/neohorse_replay_eval.py` 执行，JSON 留档 WSL 本地（含对话原文，不入库）。**关键事实：现役启发式基线=恒 tier:strong**（`model_routing.rules` 两条规则全落 strong），故评测对"建议真值"评准确率，并按 guardrail 形态统计降档空间。

| 指标 | 结果 |
|---|---|
| 直接准确率（对建议真值） | 严格 10/18（56%），宽松 12/18（67%） |
| **conf ≥ 0.5 的 7 条** | **7/7 全对**（local×4 / balanced×2 / strong×1） |
| conf < 0.5 的 11 条 | 严格仅 3/9 对——错误集中在低置信区，校准有效性直接成立 |
| **guardrail 形态（conf≥0.5 放行，其余回落恒 strong）** | **0 质量损失 + 放行集 6/7（86%）降档**（4→local、2→balanced） |
| 延迟 | 中位 ~150ms；长 state 尾部 526-607ms（p95 边缘超 500ms 门检，主因首跑/长文本） |
| WYSIATI 活案例 | 1205 字符创作任务截断至 300 字符 → 误判 balanced（conf 0.225 被阈值兜住）——state 压缩需保任务类型信号，且即便压坏阈值兜底仍有效 |

**判定：Step 1 门检通过**（fail-open + 阈值放行设计下零质量风险，放行集 86% 降档 = 真实省钱空间；对照 AppWorld 第三方实测 -52% 成本的方向一致）。**准入 Step 2 影子模式**：`chat_completion_helpers` 并行记录不生效，跑 ≥2 周真实流量，重点观察阈值曲线（0.4/0.5/0.6）与降档轮次的下游任务完成质量。

**Step 2 —— 影子模式**
- 接入 `chat_completion_helpers`：决策服务与现役规则并行跑，只记日志不生效。
- **门检（→Step 3）**：影子期（建议 ≥2 周）tier 一致率 ≥ 现有启发式基线，过度路由（选高档做低档任务）比例可控。

**Step 3 —— 生效 + 规则降级 guardrail**
- 决策服务给建议；规则层保留否决权（置信度 < 阈值回落启发式）；HealthTracker/成本表不动。
- **fail-open**：决策端点不可达 → 静默回现有规则，不阻塞启动、不阻塞请求（与 AIMC 的 fail-fast 拒启语义相反，门检别套 AIMC 模板）。
- 落位：`smart_model_routing` 配置内实现替换（Footprint Ladder 第 1 档，零新 schema）；`decision_backend` 条目 + BackendHub 候选池排除决策模型。

## 7. 消费者路线图（决策层的长大方式）

| 序 | 消费者 | 三条件 | 状态 |
|---|---|---|---|
| #1 | 模型/tier 路由 | 满足（最高频、审计最全） | 本规划 |
| #2 | web/搜索结果相关性 + 注入筛查 | 满足（只过滤/重排，可离线回放评测；文章自有示例场景） | #1 稳后 |
| #3 | 门槛类 Noul：memory prefetch 门槛、本轮是否需要 vision | 满足（低风险） | #2 稳后 |
| 远期 | delegation 时机、压缩时机 | 错误代价高 | 等 trace 积累 |
| 不做 | per-turn 工具 schema 过滤 / 主模型绕行 | 违反 cache/alternation 不变量 | 红线，见 §3 |

攒够 3 个消费者后再抽公共薄客户端（`agent/decision_client.py` 之类）——系统从下往上长，不预建框架。

## 8. 风险与缓解

- **WYSIATI**：状态缺信号不报低置信度，照样给 0.91。缓解：状态构造保信号密度；枚举类信号（"全部/所有"）保留在状态里——现有关键词层这部分恰恰要活下来；每消费者自带阈值否决。
- **失败模式已知**：AppWorld 实测中 Jev 输在"过度路由到更强模型且更强模型照样失败"（漏枚举类任务）。影子模式监控指标必须含过度路由率。
- **供应商数字不可信**：TypeSafe 评测参考答案是模型生成非人工标注；NeoHorse 六组评测自报。只认自建回放数据。
- **单实例串行**：每轮一次 predict 够用；多消费者并发后再切 vLLM + safetensors（Linux 环境 GPU 显存充裕）。

## 9. 信息缺口

- 基元律动 0.95M 路由器权重是否开放（官方核实中）——不影响架构与拓扑。
- state ≤384 tokens 的压缩策略具体设计（Step 0 时一并做）。
- NeoHorse-Jev 置信度语义需自测校准（官方未公开计算方式）。

## 10. Revisit / 退出条件

- **触发重估**：NeoHorse 大版本变更 / 0.95M 权重开源 / 影子期数据异常。
- **方向退出**：Step 1 回放一致率显著低于现有启发式、且 Q4_K_M 与 0.95M（若开源）两代候选皆如此 → 整个方向 reject，本文档归档。
- **AIMC 侧重估**：仅当出现"多客户端都主动要求网关级路由"的真实需求时，重启网关侧方案讨论（当前所有已知客户端政策在客户端侧）。
