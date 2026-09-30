"""养护机械接口：维护养护机械，覆盖安排保养、确认可用、报废机械等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult, ReminderResult
from app.services import equip_rules as rules
from app.services.equip import EquipService

router = APIRouter(prefix="/api/equip", tags=["养护机械"])

service = EquipService()

LIST_FIELDS = ["机械编号", "机械名称", "机械型号", "停放场地", "上次保养日", "下次保养日", "责任人", "机械状态"]
STATUSES = rules.STATUS_ORDER


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按机械编号检索"),
    status: str | None = Query(default=None, description="待保养、可用、保养中、已报废"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按机械编号与状态过滤养护机械列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/maintenance-reminders", response_model=ReminderResult)
def maintenance_reminders(
    keyword: str | None = Query(default=None, description="按机械编号检索"),
    page: int = 1,
    size: int = 20,
) -> ReminderResult:
    """保养提醒：与机械台账共用同一份判定口径，只返回服务端判为待保养的机械。

    界面不得自行用保养日期临时判断；已报废的机械在统一口径下不是待保养，
    因此不会再出现在提醒里。
    """
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_due(keyword=keyword, page=page, size=size)
    summary = service.status_summary()
    return ReminderResult(
        items=items,
        total=total,
        page=page,
        size=size,
        status_summary=summary,
    )


@router.get("/status-summary")
def status_summary() -> dict[str, int]:
    """台账状态统计：台账页与提醒页都读这里，保证卡片结论一致。"""
    return service.status_summary()


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出养护机械清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "equip", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条养护机械明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"养护机械 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条养护机械，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="养护机械已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条养护机械执行安排保养、确认可用、报废机械；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
