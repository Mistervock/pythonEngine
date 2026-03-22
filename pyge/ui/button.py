"""
pyge/ui/button.py
=================
Button -- интерактивный UI-компонент кнопки.

Возможности
-----------
  - Три визуальных состояния: normal / hover / pressed
  - Коллбэк on_click (callable или метод)
  - Текст на кнопке (встроенный Label)
  - Скруглённые углы (border_radius)
  - Иконка / спрайт вместо или рядом с текстом
  - Отключённое состояние (disabled)
  - Звук при клике (pygame.mixer)
  - Анимация нажатия (лёгкий scale-down)

Пример
------
from pyge.ui.button import Button

obj = GameObject("PlayBtn", x=400, y=300)
btn = Button(
    width=200, height=60,
    text="Play",
    font_size=28,
    on_click=lambda: app.load_scene(GameScene()),
    color_normal  = (60, 120, 220),
    color_hover   = (80, 150, 255),
    color_pressed = (40,  90, 180),
    border_radius = 12,
    pivot         = (0.5, 0.5),   # центр кнопки = transform.position
)
obj.add_component(btn)
scene.add(obj)
"""

from __future__ import annotations
import pygame
from pyge.component import Component
from pyge.ui.label import Label, FontCache


# ---------------------------------------------------------------------------
# Состояния кнопки
# ---------------------------------------------------------------------------

class _BtnState:
    NORMAL  = "normal"
    HOVER   = "hover"
    PRESSED = "pressed"


# ---------------------------------------------------------------------------
# Button
# ---------------------------------------------------------------------------

