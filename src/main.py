import sys
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QFont
from src.core.ffmpeg import check_ffmpeg
from src.gui.main_window import MainWindow
from src.core.theme_manager import ThemeManager


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))

    theme_mgr = ThemeManager()
    qss = theme_mgr.load_stylesheet()
    if qss:
        app.setStyleSheet(qss)

    if not check_ffmpeg():
        QMessageBox.critical(None, "错误", "未检测到 ffmpeg / ffprobe\n请安装后重试")
        sys.exit(1)

    win = MainWindow()
    win.show()

    # 延迟初始化 GPU 监控（窗口显示后）
    QTimer.singleShot(1000, lambda: (
            hasattr(win, 'gpu_indicator') and
            win.gpu_indicator.start_monitoring()
    ))

    sys.exit(app.exec())

if __name__ == "__main__":
    main()