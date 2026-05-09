"""
GPU 实时监控指示器
显示在状态栏或设置面板中，展示编码器/GPU使用率
"""
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt, QTimer
from ...core.gpu_monitor import GPUMonitor


class GPUIndicator(QFrame):
    """小型 GPU 状态指示器"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gpuIndicator")
        self.setFixedHeight(24)
        self._setup_ui()
        self._monitor = None
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update_display)

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)
        self.icon_label = QLabel("🖥")
        self.icon_label.setFixedWidth(16)
        self.gpu_label = QLabel("--")
        self.gpu_label.setObjectName("gpuValue")
        self.gpu_label.setFixedWidth(40)
        self.encoder_label = QLabel("ENC: --")
        self.encoder_label.setObjectName("encoderValue")
        self.encoder_label.setFixedWidth(60)
        self.temp_label = QLabel("🌡--°")
        self.temp_label.setObjectName("tempValue")
        layout.addWidget(self.icon_label)
        layout.addWidget(self.gpu_label)
        layout.addWidget(self.encoder_label)
        layout.addWidget(self.temp_label)
        layout.addStretch()

    def start_monitoring(self):
        """开始监控"""
        if not self._monitor:
            self._monitor = GPUMonitor(interval=2.0)  # 2秒刷新一次
            self._monitor.data_updated.connect(self._on_gpu_data)
            self._monitor.start()
            self._update_timer.start(2000)  # 备用定时器

    def stop_monitoring(self):
        """停止监控"""
        if self._monitor:
            self._monitor.stop()
            self._monitor = None
        self._update_timer.stop()

    def _on_gpu_data(self, data):
        """接收 GPU 数据更新"""
        gpu = data.get('gpu', 0)
        enc = data.get('encoder', 0)
        temp = data.get('temp', 0)
        self.gpu_label.setText(f"{gpu}%")
        self.encoder_label.setText(f"ENC:{enc}%")
        self.temp_label.setText(f"🌡{temp}°")
        # 根据负载改变颜色提示
        if gpu > 80 or enc > 80:
            self.setStyleSheet("QLabel#gpuValue { color: #f85149; }")
        elif gpu > 50:
            self.setStyleSheet("QLabel#gpuValue { color: #d29922; }")
        else:
            self.setStyleSheet("")

    def _update_display(self):
        """备用更新（当 monitor 无数据时）"""
        pass  # 主要由 signal 驱动

    def showEvent(self, event):
        super().showEvent(event)
        # 可选：显示时自动启动

    def hideEvent(self, event):
        super().hideEvent(event)
        # 可选：隐藏时自动停止以节省资源