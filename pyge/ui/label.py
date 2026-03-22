"""
pyge/ui/label.py
================
Label -- UI-компонент отображения текста.

Возможности
-----------
  - Системный шрифт или .ttf/.otf из файла
  - Выравнивание: left / center / right
  - Перенос текста по ширине (wrap_width)
  - Тень (shadow) и обводка (outline)
  - Прозрачность (alpha)
  - Динамическое обновление: label.text = "..."

Пример
------
from pyge.ui.label import Label

obj = GameObject("HUD", x=20, y=20)
lbl = Label("Score: 0", font_size=28, color=(255,255,0), align="left")
obj.add_component(lbl)
scene.add(obj)

lbl.text = f"Score: {score}"   # обновить в любой момент
"""

from __future__ import annotations
import pygame
from pyge.component import Component


# ---------------------------------------------------------------------------
# FontCache
# ---------------------------------------------------------------------------

class FontCache:
    _cache: dict = {}

    @classmethod
    def get(cls, font_path, size: int, bold: bool, italic: bool) -> pygame.font.Font:
        key = (font_path, size, bold, italic)
        if key not in cls._cache:
            if font_path:
                cls._cache[key] = pygame.font.Font(font_path, size)
            else:
                cls._cache[key] = pygame.font.SysFont(None, size, bold=bold, italic=italic)
        return cls._cache[key]

    @classmethod
    def clear(cls) -> None:
        cls._cache.clear()


# ---------------------------------------------------------------------------
# Label
# ---------------------------------------------------------------------------

class Label(Component):
    """
    Текстовый UI-компонент.

    transform.position -- верхний левый угол (align="left"),
                          верхний центр     (align="center"),
                          верхний правый    (align="right").

    Параметры
    ---------
    text         : str        отображаемый текст (поддерживает \\n)
    font_size    : int        размер шрифта в пикселях
    font_path    : str|None   путь к .ttf / .otf или None (системный)
    color        : tuple      (R,G,B)
    bold         : bool
    italic       : bool
    align        : str        "left" | "center" | "right"
    wrap_width   : int        ширина переноса (0 = отключён)
    alpha        : int        0 (невидим) .. 255 (непрозрачен)
    shadow       : bool       рисовать тень
    shadow_color : tuple      (R,G,B)
    shadow_offset: tuple      (dx, dy) смещение тени
    outline      : int        толщина обводки в пикс (0 = нет)
    outline_color: tuple      (R,G,B)
    """

    def __init__(
        self,
        text: str = "",
        font_size: int = 24,
        font_path=None,
        color: tuple = (255, 255, 255),
        bold: bool = False,
        italic: bool = False,
        align: str = "left",
        wrap_width: int = 0,
        alpha: int = 255,
        shadow: bool = False,
        shadow_color: tuple = (0, 0, 0),
        shadow_offset: tuple = (2, 2),
        outline: int = 0,
        outline_color: tuple = (0, 0, 0),
    ) -> None:
        super().__init__()
        self._text         = text
        self.font_size     = font_size
        self.font_path     = font_path
        self.color         = color
        self.bold          = bold
        self.italic        = italic
        self.align         = align
        self.wrap_width    = wrap_width
        self.alpha         = alpha
        self.shadow        = shadow
        self.shadow_color  = shadow_color
        self.shadow_offset = shadow_offset
        self.outline       = outline
        self.outline_color = outline_color

        self._font: pygame.font.Font | None = None
        self._surfaces: list = []
        self._dirty: bool = True

    # --- свойство text ---

    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        if self._text != value:
            self._text = value
            self._dirty = True

    # --- размер (после первого рендера) ---

    @property
    def width(self) -> int:
        return max((s.get_width() for s in self._surfaces), default=0)

    @property
    def height(self) -> int:
        return sum(s.get_height() for s in self._surfaces)

    # --- жизненный цикл ---

    def on_awake(self) -> None:
        pygame.font.init()
        self._font = FontCache.get(self.font_path, self.font_size, self.bold, self.italic)
        self._dirty = True

    def on_render(self, screen: pygame.Surface) -> None:
        if self._font is None:
            return
        if self._dirty:
            self._rebuild()
            self._dirty = False

        x = int(self.transform.x)
        y = int(self.transform.y)

        for surf in self._surfaces:
            w = surf.get_width()
            if self.align == "center":
                dx = x - w // 2
            elif self.align == "right":
                dx = x - w
            else:
                dx = x
            screen.blit(surf, (dx, y))
            y += surf.get_height()

    # --- внутренние методы ---

    def _rebuild(self) -> None:
        self._surfaces.clear()
        for line in self._wrap(self._text):
            surf = self._render_line(line)
            if self.alpha != 255:
                surf = surf.copy()
                surf.set_alpha(self.alpha)
            self._surfaces.append(surf)

    def _render_line(self, line: str) -> pygame.Surface:
        font  = self._font
        color = self.color[:3]
        base  = font.render(line or " ", True, color)

        if not self.shadow and self.outline == 0:
            return base

        pad = max(
            (abs(self.shadow_offset[0]) + abs(self.shadow_offset[1])) if self.shadow else 0,
            self.outline * 2,
        )
        w = base.get_width()  + pad * 2
        h = base.get_height() + pad * 2
        result = pygame.Surface((w, h), pygame.SRCALPHA)
        ox, oy = pad, pad

        if self.shadow:
            sh = font.render(line or " ", True, self.shadow_color[:3])
            result.blit(sh, (ox + self.shadow_offset[0], oy + self.shadow_offset[1]))

        if self.outline > 0:
            ol = font.render(line or " ", True, self.outline_color[:3])
            for ddx in range(-self.outline, self.outline + 1):
                for ddy in range(-self.outline, self.outline + 1):
                    if ddx == 0 and ddy == 0:
                        continue
                    result.blit(ol, (ox + ddx, oy + ddy))

        result.blit(base, (ox, oy))
        return result

    def _wrap(self, text: str) -> list:
        raw = text.split("\n")
        if self.wrap_width <= 0 or self._font is None:
            return raw
        out = []
        for raw_line in raw:
            words   = raw_line.split(" ")
            current = ""
            for word in words:
                test = (current + " " + word).strip()
                if self._font.size(test)[0] <= self.wrap_width:
                    current = test
                else:
                    if current:
                        out.append(current)
                    current = word
            if current:
                out.append(current)
        return out if out else [""]

    def __repr__(self) -> str:
        return f"<Label '{self._text[:24]}' size={self.font_size}>"
