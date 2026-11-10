import asyncio
import dataclasses
import unittest
from unittest.mock import AsyncMock
from session_spike.model import Record, percentile, summarize
from session_spike.store import SnapshotMissing, SpikeStore

class ModelTests(unittest.TestCase):
    def test_percentiles_and_outcomes_keep_timeouts(self):
        rows=[{'latency_ms':1.,'outcome':'success'} for _ in range(98)]
        rows += [{'latency_ms':2000.,'outcome':'timeout'} for _ in range(2)]
        result=summarize(rows)
        self.assertEqual(result['all_attempts']['p99_ms'],2000.)
        self.assertEqual(result['by_outcome']['success']['p99_ms'],1.)
        self.assertEqual(result['outcome_rates']['timeout'],.02)
        self.assertIsNone(percentile([], .99))

    def test_version_number_alone_does_not_prove_successor(self):
        floor=Record.new('s','A1',42,'hello',30)
        self.assertTrue(dataclasses.replace(floor,sequence=43).follows(floor))
        self.assertFalse(dataclasses.replace(floor,lineage='B1',sequence=99).follows(floor))

    def test_integrity_and_session_binding(self):
        record=Record.new('s','A1',1,'hello',30)
        self.assertEqual(Record.decode(record.encode(),'s'),record)
        with self.assertRaises(ValueError):Record.decode(record.encode(),'other')
        with self.assertRaises(ValueError):Record.decode(dataclasses.replace(record,payload='tampered').encode(),'s')

class ReadTests(unittest.IsolatedAsyncioTestCase):
    async def test_independent_reader_does_not_wait_for_unknown_write(self):
        client=AsyncMock()
        client.get.return_value=None
        store=SpikeStore({'west':client},'independent','west','local',.03,.002)
        self.assertIsNone(await store.read('west','s','latest'))
        client.get.assert_awaited_once()

    async def test_exact_missing_is_not_a_null_success(self):
        client=AsyncMock();client.get.return_value=None
        floor=Record.new('s','A1',42,'hello',30)
        store=SpikeStore({'west':client},'independent','west','local',.02,.001)
        with self.assertRaises(SnapshotMissing):await store.read('west','s','required',floor)

    async def test_latest_rechecks_successor_without_exact_snapshot(self):
        client=AsyncMock()
        floor=Record.new('s','A1',42,'hello',30)
        successor=dataclasses.replace(floor,sequence=43,version='newer')
        candidate_calls=0
        async def get(key):
            nonlocal candidate_calls
            if key==floor.hint_key:
                candidate_calls+=1
                return successor.encode() if candidate_calls>=2 else None
            return None
        client.get.side_effect=get
        store=SpikeStore({'west':client},'independent','west','local',.1,.001)
        self.assertEqual(await store.read('west','s','latest',floor),successor)
        with self.assertRaises(SnapshotMissing):await store.read('west','s','required',floor)

    async def test_other_client_context_is_not_inherited(self):
        client=AsyncMock()
        floor=Record.new('s','A1',42,'hello',30)
        unrelated=dataclasses.replace(floor,lineage='A2',sequence=99)
        client.get.side_effect=lambda key:unrelated.encode() if key==floor.hint_key else None
        store=SpikeStore({'west':client},'independent','west','local',.02,.001)
        with self.assertRaises(SnapshotMissing):await store.read('west','s','latest',floor)
        self.assertEqual(await store.read('west','s','any'),unrelated)

    async def test_infrastructure_failure_is_not_snapshot_missing(self):
        client=AsyncMock();client.get.side_effect=ConnectionError('offline')
        store=SpikeStore({'west':client},'independent','west','local',.02,.001)
        with self.assertRaises(ConnectionError):await store.read('west','s','latest')

    async def test_slow_redis_probe_is_infrastructure_timeout(self):
        client=AsyncMock()
        async def slow_get(key):
            await asyncio.sleep(.1)
        client.get.side_effect=slow_get
        floor=Record.new('s','A1',42,'hello',30)
        store=SpikeStore({'west':client},'independent','west','local',.01,.001)
        with self.assertRaises(TimeoutError):await store.read('west','s','latest',floor)

    async def test_required_rejects_unknown_context(self):
        store=SpikeStore({'west':AsyncMock()},'independent','west','local')
        with self.assertRaisesRegex(ValueError,'context_required'):await store.read('west','s','required')

if __name__=='__main__':unittest.main()
