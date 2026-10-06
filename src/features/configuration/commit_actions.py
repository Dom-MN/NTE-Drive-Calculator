# 编排基础权重页面的后台提交、草稿保留和提交后的异步刷新。
from __future__ import annotations

from src.i18n import tr

from copy import deepcopy

from PySide6.QtWidgets import QInputDialog, QMessageBox

from .dependencies import BasicWeightDependencies


_DIRTY_FIELDS = (
    "_config_dirty_character_ids", "_config_dirty_shape_bonus_ids",
    "_config_dirty_board_ids", "_config_dirty_target_suit_ids",
)


def _clear_draft(window, *, discard=False):
    window._config_dirty = False
    for field in _DIRTY_FIELDS:
        getattr(window, field, set()).clear()
    if discard:
        window._config_form_data = None
        window._config_loaded_model = None


def _submit(window, work, done, *, title, completion=None):
    from .page import _basic_weight_controller
    controller = _basic_weight_controller(window)
    if controller.is_writing():
        return False
    page = getattr(window, "config_page_view", None)
    status = getattr(window, "config_load_status", None)
    if page is not None:
        page.setEnabled(False)
    if status is not None:
        status.setText(tr("正在{title}…", title=tr(title)))

    def current():
        return (controller is getattr(window, "_basic_weight_controller", None)
                and controller.dependencies == BasicWeightDependencies.from_app_context(window.app_context))

    def unlock():
        if current():
            if page is not None:
                page.setEnabled(True)
            if status is not None:
                status.clear()

    def committed(value):
        unlock()
        if current():
            done(value)
            if completion is not None:
                completion(True)
        elif completion is not None:
            completion(False)

    def failed(error):
        unlock()
        if current():
            QMessageBox.warning(window, tr("{title}未完成", title=tr(title)), tr("编辑已保留；请核对已保存内容后重试。\n{error}", error=error))
            if completion is not None:
                completion(False)
        elif completion is not None:
            completion(False)

    def application_failed(error):
        unlock()
        if current():
            QMessageBox.warning(window, tr("提交后刷新失败"), tr("数据已提交，请重新进入页面刷新；不要重复保存。\n{error}", error=error))
            if completion is not None:
                completion(False)

    return controller.submit_change(work, committed, failed, application_failed)


def save_config_form(window, config_dir, json_edit_dialog_cls, *, completion=None, show_message=True):
    del config_dir, json_edit_dialog_cls
    from .page import _basic_weight_controller
    if getattr(window, "_current_config_name", None) != "account_weights":
        return False
    controller = _basic_weight_controller(window)
    data = deepcopy(getattr(window, "_config_form_data", {}) or {})
    fields = tuple(set(getattr(window, field, set())) for field in _DIRTY_FIELDS)

    def done(_value):
        _clear_draft(window)
        # The submitted model remains the display baseline, not a fresh database read.
        if show_message:
            QMessageBox.information(window, tr("保存"), tr("角色权重设置已保存。"))

    return _submit(window, lambda: controller.save_changes(data, *fields), done,
                   title="保存", completion=completion)


def _reload_after_weight_reset(window, config_dir, active_role):
    from .page import switch_config_form
    _clear_draft(window, discard=True)
    switch_config_form(window, config_dir=config_dir, active_role=active_role)


def _confirm_weight_reset(window, message):
    from .page import _basic_weight_controller
    if (getattr(window, "_current_config_name", None) != "account_weights"
            or _basic_weight_controller(window).is_writing()):
        return False
    return QMessageBox.question(window, tr("确认重置权重"), message,
                                QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) == QMessageBox.Yes