class Button(Component):
    """
    Интерактивная кнопка.

    transform.position -- опорная точка кнопки (см. pivot).

    Параметры
    ---------
    width, height  : int     размер кнопки в пикселях
    text           : str     текст на кнопке
    font_size      : int     размер шрифта
    font_path      : str|None
    text_color     : tuple   (R,G,B)
    on_click       : callable | None   вызывается при отпускании ЛКМ внутри кнопки
    color_normal   : tuple   фон в нормальном состоянии
    color_hover    : tuple   фон при наведении
    color_pressed  : tuple   фон при нажатии
    border_color   : tuple | None   цвет рамки (None = нет рамки)
    border_width   : int     толщина рамки
    border_radius  : int     скруглённые углы (0 = нет)
    pivot          : tuple   (px, py) -- точка привязки:
                             (0,0)=верх-лево  (0.5,0.5)=центр  (1,1)=право-низ
    disabled       : bool    кнопка неактивна (не реагирует на клики)
    disabled_color : tuple   фон в отключённом состоянии
    click_sound    : str | None  путь к .wav/.ogg (pygame.mixer)
    press_scale    : float   масштаб при нажатии (0.95 = лёгкое уменьшение)
    """

    def __init__(
        self,
        width: int = 160,
        height: int = 50,
        text: str = "Button",
        font_size: int = 22,
        font_path=None,
        text_color: tuple = (255, 255, 255),
        on_click=None,
        color_normal:   tuple = (70,  130, 220),
        color_hover:    tuple = (100, 160, 255),
        color_pressed:  tuple = (50,  100, 190),
        border_color=None,
        border_width: int = 2,
        border_radius: int = 8,
        pivot: tuple = (0.5, 0.5),
        disabled: bool = False,
        disabled_color: tuple = (100, 100, 100),
        click_sound=None,
        press_scale: float = 0.95,
    ) -> None:
        super().__init__()

        self.width          = width
        self.height         = height
        self.text           = text
        self.font_size      = font_size
        self.font_path      = font_path
        self.text_color     = text_color
        self.on_click       = on_click
        self.color_normal   = color_normal
        self.color_hover    = color_hover
        self.color_pressed  = color_pressed
        self.border_color   = border_color
        self.border_width   = border_width
        self.border_radius  = border_radius
        self.pivot          = pivot
        self.disabled       = disabled
        self.disabled_color = disabled_color
        self.press_scale    = press_scale

        self._state         = _BtnState.NORMAL
        self._font: pygame.font.Font | None = None
        self._sound         = None
        self._click_sound_path = click_sound

        # Анимация нажатия
        self._current_scale: float = 1.0
        self._target_scale:  float = 1.0
        self._SCALE_SPEED:   float = 12.0   # скорость возврата

        # Публичные события (дополнительно к on_click)
        self.on_hover_enter: callable | None = None
        self.on_hover_exit:  callable | None = None
        self.on_press:       callable | None = None

    # ------------------------------------------------------------------
    # Жизненный цикл
    # ------------------------------------------------------------------

    def on_awake(self) -> None:
        pygame.font.init()
        self._font = FontCache.get(self.font_path, self.font_size, False, False)

        if self._click_sound_path:
            try:
                pygame.mixer.init()
                self._sound = pygame.mixer.Sound(self._click_sound_path)
            except Exception:
                self._sound = None

    def on_update(self) -> None:
        # Плавный возврат масштаба
        from pyge.engine import Time
        diff = self._target_scale - self._current_scale
        self._current_scale += diff * self._SCALE_SPEED * Time.delta_time
        if abs(diff) < 0.001:
            self._current_scale = self._target_scale

    def on_event(self, event: pygame.event.Event) -> None:
        if not self.enabled or self.disabled:
            return

        rect = self._get_rect()

        if event.type == pygame.MOUSEMOTION:
            was_hover = self._state in (_BtnState.HOVER, _BtnState.PRESSED)
            now_hover = rect.collidepoint(event.pos)

            if now_hover and not was_hover:
                self._state = _BtnState.HOVER
                if callable(self.on_hover_enter):
                    self.on_hover_enter()

            elif not now_hover and was_hover:
                self._state = _BtnState.NORMAL
                self._target_scale = 1.0
                if callable(self.on_hover_exit):
                    self.on_hover_exit()

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if rect.collidepoint(event.pos):
                self._state = _BtnState.PRESSED
                self._target_scale = self.press_scale
                if callable(self.on_press):
                    self.on_press()

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._state == _BtnState.PRESSED:
                if rect.collidepoint(event.pos):
                    # Успешный клик
                    if self._sound:
                        self._sound.play()
                    if callable(self.on_click):
                        self.on_click()
                self._state = _BtnState.HOVER if rect.collidepoint(event.pos) else _BtnState.NORMAL
                self._target_scale = 1.0

    def on_render(self, screen: pygame.Surface) -> None:
        rect = self._get_rect()
        s    = self._current_scale

        # Применить анимацию масштаба
        if abs(s - 1.0) > 0.001:
            dw = int(rect.width  * (1 - s) / 2)
            dh = int(rect.height * (1 - s) / 2)
            rect = pygame.Rect(
                rect.x + dw, rect.y + dh,
                rect.width - dw * 2, rect.height - dh * 2,
            )

        # Выбрать цвет фона
        if self.disabled:
            bg = self.disabled_color
        elif self._state == _BtnState.PRESSED:
            bg = self.color_pressed
        elif self._state == _BtnState.HOVER:
            bg = self.color_hover
        else:
            bg = self.color_normal

        # Фон кнопки
        pygame.draw.rect(screen, bg, rect, border_radius=self.border_radius)

        # Рамка
        if self.border_color:
            pygame.draw.rect(screen, self.border_color, rect,
                             width=self.border_width,
                             border_radius=self.border_radius)

        # Текст по центру
        if self._font and self.text:
            text_color = (160, 160, 160) if self.disabled else self.text_color
            text_surf  = self._font.render(self.text, True, text_color[:3])
            tx = rect.centerx - text_surf.get_width()  // 2
            ty = rect.centery - text_surf.get_height() // 2
            screen.blit(text_surf, (tx, ty))

    # ------------------------------------------------------------------
    # Вспомогательные
    # ------------------------------------------------------------------

    def _get_rect(self) -> pygame.Rect:
        """Вычислить pygame.Rect кнопки с учётом pivot."""
        tx = self.transform.x
        ty = self.transform.y
        x  = int(tx - self.width  * self.pivot[0])
        y  = int(ty - self.height * self.pivot[1])
        return pygame.Rect(x, y, self.width, self.height)

    @property
    def rect(self) -> pygame.Rect:
        """Публичный доступ к прямоугольнику кнопки."""
        return self._get_rect()

    @property
    def is_hovered(self) -> bool:
        return self._state == _BtnState.HOVER

    @property
    def is_pressed(self) -> bool:
        return self._state == _BtnState.PRESSED

    def set_text(self, text: str) -> None:
        """Изменить текст кнопки."""
        self.text = text

    def __repr__(self) -> str:
        return f"<Button '{self.text}' {self.width}x{self.height} state={self._state}>"
