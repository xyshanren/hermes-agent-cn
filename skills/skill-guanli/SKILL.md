---
name: skill-guanli
description: 第三方 Skill 管理 — 添加、审计、移除第三方 Skill，记录来源和风险等级。
trigger_keywords:
  - 添加 skill
  - 安装 skill
  - 移除 skill
  - 删除 skill
  - 审计 skill
  - 检查 skill
  - 第三方 skill
  - skill 管理
  - 管理技能
  - skill guanli
  - skill-guanli
  - add skill
  - remove skill
  - audit skill
platforms: [all]
---

# Skill 管理 (skill-guanli)

> 第三方 Skill 的添加、审计、移除全生命周期管理。

## 功能

### 1. 添加第三方 Skill

```
用户: 添加 skill https://github.com/user/my-skill
↓
1. 解析来源地址
2. 克隆/下载 skill 到 ~/.hermes/skills/
3. 解析 SKILL.md 评估风险等级
4. 用户确认 → 记录到 registry
```

### 2. 审计所有 Skill

```
用户: 审计 skill
↓
列出所有第三方 Skill + 风险等级 + 建议
```

### 3. 移除 Skill

```
用户: 移除 skill my-skill
↓
确认 → 删除文件 + registry 清理
```

## 第三方 Skill 注册表

位置: `~/.hermes/third_party_skills.yaml`

```yaml
# 第三方 Skill 注册表
# 格式见下方示例，所有字段均可选（有合理默认值）

skills:
  - name: "some-custom-skill"
    source: "github.com/user/repo"
    source_type: "github"
    installed_at: "2026-05-03T10:00:00+08:00"
    version: "v1.2.0"
    description: "用户提供的自定义 skill"
    risk_level: "low"
    risk_notes: "仅读取本地文件，无网络请求"
    last_audited: "2026-05-03"
    usage_count: 0
    enabled: true
```

## 风险评估

每个第三方 Skill 安装前评估：

| 风险等级 | 条件 | 操作 |
|----------|------|------|
| 🟢 low | 纯文档/模板 skill，无脚本执行 | 直接安装 |
| 🟡 medium | 含脚本但只读本地文件 | 提示后安装 |
| 🟠 high | 含网络请求或 shell exec | 用户确认 + 审查 |
| 🔴 critical | 含系统级修改或 sudo | 强烈警告 + 二次确认 |

### 风险评估维度
1. 是否有网络请求 — 检查代码中的 http/urllib/requests 引用
2. 是否执行 shell 命令 — 检查 shell_exec/exec/os.system/subprocess 引用
3. 是否修改系统配置 — 检查写入系统目录的代码
4. 是否读取敏感文件 — 检查读取 .env/ssh keys/passwords 的代码
5. 来源可信度 — GitHub stars/comments/history

## 实现细节

### 添加 Skill
```python
import yaml
import subprocess
from pathlib import Path

def add_skill(source_url, name=None):
    """添加第三方 Skill。"""
    # 提取名称
    if not name:
        name = source_url.rstrip("/").rsplit("/", 1)[-1].replace(".git", "")
    
    skill_dir = Path.home() / ".hermes" / "skills" / name
    
    # 克隆
    subprocess.run(["git", "clone", source_url, str(skill_dir)], check=True)
    
    # 评估风险
    risk = assess_risk(skill_dir)
    
    # 记录
    registry = load_registry()
    registry["skills"].append({
        "name": name,
        "source": source_url,
        "source_type": "github",
        "installed_at": datetime.now().isoformat(),
        "risk_level": risk.level,
        "risk_notes": risk.notes,
    })
    save_registry(registry)
```

### 评估风险
```python
def assess_risk(skill_dir):
    """评估 Skill 风险等级。"""
    risk_score = 0
    notes = []
    
    for file in skill_dir.rglob("*.py"):
        content = file.read_text()
        
        if "urllib" in content or "requests" in content:
            risk_score += 1
            notes.append("含网络请求")
        if "subprocess" in content or "os.system" in content:
            risk_score += 2
            notes.append("含 shell 执行")
        if "sudo" in content:
            risk_score += 3
            notes.append("含 sudo 操作")
    
    if risk_score == 0:
        level = "low"
    elif risk_score <= 2:
        level = "medium"
    elif risk_score <= 4:
        level = "high"
    else:
        level = "critical"
    
    return AssessResult(level=level, notes=", ".join(notes))
```

### 审计
```python
def audit_skills():
    """审计所有第三方 Skill。"""
    registry = load_registry()
    
    report = []
    for skill in registry.get("skills", []):
        status = "✅" if skill.get("enabled", True) else "❌"
        risk_icon = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
        icon = risk_icon.get(skill.get("risk_level", "low"), "⬜")
        
        report.append({
            "name": skill["name"],
            "source": skill.get("source", ""),
            "risk": f"{icon} {skill.get('risk_level', 'unknown')}",
            "enabled": status,
            "installed": skill.get("installed_at", ""),
            "notes": skill.get("risk_notes", ""),
        })
    
    return report
```

## 注意事项
1. 所有第三方 Skill 默认禁用（用户手动启用）
2. 安装前备份注册表
3. 高风险 Skill 需要用户二次确认
4. 支持从本地目录安装（不用 git clone）
