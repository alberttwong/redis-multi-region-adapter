"""Measured Redis operations. Credentials never appear in result rows."""
from __future__ import annotations
import asyncio
import time
from .model import Record

# Exact identity is immutable. Conflicting replay is an error, never overwrite.
APPLY = """
local old = redis.call('GET', KEYS[1])
if old and old ~= ARGV[1] then return redis.error_reply('identity_conflict') end
if tonumber(ARGV[2]) <= 0 then return 0 end
if not old then redis.call('SET', KEYS[1], ARGV[1], 'PX', ARGV[2]) end
local hint = redis.call('GET', KEYS[2])
local candidate = cjson.decode(ARGV[1])
local update = true
if hint then
 local previous = cjson.decode(hint)
 if previous.lineage == candidate.lineage then
  update = previous.sequence <= candidate.sequence
 else
  update = true -- independent writers have no shared revision order
 end
end
if update then redis.call('SET', KEYS[2], ARGV[1], 'PX', ARGV[2]) end
return 1
"""
# Per-lineage immutable snapshots and an outbox record share the session slot.
# XADD is the spike capture mechanism, not a claim of disk-fsync durability.
CAPTURE = """
local old = redis.call('GET', KEYS[1])
if old and old ~= ARGV[1] then return redis.error_reply('identity_conflict') end
if tonumber(ARGV[2]) <= 0 then return 0 end
if not old then
 redis.call('SET', KEYS[1], ARGV[1], 'PX', ARGV[2])
 redis.call('XADD', KEYS[3], '*', 'record', ARGV[1])
end
local hint = redis.call('GET', KEYS[2])
local candidate = cjson.decode(ARGV[1])
local update = true
if hint then
 local previous = cjson.decode(hint)
 if previous.lineage == candidate.lineage then
  update = previous.sequence <= candidate.sequence
 else
  update = true -- independent writers have no shared revision order
 end
end
if update then redis.call('SET', KEYS[2], ARGV[1], 'PX', ARGV[2]) end
return 1
"""

class SnapshotMissing(Exception):
    pass

class SpikeStore:
    def __init__(self, clients: dict, mode: str, origin: str, ack: str,
                 timeout_s: float = 2, poll_s: float = .01):
        self.clients, self.mode, self.origin, self.ack = clients, mode, origin, ack
        self.timeout_s, self.poll_s = timeout_s, poll_s
        self.background: set[asyncio.Task] = set()

    async def apply(self, region: str, record: Record, capture: bool = False):
        if record.remaining_ms <= 0:
            return False
        client = self.clients[region]
        if capture:
            result = await client.eval(CAPTURE, 3, record.key, record.hint_key,
                                       f"spike:{{{record.session}}}:outbox", record.encode(), record.remaining_ms)
        elif self.mode == "active-active":
            # No script replicated through AA; two separate origin SETs.
            # Hint is explicitly best effort, not atomically globally ordered.
            await client.set(record.key, record.encode(), px=record.remaining_ms, nx=True)
            await client.set(record.hint_key, record.encode(), px=max(1, record.remaining_ms))
            result = 1
        else:
            result = await client.eval(APPLY, 2, record.key, record.hint_key,
                                       record.encode(), record.remaining_ms)
        if not result:
            return False
        return True

    async def deliver(self, record: Record, region: str):
        if region == self.origin:
            return
        if self.mode == "independent":
            await self.apply(region, record)
        # Verify exact identity after transfer; this adds a measured GET phase.
        while True:
            raw = await self.clients[region].get(record.key)
            if raw is not None:
                checked = Record.decode(raw, record.session)
                if checked != record:
                    raise ValueError("identity_conflict")
                return
            await asyncio.sleep(self.poll_s)

    async def write(self, record: Record, capture: bool = False):
        async with asyncio.timeout(self.timeout_s):
            if not await self.apply(self.origin, record, capture=capture):
                raise ValueError("expired")
            remote = [r for r in self.clients if r != self.origin]
            if self.ack == "all-targets":
                await asyncio.gather(*(self.deliver(record, r) for r in remote))
            elif self.mode == "independent" and not capture:
                # Request-only: best-effort current write only; no old snapshot queue.
                task = asyncio.create_task(self._bounded_fanout(record, remote))
                self.background.add(task)
                task.add_done_callback(self.background.discard)

    async def _bounded_fanout(self, record, regions):
        try:
            async with asyncio.timeout(self.timeout_s):
                await asyncio.gather(*(self.deliver(record, r) for r in regions))
        except Exception:
            # Acknowledgment does not expose background delivery completion.
            # This mode has no durable repair guarantee.
            return

    async def read(self, region: str, session: str, policy: str, floor: Record | None = None):
        if policy not in {"latest", "required", "any"}:
            raise ValueError("unknown_policy")
        if policy == "required" and floor is None:
            raise ValueError("context_required")
        client = self.clients[region]
        probe_in_flight = False
        async def lookup(key):
            nonlocal probe_in_flight
            probe_in_flight = True
            value = await client.get(key)
            probe_in_flight = False
            return value
        try:
            async with asyncio.timeout(self.timeout_s):
                while True:
                    if policy != "required":
                        raw = await lookup(f"spike:{{{session}}}:available")
                        if raw is not None:
                            candidate = Record.decode(raw, session)
                            if candidate.remaining_ms <= 0:
                                candidate = None
                            if candidate and (floor is None or policy == "any" or candidate.follows(floor)):
                                return candidate
                        if floor is None or policy == "any":
                            return None
                    if floor is not None:
                        if floor.remaining_ms <= 0:
                            raise ValueError("expired")
                        raw = await lookup(floor.key)
                        if raw is not None:
                            exact = Record.decode(raw, session)
                            if exact != floor:
                                raise ValueError("identity_conflict")
                            return exact
                    await asyncio.sleep(self.poll_s)
        except TimeoutError as exc:
            if probe_in_flight:
                raise TimeoutError("redis_probe_deadline") from exc
            raise SnapshotMissing("snapshot_missing") from exc

    async def close(self):
        pending = list(self.background)
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
