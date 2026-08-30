"""Ollama 本地模型调用：只做意图解析，输出结构化 JSON。"""
import json

import httpx
from app.core.config import get_settings
from app.core.logging import setup_logging

logger = setup_logging()


class OllamaError(Exception):
    """Ollama 调用失败。"""


def chat_json(system: str, user: str) -> dict:
    """调用 Ollama /api/chat，强制 JSON 输出。失败抛 OllamaError。"""
    settings = get_settings()
    payload = {
        "model": settings.OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }
    try:
        resp = httpx.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json=payload,
            timeout=settings.OLLAMA_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.error("Ollama 调用失败: %s", e)
        raise OllamaError(f"Ollama 服务调用失败: {e}") from e

    try:
        content = resp.json()["message"]["content"]
        return json.loads(content)
    except (KeyError, json.JSONDecodeError) as e:
        logger.error("Ollama 返回内容不是合法 JSON: %s", content[:200])
        raise OllamaError("模型返回内容无法解析为 JSON") from e
