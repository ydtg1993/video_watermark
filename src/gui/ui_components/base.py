"""
UI 基础工厂 - 消除重复代码的核心
提供统一的控件创建方法，确保样式一致且便于全局修改
"""
from PySide6.QtWidgets import (
    QPushButton, QLabel, QSpinBox, QDoubleSpinBox,
    QLineEdit, QComboBox, QCheckBox, QHBoxLayout, QWidget,
    QFrame, QVBoxLayout, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIcon

class UIBaseMixin:
    """UI 创建混入类，提供标准化的控件工厂方法"""

    # ==================== 按钮工厂 ====================
    def create_btn(self, text="", icon_text=None, obj_name="navButton",
                   tooltip=None, checkable=False, checked=False,
                   fixed_size=None, click_handler=None, enabled=True):
        """
        统一创建按钮
        Args:
            text: 显示文本（优先级低于 icon_text）
            icon_text: 图标文字（如 ⚡📋⚙）
            obj_name: QSS 样式对象名
            tooltip: 鼠标悬停提示
            checkable: 是否可选中
            fixed_size: 固定大小 (w, h) 或 None 或 int(正方形)
            click_handler: 点击事件槽函数
            enabled: 是否启用
        """
        btn = QPushButton(icon_text or text)
        btn.setObjectName(obj_name)
        if tooltip:
            btn.setToolTip(tooltip)
        if checkable:
            btn.setCheckable(True)
            if checked:
                btn.setChecked(True)
        if fixed_size is not None:
            if isinstance(fixed_size, int):
                btn.setFixedSize(fixed_size, fixed_size)
            elif isinstance(fixed_size, tuple) and len(fixed_size) == 2:
                btn.setFixedSize(fixed_size[0], fixed_size[1])
        btn.setEnabled(enabled)
        if click_handler:
            btn.clicked.connect(click_handler)
        return btn

    def create_icon_btn(self, icon_name, tooltip=None,
                        checkable=False, checked=False,
                        obj_name="navButton", fixed_size=None,
                        click_handler=None, enabled=True):
        btn = QPushButton()
        btn.setEnabled(enabled)
        btn.setObjectName(obj_name)
        if tooltip:
            btn.setToolTip(tooltip)
        if checkable:
            btn.setCheckable(True)
            if checked:
                btn.setChecked(True)
        if fixed_size is not None:
            if isinstance(fixed_size, int):
                btn.setFixedSize(fixed_size, fixed_size)
            elif isinstance(fixed_size, tuple) and len(fixed_size) == 2:
                btn.setFixedSize(fixed_size[0], fixed_size[1])
        if click_handler:
            btn.clicked.connect(click_handler)
        # 设置当前主题图标
        self._set_icon_on_button(btn, icon_name)
        return btn

    def _set_icon_on_button(self, btn, icon_name):
        if not hasattr(self, 'theme_manager') or not self.theme_manager:
            print("警告：未设置 theme_manager，图标将保持空白")
            return
        path = self.theme_manager.icon_path(icon_name)
        if path.exists():
            btn.setIcon(QIcon(str(path)))
        else:
            print(f"图标缺失: {path}")

    def create_label_row(self, label_text, widget, label_width=60):
        """创建标准的 "标签: [控件]" 水平布局"""
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(label_text)
        lbl.setFixedWidth(label_width)
        lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(lbl)
        row.addWidget(widget, 1)
        return row

    # ==================== 坐标输入工厂 ====================
    def create_coord_spins(self, prefix_list=["X", "Y", "W", "H"],
                           range_max=9999, value_changed_handler=None):
        """批量创建坐标输入框 (X Y W H)"""
        spins = []
        for prefix in prefix_list:
            spin = QSpinBox()
            spin.setObjectName("coordSpin")
            spin.setPrefix(f"{prefix} ")
            spin.setRange(0, range_max)
            spin.setAlignment(Qt.AlignCenter)
            if value_changed_handler:
                spin.valueChanged.connect(value_changed_handler)
            spins.append(spin)
        return spins

    # ==================== 输入框行工厂 ====================
    def create_input_row(self, label_text, placeholder="", read_only=False,
                         browse_handler=None, browse_text="浏览",
                         fixed_btn_size=(60, 32)):
        """创建带浏览按钮的输入框行"""
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        if read_only:
            edit.setReadOnly(True)
        btn = None
        if browse_handler:
            btn = self.create_btn(browse_text, obj_name="toolbarButton",
                                  fixed_size=fixed_btn_size, click_handler=browse_handler)
        row = QHBoxLayout()
        row.addWidget(edit, 1)
        if btn:
            row.addWidget(btn)
        return edit, btn, row

    # ==================== 下拉框行工厂 ====================
    def create_combo_row(self, label_text, items, current_index=0, change_handler=None):
        """创建标签+下拉框"""
        combo = QComboBox()
        combo.addItems(items)
        combo.setCurrentIndex(current_index)
        combo.setMinimumHeight(36)
        if change_handler:
            combo.currentIndexChanged.connect(change_handler)
        row = self.create_label_row(label_text, combo)
        return combo, row

    # ==================== 复选框工厂 ====================
    def create_checkbox(self, text, checked=False, state_change_handler=None):
        cb = QCheckBox(text)
        cb.setChecked(checked)
        if state_change_handler:
            cb.stateChanged.connect(state_change_handler)
        return cb

    # ==================== 数值输入行工厂 ====================
    def create_double_spin_row(self, label_text, min_val=0.0, max_val=1.0,
                               default=0.8, step=0.1, prefix="", suffix=""):
        """创建浮点数输入行"""
        spin = QDoubleSpinBox()
        spin.setRange(min_val, max_val)
        spin.setSingleStep(step)
        spin.setValue(default)
        if prefix:
            spin.setPrefix(prefix)
        if suffix:
            spin.setSuffix(suffix)
        row = self.create_label_row(label_text, spin)
        return spin, row

    # ==================== 分组标题工厂 ====================
    def create_section_header(self, title, action_btn=None):
        """创建带可选操作按钮的区域标题行"""
        header = QHBoxLayout()
        lbl = QLabel(title)
        lbl.setStyleSheet("font-weight: bold; color: var(--text-primary);")
        header.addWidget(lbl)
        header.addStretch()
        if action_btn:
            header.addWidget(action_btn)
        return header


class StyledWidget(QFrame):
    """带样式的基类 Widget，用于复杂面板组件"""
    def __init__(self, obj_name=None, parent=None):
        super().__init__(parent)
        if obj_name:
            self.setObjectName(obj_name)
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(16, 16, 16, 16)
        self._main_layout.setSpacing(12)
        self._build_ui()

    def _build_ui(self):
        """子类重写此方法，将子控件添加到 self._main_layout 中"""
        pass

    def _setup_ui(self):
        """子类重写此方法构建UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
