from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebhookConfig:
    enabled: bool = False
    urls: tuple[str, ...] = ()
    timeout_seconds: float = 5.0


class WebhookNotifier:
    """Best-effort webhook notifier for alerts and recommendations."""

    def __init__(self, cfg: WebhookConfig) -> None:
        self._cfg = cfg

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "WebhookNotifier | None":
        integration_cfg = config.get("integration", {})
        webhook_cfg = integration_cfg.get("webhooks", {})
        enabled = bool(webhook_cfg.get("enabled", False))
        urls = tuple(
            str(url).strip() for url in webhook_cfg.get("urls", []) if str(url).strip()
        )
        if not enabled or not urls:
            return None
        return cls(
            WebhookConfig(
                enabled=enabled,
                urls=urls,
                timeout_seconds=float(webhook_cfg.get("timeout_seconds", 5.0)),
            )
        )

    def notify(self, event_type: str, payload: dict[str, Any]) -> None:
        if not self._cfg.enabled:
            return

        message = {
            "event_type": event_type,
            "payload": payload,
        }
        for url in self._cfg.urls:
            try:
                response = requests.post(url, json=message, timeout=self._cfg.timeout_seconds)
                response.raise_for_status()
            except Exception as exc:
                LOGGER.warning("Webhook delivery failed url=%s event_type=%s error=%s", url, event_type, exc)
