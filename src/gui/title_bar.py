from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtGui import QPalette, QColor
from qfluentwidgets import ToolButton, FluentIcon as FIF


class TitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.dragPos = QPoint()
        self.setFixedHeight(36)

        # 直接设置调色板背景色，绕过 QSS 主题覆盖
        pal = self.palette()
        pal.setColor(QPalette.Window, QColor("#0a0a0a"))
        self.setAutoFillBackground(True)
        self.setPalette(pal)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题
        self.titleLabel = QLabel("修影器")
        self.titleLabel.setStyleSheet("color: #e0e0e0; font-size: 14px; padding-left: 12px;")
        layout.addWidget(self.titleLabel)
        layout.addStretch()

        # 按钮通用样式模板
        btn_style = """
                    QToolButton {
                        color: #e0e0e0;
                        border: none;
                        padding: 0 5px;
                        min-width: 46px;
                        min-height: 36px;
                    }
                    QToolButton:hover {
                        background: #2d2d2d;
                    }
                """
        close_btn_style = """
                    QToolButton {
                        color: #e0e0e0;
                        border: none;
                        padding: 0 5px;
                        min-width: 46px;
                        min-height: 36px;
                    }
                    QToolButton:hover {
                        background: #e81123;
                    }
                """

        # 最小化按钮
        self.minBtn = ToolButton(FIF.MINIMIZE)
        self.minBtn.setStyleSheet(btn_style)
        self.minBtn.clicked.connect(parent.showMinimized)

        # 最大化按钮
        self.maxBtn = ToolButton(FIF.FULL_SCREEN)
        self.maxBtn.setStyleSheet(btn_style)
        self.maxBtn.clicked.connect(self.toggleMaxRestore)

        # 关闭按钮
        self.closeBtn = ToolButton(FIF.CLOSE)
        self.closeBtn.setStyleSheet(close_btn_style)
        self.closeBtn.clicked.connect(parent.close)

        layout.addWidget(self.minBtn)
        layout.addWidget(self.maxBtn)
        layout.addWidget(self.closeBtn)

    def toggleMaxRestore(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            if not self.parent.isMaximized():
                self.parent.move(
                    self.parent.pos() +
                    event.globalPosition().toPoint() -
                    self.dragPos
                )
                self.dragPos = event.globalPosition().toPoint()

    def mouseDoubleClickEvent(self, event):
        self.toggleMaxRestore()
