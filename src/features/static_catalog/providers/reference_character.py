# 使用资料库现有只读视图展示未完整角色，独立于计算角色列表。
import json
from pathlib import Path

from src.features.static_catalog.contracts import (
    CatalogDetail, CatalogDomain, CatalogItem, CatalogPage, CatalogSection,
)
from src.features.static_catalog.providers._shared import annotation, official, ensure_release_path
from src.storage.sqlite.catalog.static_catalog_reference_characters import ReferenceCharacterQueries


class ReferenceCharacterProvider:
    domain = CatalogDomain('reference_characters', '未完整角色', '已知资料与缺项；仅供查看，不参与计算', 15)

    def __init__(self, database_path):
        self._path = Path(database_path).resolve()
        self._queries = ReferenceCharacterQueries(self._path)

    def close(self):
        self._queries.close()

    def _item(self, row):
        return CatalogItem(self.domain.key, str(row['character_id']), row['name_zh'],
                           '数据未完整 · 仅供查看 · 不参与计算')

    def search(self, release, *, query, offset, limit):
        ensure_release_path(release, self._path)
        rows = [r for r in self._queries.entries()
                if str(query).casefold() in f"{r['character_id']} {r['name_zh']}".casefold()]
        offset, limit = max(0, int(offset)), max(1, min(100, int(limit)))
        return CatalogPage(tuple(self._item(r) for r in rows[offset:offset+limit]), len(rows), offset, limit)

    def detail(self, release, record_id):
        ensure_release_path(release, self._path)
        row = next((r for r in self._queries.entries() if str(r['character_id']) == record_id), None)
        if row is None:
            return None
        reason = row['reason_zh']
        if reason.startswith('missing_likeability_modifier:'):
            reason = '好感度加成配置缺失，养成数据未完整。'
        sections = [CatalogSection('数据状态', (
            annotation('可用范围', '仅供查看，不参与配装、伤害计算或反事实'),
            annotation('缺项', reason),
            annotation('说明', '以下为当前资料来源中的配置；占位内容与未提供字段保留原样，不代表完整实装。'),
        ))]
        for section in json.loads(row['sections_json']):
            fields = tuple(official(k, v) for k, v in section['fields'])
            if any(k == '觉醒／共鸣说明' for k, _ in section['fields']):
                fields = (annotation('验证状态', '觉醒配置尚未确认；含其他角色名称的内容属于待核对占位，不作为本角色效果。'), *fields)
            sections.append(CatalogSection(section['title'], fields))
        return CatalogDetail(self._item(row), tuple(sections))
