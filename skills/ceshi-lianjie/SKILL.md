---
name: ceshi-lianjie
description: 一键测试所有已配置模型的连通性。消耗最小 token、并发测试、汇总报告。
trigger_keywords:
  - 测试连接
  - 测试连通性
  - 连通性测试
  - 检查模型
  - 模型连通性
  - 测试模型
  - 测试 API
  - ceshi lianjie
  - ceshi-lianjie
  - check connection
  - test connection
  - test model
platforms: [all]
---

# 连通性测试 (ceshi-lianjie)

> 一键测试所有已配置模型的连通性，消耗最小 token。

## 工作流程

当用户说"测试连接"时：

### 第一步：检测已配置的 Provider

读取 `~/.hermes/config.yaml` 和环境变量，列出已配置的 Provider。

### 第二步：并发测试连通性

对每个已配置 Provider，发送**最小化请求**：

```python
# 最小 token 消耗测试
import http.client
import json
import time
import os

def test_provider(name, base_url, api_key, transport="openai_chat"):
    """测试单个 Provider 连通性。"""
    start = time.time()
    
    try:
        if name == "ollama":
            # Ollama：GET /api/tags
            conn = http.client.HTTPConnection("localhost", 11434, timeout=5)
            conn.request("GET", "/api/tags")
            resp = conn.getresponse()
            resp.read()
            elapsed = (time.time() - start) * 1000
            return {"name": name, "status": "ok", "latency_ms": elapsed}
        
        if name == "embedded":
            # 嵌入式：检查模型文件是否存在
            from pathlib import Path
            models_dir = Path.home() / ".hermes" / "models"
            ggufs = list(models_dir.glob("*.gguf"))
            elapsed = (time.time() - start) * 1000
            if ggufs:
                return {"name": name, "status": "ok", "latency_ms": elapsed, 
                        "models": [g.stem for g in ggufs]}
            return {"name": name, "status": "error", "latency_ms": elapsed,
                    "error": "模型文件未找到"}
        
        # 云端 API：最小 token 请求
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        body = json.dumps({
            "model": "auto",  # 让 API 选默认模型
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 1,
        })
        
        from urllib.parse import urlparse
        parsed = urlparse(base_url)
        endpoint = f"{parsed.path.rstrip('/')}/chat/completions"
        
        if parsed.scheme == "https":
            conn = http.client.HTTPSConnection(parsed.hostname, timeout=10)
        else:
            conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=10)
        
        conn.request("POST", endpoint, body=body, headers=headers)
        resp = conn.getresponse()
        resp.read()
        
        elapsed = (time.time() - start) * 1000
        if resp.status == 200:
            return {"name": name, "status": "ok", "latency_ms": elapsed}
        else:
            return {"name": name, "status": "error", "latency_ms": elapsed,
                    "error": f"HTTP {resp.status}"}
    
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return {"name": name, "status": "error", "latency_ms": elapsed,
                "error": str(e)[:50]}
```

### 第三步：汇总报告

生成中文报告：

```
=== 模型连通性报告 ===

✅ deepseek        152ms   正常
✅ minimax         289ms   正常  
✅ ollama           23ms   本地正常
✅ embedded         15ms   已安装 (qwen-0.5b, qwen-coder-1.5b)
❌ kimi            超时    请检查 API Key 或网络
❌ zai               —     未配置

总计: 4/6 可用
```

## 设计要点

| 维度 | 策略 |
|------|------|
| Token 消耗 | `max_tokens=1, content="hi"` — 最小化 |
| 超时阈值 | 云端 10s、本地 5s、Ollama 3s |
| 并发测试 | 所有 Provider 并发测试，汇总等待 |
| 不修改文件 | 仅输出报告，不写任何文件 |
| 单独测试 | 支持 `测试连接 deepseek` 指定目标 |

## 提供商测试配置

### DeepSeek
- Base URL: `https://api.deepseek.com/v1`
- API Key: `os.environ.get("DEEPSEEK_API_KEY")`

### MiniMax
- Base URL: `https://api.minimaxi.com/v1`
- API Key: `os.environ.get("MINIMAX_API_KEY")`

### MiniMax CN
- Base URL: `https://api.minimaxi.cn/v1`
- API Key: `os.environ.get("MINIMAX_CN_API_KEY")`

### Kimi
- Base URL: `https://api.moonshot.cn/v1`
- API Key: `os.environ.get("KIMI_API_KEY")`

### 智谱 GLM
- Base URL: `https://open.bigmodel.cn/api/paas/v4`
- API Key: `os.environ.get("GLM_API_KEY")`

### Ollama
- Base URL: `http://localhost:11434`
- 无需 API Key

### 嵌入式
- 检查 `~/.hermes/models/*.gguf` 存在性
- 无需 API Key

### 自定义端点
- 从 `config.yaml` 的 `custom_providers` 读取
- 使用配置的 base_url + key_env

## 注意事项

1. **不泄露 Key**：报告中不显示 API Key 内容
2. **超时友好**：单个 Provider 超时不阻塞整体报告
3. **结果缓存**：同一次调用内不重复测试
4. **用户友好**：所有输出用中文，错误信息清晰
