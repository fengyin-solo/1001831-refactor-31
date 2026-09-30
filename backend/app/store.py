"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
"""
from __future__ import annotations

from typing import Any

from app.seed import SEED_ROWS
from app.services import equip_rules


def _backfill_existing_rows() -> dict[str, list[dict[str, Any]]]:
    """载入示例数据后，按各模块的统一口径回填存量记录。

    养护机械的「保养到期/可用/报废」结论只保留 equip_rules 一份：回填只改写口径
    推导出的状态字段，机械记录本身（编号、名称、型号）、停放场地、保养日期等
    存量数据原样保留。
    """
    tables: dict[str, list[dict[str, Any]]] = {
        name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
    }
    for row in tables.get("equip", []):
        equip_rules.apply_status(row)
    return tables


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = _backfill_existing_rows()

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
