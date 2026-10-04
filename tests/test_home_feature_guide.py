# 核对工作台按钮弹窗的入口、分模式步骤和无提示音实现。
from src.features.home.feature_guide import FEATURE_GUIDES
from src.services.allocation_filter_settings import AllocationFilterSettings


def test_feature_guides_have_correct_entry_and_navigation():
    guides = {guide.title: guide for guide in FEATURE_GUIDES}
    assert len(guides) == 6
    assert guides['基础计算'].entry == '计算'
    assert guides['配装功能'].entry == '配装'
    assert guides['弃置锁定'].entry == '低风险计算，中风险仓库（推荐）'
    assert guides['倒带推荐'].entry == '工具 → 倒带推荐'
    assert guides['边际计算'].entry == '战报 → 审计 → 边际计算'
    assert guides['边际计算'].destinations == (('前往战报', 'battle_report'),)
    assert {key for guide in FEATURE_GUIDES for _, key in guide.destinations} == {
        'execute', 'equipment', 'warehouse', 'identify', 'toolbox', 'battle_report',
    }


def test_feature_guides_preserve_requested_mode_instructions():
    guides = {guide.title: guide for guide in FEATURE_GUIDES}
    basic = guides['基础计算']
    assert basic.sections[0].lines[2].endswith('「保存配装」。')
    assert '背包同步（推荐）' in basic.sections[1].lines[0]
    assert '同步游戏数据（推荐）' in basic.sections[2].lines[0]
    disposal = guides['弃置锁定']
    assert (disposal.sections[0].title, disposal.sections[1].title) == ('低风险', '中风险')
    assert all(len(section.lines) == 3 and section.numbered for section in disposal.sections)
    assert '全量扫描' in disposal.sections[0].lines[0]
    assert '仓库' in disposal.sections[1].lines[0]
    assert '重算' in guides['边际计算'].sections[0].lines[2]


def test_new_allocation_limit_is_2000_but_saved_choice_survives():
    assert AllocationFilterSettings().blueprint_combo_limit == 2000
    assert AllocationFilterSettings.from_payload({}).blueprint_combo_limit == 2000
    assert AllocationFilterSettings.from_payload({'blueprint_combo_limit': 500}).blueprint_combo_limit == 500
