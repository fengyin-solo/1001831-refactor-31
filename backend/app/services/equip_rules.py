"""养护机械状态口径——全平台唯一一份判断来源。

保养到期、可用、报废三处判断统一收在这里：机械台账列表、保养提醒、状态流转动作
以及存量数据回填都只能调用本模块，界面和接口不得再各写一遍判断。

口径优先级（高 → 低）：

1. 已报废：已登记报废的机械终止后续一切判断，不再进入保养提醒；
2. 保养中：已安排保养、尚未确认可用的机械；
3. 待保养（保养到期）：未报废、未在保养中，且「下次保养日」已到或已过；
4. 可用：其余机械（包括没有可识别保养计划的机械）。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable

# 机械台账与保养提醒共用的状态序列，顺序即流转口径，任何地方都不要再手抄一份。
SCRAPPED = "已报废"
IN_MAINTENANCE = "保养中"
DUE = "待保养"
AVAILABLE = "可用"
STATUS_ORDER = [DUE, AVAILABLE, IN_MAINTENANCE, SCRAPPED]

# 台账上回填给「机械状态」字段时使用的键，避免多处拼写不一致。
STATUS_FIELD = "机械状态"
NEXT_MAINTENANCE_FIELD = "下次保养日"


def parse_maintenance_date(value: Any) -> date | None:
    """把「下次保养日」解析成日期；无法识别的历史填法返回 None，按无保养计划处理。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def derive_status(entry: dict[str, Any], *, today: date | None = None) -> str:
    """按统一口径计算单条机械记录当前应有的状态。"""
    today = today or date.today()
    stored = str(entry.get("status") or "").strip()
    # 1. 已报废：最高优先级，报废后不再参与任何到期判断。
    if stored == SCRAPPED:
        return SCRAPPED
    # 2. 保养中：以台账上的流转状态为准。
    if stored == IN_MAINTENANCE:
        return IN_MAINTENANCE
    # 3. 待保养：下次保养日已到或已过（当天也算到期）。
    next_date = parse_maintenance_date(entry.get(NEXT_MAINTENANCE_FIELD))
    if next_date is not None and next_date <= today:
        return DUE
    # 4. 可用：没有可识别保养计划，或保养日尚在未来。
    return AVAILABLE


def reconcile_equip(entry: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    """按统一口径把结论回填到机械记录上，返回同一条记录。

    回填只覆盖派生字段（status/pending/abnormal/机械状态）；
    机械编号、停放场地、保养日期等存量业务字段一律不动。
    """
    status = derive_status(entry, today=today)
    entry["status"] = status
    entry[STATUS_FIELD] = status
    entry["pending"] = status == DUE
    entry["abnormal"] = False
    return entry


def backfill_equips(rows: Iterable[dict[str, Any]], *, today: date | None = None) -> None:
    """存量机械记录按新口径逐条回填，不新增、不删除、不改业务字段。"""
    for row in rows:
        reconcile_equip(row, today=today)


def maintenance_due(rows: Iterable[dict[str, Any]], *, today: date | None = None) -> list[dict[str, Any]]:
    """保养提醒名单：与台账筛选「待保养」是同一份口径下的同一批记录。

    已报废、保养中的机械不会出现；判断前先按统一口径回填，保证与台账结论一致。
    """
    return [
        row for row in rows
        if reconcile_equip(row, today=today)["status"] == DUE
    ]


def summarize(rows: Iterable[dict[str, Any]], *, today: date | None = None) -> list[dict[str, Any]]:
    """统计卡片口径：台账与提醒页共用，前端只展示、不自行计数。"""
    counts = {DUE: 0, AVAILABLE: 0, IN_MAINTENANCE: 0, SCRAPPED: 0}
    total = 0
    for row in rows:
        total += 1
        counts[reconcile_equip(row, today=today)["status"]] += 1
    return [
        {"label": "在册机械", "value": total},
        {"label": "待保养机械", "value": counts[DUE]},
        {"label": "保养中机械", "value": counts[IN_MAINTENANCE]},
        {"label": "已报废机械", "value": counts[SCRAPPED]},
    ]
