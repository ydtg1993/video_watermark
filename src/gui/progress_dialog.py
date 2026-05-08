from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar, QPushButton, QApplication
)
from PySide6.QtCore import Qt, QTimer

class ProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("处理进度")
        self.setFixedSize(400, 120)
        self.setWindowModality(Qt.NonModal)

        layout = QVBoxLayout(self)
        self.label = QLabel("准备中...")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.cancel_btn = QPushButton("取消")
        layout.addWidget(self.label)
        layout.addWidget(self.bar)
        layout.addWidget(self.cancel_btn)

        self._timer = QTimer(self)
        self._timer.timeout.connect(lambda: QApplication.processEvents())
        self._timer.start(100)

    def set_progress(self, value: int):
        self.bar.setValue(value)
        QApplication.processEvents()

    def set_status(self, text: str):
        self.label.setText(text)
        QApplication.processEvents()