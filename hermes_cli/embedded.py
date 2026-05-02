"""
嵌入式 CPU 推理 Provider — 通过 llama-cpp-python 直接加载 GGUF 模型。

Hermes-Agent-CN 内置，零外部依赖，无需 Ollama/云端 API。
作为三层路由的 Tier 3 兜底方案，保证离线可用。

架构:
    EmbeddedProvider
        ├── __init__() → model_manager.load_embedded_model()
        ├── chat()      → model_manager.chat_completion()
        └── list_models() → model_manager.get_available_embedded_model()

使用方式:
    from hermes_cli.embedded import EmbeddedProvider
    provider = EmbeddedProvider()          # 自动选择最佳可用模型
    provider = EmbeddedProvider("qwen-coder-1.5b")  # 指定模型
    response = provider.chat([{"role": "user", "content": "你好"}])
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 嵌入式 Provider ID 常量
EMBEDDED_PROVIDER_ID = "embedded"
EMBEDDED_PREFIX = "embedded:"


class EmbeddedProvider:
    """嵌入式 CPU 推理 Provider，通过 llama-cpp-python 加载 GGUF。

    特性:
        - 懒加载：首次 chat() 时才初始化 Llama 实例
        - 自动选择：不指定 model 时选已安装的最佳模型
        - 优雅降级：llama-cpp-python 未安装时返回提示信息
        - 内存友好：支持手动 unload() 释放资源
    """

    def __init__(self, model_id: Optional[str] = None):
        """初始化嵌入式 Provider。

        Args:
            model_id: 模型 ID（如 "qwen-0.5b", "qwen-coder-1.5b"）。
                      为 None 时自动选择已安装的最佳模型。
        """
        self._model_id = model_id
        self._llm = None
        self._loaded_model_id: Optional[str] = None
        self._initialized = False

    @property
    def model_id(self) -> str:
        """当前使用的模型 ID。"""
        if self._loaded_model_id:
            return self._loaded_model_id
        return self._model_id or "auto"

    @property
    def is_available(self) -> bool:
        """检查嵌入式推理是否可用（llama-cpp-python 已安装 + 模型已下载）。"""
        return self._resolve_model() is not None

    def _resolve_model(self) -> Optional[str]:
        """解析实际使用的模型 ID。"""
        try:
            from hermes_cli.model_manager import get_available_embedded_model
            if self._model_id:
                # 检查指定模型是否存在
                available = get_available_embedded_model()
                if available and available.get("model_id") == self._model_id:
                    return self._model_id
                # 尝试直接检查
                from hermes_cli.model_manager import _find_gguf_file
                gguf = _find_gguf_file(self._model_id)
                return self._model_id if gguf else None
            else:
                result = get_available_embedded_model()
                if result:
                    return result.get("model_id")
                return None
        except ImportError:
            logger.debug("model_manager 不可导入，嵌入式推理不可用")
            return None
        except Exception as e:
            logger.debug("解析嵌入式模型失败: %s", e)
            return None

    def _ensure_loaded(self) -> bool:
        """确保模型已加载（懒加载）。"""
        if self._llm is not None:
            return True

        model_id = self._resolve_model()
        if not model_id:
            logger.debug("没有可用的嵌入式模型")
            return False

        try:
            from hermes_cli.model_manager import load_embedded_model
            self._llm = load_embedded_model(model_id)
            if self._llm:
                self._loaded_model_id = model_id
                self._initialized = True
                logger.info("嵌入式模型已加载: %s", model_id)
                return True
        except ImportError:
            logger.debug("llama-cpp-python 未安装")
        except Exception as e:
            logger.warning("加载嵌入式模型失败 (%s): %s", model_id, e)

        return False

    def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 2048,
        temperature: float = 0.7,
        stop: Optional[List[str]] = None,
    ) -> Optional[str]:
        """执行聊天推理。

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            max_tokens: 最大生成 token 数
            temperature: 温度参数
            stop: 停止词列表

        Returns:
            模型生成的文本，或 None（推理不可用时）
        """
        if not self._ensure_loaded():
            return None

        try:
            from hermes_cli.model_manager import chat_completion
            return chat_completion(
                self._loaded_model_id,
                messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop,
            )
        except Exception as e:
            logger.error("嵌入式推理失败: %s", e)
            return None

    def list_models(self) -> List[Dict[str, Any]]:
        """列出所有可用的嵌入式模型。"""
        models = []
        try:
            from hermes_cli.model_manager import MODEL_REGISTRY
            for model_id, info in MODEL_REGISTRY.items():
                if info.get("type") == "gguf":
                    from hermes_cli.model_manager import _find_gguf_file
                    gguf_path = _find_gguf_file(model_id)
                    models.append({
                        "id": f"{EMBEDDED_PREFIX}{model_id}",
                        "name": info.get("name", model_id),
                        "installed": gguf_path is not None,
                        "tier": info.get("tier", "optional"),
                        "size_gb": info.get("size_gb", 0),
                    })
        except ImportError:
            pass
        return models

    def unload(self):
        """卸载模型，释放内存。"""
        if self._llm is not None:
            del self._llm
            self._llm = None
            self._loaded_model_id = None
            self._initialized = False
            logger.info("嵌入式模型已卸载")

    def __del__(self):
        """析构时自动释放资源。"""
        try:
            self.unload()
        except Exception:
            pass

    def __repr__(self) -> str:
        status = "loaded" if self._llm else "lazy"
        return f"<EmbeddedProvider model={self.model_id} status={status}>"


# -- 便捷函数 ----------------------------------------------------------------

def get_embedded_provider(model_id: Optional[str] = None) -> Optional[EmbeddedProvider]:
    """获取嵌入式 Provider 实例（如果可用）。

    Args:
        model_id: 指定模型 ID，None 则自动选择。

    Returns:
        EmbeddedProvider 实例，或 None（不可用时）。
    """
    provider = EmbeddedProvider(model_id)
    if provider.is_available:
        return provider
    return None


def is_embedded_available() -> bool:
    """快速检查嵌入式推理是否可用（不加载模型）。"""
    try:
        from hermes_cli.model_manager import get_available_embedded_model
        return get_available_embedded_model() is not None
    except Exception:
        return False
