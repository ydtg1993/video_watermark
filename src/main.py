import sys
from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QFont
from qfluentwidgets import setTheme, Theme,FluentWindow,setThemeColor
from src.core.ffmpeg import check_ffmpeg
from src.gui.main_window import MainWindow


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei", 10))

    setTheme(Theme.DARK)  # 深色主题启动
    app.setStyleSheet("QLabel { color: #e0e0e0; }")

    if not check_ffmpeg():
        QMessageBox.critical(None, "错误", "未检测到 ffmpeg / ffprobe\n请安装后重试")
        sys.exit(1)

    win = MainWindow()
    win.setWindowFlags(
            Qt.FramelessWindowHint
    )
    win.resize(1600, 960)
    win.setMinimumSize(1400, 860)
    win.show()

    QTimer.singleShot(1000, lambda: win.gpu_indicator.start_monitoring())
    sys.exit(app.exec())


if __name__ == "__main__":
    main()