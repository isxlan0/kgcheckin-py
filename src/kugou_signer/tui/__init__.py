__all__ = ["SchedulerTUIApp"]


def __getattr__(name: str):
    if name != "SchedulerTUIApp":
        raise AttributeError(name)
    from kugou_signer.tui.app import SchedulerTUIApp

    return SchedulerTUIApp
