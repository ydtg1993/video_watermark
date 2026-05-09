from pathlib import Path

THEMES = {
    "dark": "dark_theme.qss",
    "light": "light_theme.qss"
}


class ThemeManager:
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent / "styles"
        self.icons_dir = Path(__file__).parent.parent / "icons"
        self._current = "dark"

    @property
    def current_theme(self) -> str:
        return self._current

    def set_theme(self, name: str):
        if name in THEMES:
            self._current = name

    def load_stylesheet(self, name=None) -> str:
        theme = name or self._current
        qss_path = self.base_dir / THEMES.get(theme, "")
        if qss_path.exists():
            return qss_path.read_text(encoding="utf-8")
        return ""

    def icon_path(self, name: str) -> Path:
        """返回当前主题下对应图标的完整路径"""
        theme_subdir = f"{self._current}_theme"
        return self.icons_dir / theme_subdir / f"{name}.svg"