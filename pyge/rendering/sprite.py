"""
pyge/rendering/sprite.py
========================
Содержит:
  - SpriteRenderer  -- компонент отрисовки спрайта на экране
  - ImageCache      -- глобальный кэш загруженных Surface (не грузим одно дважды)

Возможности
-----------
  - Загрузка из файла или pygame.Surface напрямую
  - Поддержка прозрачности (PNG с alpha-каналом)
  - Масштаб из transform.scale
  - Поворот из transform.rotation
  - Смещение origin (pivot): по умолчанию центр спрайта
  - Цветовой тинт (color_tint) и прозрачность (alpha 0-255)
  - flip_x / flip_y
  - Отрисовка отладочного прямоугольника

Пример
------
from pyge.rendering.sprite import SpriteRenderer

hero = GameObject("Hero", x=400, y=300)
sr = SpriteRenderer("assets/hero.png")
hero.add_component(sr)
scene.add(hero)

# Позже:
sr.flip_x = True           # отзеркалить
sr.alpha  = 128            # полупрозрачность
sr.color_tint = (255,0,0)  # красный тинт
"""

from __future__ import annotations
import os
from typing import TYPE_CHECKING
import pygame

from pyge.component import Component

if TYPE_CHECKING:
    from pyge.game_object import Vector2


# ---------------------------------------------------------------------------
# ImageCache
# ---------------------------------------------------------------------------

class ImageCache:
    """
    Глобальный кэш pygame.Surface по пути к файлу.
    Один файл загружается в память только один раз.
    """
    _cache: dict[str, pygame.Surface] = {}

    @classmethod
    def load(cls, path: str, use_alpha: bool = True) -> pygame.Surface:
        """
        Загрузить изображение по пути. Повторный вызов вернёт кэшированный Surface.
        use_alpha=True  -- convert_alpha() (PNG с прозрачностью)
        use_alpha=False -- convert()       (непрозрачные JPG/BMP)
        """
        key = os.path.normpath(path)
        if key not in cls._cache:
            if not os.path.exists(path):
                raise FileNotFoundError(f"ImageCache: файл не найден: '{path}'")
            raw = pygame.image.load(path)
            cls._cache[key] = raw.convert_alpha() if use_alpha else raw.convert()
        return cls._cache[key]

    @classmethod
    def store(cls, key: str, surface: pygame.Surface) -> None:
        """Сохранить Surface под произвольным ключом (например, для динамических спрайтов)."""
        cls._cache[key] = surface

    @classmethod
    def clear(cls) -> None:
        """Очистить весь кэш (например, при смене сцены)."""
        cls._cache.clear()


# ---------------------------------------------------------------------------
# SpriteRenderer
# ---------------------------------------------------------------------------

