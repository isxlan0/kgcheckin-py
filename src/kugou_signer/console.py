from __future__ import annotations

from kugou_signer.config.store import AccountStore, ConfigStore
from kugou_signer.management import ManagementController
from kugou_signer.scheduler.engine import SchedulerRunner


class InteractiveConsole:
    def __init__(self, config_store: ConfigStore, account_store: AccountStore) -> None:
        self.config_store = config_store
        self.account_store = account_store
        self.controller = ManagementController(config_store, account_store)

    def run(self) -> int:
        while True:
            print("\nKuGou Signer 控制台")
            print("1. 查看账号")
            print("2. 二维码添加账号")
            print("3. 手机号添加账号")
            print("4. 删除账号")
            print("5. 查看定时配置")
            print("6. 设置定时配置")
            print("7. 设置执行间隔")
            print("8. 启动守护签到")
            print("0. 退出")
            choice = input("请输入操作编号: ").strip()
            try:
                if choice == "1":
                    self._show_accounts()
                elif choice == "2":
                    self._add_account_by_qr()
                elif choice == "3":
                    self._add_account_by_phone()
                elif choice == "4":
                    self._remove_account()
                elif choice == "5":
                    self._show_schedule()
                elif choice == "6":
                    self._set_schedule()
                elif choice == "7":
                    self._set_execution()
                elif choice == "8":
                    runner = SchedulerRunner(self.config_store, self.account_store)
                    return runner.run_forever()
                elif choice == "0":
                    return 0
                else:
                    print("无效输入，请重新选择。")
            except Exception as exc:
                print(f"操作失败: {exc}")

    def _show_accounts(self) -> None:
        self.controller.show_accounts()

    def _add_account_by_qr(self) -> None:
        self.controller.add_account_by_qr()

    def _add_account_by_phone(self) -> None:
        self.controller.add_account_by_phone()

    def _remove_account(self) -> None:
        self.controller.remove_account()

    def _show_schedule(self) -> None:
        self.controller.show_schedule()

    def _set_schedule(self) -> None:
        self.controller.prompt_schedule_update()

    def _set_execution(self) -> None:
        config = self.config_store.load()
        account_min = (
            input(f"账号间隔最小秒数 [{config.execution.account_gap_min_seconds}]: ").strip()
            or str(config.execution.account_gap_min_seconds)
        )
        account_max = (
            input(f"账号间隔最大秒数 [{config.execution.account_gap_max_seconds}]: ").strip()
            or str(config.execution.account_gap_max_seconds)
        )
        ad_min = (
            input(f"广告间隔最小秒数 [{config.execution.vip_ad_gap_min_seconds}]: ").strip()
            or str(config.execution.vip_ad_gap_min_seconds)
        )
        ad_max = (
            input(f"广告间隔最大秒数 [{config.execution.vip_ad_gap_max_seconds}]: ").strip()
            or str(config.execution.vip_ad_gap_max_seconds)
        )
        self.controller.save_execution_settings(
            account_gap_min_seconds=int(account_min),
            account_gap_max_seconds=int(account_max),
            vip_ad_gap_min_seconds=int(ad_min),
            vip_ad_gap_max_seconds=int(ad_max),
        )
