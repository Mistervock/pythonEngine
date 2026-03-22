"""
pyge/input.py
=============
Глобальный менеджер ввода. Обёртка над pygame для удобной работы
с клавиатурой и мышью в стиле Unity.

Использование
-------------
from pyge.input import Input

class PlayerMover(Component):
    def on_update(self) -> None:
        # Клавиатура
        if Input.key_held("right"):
            self.transform.x += 200 * Time.delta_time

        if Input.key_down("space"):       # нажата ИМЕННО в этот кадр
            self.jump()

        if Input.key_up("shift"):         # отпущена ИМЕННО в этот кадр
            self.stop_run()

        # Мышь
        if Input.mouse_button_down(1):    # ЛКМ нажата в этот кадр
            print("клик в", Input.mouse_position)

        dx, dy = Input.mouse_delta        # смещение мыши за кадр

Имена клавиш
------------
Можно передавать:
  - строку-псевдоним : "left", "right", "up", "down", "space",
                       "enter", "escape", "shift", "ctrl", "alt",
                       "a".."z", "0".."9", "f1".."f12" и т.д.
  - pygame.K_* константу : Input.key_down(pygame.K_LEFT)
"""

from __future__ import annotations
import pygame


# ---------------------------------------------------------------------------
# Таблица псевдонимов  имя -> pygame.K_*
# ---------------------------------------------------------------------------

_ALIASES: dict[str, int] = {
    # Стрелки
    "left":       pygame.K_LEFT,
    "right":      pygame.K_RIGHT,
    "up":         pygame.K_UP,
    "down":       pygame.K_DOWN,

    # Часто используемые
    "space":      pygame.K_SPACE,
    "enter":      pygame.K_RETURN,
    "escape":     pygame.K_ESCAPE,
    "backspace":  pygame.K_BACKSPACE,
    "tab":        pygame.K_TAB,
    "delete":     pygame.K_DELETE,
    "home":       pygame.K_HOME,
    "end":        pygame.K_END,
    "pageup":     pygame.K_PAGEUP,
    "pagedown":   pygame.K_PAGEDOWN,

    # Модификаторы
    "shift":      pygame.K_LSHIFT,
    "lshift":     pygame.K_LSHIFT,
    "rshift":     pygame.K_RSHIFT,
    "ctrl":       pygame.K_LCTRL,
    "lctrl":      pygame.K_LCTRL,
    "rctrl":      pygame.K_RCTRL,
    "alt":        pygame.K_LALT,
    "lalt":       pygame.K_LALT,
    "ralt":       pygame.K_RALT,

    # Функциональные
    "f1":  pygame.K_F1,  "f2":  pygame.K_F2,  "f3":  pygame.K_F3,
    "f4":  pygame.K_F4,  "f5":  pygame.K_F5,  "f6":  pygame.K_F6,
    "f7":  pygame.K_F7,  "f8":  pygame.K_F8,  "f9":  pygame.K_F9,
    "f10": pygame.K_F10, "f11": pygame.K_F11, "f12": pygame.K_F12,
}

# Добавляем все буквы a-z и цифры 0-9 автоматически
for _ch in "abcdefghijklmnopqrstuvwxyz0123456789":
    _ALIASES[_ch] = ord(_ch)


def _resolve(key) -> int:
    """Привести имя клавиши или pygame.K_* к int."""
    if isinstance(key, int):
        return key
    low = key.lower()
    if low in _ALIASES:
        return _ALIASES[low]
    # Последняя попытка: getattr(pygame, "K_" + key.upper())
    attr = "K_" + key.upper()
    val = getattr(pygame, attr, None)
    if val is not None:
        return val
    raise ValueError(f"Input: неизвестная клавиша '{key}'")


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

