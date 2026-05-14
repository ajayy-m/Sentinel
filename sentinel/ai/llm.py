"""Ollama LLM client for local, streaming responses without cloud dependency."""
from __future__ import annotations

import json
import logging
from typing import Any, Generator

import requests

logger = logging.getLogger(__name__)


class OllamaClient:
    """
    Local Ollama LLM client.
    Assumes Ollama is running on localhost:11434.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self._health_checked = False

    def is_healthy(self) -> bool:
        """Check if Ollama is reachable and healthy."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            self._health_checked = resp.status_code == 200
            return self._health_checked
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    def list_models(self) -> list[str]:
        """List available models."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            return [m.get("name", "") for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"Failed to list models: {e}")
            return []

    def _resolve_model_name(self) -> str:
        """Use the configured model if it exists, otherwise pick a bundled model."""
        available_models = self.list_models()
        if not available_models:
            return self.model
        if self.model in available_models:
            return self.model

        preferred_fallbacks = ("qwen2.5:7b", "qwen2.5:14b")
        for fallback in preferred_fallbacks:
            if fallback in available_models:
                logger.warning(
                    "Configured Ollama model '%s' is unavailable; using '%s' instead",
                    self.model,
                    fallback,
                )
                return fallback

        fallback = available_models[0]
        logger.warning(
            "Configured Ollama model '%s' is unavailable; using '%s' instead",
            self.model,
            fallback,
        )
        return fallback

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 512,
    ) -> str:
        """
        Generate a single response (non-streaming).
        
        Args:
            prompt: User query
            system_prompt: System context
            temperature: Creativity (0.0 = deterministic, 1.0 = creative)
            top_p: Nucleus sampling threshold
            max_tokens: Max response length
            
        Returns:
            Generated text response
        """
        try:
            model_name = self._resolve_model_name()
            payload = self._build_chat_payload(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                stream=False,
                model_name=model_name,
            )

            try:
                resp = self._post_json("/api/chat", payload)
                data = resp.json()
                content = data.get("message", {}).get("content", "").strip()
                if content:
                    return content
                if data.get("error"):
                    return f"Ollama error: {data.get('error')}"
                return ""
            except requests.HTTPError as exc:
                if exc.response is None or exc.response.status_code != 404:
                    raise

            fallback_payload = self._build_generate_payload(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                stream=False,
                model_name=model_name,
            )
            resp = self._post_json("/api/generate", fallback_payload)
            data = resp.json()
            content = data.get("response", "").strip()
            if content:
                return content
            if data.get("error"):
                return f"Ollama error: {data.get('error')}"
            return ""
        except Exception as e:
            logger.exception("LLM generation failed: %s", e)
            return f"LLM generation failed: {e}"

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_tokens: int = 512,
    ) -> Generator[str, None, None]:
        """
        Stream a response token-by-token for real-time UI updates.
        
        Args:
            prompt: User query
            system_prompt: System context
            temperature: Creativity
            top_p: Nucleus sampling
            max_tokens: Max length
            
        Yields:
            Text chunks as they arrive
        """
        try:
            model_name = self._resolve_model_name()
            payload = self._build_chat_payload(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                stream=True,
                model_name=model_name,
            )

            try:
                resp = self._post_json("/api/chat", payload, stream=True)
                yield from self._stream_chat_response(resp)
                return
            except requests.HTTPError as exc:
                if exc.response is None or exc.response.status_code != 404:
                    raise

            fallback_payload = self._build_generate_payload(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                stream=True,
                model_name=model_name,
            )
            resp = self._post_json("/api/generate", fallback_payload, stream=True)
            yield from self._stream_generate_response(resp)
        except Exception as e:
            logger.exception("LLM streaming failed: %s", e)
            yield f"Error: {e}"

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "OllamaClient":
        """Create client from config dict."""
        ai_cfg = config.get("ai", {})
        llm_cfg = ai_cfg.get("llm", {})
        return cls(
            base_url=str(llm_cfg.get("base_url", "http://localhost:11434")),
            model=str(llm_cfg.get("model", "mistral:7b-instruct")),
            timeout=int(llm_cfg.get("timeout_seconds", 30)),
        )

    def _post_json(self, path: str, payload: dict[str, Any], stream: bool = False) -> requests.Response:
        resp = requests.post(
            f"{self.base_url}{path}",
            json=payload,
            timeout=self.timeout,
            stream=stream,
        )
        resp.raise_for_status()
        return resp

    def _build_chat_payload(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        top_p: float,
        max_tokens: int,
        stream: bool,
        model_name: str,
    ) -> dict[str, Any]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return {
            "model": model_name,
            "messages": messages,
            "stream": stream,
            "temperature": temperature,
            "top_p": top_p,
            "num_predict": max_tokens,
        }

    def _build_generate_payload(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        top_p: float,
        max_tokens: int,
        stream: bool,
        model_name: str,
    ) -> dict[str, Any]:
        parts = []
        if system_prompt:
            parts.append(system_prompt.strip())
        parts.append(prompt.strip())
        combined_prompt = "\n\n".join(part for part in parts if part)
        return {
            "model": model_name,
            "prompt": combined_prompt,
            "stream": stream,
            "temperature": temperature,
            "top_p": top_p,
            "num_predict": max_tokens,
        }

    def _stream_chat_response(self, resp: requests.Response) -> Generator[str, None, None]:
        for line in resp.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                except json.JSONDecodeError:
                    pass

    def _stream_generate_response(self, resp: requests.Response) -> Generator[str, None, None]:
        for line in resp.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    chunk = data.get("response", "")
                    if chunk:
                        yield chunk
                except json.JSONDecodeError:
                    pass
