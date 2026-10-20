# Hermes Agent - Development Guide

For AI coding assistants and developers working on hermes-agent. This root file is a hub: what
applies everywhere, then a routing table. Each area's `AGENTS.md` loads automatically when you work
in that directory; read it before editing there. `python scripts/check` caps this file at 12k chars
and every root-to-area chain at 30k, so it loads whole on 128k+ models: long form goes in the guide.

**Never give up on the right solution.**

## What Hermes Is

Hermes is a personal AI agent that runs the same agent core across a CLI, a messaging
gateway (Telegram, Discord, Slack, ~20 platforms), a TUI, and an Electron desktop app. It
learns across sessions (memory + skills), delegates to subagents, runs scheduled jobs, and
drives a real terminal and browser. It is extended primarily through **plugins and skills**,
not by growing the core.

Two invariants shape almost every design decision and are the lens for reviewing any change:

- **Per-conversation prompt caching is sacred.** Mutating past context, swapping toolsets,
  reloading memories or rebuilding the system prompt mid-conversation breaks the cached prefix and
  multiplies the user's cost; the ONE exception is context compression. Slash commands that change
  system-prompt state defer to the next session, with an opt-in `--now` (`/skills install --now`).
- **The core is a narrow waist; capability lives at the edges.** Every model tool is sent on
  every API call, so the bar for a new *core* tool is high. New capability should arrive as a
  CLI command + skill, a service-gated tool, or a plugin — not as core surface.

## CN Fork Strategy

> hermes-agent-cn 是 upstream hermes-agent 的 CN 本地化分支。
> 哲学："本地化 + 做减法"——边界清晰 > 功能完备，差异放 CN 端 > 污染 upstream。

### 同步上游的核心原则（2026-06-11 立）

1. **被裁剪的不合** —— 上游裁掉的（外国 platform / provider）我们也不合
2. **应裁剪的不合** —— 上游没裁但按 CN 设计思想未来要裁的，也不合
3. **真需要才合** —— 只有 (a) 修复 cn 分支已存在代码的 bug，(b) cn 分支需要的新功能

### 减法哲学（4 元原则，演绎自同步原则）

1. **用户群决定代码边界** —— 服务什么用户就保留什么代码
2. **基础设施决定架构选择** —— 物理可达性先于功能完备性
3. **可维护性比功能完备更重要** —— 拒绝是工程化动作不是态度
4. **收敛边界，加速迭代** —— 边界固定后差异化才能跑起来

### 工程化操作清单

5. **Selective absorption** —— upstream 出新功能 ≠ 全盘接受
   每次评估 4 选 1：adopt / reimplement / reject / defer
   记录在 `docs/upstream-decisions.md`
6. **Borrow approach, not copy** —— 直接 merge 冲突大时借鉴思路自己重写
7. **0 改 upstream 是策略不是禁令** —— 能少改就少改，但真要改允许
8. **每次偏离 upstream 都记录** —— what / why / when-to-delete 必填
9. **Verify before adopt** —— upstream 新功能先隔离 branch 试
10. **Sprint 收尾必 verify** —— 0 regression + .env 保护 + push + tag + cron（如适用）
11. **跨 project 教训落 mavis agent memory** —— 不散在项目里

### 配套文档（项目级，权威）

- `docs/upstream-decisions.md` —— upstream 评估决策滚动 log
- `docs/cn-divergences.md` —— CN 端差异类别 audit

### 配套工作文档（开发期，notes dir，**不进版本控制**）

- `~/projects/hermes-agent-cn-notes/UPSTREAM_CLASSIFICATION_REPORT.md` —— 2026-06-11 2125 commit 分类原始数据
- `~/projects/hermes-agent-cn-notes/merge-plan-v*/` —— 各版本合入计划
- `~/projects/hermes-agent-cn-notes/POSTMORTEM_*.md` —— postmortem
- `~/projects/hermes-agent-cn-notes/ROADMAP.md` / `freeze/` / `research/` —— 阶段文档
- `~/projects/hermes-agent-cn-notes/cross-pollination/` —— sprint retrospect / candidate pool / sparks

任何时候觉得某份 working doc 应该"沉淀"成项目级 doc，promote 到 `docs/`。

## Contribution Rubric — What We Want / What We Don't
## Contribution rubric

The project's intent layer, for contributors and for the triage sweeper (which may only close on
`implemented_on_main`, `cannot_reproduce` or `incoherent`; taste-based closes are a maintainer's
call, and when in doubt a PR stays open). Long form with examples:
`website/docs/developer-guide/contributing.md` § Contribution rubric.

**Wanted:** real bug fixes (repro on `main`, the exact line, the whole class incl. sibling paths);
reach at the edges (adapters, providers, models, UI features) wired into the existing setup UX;
god-file → module refactors; extending before duplicating (3+ PRs in one category → an ABC +
orchestrator); behaviour-contract tests; E2E with real imports against a temp `HERMES_HOME` for
resolution, config, security and I/O changes; salvage by cherry-pick so authorship survives.

