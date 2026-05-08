import sys

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QFont

from src.core.ffmpeg import check_ffmpeg
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    # ✅ 强制统一字体（解决 DirectWrite 问题）
    app.setFont(QFont("Microsoft YaHei", 10))

    if not check_ffmpeg():
        QMessageBox.critical(
            None,
            "错误",
            "未检测到 ffmpeg / ffprobe，请先安装并加入 PATH"
        )
        sys.exit(1)

    win = MainWindow()
    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()