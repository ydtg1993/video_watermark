from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QDialogButtonBox, QAbstractItemView

class HistoryDialog(QDialog):
    """历史记录对话框（Fluent 风格）"""
    def __init__(self, records, parent=None):
        super().__init__(parent)
        self.setWindowTitle("历史记录")
        self.resize(500, 400)
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.NoSelection)
        for rec in records:
            item = QListWidgetItem(f"{rec['time']}  {rec['source']}\n    → {rec['output']} [{rec['status']}]")
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok)
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)