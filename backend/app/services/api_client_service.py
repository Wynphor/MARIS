"""
APIClientService — 真实 LLM API 流式调用

支持的 Provider:
  - OpenAI 兼容接口: DeepSeek, MIMO, Grok, OpenAI
  - Anthropic Claude: Messages API
  - Google Gemini: generateContent API + CLI fallback

所有调用均以 SSE (Server-Sent Events) 格式 yield，供 FastAPI StreamingResponse 消费。
"""
import json
import asyncio
import subprocess
import sys
from typing import AsyncGenerator, Optional
from ..core.config import settings

# ============================================================
# Provider 配置
# ============================================================

PROVIDER_CONFIGS = {
    "deepseek": {
        "base_url": settings.DEEPSEEK_BASE_URL,        # https://api.deepseek.com
        "api_key":  settings.DEEPSEEK_API_KEY,
        "default_model": "deepseek-chat",
        "context_window": "64k",
        "type": "openai_compat",
    },
    "mimo": {
        "base_url": settings.MIMO_BASE_URL,             # https://token-plan-cn.xiaomimimo.com/v1
        "api_key":  settings.MIMO_API_KEY,
        "default_model": "mimo-v2.5",
        "context_window": "64k",
        "type": "openai_compat",
    },
    "openai": {
        "base_url": settings.OPENAI_BASE_URL,           # https://api.openai.com/v1
        "api_key":  settings.OPENAI_API_KEY,
        "default_model": "gpt-4o",
        "context_window": "128k",
        "type": "openai_compat",
    },
    "grok": {
        "base_url": settings.GROK_BASE_URL,             # https://api.x.ai/v1
        "api_key":  settings.GROK_API_KEY,
        "default_model": "grok-beta",
        "context_window": "128k",
        "type": "openai_compat",
    },
    "claude": {
        "base_url": settings.CLAUDE_BASE_URL,           # https://api.anthropic.com/v1
        "api_key":  settings.CLAUDE_API_KEY,
        "default_model": "claude-sonnet-4-20250514",
        "context_window": "200k",
        "type": "anthropic",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key":  settings.GEMINI_API_KEY,
        "default_model": "gemini-2.5-flash",
        "context_window": "1m",
        "type": "gemini",
    },
}


# ============================================================
# APIClientService
# ============================================================

