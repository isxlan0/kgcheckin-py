import tempfile
import unittest
from pathlib import Path

from kugou_signer.config.paths import RepoPaths
from kugou_signer.config.store import AccountStore, ConfigStore
from kugou_signer.scheduler.commands import RuntimeCommandHandler


class RuntimeCommandTests(unittest.TestCase):
    def test_suggestions_match_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = RepoPaths.resolve(Path(temp_dir))
            handler = RuntimeCommandHandler(ConfigStore(paths), AccountStore(paths))
            suggestions = handler.suggestions("/add")
            self.assertTrue(any("/add qr" in item for item in suggestions))
            self.assertTrue(any("/add <手机号>" in item for item in suggestions))

    def test_matching_commands_accept_text_without_leading_slash(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = RepoPaths.resolve(Path(temp_dir))
            handler = RuntimeCommandHandler(ConfigStore(paths), AccountStore(paths))
            matches = handler.matching_commands("add")
            commands = {item.completion for item in matches}
            self.assertIn("/add qr", commands)
            self.assertIn("/add 13800138000", commands)

    def test_schedule_set_updates_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = RepoPaths.resolve(Path(temp_dir))
            config_store = ConfigStore(paths)
            account_store = AccountStore(paths)
            handler = RuntimeCommandHandler(config_store, account_store)
            messages: list[str] = []
            result = handler.handle("/schedule set 08:30 45", emit=messages.append)
            config = config_store.load()
            self.assertEqual(result.action, "reload_schedule")
            self.assertEqual(config.schedule.time, "08:30")
            self.assertEqual(config.schedule.jitter_min_seconds, -45)
            self.assertEqual(config.schedule.jitter_max_seconds, 45)
            self.assertIn("定时配置已更新。", messages)

    def test_add_without_args_shows_hint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = RepoPaths.resolve(Path(temp_dir))
            handler = RuntimeCommandHandler(ConfigStore(paths), AccountStore(paths))
            messages: list[str] = []
            result = handler.handle("/add", emit=messages.append)
            self.assertEqual(result.action, "continue")
            self.assertIn("添加账号: /add qr 或 /add <手机号>", messages)

    def test_settings_set_updates_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = RepoPaths.resolve(Path(temp_dir))
            config_store = ConfigStore(paths)
            account_store = AccountStore(paths)
            handler = RuntimeCommandHandler(config_store, account_store)
            messages: list[str] = []
            result = handler.handle("/settings set account-gap 5 12", emit=messages.append)
            config = config_store.load()
            self.assertEqual(result.action, "continue")
            self.assertEqual(config.execution.account_gap_min_seconds, 5)
            self.assertEqual(config.execution.account_gap_max_seconds, 12)
            self.assertIn("执行间隔配置已更新。", messages)

    def test_handle_collapses_repeated_slashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            paths = RepoPaths.resolve(Path(temp_dir))
            handler = RuntimeCommandHandler(ConfigStore(paths), AccountStore(paths))
            messages: list[str] = []
            result = handler.handle("/////help", emit=messages.append)
            self.assertEqual(result.action, "continue")
            self.assertTrue(any("/help" in item for item in messages))


if __name__ == "__main__":
    unittest.main()