class Input:
    """
    Статический менеджер ввода. Обновляется движком раз в кадр.

    Клавиатура
    ----------
    Input.key_down(key)   -> bool   нажата в ЭТОМ кадре
    Input.key_up(key)     -> bool   отпущена в ЭТОМ кадре
    Input.key_held(key)   -> bool   удерживается сейчас
    Input.any_key_down()  -> bool   любая клавиша нажата в этом кадре
    Input.any_key_held()  -> bool   любая клавиша удерживается

    Мышь
    ----
    Input.mouse_position  -> tuple(x, y)   текущая позиция курсора
    Input.mouse_delta     -> tuple(dx, dy)  смещение за кадр
    Input.mouse_button_down(btn)   -> bool  нажата в ЭТОМ кадре  (1=ЛКМ, 2=СКМ, 3=ПКМ)
    Input.mouse_button_up(btn)     -> bool  отпущена в ЭТОМ кадре
    Input.mouse_button_held(btn)   -> bool  удерживается сейчас
    Input.scroll_up        -> bool  колесо вверх в этом кадре
    Input.scroll_down      -> bool  колесо вниз в этом кадре

    Ось (аналог Input.GetAxis в Unity)
    -----------------------------------
    Input.axis("horizontal")  -> float  -1 (left) .. +1 (right)
    Input.axis("vertical")    -> float  -1 (up)   .. +1 (down)
    """

    # --- Клавиатура ---
    _keys_down:  set[int] = set()   # нажаты в этом кадре
    _keys_up:    set[int] = set()   # отпущены в этом кадре
    _keys_held:  set[int] = set()   # удерживаются прямо сейчас

    # --- Мышь: позиция ---
    _mouse_pos:       tuple = (0, 0)
    _mouse_pos_prev:  tuple = (0, 0)

    # --- Мышь: кнопки (индекс 1=ЛКМ, 2=СКМ, 3=ПКМ) ---
    _mouse_down: set[int] = set()
    _mouse_up:   set[int] = set()
    _mouse_held: set[int] = set()

    # --- Колесо ---
    _scroll_up:   bool = False
    _scroll_down: bool = False

    # ------------------------------------------------------------------
    # Обновление (вызывается движком в начале каждого кадра)
    # ------------------------------------------------------------------

    @classmethod
    def _update(cls, events: list) -> None:
        """
        Вызывается один раз за кадр в Application._handle_system_events
        ПОСЛЕ сбора событий. Не вызывайте вручную.
        """
        # Сбросить однокадровые состояния
        cls._keys_down.clear()
        cls._keys_up.clear()
        cls._mouse_down.clear()
        cls._mouse_up.clear()
        cls._scroll_up   = False
        cls._scroll_down = False

        # Сохранить предыдущую позицию мыши
        cls._mouse_pos_prev = cls._mouse_pos
        cls._mouse_pos = pygame.mouse.get_pos()

        for event in events:
            # Клавиатура
            if event.type == pygame.KEYDOWN:
                cls._keys_down.add(event.key)
                cls._keys_held.add(event.key)

            elif event.type == pygame.KEYUP:
                cls._keys_up.add(event.key)
                cls._keys_held.discard(event.key)

            # Мышь -- кнопки
            elif event.type == pygame.MOUSEBUTTONDOWN:
                cls._mouse_down.add(event.button)
                cls._mouse_held.add(event.button)

            elif event.type == pygame.MOUSEBUTTONUP:
                cls._mouse_up.add(event.button)
                cls._mouse_held.discard(event.button)

            # Колесо мыши
            elif event.type == pygame.MOUSEWHEEL:
                if event.y > 0:
                    cls._scroll_up = True
                elif event.y < 0:
                    cls._scroll_down = True

    # ------------------------------------------------------------------
    # Клавиатура
    # ------------------------------------------------------------------

    @classmethod
    def key_down(cls, key) -> bool:
        """True если клавиша нажата ИМЕННО в этом кадре."""
        return _resolve(key) in cls._keys_down

    @classmethod
    def key_up(cls, key) -> bool:
        """True если клавиша отпущена ИМЕННО в этом кадре."""
        return _resolve(key) in cls._keys_up

    @classmethod
    def key_held(cls, key) -> bool:
        """True если клавиша удерживается прямо сейчас."""
        return _resolve(key) in cls._keys_held

    @classmethod
    def any_key_down(cls) -> bool:
        """True если хоть одна клавиша нажата в этом кадре."""
        return len(cls._keys_down) > 0

    @classmethod
    def any_key_held(cls) -> bool:
        """True если хоть одна клавиша удерживается."""
        return len(cls._keys_held) > 0

    # ------------------------------------------------------------------
    # Мышь
    # ------------------------------------------------------------------

    @classmethod
    @property
    def mouse_position(cls) -> tuple:
        """Текущая позиция курсора (x, y)."""
        return cls._mouse_pos

    @classmethod
    @property
    def mouse_delta(cls) -> tuple:
        """Смещение курсора за последний кадр (dx, dy)."""
        return (
            cls._mouse_pos[0] - cls._mouse_pos_prev[0],
            cls._mouse_pos[1] - cls._mouse_pos_prev[1],
        )

    @classmethod
    def mouse_button_down(cls, button: int = 1) -> bool:
        """True если кнопка мыши нажата ИМЕННО в этом кадре. 1=ЛКМ 2=СКМ 3=ПКМ."""
        return button in cls._mouse_down

    @classmethod
    def mouse_button_up(cls, button: int = 1) -> bool:
        """True если кнопка мыши отпущена ИМЕННО в этом кадре."""
        return button in cls._mouse_up

    @classmethod
    def mouse_button_held(cls, button: int = 1) -> bool:
        """True если кнопка мыши удерживается прямо сейчас."""
        return button in cls._mouse_held

    @classmethod
    @property
    def scroll_up(cls) -> bool:
        """True если колесо мыши прокручено вверх в этом кадре."""
        return cls._scroll_up

    @classmethod
    @property
    def scroll_down(cls) -> bool:
        """True если колесо мыши прокручено вниз в этом кадре."""
        return cls._scroll_down

    # ------------------------------------------------------------------
    # Оси (аналог Unity Input.GetAxis)
    # ------------------------------------------------------------------

    @classmethod
    def axis(cls, name: str) -> float:
        """
        Вернуть значение оси от -1.0 до +1.0.

        Поддерживаемые оси:
          "horizontal"  -- A/Left = -1,  D/Right = +1
          "vertical"    -- W/Up   = -1,  S/Down  = +1
                          (минус потому что Y в pygame растёт вниз)
        """
        name = name.lower()

        if name in ("horizontal", "x"):
            val = 0.0
            if cls.key_held("left")  or cls.key_held("a"):
                val -= 1.0
            if cls.key_held("right") or cls.key_held("d"):
                val += 1.0
            return val

        if name in ("vertical", "y"):
            val = 0.0
            if cls.key_held("up")   or cls.key_held("w"):
                val -= 1.0
            if cls.key_held("down") or cls.key_held("s"):
                val += 1.0
            return val

        raise ValueError(f"Input.axis: неизвестная ось '{name}'")

    # ------------------------------------------------------------------
    # Утилиты
    # ------------------------------------------------------------------

    @classmethod
    def get_mouse_pos(cls) -> tuple:
        """Текущая позиция курсора (x, y). Альтернатива mouse_position."""
        return cls._mouse_pos

    @classmethod
    def is_mouse_over_rect(cls, rect: pygame.Rect) -> bool:
        """True если курсор находится внутри pygame.Rect."""
        return rect.collidepoint(cls._mouse_pos)
