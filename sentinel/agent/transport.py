from __future__ import annotations

from typing import Any

import msgpack
import zmq


class PushClient:
    def __init__(self, endpoint: str, send_timeout_ms: int = 1000) -> None:
        self._context = zmq.Context.instance()
        self._socket = self._context.socket(zmq.PUSH)
        self._socket.setsockopt(zmq.SNDTIMEO, send_timeout_ms)
        self._socket.connect(endpoint)

    def send(self, payload: dict[str, Any]) -> None:
        self._socket.send(msgpack.packb(payload, use_bin_type=True))

    def close(self) -> None:
        self._socket.close(linger=0)
