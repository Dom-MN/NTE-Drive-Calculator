# 调用组合根显式注入的用户入口说明与环境问题回调。
from typing import Any


def request_input_entry(owner: Any, capability: str, label: str) -> bool:
    callback = getattr(owner, "operation_entry", None)
    return bool(callback(capability, label)) if callable(callback) else False


def show_input_unavailable(owner: Any, label: str, detail: str, target: str = "detection") -> None:
    callback = getattr(owner, "operation_unavailable", None)
    if callable(callback):
        callback(label, detail, target)


def show_sync_required(owner: Any, label: str) -> None:
    """将需要已开启同步的操作统一引导到工作台，不自动重试原操作。"""
    show_input_unavailable(
        owner, label,
        "同步连接未开启。\n请到工作台开启“自动同步”，进入游戏场景并等待同步就绪。",
        target="home",
    )