**Rejected even when well-built:** hooks with no concrete consumer; new `HERMES_*` env vars for
non-secret config (`.env` is secrets only, behaviour goes in `config.yaml`); a new core tool when
terminal + file or a skill already does the job; `offset`/`limit` pagination on instructional tools;
"fixes" that destroy the feature they secure; outbound telemetry without an opt-in gate;
change-detector tests; plugins that touch core files; third-party products in the core tree (ship a
standalone plugin repo).

**Before you call it a bug,** verify the claim AND the intent (`git log -p -S "<symbol>"`): the
isolation is often the design (profiles are islands on purpose), an absence can be load-bearing,
and a fix that cannot point to the line where the bug manifests has an unverified premise.

**Security:** `SECURITY.md` is the scope authority. A §3.1 finding goes private (GitHub Security
Advisories or security@nousresearch.com), never into a public issue, PR, commit or comment; §3.2
hardening is ordinary public work. Name the §2 boundary crossed, with a repro on `main`.

**Footprint ladder** (take the highest rung that solves it): extend existing code → CLI command +
skill → service-gated tool (`check_fn` answers reachability/opt-in, never per-session surface:
`tools/AGENTS.md`) → plugin → MCP server in the catalog → new core tool (fundamental, broadly useful,
unreachable otherwise).

## Development Environment

`source ./activate` (fish: `activate.fish`, PowerShell: `activate.ps1`) provisions and activates the
PM environment; pick an isolated `HERMES_HOME`/`HERMES_RUNTIME_DIR` first
(`website/docs/reference/package-management.md#developer-workflow`). Tests need the separate test
environment in `CONTRIBUTING.md`. **`python scripts/check`** runs every blocking lint check CI
runs, with CI's pinned tools; `--install-hook pre-push` runs it on every push (re-run after
pulling to refresh the hook). `# noqa` does not waive a ratchet finding:
`# health: allow <RULE> -- <why>` does.

## Project Structure

Counts shift constantly; the filesystem is canonical. Load-bearing entry points:

```
hermes-agent/
├── run_agent.py          # AIAgent facade; the turn loop lives in agent/turn_*.py
├── model_tools.py        # Tool orchestration, discover_builtin_tools(), handle_function_call()
├── toolsets.py           # TOOLSETS dict, _HERMES_CORE_TOOLS
├── cli.py                # HermesCLI (REPL, slash dispatch) + hermes_cli/cli_*_mixin.py
├── hermes_state.py       # SessionDB facade; hermes_state_*.py siblings
├── hermes_constants.py   # get_hermes_home(), display_hermes_home() — profile-aware paths
├── agent/                # turn loop phases, providers, memory, compression, prompt builder
├── hermes_cli/           # CLI subcommands, setup, config, plugins loader, updater, web_routers/
├── tools/                # Tool implementations (tools/registry.py) + environments/ backends
├── gateway/              # run.py facade + run_*.py phases + session*.py + platforms/
├── plugins/              # memory/, context_engine/, model-providers/, kanban/, image_gen/, ...
├── skills/               # Built-in skills (by category)   optional-skills/: shipped, not active
├── ui-tui/, tui_gateway/ # Ink terminal UI + its Python JSON-RPC backend (also serves Desktop)
├── apps/desktop/         # Electron desktop app (+ apps/shared)   web/: dashboard SPA
├── cron/                 # jobs.py + scheduler.py (+ scheduler_*.py)
├── pm/, hermes_platform/ # dependency/environment manager; machine facts + executable lookup
├── scripts/              # check, run_tests.sh, code_health/, ci/
├── website/              # Docusaurus docs (developer-guide/ holds the long-form area docs)
└── tests/                # Pytest suite, mirrors the source tree
```

**User state:** `~/.hermes/config.yaml` (settings), `.env` (secrets only), `logs/` (`hermes logs`);
all profile-aware via `get_hermes_home()`.

### Facade + siblings layout

Every former god file is a **facade** (public entry points + the names other packages import) plus
**siblings** `<stem>_<topic>.py`, each owning one topic (`hermes_state.py`, `gateway/run.py`,
`tools/mcp_tool.py`, `hermes_cli/kanban.py`, `hermes_cli/web_server.py`, `cli.py` →
`hermes_cli/cli_*_mixin.py`, `run_agent.py` → `agent/turn_*.py`).

- **Find code by topic:** `grep -rn "def name" <dir>/<stem>_*.py`, not by reading the facade.
- **Siblings late-import the facade** inside functions; never a module-level cycle.
- **Patch where production reads:** a sibling doing `from <facade> import name` inside the function
  makes the facade the seam; a patch on the defining module passes silently.
- **Size and complexity are ratcheted per unit** (`scripts/code_health/config.py`): new functions
  CC ≤ 20, ≤ 300 lines, nesting ≤ 6; files ≤ 2,000 lines; units already over may only go down (move
  a function into a sibling to offset growth, or put new tests in a new test file). Behaviour goes
  in a sibling, never a facade; name ladders become a dict → handler.