class APIClientService:

    # ----------------------------------------------------------
    # 公共入口：统一流式调用
    # ----------------------------------------------------------

    # Provider fallback order
    PROVIDER_FALLBACK_ORDER = ["deepseek", "mimo", "openai", "claude", "grok", "gemini"]

    @staticmethod
    async def call_llm_stream(
        provider: str,
        workspace_id: str,
        stage: str,
        system_prompt: str,
        user_prompt: str,
        model_name: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 8192,
    ) -> AsyncGenerator[str, None]:
        """
        统一 LLM 流式调用入口。
        根据 provider 类型分发到不同的 HTTP handler。
        包含重试逻辑和跨 provider 降级。
        """
        # Build fallback chain: primary provider first, then alternatives
        fallback_chain = [provider.lower()]
        for p in APIClientService.PROVIDER_FALLBACK_ORDER:
            if p != provider.lower() and PROVIDER_CONFIGS.get(p, {}).get("api_key", ""):
                fallback_chain.append(p)

        last_error = ""
        for attempt_provider in fallback_chain:
            config = PROVIDER_CONFIGS.get(attempt_provider)
            if not config or not config["api_key"]:
                if attempt_provider != "gemini":
                    continue

            model = model_name or config["default_model"]

            # Retry logic for transient errors
            max_retries = 2
            for retry in range(max_retries):
                try:
                    collected_chunks = []
                    has_error = False

                    if config["type"] == "openai_compat":
                        async for chunk in APIClientService._stream_openai_compat(
                            config, model, system_prompt, user_prompt, temperature, max_tokens
                        ):
                            collected_chunks.append(chunk)
                            yield chunk
                    elif config["type"] == "gemini":
                        async for chunk in APIClientService._stream_gemini(
                            config, model, system_prompt, user_prompt, temperature, max_tokens
                        ):
                            collected_chunks.append(chunk)
                            yield chunk
                    else:
                        yield f"data: [ERROR] 未知的 API 类型: {config['type']}\n\n"
                        return

                    # Check if any chunk contained an error
                    for c in collected_chunks:
                        if "[ERROR]" in c:
                            has_error = True
                            last_error = c
                            break

                    if has_error and retry < max_retries - 1:
                        yield f"data: [INFO] 重试 {attempt_provider} (第 {retry + 2} 次)...\n\n"
                        import asyncio
                        await asyncio.sleep(2 ** retry)  # Exponential backoff
                        continue

                    if not has_error:
                        return  # Success, no need to fallback

                except Exception as e:
                    last_error = str(e)
                    if retry < max_retries - 1:
                        yield f"data: [INFO] {attempt_provider} 异常，重试中...\n\n"
                        import asyncio
                        await asyncio.sleep(2 ** retry)
                        continue

            # This provider failed all retries, try next
            if attempt_provider != fallback_chain[-1]:
                yield f"data: [WARNING] {attempt_provider} 失败，尝试降级到备用 provider...\n\n"

        # All providers failed
        yield f"data: [ERROR] 所有 LLM Provider 均失败。最后错误: {last_error}\n\n"

    # ----------------------------------------------------------
    # 便捷方法：调用 LLM 并收集完整输出
    # ----------------------------------------------------------
    @staticmethod
    async def call_and_collect(
        provider: str,
        workspace_id: str,
        stage: str,
        system_prompt: str,
        user_prompt: str,
        model_name: str = None,
        temperature: float = 0.4,
        max_tokens: int = 8192,
    ) -> str:
        """
        调用 LLM 并收集完整输出文本（过滤 SSE 系统消息）。

        返回纯文本内容，不包含 [TASK], [INFO] 等系统标签。
        适用于需要对 AI 输出做后处理的场景（如提取代码块、解析 JSON）。
        """
        content = ""
        async for chunk in APIClientService.call_llm_stream(
            provider=provider,
            workspace_id=workspace_id,
            stage=stage,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            if chunk.startswith("data: ") and not chunk.startswith("data: ["):
                content += chunk[6:].strip()
        return content

    @staticmethod
    async def call_llm(
        system: str,
        user: str,
        temperature: float = 0.4,
        max_tokens: int = 8192,
    ) -> AsyncGenerator[str, None]:
        """
        简化 LLM 调用入口（自动选择 provider）。
        用于 triage、data scraping 等非 pipeline 场景。
        返回纯文本内容块（已过滤系统标签）。
        """
        from ..core.config import settings

        # Auto-select first available provider
        provider_order = ["deepseek", "mimo", "openai", "claude", "grok", "gemini"]
        provider = "deepseek"  # default
        for p in provider_order:
            key = getattr(settings, f"{p.upper()}_API_KEY", "")
            if key:
                provider = p
                break

        async for chunk in APIClientService.call_llm_stream(
            provider=provider,
            workspace_id="system",
            stage="triage",
            system_prompt=system,
            user_prompt=user,
            temperature=temperature,
            max_tokens=max_tokens,
        ):
            # Filter out system messages, yield only content
            if chunk.startswith("data: ["):
                continue
            if chunk.startswith("data: "):
                yield chunk[6:]

    @staticmethod
    async def call_llm_vision(
        system: str,
        text: str,
        image_paths: list,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """
        多模态 LLM 调用（文本 + 图片）。
        自动选择支持 vision 的 provider，将图片 base64 编码后发送。
        """
        import base64
        from pathlib import Path
        from ..core.config import settings

        # Build image content parts
        image_parts = []
        for img_path in image_paths[:10]:  # Max 10 images
            p = Path(img_path)
            if not p.exists() or p.stat().st_size > 10 * 1024 * 1024:  # Skip >10MB
                continue
            try:
                img_bytes = p.read_bytes()
                b64 = base64.b64encode(img_bytes).decode("ascii")
                mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
                image_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}"},
                })
            except Exception:
                pass

        if not image_parts:
            # No images, fall back to text-only
            async for chunk in APIClientService.call_llm(
                system=system, user=text,
                temperature=temperature, max_tokens=max_tokens,
            ):
                yield chunk
            return

        # Select provider that supports vision
        vision_providers = ["openai", "claude", "grok"]
        provider = None
        for p in vision_providers:
            key = getattr(settings, f"{p.upper()}_API_KEY", "")
            if key:
                provider = p
                break
        if not provider:
            # Fallback to any available provider (won't see images but won't crash)
            for p in ["deepseek", "mimo", "gemini"]:
                key = getattr(settings, f"{p.upper()}_API_KEY", "")
                if key:
                    provider = p
                    break
        if not provider:
            provider = "deepseek"

        # Build multimodal message content
        content_parts = [{"type": "text", "text": text}]
        content_parts.extend(image_parts)

        from .task_service import get_model_for_stage
        config = get_model_for_stage("figure-audit")

        # Use OpenAI-compatible multimodal format
        try:
            import httpx
            url = f"{config['base_url'].rstrip('/')}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config['api_key']}",
            }
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": content_parts})

            payload = {
                "model": config.get("model", "gpt-4o"),
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,
            }

            async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0)) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        yield f"data: [ERROR] Vision API error {resp.status_code}: {body[:200].decode()}\n\n"
                        return
                    buffer = ""
                    async for raw in resp.aiter_bytes():
                        buffer += raw.decode("utf-8", errors="replace")
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            if not line.startswith("data: ") or line == "data: [DONE]":
                                continue
                            try:
                                delta = json.loads(line[6:])["choices"][0]["delta"]
                                content = delta.get("content", "")
                                if content:
                                    yield f"data: {content}"
                            except (json.JSONDecodeError, KeyError, IndexError):
                                pass
        except Exception as e:
            yield f"data: [ERROR] Vision call failed: {str(e)}\n\n"

    # ----------------------------------------------------------
    # OpenAI 兼容接口 (DeepSeek / MIMO / Grok / OpenAI)
    # ----------------------------------------------------------
    @staticmethod
    async def _stream_openai_compat(
        config: dict,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """调用 OpenAI 兼容 API 的 streaming 接口。"""
        try:
            import httpx
        except ImportError:
            yield "data: [ERROR] httpx 未安装，请运行 pip install httpx\n\n"
            return

        url = f"{config['base_url'].rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config['api_key']}",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        total_tokens = 0
        full_response = ""

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0)) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                if resp.status_code != 200:
                    error_body = ""
                    async for line in resp.aiter_text():
                        error_body += line
                    yield f"data: [ERROR] HTTP {resp.status_code}: {error_body[:500]}\n\n"
                    return

                buffer = ""
                async for raw_line in resp.aiter_text():
                    buffer += raw_line
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                choices = data.get("choices", [])
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        full_response += content
                                        total_tokens += 1
                                        yield f"data: {content}\n\n"
                                    # 提取 usage 信息（如果有的话）
                                    usage = data.get("usage")
                                    if usage:
                                        total_tokens = usage.get("total_tokens", total_tokens)
                            except json.JSONDecodeError:
                                continue

        # 完成统计
        final_stats = {
            "total_chars": len(full_response),
            "approx_tokens": total_tokens,
            "model": model,
        }
        yield f"data: [DONE] {json.dumps(final_stats)}\n\n"

    # ----------------------------------------------------------
    # Anthropic Claude Messages API
    # ----------------------------------------------------------
    @staticmethod
    async def _stream_anthropic(
        config: dict,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """调用 Anthropic Claude Messages API 的 streaming 接口。"""
        try:
            import httpx
        except ImportError:
            yield "data: [ERROR] httpx 未安装\n\n"
            return

        url = f"{config['base_url'].rstrip('/')}/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": config["api_key"],
            "anthropic-version": "2023-06-01",
        }
        payload = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": user_prompt}],
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt

        total_tokens = 0
        full_response = ""

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0)) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                if resp.status_code != 200:
                    error_body = ""
                    async for line in resp.aiter_text():
                        error_body += line
                    yield f"data: [ERROR] HTTP {resp.status_code}: {error_body[:500]}\n\n"
                    return

                buffer = ""
                async for raw_line in resp.aiter_text():
                    buffer += raw_line
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:]
                            try:
                                data = json.loads(data_str)
                                event_type = data.get("type", "")
                                if event_type == "content_block_delta":
                                    delta = data.get("delta", {})
                                    content = delta.get("text", "")
                                    if content:
                                        full_response += content
                                        yield f"data: {content}\n\n"
                                elif event_type == "message_delta":
                                    usage = data.get("usage", {})
                                    total_tokens = usage.get("output_tokens", total_tokens)
                                elif event_type == "message_stop":
                                    break
                            except json.JSONDecodeError:
                                continue

        final_stats = {
            "total_chars": len(full_response),
            "output_tokens": total_tokens,
            "model": model,
        }
        yield f"data: [DONE] {json.dumps(final_stats)}\n\n"

    # ----------------------------------------------------------
    # Google Gemini API (HTTP)
    # ----------------------------------------------------------
    @staticmethod
    async def _stream_gemini(
        config: dict,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
    ) -> AsyncGenerator[str, None]:
        """调用 Google Gemini generateContent API (streamGenerateContent)。"""
        try:
            import httpx
        except ImportError:
            yield "data: [ERROR] httpx 未安装\n\n"
            return

        url = (
            f"{config['base_url']}/models/{model}:streamGenerateContent"
            f"?alt=sse"
        )
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": config["api_key"],
        }
        # Gemini 使用 contents 格式
        contents = [{"role": "user", "parts": [{"text": user_prompt}]}]
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        full_response = ""

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0)) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                if resp.status_code != 200:
                    error_body = ""
                    async for line in resp.aiter_text():
                        error_body += line
                    # Gemini API 错误时尝试 CLI fallback
                    yield f"data: [WARN] Gemini API 返回 {resp.status_code}，尝试 CLI 回退...\n\n"
                    async for chunk in APIClientService._call_gemini_cli(system_prompt, user_prompt):
                        yield chunk
                    return

                buffer = ""
                async for raw_line in resp.aiter_text():
                    buffer += raw_line
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("data: "):
                            data_str = line[6:]
                            try:
                                data = json.loads(data_str)
                                candidates = data.get("candidates", [])
                                if candidates:
                                    content_parts = candidates[0].get("content", {}).get("parts", [])
                                    for part in content_parts:
                                        text = part.get("text", "")
                                        if text:
                                            full_response += text
                                            yield f"data: {text}\n\n"
                            except json.JSONDecodeError:
                                continue

        final_stats = {"total_chars": len(full_response), "model": model}
        yield f"data: [DONE] {json.dumps(final_stats)}\n\n"

    # ----------------------------------------------------------
    # Gemini CLI Fallback（无 API Key 时使用）
    # ----------------------------------------------------------
    @staticmethod
    async def _call_gemini_cli(
        system_prompt: str,
        user_prompt: str,
    ) -> AsyncGenerator[str, None]:
        """回退到 gemini CLI 命令行调用（通过 stdin 传递 prompt，避免命令行注入）。"""
        full_prompt = user_prompt
        if system_prompt:
            full_prompt = f"System instruction:\n{system_prompt}\n\nUser Prompt:\n{user_prompt}"

        try:
            process = await asyncio.create_subprocess_exec(
                "gemini", "--skip-trust", "-p", "-",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            yield "data: [INFO] Gemini CLI 启动...\n\n"

            # Write prompt to stdin and close
            process.stdin.write(full_prompt.encode("utf-8"))
            await process.stdin.drain()
            process.stdin.close()

            # Read output with timeout (120s)
            try:
                while True:
                    line = await asyncio.wait_for(
                        process.stdout.readline(), timeout=120
                    )
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace").strip()
                    if any(skip in decoded for skip in [
                        "Warning: 256-color", "Ripgrep is not", "npm warn"
                    ]):
                        continue
                    if decoded:
                        yield f"data: {decoded}\n\n"
            except asyncio.TimeoutError:
                yield f"data: [ERROR] Gemini CLI 超时 (120s)\n\n"
                process.terminate()
                return

            await process.wait()

            if process.returncode == 0:
                yield "data: [DONE] Gemini CLI 执行完成。\n\n"
            else:
                yield f"data: [ERROR] Gemini CLI 退出码 {process.returncode}\n\n"

        except FileNotFoundError:
            yield "data: [ERROR] gemini CLI 未安装。请安装或配置 GEMINI_API_KEY。\n\n"
        except Exception as e:
            yield f"data: [ERROR] Gemini CLI 调用失败: {str(e)}\n\n"
