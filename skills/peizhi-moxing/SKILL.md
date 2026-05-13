---
name: peizhi-moxing
description: 零选择一步配置模型 API。支持 DeepSeek / MiniMax / Kimi / 智谱 / Ollama 等国产模型。
trigger_keywords:
  - 配置模型
  - 配置 API
  - 设置模型
  - 添加模型
  - 模型配置
  - 配置 deepseek
  - 配置 minimax
  - 配置 kimi
  - 配置智谱
  - 配置 ollama
  - peizhi-moxing
  - peizhi moxing
  - setup model
  - config model
platforms: [all]
---

# 配置模型 (peizhi-moxing)

> 零选择体验 — 说"配置模型"即可一步完成 API 配置。

## 工作流程

当用户说"配置模型"时，按以下流程操作：

### 第一步：检测当前状态

读取 `~/.hermes/config.yaml` 中的 `providers:` 段，检查哪些 Provider 已配置。

### 第二步：列出可用服务

用中文向用户展示：

```
可配置的模型服务：

1. DeepSeek      (国产性价比之王，推荐)  [未配置]
2. MiniMax        (长文本处理优势)        [未配置]
3. Kimi           (代码助手特化)          [未配置]
4. 智谱 GLM       (多模态支持)            [未配置]
5. Ollama         (本地推理，免费)         [已配置 ✓]
6. 自定义端点     (OpenAI 兼容)           [未配置]

请输入要配置的编号（如 1, 2, 3）：
```

### 第三步：逐一询问 API Key

对用户选中的每个 Provider：

```
DeepSeek
├── 获取 Key: https://platform.deepseek.com/api_keys
└── 请输入 DeepSeek API Key: [等待输入，不回显]
```

- API Key 输入时使用 masking，不显示明文
- 支持批量输入（多个 Key 一次性粘贴）

### 第四步：写入配置

将 API Key 写入 `~/.hermes/config.yaml`：

```yaml
providers:
  deepseek:
    key_env: DEEPSEEK_API_KEY
    name: DeepSeek
  minimax:
    key_env: MINIMAX_API_KEY
    name: MiniMax
```

同时设置环境变量（当前会话生效）：
```bash
export DEEPSEEK_API_KEY="sk-xxx"
export MINIMAX_API_KEY="eyJxxx"
```

### 第五步：确认完成

```
✅ 配置完成！
   已配置: DeepSeek, MiniMax
   环境变量已设置（当前会话生效）
   
💡 提示：重启 Hermes 后配置永久生效。
   下次使用时说"测试连接"可验证配置。
```

## 各 Provider 详细信息

### DeepSeek
- 官网: https://platform.deepseek.com
- 注册 Key: https://platform.deepseek.com/api_keys
- 价格: ¥1/M tokens (输入), ¥2/M tokens (输出)  — 性价比极高
- 推荐模型: deepseek-v4-flash (主力), deepseek-v4-pro (增强)
- 环境变量: `DEEPSEEK_API_KEY`

### MiniMax
- 官网: https://platform.minimaxi.com
- 注册 Key: 官网 → 账户管理 → API Keys
- 价格: ¥1.5/M tokens (输入), ¥6/M tokens (输出)
- 推荐模型: minimax-m2
- 环境变量: `MINIMAX_API_KEY`
- 中国站: `MINIMAX_CN_API_KEY`

### Kimi (Moonshot)
- 官网: https://platform.moonshot.cn
- 注册 Key: 官网 → 控制台 → API Keys
- 推荐模型: kimi-k2 (代码特化)
- 环境变量: `KIMI_API_KEY`

### 智谱 GLM (ZhipuAI)
- 官网: https://open.bigmodel.cn
- 注册 Key: 官网 → 控制台 → API Keys
- 免费额度: 新用户赠送
- 推荐模型: glm-5.1
- 环境变量: `GLM_API_KEY`

### Ollama (本地推理)
- 官网: https://ollama.com
- 无需 API Key，自动检测 localhost:11434
- 推荐模型: qwen3-vl:4b
- 安装: `ollama pull qwen3-vl:4b`

### 自定义端点
- 支持任意 OpenAI 兼容 API
- 需提供: base_url + api_key + 模型名称
- 用于接入 LM Studio、vLLM、OneAPI 等

## 实现细节

### 读取配置
```python
import yaml
from pathlib import Path

config_path = Path.home() / ".hermes" / "config.yaml"
if config_path.exists():
    config = yaml.safe_load(config_path.read_text())
    providers = config.get("providers", {})
```

### 写入配置
```python
config.setdefault("providers", {})
config["providers"]["deepseek"] = {
    "key_env": "DEEPSEEK_API_KEY",
    "name": "DeepSeek",
}
config_path.write_text(yaml.dump(config, allow_unicode=True))
```

### 设置环境变量
```python
import os
os.environ["DEEPSEEK_API_KEY"] = api_key
```

## 注意事项

1. **API Key 不回显**：输入时使用 getpass.getpass() 或类似遮蔽机制
2. **已有配置跳过**：已配置的 Provider 显示 ✓ 标记
3. **支持跳过**：用户可以说"跳过"来跳过某个 Provider
4. **批量配置**：一次性选择多个 Provider 批量输入
5. **写操作安全**：写入前备份 config.yaml 为 config.yaml.bak
