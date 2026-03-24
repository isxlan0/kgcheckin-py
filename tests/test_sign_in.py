from datetime import datetime
import tempfile
import unittest
from pathlib import Path

from kugou_signer.config.paths import RepoPaths
from kugou_signer.config.store import AccountStore
from kugou_signer.models import Account, AppConfig, ExecutionSettings, ScheduleSettings
from kugou_signer.services.sign_in import SignInService


class FakeClient:
    def __init__(self) -> None:
        self._claim_counts: dict[str, int] = {}

    def get_user_detail(self, account: Account) -> dict:
        return {"data": {"nickname": account.nickname or f"user-{account.user_id}"}}

    def refresh_token(self, account: Account) -> dict:
        return {"status": 1, "data": {"token": account.token}}

    def listen_song(self, _account: Account) -> dict:
        return {"status": 1}

    def claim_vip(self, account: Account) -> dict:
        current = self._claim_counts.get(account.user_id, 0)
        self._claim_counts[account.user_id] = current + 1
        if current == 0:
            return {"status": 1}
        return {"status": 0, "error_code": 30002}

    def get_vip_detail(self, _account: Account) -> dict:
        return {"status": 1, "data": {"busi_vip": [{"vip_end_time": "2099-12-31"}]}}


class SignInServiceTests(unittest.TestCase):
    def test_run_once_applies_account_and_ad_delays(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = RepoPaths.resolve(Path(temp_dir))
            store = AccountStore(paths)
            store.save(
                [
                    Account(user_id="10001", token="token-1", nickname="账号一"),
                    Account(user_id="10002", token="token-2", nickname="账号二"),
                ]
            )
            sleep_calls: list[float] = []
            messages: list[str] = []
            service = SignInService(
                store,
                FakeClient(),
                config=AppConfig(
                    timezone="Asia/Shanghai",
                    schedule=ScheduleSettings(time="00:01"),
                    execution=ExecutionSettings(
                        account_gap_min_seconds=2,
                        account_gap_max_seconds=2,
                        vip_ad_gap_min_seconds=4,
                        vip_ad_gap_max_seconds=4,
                    ),
                ),
                sleep=sleep_calls.append,
            )

            results = service.run_once(datetime(2026, 3, 23, 0, 1, 0), emit=messages.append)

            self.assertEqual([call for call in sleep_calls], [4, 2, 4])
            self.assertEqual(len(results), 2)
            self.assertTrue(any("等待下一个账号 2 秒" in item for item in messages))
            self.assertTrue(any("广告领取间隔等待 4 秒" in item for item in messages))


if __name__ == "__main__":
    unittest.main()