- **No re-export shims for internal moves;** internal paths are not API. Moving a symbol means
  fixing its docs in the same PR (grep `website/docs`, `skills/`, every `AGENTS.md`).

## Rules that apply everywhere

- **No defensive clutter:** no wrappers or `try/except: pass` around code that cannot fail, no flags
  nobody sets, no dead code wired in without E2E proof. Comments keep the WHY, cut the WHAT.
- **Never infer process identity from argv substrings;** use
  `gateway.status.looks_like_gateway_command_line` / `hermes_cli.update_cmd._hermes_holder_subcommand`
  (HX003; details `hermes_cli/AGENTS.md`).
- **Never hardcode `~/.hermes`:** `get_hermes_home()` for paths, `display_hermes_home()` for text
  (HX001). `_get_profiles_root()` is HOME-anchored on purpose.
- **One process serves many profiles.** Code that runs outside a turn (boot probes, eviction,
  tickers, deferred callbacks, RPC methods, thread hops, child spawns) binds the owning profile scope
  explicitly; `os.environ`, module globals and import-time values hold the launch profile's, so an
  unbound read is a silent default-profile leak. Binding points and seams: `gateway/AGENTS.md`
  § Profile scope (HX002/HX004/HX005/HX012, PS-P05/P06).
- **Machine facts and executable lookup go through `hermes_platform`** (`hermes_platform/AGENTS.md`).
- **Dependencies carry upper bounds** (`>=floor,<next_major`; git URLs and Actions pinned to a SHA);
  after editing `pyproject.toml` run `hermes pm lock` and commit `uv.lock`; never mutate a Hermes
  environment with raw pip/uv. Full policy: `pm/AGENTS.md`.
- **TypeScript (desktop, TUI, website):** feature-owned nanostores over threaded state, thin route
  roots, narrow hooks and colocated action modules, `interface` for props and shared shapes,
  table-driven dispatch over condition ladders; `src/app` routes, `src/store` atoms, `src/lib` pure
  helpers.
- **Commits and PRs:** rebase onto `main` before merging (a squash from a stale branch silently
  reverts newer fixes); 1–2 invariant tests per fix, proven red on the base.
- **Tests:** always `scripts/run_tests.sh`, never bare `pytest`; behaviour contracts, never
  change-detectors or source-reading tests; host-specific behaviour is tested on that host with
  `@pytest.mark.platforms(...)`, never by faking `sys.platform`; tests never write to `~/.hermes/`.
  Everything else: `tests/AGENTS.md`.

## Routing Table — working in X → read X/AGENTS.md

| Area | Read | Covers |
|---|---|---|
| `run_agent.py`, `agent/` | `agent/AGENTS.md` | turn phases, caching and message-flow invariants, compression, model/aux resolution |
| `cli.py`, `hermes_cli/` | `hermes_cli/AGENTS.md` | CLI mixins, slash registry, config system, skins, `hermes update`, profiles / multiplex |
| `gateway/` | `gateway/AGENTS.md` | adapters, message guards, streaming, notifications, token locks, § Profile scope |
| `gateway/platforms/` new adapter | `gateway/platforms/ADDING_A_PLATFORM.md` | step-by-step adapter guide |
| `tools/`, `toolsets.py`, `model_tools.py` | `tools/AGENTS.md` | adding tools, registry, toolsets, delegation, session-scoped surface tools |
| `plugins/`, `hermes_cli/plugins*.py` | `plugins/AGENTS.md` | plugin kinds, native compat contract, in-tree policy |
| `plugin-catalog/` | `plugin-catalog/README.md` | catalog admission rules (mirrored in the developer guide; keep identical) |
| `tui_gateway/`, `ui-tui/` | `tui_gateway/AGENTS.md` | process model, JSON-RPC transport, slash flow |
| `web/`, `hermes_cli/web_routers/` | `web/AGENTS.md` | dashboard embeds the real TUI |
| `apps/desktop/` | `apps/desktop/AGENTS.md`, `apps/desktop/src/AGENTS.md` | `serve` backend, slash palette, Bot Mode |
| `skills/`, `optional-skills/`, `agent/curator*.py` | `skills/AGENTS.md` | frontmatter, authoring standards, curator |
| `cron/`, kanban | `cron/AGENTS.md` | scheduler invariants, job fields, kanban dispatcher |
| `tests/` | `tests/AGENTS.md` | runner, placement, OS markers, `wine2e`, banned test shapes |
| `pm/`, `pyproject.toml` | `pm/AGENTS.md` | pinning policy, PM-owned environments, plugin quarantine |
| `hermes_platform/` | `hermes_platform/AGENTS.md` | host facts, resolvers |

Long-form background: `website/docs/developer-guide/`. Workflow rules (PR/issue/review/salvage
process) live in the `hermes-agent-dev` skill, not here.
