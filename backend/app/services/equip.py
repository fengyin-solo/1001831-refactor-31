"""养护机械业务规则：状态流转、字段校验、筛选口径与保养提醒。

所有「保养到期 / 可用 / 报废」的判定都委托给 equip_rules 这一份口径，
台账列表、保养提醒、存量回填共用同一结论，本模块不再自行判断状态。
"""
from __future__ import annotations

from typing import Any

from app.services import equip_rules as rules
from app.store import store

MODULE = "equip"
REQUIRED_FIELDS = ["机械编号", "机械名称", "机械型号"]
STATUS_ORDER = rules.STATUS_ORDER
ACTION_RULES = rules.ACTION_RULES
NEGATIVE_ACTIONS: list[str] = []


class EquipService:
    # ---- 统一口径：读出台账时先按服务端口径回填，保证提醒与台账结论一致 ----

    def _reconciled_rows(self) -> list[dict[str, Any]]:
        return [rules.apply_status(row) for row in store.rows(MODULE)]

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = self._reconciled_rows()
        if keyword:
            rows = [row for row in rows if keyword in str(row.get(rules.CODE_FIELD, ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def list_due(
        self,
        *,
        keyword: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """保养提醒清单：只取统一口径判为待保养的机械，已报废机械天然被排除。"""
        rows = [row for row in self._reconciled_rows() if rules.is_due(row)]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get(rules.CODE_FIELD, ""))]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def status_summary(self) -> dict[str, int]:
        """台账各状态数量；统计同样走统一口径，供台账与提醒页面共用。"""
        summary = {status: 0 for status in STATUS_ORDER}
        for row in self._reconciled_rows():
            summary[str(row["status"])] = summary.get(str(row["status"]), 0) + 1
        return summary

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return rules.apply_status(entry)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry[rules.NEXT_MAINT_FIELD] = values.get(rules.NEXT_MAINT_FIELD)
        entry[rules.LAST_MAINT_FIELD] = values.get(rules.LAST_MAINT_FIELD)
        entry["停放场地"] = values.get("停放场地")
        entry["责任人"] = values.get("责任人")
        entry["status"] = STATUS_ORDER[0]
        rows.append(entry)
        return rules.apply_status(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"养护机械 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于养护机械可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        # 动作后仍由统一口径回填结论，保养提醒读取到的状态与台账保持一致。
        rules.apply_status(entry)
        return entry, f"养护机械已{action}"