class SpriteRenderer(Component):
    """
    Компонент отрисовки спрайта.

    Параметры
    ---------
    source : str | pygame.Surface | None
        Путь к файлу изображения, готовый Surface, или None (пустой спрайт).
    pivot : tuple(float, float)
        Точка привязки в долях от размера: (0.5, 0.5) = центр (по умолчанию),
        (0.0, 0.0) = верхний левый угол, (1.0, 1.0) = нижний правый.
    color_tint : tuple(R,G,B) | None
        Цветовое наложение. None = без тинта.
    alpha : int
        Прозрачность 0 (невидимый) .. 255 (непрозрачный).
    flip_x : bool
        Отзеркалить по горизонтали.
    flip_y : bool
        Отзеркалить по вертикали.
    order_in_layer : int
        Дополнительный порядок внутри одного z_order (не используется движком
        напрямую, но доступен для кастомной сортировки).
    debug : bool
        Рисовать bounding rect для отладки.
    """

    def __init__(
        self,
        source=None,
        pivot: tuple = (0.5, 0.5),
        color_tint=None,
        alpha: int = 255,
        flip_x: bool = False,
        flip_y: bool = False,
        order_in_layer: int = 0,
        debug: bool = False,
    ) -> None:
        super().__init__()

        self._original: pygame.Surface | None = None   # исходный Surface (не трогаем)
        self._cached_surface: pygame.Surface | None = None  # трансформированный кэш
        self._cache_key: tuple | None = None           # ключ для инвалидации кэша

        self.pivot             = pivot
        self.color_tint        = color_tint
        self.alpha             = alpha
        self.flip_x            = flip_x
        self.flip_y            = flip_y
        self.order_in_layer    = order_in_layer
        self.debug             = debug

        if source is not None:
            self.set_source(source)

    # ------------------------------------------------------------------
    # Публичный API
    # ------------------------------------------------------------------

    def set_source(self, source) -> None:
        """
        Установить спрайт из файла или pygame.Surface.

            sr.set_source("assets/explosion.png")
            sr.set_source(my_surface)
        """
        if isinstance(source, str):
            self._original = ImageCache.load(source)
        elif isinstance(source, pygame.Surface):
            self._original = source
        else:
            raise TypeError(f"SpriteRenderer.set_source: ожидается str или Surface, получено {type(source)}")
        self._cache_key = None   # сбросить кэш трансформации

    def set_color(self, color: tuple) -> None:
        """Установить цветовой тинт (R, G, B)."""
        self.color_tint = color
        self._cache_key = None

    def clear_color(self) -> None:
        """Убрать цветовой тинт."""
        self.color_tint = None
        self._cache_key = None

    @property
    def size(self) -> tuple:
        """Размер оригинального спрайта (w, h) в пикселях. (0,0) если не задан."""
        if self._original is None:
            return (0, 0)
        return self._original.get_size()

    @property
    def width(self) -> int:
        return self.size[0]

    @property
    def height(self) -> int:
        return self.size[1]

    @property
    def rect(self) -> pygame.Rect:
        """
        pygame.Rect спрайта в мировых координатах с учётом pivot.
        Используется для коллизий и проверок.
        """
        if self._original is None:
            x, y = int(self.transform.x), int(self.transform.y)
            return pygame.Rect(x, y, 0, 0)

        sx = self.transform.scale.x
        sy = self.transform.scale.y
        w = int(self._original.get_width()  * abs(sx))
        h = int(self._original.get_height() * abs(sy))
        ox = int(self.transform.x - w * self.pivot[0])
        oy = int(self.transform.y - h * self.pivot[1])
        return pygame.Rect(ox, oy, w, h)

    # ------------------------------------------------------------------
    # Жизненный цикл
    # ------------------------------------------------------------------

    def on_render(self, screen: pygame.Surface) -> None:
        if self._original is None:
            return

        surface = self._get_transformed_surface()
        if surface is None:
            return

        # Позиция с учётом pivot
        w, h = surface.get_size()
        draw_x = int(self.transform.x - w * self.pivot[0])
        draw_y = int(self.transform.y - h * self.pivot[1])

        screen.blit(surface, (draw_x, draw_y))

        # Отладочный прямоугольник
        if self.debug:
            pygame.draw.rect(screen, (0, 255, 0), (draw_x, draw_y, w, h), 1)
            # Крестик в точке transform (origin)
            cx, cy = int(self.transform.x), int(self.transform.y)
            pygame.draw.line(screen, (255, 0, 0), (cx - 4, cy), (cx + 4, cy), 1)
            pygame.draw.line(screen, (255, 0, 0), (cx, cy - 4), (cx, cy + 4), 1)

    # ------------------------------------------------------------------
    # Внутренняя трансформация с кэшем
    # ------------------------------------------------------------------

    def _get_transformed_surface(self) -> pygame.Surface | None:
        """
        Вернуть трансформированный Surface (scale + flip + rotate + tint + alpha).
        Результат кэшируется: пересчёт только при изменении параметров.
        """
        sx = self.transform.scale.x
        sy = self.transform.scale.y
        rot = self.transform.rotation

        key = (
            id(self._original),
            round(sx, 4), round(sy, 4),
            round(rot, 2),
            self.flip_x, self.flip_y,
            self.color_tint,
            self.alpha,
        )

        if key == self._cache_key and self._cached_surface is not None:
            return self._cached_surface

        surf = self._original

        # 1. Масштаб + flip
        orig_w, orig_h = surf.get_size()
        new_w = max(1, int(orig_w * abs(sx)))
        new_h = max(1, int(orig_h * abs(sy)))

        # flip_x/flip_y складываются с отрицательным scale
        fx = self.flip_x ^ (sx < 0)
        fy = self.flip_y ^ (sy < 0)

        if (new_w, new_h) != (orig_w, orig_h) or fx or fy:
            surf = pygame.transform.scale(surf, (new_w, new_h))
            if fx or fy:
                surf = pygame.transform.flip(surf, fx, fy)

        # 2. Цветовой тинт
        if self.color_tint is not None:
            surf = surf.copy()
            tint_surf = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            r, g, b = self.color_tint[:3]
            tint_surf.fill((r, g, b, 0))
            surf.blit(tint_surf, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

        # 3. Поворот (после масштаба, чтобы не терять качество)
        if rot % 360 != 0:
            surf = pygame.transform.rotate(surf, -rot)  # pygame: + = против часовой

        # 4. Прозрачность
        if self.alpha != 255:
            surf = surf.copy()
            surf.set_alpha(self.alpha)

        self._cached_surface = surf
        self._cache_key = key
        return surf
