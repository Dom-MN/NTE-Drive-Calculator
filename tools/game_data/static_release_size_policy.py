# 集中定义主静态数据库的发行体积预算与提示边界。
"""Public static release size policy shared by candidate promotion."""

from __future__ import annotations


MIB_BYTES = 1024 * 1024
DATABASE_WARNING_BYTES = 95 * MIB_BYTES
DATABASE_REPOSITORY_BUDGET_BYTES = 96 * MIB_BYTES
DATABASE_HARD_LIMIT_BYTES = 100 * MIB_BYTES


class StaticReleasePromotionError(RuntimeError):
    """候选静态库不满足发行晋升条件。"""


def format_size(size_bytes: int) -> str:
    """同时显示无歧义的字节数和二进制 MiB。"""

    return f"{size_bytes} bytes ({size_bytes / MIB_BYTES:.2f} MiB)"


def validate_database_size(
    size_bytes: int,
    *,
    allow_size_warning: bool = False,
    repository_bound: bool = True,
) -> None:
    """执行项目体积预算与 GitHub 100 MiB 单文件硬边界。"""

    if size_bytes >= DATABASE_HARD_LIMIT_BYTES:
        raise StaticReleasePromotionError(
            "发行静态数据库达到 GitHub 单文件永久硬上限："
            f"实际={format_size(size_bytes)}，"
            f"上限<{format_size(DATABASE_HARD_LIMIT_BYTES)}"
        )
    if repository_bound and size_bytes > DATABASE_REPOSITORY_BUDGET_BYTES:
        raise StaticReleasePromotionError(
            "发行静态数据库超过仓库绝对预算："
            f"实际={format_size(size_bytes)}，"
            f"预算<={format_size(DATABASE_REPOSITORY_BUDGET_BYTES)}；"
            "请改为 Release 分发或拆分只读库"
        )
    if size_bytes >= DATABASE_WARNING_BYTES and not allow_size_warning:
        raise StaticReleasePromotionError(
            "发行静态数据库达到默认阻断边界："
            f"实际={format_size(size_bytes)}，"
            f"边界={format_size(DATABASE_WARNING_BYTES)}；"
            "审计增量后可显式使用 --allow-size-warning"
        )
