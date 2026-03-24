from datetime import datetime
import tempfile
import unittest
from pathlib import Path

from kugou_signer.config.paths import RepoPaths
from kugou_signer.config.store import AccountStore, ConfigStore
from kugou_signer.models import Account
from kugou_signer.models import AppConfig, ScheduleSettings
from kugou_signer.scheduler.engine import SchedulerController, compute_next_run, format_seconds
from kugou_signer.timezones import resolve_timezone


class DummyRandom:
    def __init__(self, value: int) -> None:
        self.value = value

    def randint(self, _minimum: int, _maximum: int) -> int:
        return self.value


class SchedulerTests(unittest.TestCase):
    def test_compute_next_run_same_day(self) -> None:
        config = AppConfig(
            timezone="Asia/Shanghai",
            schedule=ScheduleSettings(time="00:01", jitter_min_seconds=-30, jitter_max_seconds=30),
        )
        timezone = resolve_timezone("Asia/Shanghai")
        now = datetime(2026, 3, 24, 0, 0, 0, tzinfo=timezone)
        scheduled = compute_next_run(now, config, DummyRandom(15))
        self.assertEqual(scheduled.run_at, datetime(2026, 3, 24, 0, 1, 15, tzinfo=timezone))
        self.assertEqual(scheduled.jitter_seconds, 15)

    def test_compute_next_run_rolls_to_tomorrow(self) -> None:
        config = AppConfig(
            timezone="Asia/Shanghai",
            schedule=ScheduleSettings(time="00:01", jitter_min_seconds=-30, jitter_max_seconds=30),
        )
        timezone = resolve_timezone("Asia/Shanghai")
        now = datetime(2026, 3, 24, 0, 2, 0, tzinfo=timezone)
        scheduled = compute_next_run(now, config, DummyRandom(-10))
        self.assertEqual(scheduled.run_at, datetime(2026, 3, 25, 0, 0, 50, tzinfo=timezone))

    def test_format_seconds(self) -> None:
        self.assertEqual(format_seconds(3661), "01:01:01")
        self.assertEqual(format_seconds(-1), "00:00:00")

    def test_controller_status_snapshot_counts_enabled_accounts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = RepoPaths.resolve(Path(temp_dir))
            account_store = AccountStore(paths)
            account_store.save(
                [
                    Account(user_id="1", token="a", nickname="A", enabled=True),
                    Account(user_id="2", token="b", nickname="B", enabled=False),
                ]
            )
            controller = SchedulerController(ConfigStore(paths), account_store)

            snapshot = controller.status_snapshot()
            status_line = controller.format_status(snapshot)

            self.assertEqual(snapshot.enabled_accounts, 1)
            self.assertEqual(snapshot.total_accounts, 2)
            self.assertIn("账号 1/2", status_line)
            self.assertIn("倒计时", status_line)


if __name__ == "__main__":
    unittest.main()
