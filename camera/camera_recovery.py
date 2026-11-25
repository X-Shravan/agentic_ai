from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class RecoveryPolicy:
    retry_delays: Sequence[float] = (1.0, 2.0, 5.0, 10.0)

    def delay_for_attempt(self, attempt: int) -> float:
        index = min(max(attempt - 1, 0), len(self.retry_delays) - 1)
        return float(self.retry_delays[index])
