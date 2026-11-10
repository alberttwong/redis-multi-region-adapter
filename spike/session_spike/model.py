"""Wire model and percentile math shared by real runners and offline tests."""
from __future__ import annotations
import hashlib
import json
import math
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Iterable

@dataclass(frozen=True)
class Record:
    session: str
    lineage: str
    sequence: int
    version: str
    expires_at_ms: int
    payload: str
    digest: str

    @classmethod
    def new(cls, session: str, lineage: str, sequence: int, payload: str, ttl_s: int):
        return cls(session, lineage, sequence, uuid.uuid4().hex,
                   int(time.time() * 1000) + ttl_s * 1000, payload,
                   hashlib.sha256(payload.encode()).hexdigest())

    def encode(self) -> bytes:
        return json.dumps(asdict(self), separators=(",", ":")).encode()

    @classmethod
    def decode(cls, raw: bytes, session: str):
        record = cls(**json.loads(raw))
        if record.session != session or hashlib.sha256(record.payload.encode()).hexdigest() != record.digest:
            raise ValueError("integrity_error")
        return record

    def follows(self, floor: Record) -> bool:
        # This spike serializes each writer's operations. This is not a
        # production multi-process sequencing or authenticated-context protocol.
        return (self.session == floor.session and self.lineage == floor.lineage
                and self.sequence >= floor.sequence)

    @property
    def key(self) -> str:
        return f"spike:{{{self.session}}}:v:{self.version}"

    @property
    def hint_key(self) -> str:
        return f"spike:{{{self.session}}}:available"

    @property
    def remaining_ms(self) -> int:
        return max(0, self.expires_at_ms - int(time.time() * 1000))


def percentile(values: Iterable[float], q: float) -> float | None:
    """Nearest-rank quantile; never average per-host quantiles."""
    ordered = sorted(values)
    if not ordered:
        return None
    if not 0 < q <= 1:
        raise ValueError("q must be in (0, 1]")
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def summarize(rows: list[dict]) -> dict:
    def distribution(items):
        values = [r["latency_ms"] for r in items]
        return {"n": len(values), **{name: percentile(values, q) for name, q in
                (("p50_ms", .5), ("p95_ms", .95), ("p99_ms", .99), ("max_ms", 1))}}
    outcomes = sorted({r["outcome"] for r in rows})
    return {"all_attempts": distribution(rows),
            "by_outcome": {o: distribution([r for r in rows if r["outcome"] == o]) for o in outcomes},
            "outcome_rates": {o: sum(r["outcome"] == o for r in rows) / len(rows) for o in outcomes},
            "tail_sample_warning": len(rows) < 10000}
