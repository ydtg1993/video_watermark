from PySide6.QtWidgets import QLabel, QMainWindow
from .gpu_indicator import GPUIndicator

def setup_status_bar(window: QMainWindow):
    """
    配置主窗口状态栏，返回 (status_label, gpu_indicator)
    """
    status_bar = window.statusBar()
    status_bar.setStyleSheet("""
        QStatusBar {
            background-color: #0a0a0a;
            color: #e0e0e0;
        }
        QLabel {
            color: #e0e0e0;
        }
    """)
    status_label = QLabel("准备就绪")
    status_bar.addWidget(status_label, 1)

    gpu_indicator = GPUIndicator()
    status_bar.addPermanentWidget(gpu_indicator)

    return status_label, gpu_indicator