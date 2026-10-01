"""养护机械业务规则：状态流转、字段校验与筛选口径都收在这里。

状态怎么算只有 app.services.equip_rules 一份，本服务负责调用它完成台账查询、
保养提醒、动作流转与登记；任何接口和界面都不允许再自行判断到期/可用/报废。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.services import equip_rules as rules
from app.store import store

MODULE = "equip"
REQUIRED_FIELDS = ["机械编号", "机械名称", "机械型号"]
# 登记时允许一并落库的存量业务字段，统一口径不改变这些字段的既有取值。
OPTIONAL_FIELDS = ["停放场地", "上次保养日", "下次保养日", "责任人"]
STATUS_ORDER = rules.STATUS_ORDER
ACTION_RULES = {"安排保养": rules.IN_MAINTENANCE, "确认可用": rules.AVAILABLE, "报废机械": rules.SCRAPPED}
NEGATIVE_ACTIONS = []


class EquipService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
        today: date | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        # 读出台账先按统一口径重算：以服务端台账为准，任何历史临时结论一律作废。
        rows = [rules.reconcile_equip(row, today=today) for row in rows]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("机械编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def list_reminders(
        self,
        *,
        keyword: str | None = None,
        page: int = 1,
        size: int = 20,
        today: date | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """保养提醒名单：直接取台账按「待保养」筛出的同一批记录。"""
        return self.list_entries(keyword=keyword, status=rules.DUE, page=page, size=size, today=today)

    def stats(self, *, today: date | None = None) -> list[dict[str, Any]]:
        return rules.summarize(store.rows(MODULE), today=today)

    def get_entry(self, entry_id: int, *, today: date | None = None) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return rules.reconcile_equip(entry, today=today)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        for field in OPTIONAL_FIELDS:
            if str(values.get(field) or "").strip():
                entry[field] = values.get(field)
        # 新登记机械没有报废/保养中流转记录，统一口径会据保养日给出待保养或可用。
        entry["status"] = ""
        rows.append(entry)
        return rules.reconcile_equip(entry), []

    def run_action(self, entry_id: int, action: str, *, today: date | None = None) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"养护机械 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于养护机械可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        # 已报废是终态，任何继续流转都拒绝，避免报废机械又被排进保养。
        if rules.derive_status(entry, today=today) == rules.SCRAPPED:
            return None, "该机械已报废，不能再安排保养或确认可用"
        entry["status"] = target
        # 动作完成后仍以统一口径回填，保证台账与保养提醒立即得到同样结论。
        rules.reconcile_equip(entry, today=today)
        return entry, f"养护机械已{action}"
