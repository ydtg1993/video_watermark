# src/gui/progress_dialog.py
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QProgressBar, QLabel

class ProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("处理进度")
        self.setModal(True)
        self.setFixedSize(400, 100)
        layout = QVBoxLayout(self)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.label = QLabel("准备中...")
        layout.addWidget(self.label)
        layout.addWidget(self.bar)

    def set_progress(self, value: int):
        self.bar.setValue(value)

    def set_status(self, text: str):
        self.label.setText(text)