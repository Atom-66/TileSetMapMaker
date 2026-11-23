import os
import time
from collections import deque
from typing import Deque, Dict, Optional


class PerformanceMetrics:
    """Lightweight rolling measurements for interactive editor operations."""

    def __init__(self, sample_limit: int = 60):
        self.sample_limit = max(1, sample_limit)
        self.render_ms: Deque[float] = deque(maxlen=self.sample_limit)
        self.visible_items: Deque[int] = deque(maxlen=self.sample_limit)
        self._render_started: Optional[float] = None
        self._drawn_items = 0

    def begin_render(self) -> None:
        self._render_started = time.perf_counter()
        self._drawn_items = 0

    def count_drawn_item(self) -> None:
        self._drawn_items += 1

    def end_render(self) -> float:
        if self._render_started is None:
            return 0.0
        duration_ms = (time.perf_counter() - self._render_started) * 1000.0
        self.render_ms.append(duration_ms)
        self.visible_items.append(self._drawn_items)
        self._render_started = None
        return duration_ms

    @property
    def last_render_ms(self) -> float:
        return self.render_ms[-1] if self.render_ms else 0.0

    @property
    def average_render_ms(self) -> float:
        return sum(self.render_ms) / len(self.render_ms) if self.render_ms else 0.0

    @staticmethod
    def process_memory_mb() -> float:
        try:
            with open("/proc/self/status", "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) / 1024.0
        except (OSError, ValueError):
            pass
        return 0.0

    def summary(self) -> Dict[str, float | int]:
        return {
            "last_render_ms": self.last_render_ms,
            "average_render_ms": self.average_render_ms,
            "last_visible_items": self.visible_items[-1] if self.visible_items else 0,
            "memory_mb": self.process_memory_mb(),
            "samples": len(self.render_ms),
            "pid": os.getpid(),
        }
