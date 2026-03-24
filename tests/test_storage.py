import json
import os
import tempfile
import unittest
from pathlib import Path

from kugou_signer.config.paths import RepoPaths
from kugou_signer.config.store import AccountStore, ConfigStore
from kugou_signer.models import Account


class StorageTests(unittest.TestCase):
    def test_config_store_creates_default_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = RepoPaths.resolve(Path(temp_dir))
            store = ConfigStore(paths)
            config = store.load()
            self.assertEqual(config.timezone, "Asia/Shanghai")
            self.assertEqual(config.execution.account_gap_min_seconds, 0)
            self.assertEqual(config.execution.account_gap_max_seconds, 0)
            self.assertEqual(config.execution.vip_ad_gap_min_seconds, 30)
            self.assertEqual(config.execution.vip_ad_gap_max_seconds, 30)
            self.assertTrue(paths.config_file.exists())

    def test_account_store_migrates_old_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = RepoPaths.resolve(Path(temp_dir))
            paths.data_dir.mkdir(parents=True, exist_ok=True)
            paths.accounts_file.write_text(
                json.dumps([{"userid": "10001", "token": "abc", "nickname": "旧账号"}], ensure_ascii=False),
                encoding="utf-8",
            )
            store = AccountStore(paths)
            accounts = store.load()
            self.assertEqual(accounts[0].user_id, "10001")
            saved = json.loads(paths.accounts_file.read_text(encoding="utf-8"))
            self.assertIn("user_id", saved[0])
            self.assertNotIn("userid", saved[0])

    def test_account_store_imports_from_userinfo_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = RepoPaths.resolve(Path(temp_dir))
            store = AccountStore(paths)
            os.environ["USERINFO"] = json.dumps([{"userid": "20002", "token": "xyz"}], ensure_ascii=False)
            try:
                accounts = store.load()
            finally:
                os.environ.pop("USERINFO", None)
            self.assertEqual(accounts, [Account(user_id="20002", token="xyz")])
            self.assertTrue(paths.accounts_file.exists())


if __name__ == "__main__":
    unittest.main()
