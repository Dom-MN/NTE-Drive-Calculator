# 将冻结的历史配置与轻量合计格式化为只读文本，不重新计算或读取当前账号状态。
from __future__ import annotations

from src.i18n import display_term, tr

from datetime import datetime

from src.domain.cultivation_history import HistorySummary, decode_summary


def summary_text(summary: HistorySummary) -> tuple[str, str]:
    try:
        value = decode_summary(summary.summary_json)
        names = summary.character_labels or tuple(item["name"] for item in value["characters"])
        name = tr("、").join(display_term(name) for name in names)
        total = value["total_stamina"]
        stamina = f"{total:,}" if total is not None else tr("已知 {known} · 未完整", known=f"{value['known_stamina']:,}")
        return name, stamina
    except (ValueError, TypeError, KeyError, RecursionError):
        return tr("记录摘要异常，仍可勾选删除"), tr("请查看详情或删除")


def local_history_time(raw: str) -> str:
    """只改变显示格式；存储和排序继续使用原 UTC 时间。"""
    try:
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if moment.utcoffset() is None:
            raise ValueError("历史时间缺少时区")
        return moment.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, AttributeError, OverflowError, OSError):
        return "时间格式异常"