def reset_current_config_weights(window, config_dir):
    from .page import _basic_weight_controller
    name = str(getattr(window, "_config_active_role", "") or "")
    role = (getattr(window, "_config_form_data", {}) or {}).get(name) or {}
    if not name or not role:
        QMessageBox.information(window, tr("重置当前"), tr("请先选择一个角色。"))
        return
    if role.get("is_custom"):
        QMessageBox.information(window, tr("重置当前"), tr("自建角色没有发行默认权重，保留当前自定义值。"))
        return
    if not _confirm_weight_reset(window,
        f"将清除当前账号中 [{name}] 的自定义卡带主词条和驱动副词条权重，并恢复为当前异环工坊默认值。\n\n"
        "额外形状标签和额外形状加成不会改变；当前未保存编辑会丢弃。\n若权重未生效，请重启计算器。"):
        return
    controller, ids = _basic_weight_controller(window), (int(role["character_id"]),)

    def done(_value):
        _reload_after_weight_reset(window, config_dir, name)
        QMessageBox.information(window, tr("重置当前"), tr("[{name}] 已恢复为默认权重，后续可随新版本更新。", name=name))

    _submit(window, lambda: controller.reset_weights(ids), done, title="重置")


def reset_all_config_weights(window, config_dir):
    from .page import _basic_weight_controller
    data = getattr(window, "_config_form_data", {}) or {}
    ids = tuple(int(role["character_id"]) for role in data.values()
                if isinstance(role, dict) and role.get("character_id") is not None and not role.get("is_custom"))
    if not ids or not _confirm_weight_reset(window,
        f"将清除当前账号全部 {len(ids)} 名角色的自定义卡带主词条和驱动副词条权重，恢复为当前异环工坊默认值。\n\n"
        "此操作无法撤销；额外形状标签和额外形状加成不会改变，当前未保存编辑会丢弃。\n若权重未生效，请重启计算器。"):
        return
    controller, active = _basic_weight_controller(window), str(getattr(window, "_config_active_role", "") or "")

    def done(restored):
        _reload_after_weight_reset(window, config_dir, active)
        QMessageBox.information(window, tr("重置所有"), tr("已恢复 {restored_len} 名角色的默认权重，后续可随新版本更新。", restored_len=len(restored)))

    _submit(window, lambda: controller.reset_weights(ids), done, title="重置")


def reset_config_form(window, config_dir, bundled_config_dir):
    del bundled_config_dir
    _reload_after_weight_reset(window, config_dir, None)


def create_custom_role(window):
    from .page import _basic_weight_controller, confirm_pending_config_changes, switch_config_form
    controller = _basic_weight_controller(window)
    if controller.is_writing():
        return
    if getattr(window, "_config_dirty", False):
        if not confirm_pending_config_changes(window, window.app_context.paths.config_dir,
                completion=lambda success: create_custom_role(window) if success else None):
            return
    name, accepted = QInputDialog.getText(window, tr("新建角色"), tr("角色名称（也作为游戏内名称）："))
    if not accepted:
        return

    def done(role):
        _clear_draft(window, discard=True)
        switch_config_form(window, active_role=str(role["name_zh"]))

    _submit(window, lambda: controller.create_custom_role(str(name)), done, title=tr("新建角色"))


def delete_custom_role(window, role_name, role_data, rebuild_all_tabs):
    from .page import _basic_weight_controller
    controller = _basic_weight_controller(window)
    if controller.is_writing() or QMessageBox.question(window, tr("删除角色"),
        tr("删除 [{role_name}] 以及它的计算偏好和配装槽位？", role_name=role_name),
        QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel) != QMessageBox.Yes:
        return
    character_id = int(role_data["character_id"])

    def done(_value):
        # Match the existing deletion rule: remove this draft, retain other staged values.
        for field in _DIRTY_FIELDS:
            getattr(window, field, set()).discard(character_id)
        window._config_dirty = any(getattr(window, field, set()) for field in _DIRTY_FIELDS)
        (getattr(window, "_config_form_data", {}) or {}).pop(role_name, None)
        window._config_loaded_model = None
        rebuild_all_tabs()

    _submit(window, lambda: controller.delete_custom_role(character_id), done, title="删除角色")
