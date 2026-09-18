"""
BOSS 自动回复机器人 - OpenAI 客户端工厂

统一创建 OpenAI 兼容客户端：
- 支持 AI_HTTP_PROXY 代理（部分网络直连 API 的 TLS 握手会间歇超时）
- 统一超时与重试策略，快速失败以便切换备用 API
"""

import logging

from . import config

logger = logging.getLogger(__name__)

_TIMEOUT = 30
_MAX_RETRIES = 1


def make_client(api_key: str, base_url: str, timeout: float = None):
    """创建 OpenAI 兼容客户端，按配置自动挂代理"""
    from openai import OpenAI

    kwargs = {
        "api_key": api_key,
        "base_url": base_url,
        "timeout": timeout or _TIMEOUT,
        "max_retries": _MAX_RETRIES,
    }
    proxy = config.AI_HTTP_PROXY
    if proxy:
        try:
            import httpx
            kwargs["http_client"] = httpx.Client(proxy=proxy, timeout=timeout or _TIMEOUT)
        except Exception as e:
            logger.warning(f"代理客户端创建失败（将直连）: {e}")
    return OpenAI(**kwargs)