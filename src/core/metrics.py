from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Metrics:
    _start: float = field(default_factory=time.time)
    messages_processed: int = 0
    documents_generated: int = 0
    errors: int = 0

    def inc_messages(self) -> None:
        self.messages_processed += 1

    def inc_documents_generated(self) -> None:
        self.documents_generated += 1

    def inc_errors(self) -> None:
        self.errors += 1

    def uptime_seconds(self) -> float:
        return time.time() - self._start
