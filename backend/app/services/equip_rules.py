"""养护机械判定口径（唯一事实来源）。

保养到期、可用、报废这三处判定，台账服务、保养提醒接口与存量回填都只能调用这里的
函数，任何界面或后台都不再各自重写一遍；界面拿到的结论以服务端台账为准。

判定优先级（高到低）：
1. 已报废：显式标记报废的机械，任何情况下都不再可用，也不进入保养提醒；
2. 保养中：显式处于保养流程的机械，暂不参与到期/可用判定；
3. 保养到期：未报废、未在保养中时，以「下次保养日」与当天比较，到期（含当天）
   或日期无法识别的，按待保养处理；日期在未来的，判定为可用。
"""
from __future__ import annotations

from datetime import date
from typing import Any

SCRAPPED = "已报废"
MAINTAINING = "保养中"
PENDING = "待保养"
AVAILABLE = "可用"

# 规范状态序列，路由层的可选项也从这里取，避免另写一份。
STATUS_ORDER = [PENDING, AVAILABLE, MAINTAINING, SCRAPPED]

ACTION_RULES: dict[str, str] = {"安排保养": MAINTAINING, "确认可用": AVAILABLE, "报废机械": SCRAPPED}

CODE_FIELD = "机械编号"
STATUS_FIELD = "机械状态"
NEXT_MAINT_FIELD = "下次保养日"
LAST_MAINT_FIELD = "上次保养日"

# 结论回填时只允许写这两个由口径推导出来的字段；
# 机械记录本身、停放场地、保养日期等存量数据一律不动。
BACKFILL_FIELDS = ("status", STATUS_FIELD)


def _parse_date(value: Any) -> date | None:
    """把台账里的日期值解析成 date；无法识别（空值、占位文本等）时返回 None。"""
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def resolve_status(entry: dict[str, Any], *, today: date | None = None) -> str:
    """按统一口径推导一条机械记录当前应有的规范状态。"""
    current = str(entry.get("status") or "").strip()
    if current == SCRAPPED:
        return SCRAPPED
    if current == MAINTAINING:
        return MAINTAINING
    today = today or date.today()
    next_maint = _parse_date(entry.get(NEXT_MAINT_FIELD))
    # 日期缺失或识别不了时保守处理：视为需要保养，而不是默认可用。
    if next_maint is None or next_maint <= today:
        return PENDING
    return AVAILABLE


def apply_status(entry: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    """把统一口径的结论回填到机械记录上（status 与界面展示用的「机械状态」同步）。"""
    status = resolve_status(entry, today=today)
    entry["status"] = status
    entry[STATUS_FIELD] = status
    # 保养提醒只看待保养；报废机械永远不进待办，保养中/可用期间也不提醒。
    entry["pending"] = status == PENDING
    entry["abnormal"] = False
    return entry


def is_due(entry: dict[str, Any], *, today: date | None = None) -> bool:
    """该机械是否进入保养提醒：只有按统一口径判为「待保养」时才提醒。"""
    return resolve_status(entry, today=today) == PENDING
