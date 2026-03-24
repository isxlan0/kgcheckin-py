from __future__ import annotations

import argparse

from kugou_signer.config.store import AccountStore, ConfigStore
from kugou_signer.exceptions import KugouSignerError
from kugou_signer.management import ManagementController
from kugou_signer.scheduler.engine import SchedulerRunner
from kugou_signer.terminal import configure_terminal


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="KuGou Signer Python 控制台")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("run", help="启动常驻倒计时与自动签到")

    account_parser = subparsers.add_parser("account", help="账号管理")
    account_subparsers = account_parser.add_subparsers(dest="account_command", required=True)
    account_subparsers.add_parser("list", help="列出账号")
    account_subparsers.add_parser("add-qr", help="通过二维码添加账号")
    phone_parser = account_subparsers.add_parser("add-phone", help="通过手机号添加账号")
    phone_parser.add_argument("--phone", required=True, help="手机号")
    phone_parser.add_argument("--code", help="验证码；留空时会先发送验证码并提示输入")
    remove_parser = account_subparsers.add_parser("remove", help="删除账号")
    remove_parser.add_argument("--user-id", required=True, help="要删除的 user_id")

    schedule_parser = subparsers.add_parser("schedule", help="定时配置")
    schedule_subparsers = schedule_parser.add_subparsers(dest="schedule_command", required=True)
    schedule_subparsers.add_parser("show", help="显示当前定时配置")
    set_parser = schedule_subparsers.add_parser("set", help="设置定时配置")
    set_parser.add_argument("--time", required=True, help="每日执行时间，格式 HH:MM")
    set_parser.add_argument("--jitter-seconds", type=int, default=None, help="对称随机波动秒数，例如 30 表示 -30..30")
    set_parser.add_argument("--jitter-min-seconds", type=int, default=None, help="最小波动秒数")
    set_parser.add_argument("--jitter-max-seconds", type=int, default=None, help="最大波动秒数")

    settings_parser = subparsers.add_parser("settings", help="执行间隔配置")
    settings_subparsers = settings_parser.add_subparsers(dest="settings_command", required=True)
    settings_subparsers.add_parser("show", help="显示账号间隔与广告间隔配置")
    settings_set_parser = settings_subparsers.add_parser("set", help="设置执行间隔配置")
    settings_set_parser.add_argument("--account-gap-min-seconds", type=int, default=None, help="账号之间的最小等待秒数")
    settings_set_parser.add_argument("--account-gap-max-seconds", type=int, default=None, help="账号之间的最大等待秒数")
    settings_set_parser.add_argument("--vip-ad-gap-min-seconds", type=int, default=None, help="广告领取之间的最小等待秒数")
    settings_set_parser.add_argument("--vip-ad-gap-max-seconds", type=int, default=None, help="广告领取之间的最大等待秒数")
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_terminal()
    parser = build_parser()
    try:
        args = parser.parse_args(argv)

        config_store = ConfigStore()
        account_store = AccountStore()
        controller = ManagementController(config_store, account_store)
        runner = SchedulerRunner(config_store, account_store)

        if args.command is None:
            return runner.run_forever()

        if args.command == "run":
            return runner.run_forever()

        if args.command == "account":
            if args.account_command == "list":
                return _handle_account_list(controller)
            if args.account_command == "remove":
                return _handle_account_remove(controller, args.user_id)
            if args.account_command == "add-qr":
                return _handle_account_add_qr(controller)
            if args.account_command == "add-phone":
                return _handle_account_add_phone(controller, args.phone, args.code)

        if args.command == "schedule":
            if args.schedule_command == "show":
                return _handle_schedule_show(controller)
            if args.schedule_command == "set":
                return _handle_schedule_set(
                    controller,
                    args.time,
                    args.jitter_seconds,
                    args.jitter_min_seconds,
                    args.jitter_max_seconds,
                )

        if args.command == "settings":
            if args.settings_command == "show":
                return _handle_settings_show(controller)
            if args.settings_command == "set":
                return _handle_settings_set(
                    controller,
                    args.account_gap_min_seconds,
                    args.account_gap_max_seconds,
                    args.vip_ad_gap_min_seconds,
                    args.vip_ad_gap_max_seconds,
                )

        parser.print_help()
        return 1
    except KeyboardInterrupt:
        print("\n已取消。")
        return 130
    except (KugouSignerError, ValueError) as exc:
        print(f"错误: {exc}")
        return 1


def _handle_account_list(controller: ManagementController) -> int:
    controller.show_accounts()
    return 0


def _handle_account_remove(controller: ManagementController, user_id: str) -> int:
    return 0 if controller.remove_account(user_id) else 1


def _handle_account_add_qr(controller: ManagementController) -> int:
    controller.add_account_by_qr()
    return 0


def _handle_account_add_phone(controller: ManagementController, phone: str, code: str | None) -> int:
    controller.add_account_by_phone(phone=phone, code=code)
    return 0


def _handle_schedule_show(controller: ManagementController) -> int:
    controller.show_schedule()
    return 0


def _handle_schedule_set(
    controller: ManagementController,
    schedule_time: str,
    jitter_seconds: int | None,
    jitter_min_seconds: int | None,
    jitter_max_seconds: int | None,
) -> int:
    current = controller.config_store.load()
    if jitter_seconds is not None:
        jitter_min = -abs(jitter_seconds)
        jitter_max = abs(jitter_seconds)
    else:
        jitter_min = jitter_min_seconds if jitter_min_seconds is not None else current.schedule.jitter_min_seconds
        jitter_max = jitter_max_seconds if jitter_max_seconds is not None else current.schedule.jitter_max_seconds
    controller.save_schedule(schedule_time, jitter_min, jitter_max)
    return 0


def _handle_settings_show(controller: ManagementController) -> int:
    controller.show_schedule()
    return 0


def _handle_settings_set(
    controller: ManagementController,
    account_gap_min_seconds: int | None,
    account_gap_max_seconds: int | None,
    vip_ad_gap_min_seconds: int | None,
    vip_ad_gap_max_seconds: int | None,
) -> int:
    current = controller.config_store.load()
    controller.save_execution_settings(
        account_gap_min_seconds=(
            current.execution.account_gap_min_seconds
            if account_gap_min_seconds is None
            else account_gap_min_seconds
        ),
        account_gap_max_seconds=(
            current.execution.account_gap_max_seconds
            if account_gap_max_seconds is None
            else account_gap_max_seconds
        ),
        vip_ad_gap_min_seconds=(
            current.execution.vip_ad_gap_min_seconds
            if vip_ad_gap_min_seconds is None
            else vip_ad_gap_min_seconds
        ),
        vip_ad_gap_max_seconds=(
            current.execution.vip_ad_gap_max_seconds
            if vip_ad_gap_max_seconds is None
            else vip_ad_gap_max_seconds
        ),
    )
    return 0
