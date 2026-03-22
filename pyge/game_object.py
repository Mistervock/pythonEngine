"""
pyge/game_object.py
===================
Vector2   -- 2D-вектор с математикой
Transform -- позиция / поворот / масштаб
GameObject -- базовая единица сцены (контейнер компонентов)
"""

from __future__ import annotations
import math
from typing import TYPE_CHECKING
import pygame

if TYPE_CHECKING:
    from pyge.scene import Scene
    from pyge.component import Component


# ============================================================
#  Vector2
# ============================================================

class Vector2:
    __slots__ = ("x", "y")

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)

    # ---------- арифметика ----------

    def __add__(self, other: "Vector2") -> "Vector2":
        return Vector2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vector2") -> "Vector2":
        return Vector2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vector2":
        return Vector2(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar: float) -> "Vector2":
        return Vector2(self.x * scalar, self.y * scalar)

    def __truediv__(self, scalar: float) -> "Vector2":
        return Vector2(self.x / scalar, self.y / scalar)

    def __neg__(self) -> "Vector2":
        return Vector2(-self.x, -self.y)

    def __iadd__(self, other: "Vector2") -> "Vector2":
        self.x += other.x
        self.y += other.y
        return self

    def __isub__(self, other: "Vector2") -> "Vector2":
        self.x -= other.x
        self.y -= other.y
        return self

    def __imul__(self, scalar: float) -> "Vector2":
        self.x *= scalar
        self.y *= scalar
        return self

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Vector2):
            return NotImplemented
        return abs(self.x - other.x) < 1e-9 and abs(self.y - other.y) < 1e-9

    # ---------- свойства ----------

    @property
    def magnitude(self) -> float:
        """Длина вектора."""
        return math.sqrt(self.x * self.x + self.y * self.y)

    @property
    def sqr_magnitude(self) -> float:
        """Квадрат длины (без sqrt -- быстрее)."""
        return self.x * self.x + self.y * self.y

    @property
    def normalized(self) -> "Vector2":
        """Единичный вектор того же направления."""
        m = self.magnitude
        if m < 1e-9:
            return Vector2(0.0, 0.0)
        return Vector2(self.x / m, self.y / m)

    def normalize(self) -> None:
        """Нормализовать на месте."""
        m = self.magnitude
        if m > 1e-9:
            self.x /= m
            self.y /= m

    # ---------- операции ----------

    def dot(self, other: "Vector2") -> float:
        return self.x * other.x + self.y * other.y

    def cross(self, other: "Vector2") -> float:
        return self.x * other.y - self.y * other.x

    def copy(self) -> "Vector2":
        return Vector2(self.x, self.y)

    def to_tuple(self) -> tuple:
        return (self.x, self.y)

    def to_int_tuple(self) -> tuple:
        return (int(self.x), int(self.y))

    # ---------- статические ----------

    @staticmethod
    def distance(a: "Vector2", b: "Vector2") -> float:
        return (b - a).magnitude

    @staticmethod
    def lerp(a: "Vector2", b: "Vector2", t: float) -> "Vector2":
        t = max(0.0, min(1.0, t))
        return Vector2(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)

    @staticmethod
    def move_towards(current: "Vector2", target: "Vector2", max_delta: float) -> "Vector2":
        diff = target - current
        dist = diff.magnitude
        if dist <= max_delta or dist < 1e-9:
            return target.copy()
        return current + diff.normalized * max_delta

    @staticmethod
    def angle(a: "Vector2", b: "Vector2") -> float:
        """Угол между двумя векторами в градусах."""
        d = max(-1.0, min(1.0, a.normalized.dot(b.normalized)))
        return math.degrees(math.acos(d))

    # ---------- константы ----------

    @staticmethod
    def zero() -> "Vector2":
        return Vector2(0.0, 0.0)

    @staticmethod
    def one() -> "Vector2":
        return Vector2(1.0, 1.0)

    @staticmethod
    def up() -> "Vector2":
        return Vector2(0.0, -1.0)   # pygame: Y растёт вниз

    @staticmethod
    def down() -> "Vector2":
        return Vector2(0.0, 1.0)

    @staticmethod
    def left() -> "Vector2":
        return Vector2(-1.0, 0.0)

    @staticmethod
    def right() -> "Vector2":
        return Vector2(1.0, 0.0)

    def __repr__(self) -> str:
        return f"Vector2({self.x:.3f}, {self.y:.3f})"


# ============================================================
#  Transform
# ============================================================

class Transform:
    """
    Позиция, поворот и масштаб объекта.
    Каждый GameObject имеет ровно один Transform -- obj.transform
    """

    __slots__ = ("position", "rotation", "scale", "_game_object")

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        rotation: float = 0.0,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
    ) -> None:
        self.position = Vector2(x, y)
        self.rotation = rotation          # градусы, по часовой
        self.scale    = Vector2(scale_x, scale_y)
        self._game_object = None

    @property
    def x(self) -> float:
        return self.position.x

    @x.setter
    def x(self, value: float) -> None:
        self.position.x = float(value)

    @property
    def y(self) -> float:
        return self.position.y

    @y.setter
    def y(self, value: float) -> None:
        self.position.y = float(value)

    def translate(self, dx: float = 0.0, dy: float = 0.0) -> None:
        """Сдвинуть объект на (dx, dy)."""
        self.position.x += dx
        self.position.y += dy

    def translate_v(self, delta: Vector2) -> None:
        """Сдвинуть объект на вектор."""
        self.position += delta

    def look_at(self, target: Vector2) -> None:
        """Повернуть объект лицом к точке target."""
        dx = target.x - self.position.x
        dy = target.y - self.position.y
        self.rotation = math.degrees(math.atan2(dy, dx))

    def __repr__(self) -> str:
        return (
            f"Transform(pos={self.position}, "
            f"rot={self.rotation:.1f}deg, "
            f"scale={self.scale})"
        )


# ============================================================
#  GameObject
# ============================================================

class GameObject:
    """
    Базовая единица сцены. Аналог GameObject из Unity.
    Сам по себе ничего не делает -- поведение задают компоненты.

    Параметры
    ---------
    name    : str   -- имя объекта
    x, y    : float -- начальная позиция
    tag     : str   -- тег для поиска ("player", "enemy", ...)
    z_order : int   -- порядок отрисовки (меньше = ниже)

    Пример
    ------
    hero = GameObject("Hero", x=200, y=300, tag="player")
    hero.add_component(SpriteRenderer("assets/hero.png"))
    scene.add(hero)

    sr = hero.get_component(SpriteRenderer)
    hero.active  = False   # выключить update + render
    hero.visible = False   # только скрыть
    """

    def __init__(
        self,
        name: str = "GameObject",
        x: float = 0.0,
        y: float = 0.0,
        tag: str = "",
        z_order: int = 0,
    ) -> None:
        self.name:    str  = name
        self.tag:     str  = tag
        self.z_order: int  = z_order
        self.active:  bool = True    # update + render
        self.visible: bool = True    # только render

        self.transform = Transform(x, y)
        self.transform._game_object = self

        self._components: list = []
        self._scene = None           # устанавливается в Scene.add()
        self._started: bool = False

    # ------ удобные свойства ------

    @property
    def scene(self):
        if self._scene is None:
            raise RuntimeError(f"GameObject '{self.name}' не добавлен в сцену.")
        return self._scene

    @property
    def x(self) -> float:
        return self.transform.x

    @x.setter
    def x(self, value: float) -> None:
        self.transform.x = value

    @property
    def y(self) -> float:
        return self.transform.y

    @y.setter
    def y(self, value: float) -> None:
        self.transform.y = value

    @property
    def position(self) -> Vector2:
        return self.transform.position

    @position.setter
    def position(self, value: Vector2) -> None:
        self.transform.position = value

    # ------ компоненты ------

    def add_component(self, component) -> object:
        """
        Добавить компонент. Возвращает его же (для chaining).

            hero.add_component(SpriteRenderer(...))
        """
        component._game_object = self
        self._components.append(component)
        if self._started:
            component.on_awake()
            component.on_start()
        return component

    def get_component(self, component_type: type):
        """Первый компонент заданного типа или None."""
        for c in self._components:
            if isinstance(c, component_type):
                return c
        return None

    def get_components(self, component_type: type) -> list:
        """Все компоненты заданного типа."""
        return [c for c in self._components if isinstance(c, component_type)]

    def has_component(self, component_type: type) -> bool:
        return any(isinstance(c, component_type) for c in self._components)

    def remove_component(self, component) -> None:
        if component in self._components:
            component.on_destroy()
            self._components.remove(component)

    # ------ жизненный цикл -- переопределяйте ------

    def on_awake(self) -> None:
        """Вызывается при добавлении в сцену, до on_start."""

    def on_start(self) -> None:
        """Первый кадр в сцене -- все объекты уже существуют."""

    def on_update(self) -> None:
        """Каждый кадр после обновления компонентов."""

    def on_render(self, screen: pygame.Surface) -> None:
        """Каждый кадр после рендера компонентов."""

    def on_event(self, event: pygame.event.Event) -> None:
        """Каждое pygame-событие."""

    def on_destroy(self) -> None:
        """При удалении из сцены."""

    # ------ внутренние методы (вызывает движок) ------

    def _on_awake(self) -> None:
        for c in self._components:
            c._game_object = self
            c.on_awake()
        self.on_awake()

    def _on_start(self) -> None:
        for c in self._components:
            c.on_start()
        self.on_start()
        self._started = True

    def _update(self) -> None:
        if not self._started:
            self._on_start()
        for c in self._components:
            if c.enabled:
                c.on_update()
        self.on_update()

    def _render(self, screen: pygame.Surface) -> None:
        for c in self._components:
            if c.enabled:
                c.on_render(screen)
        self.on_render(screen)

    def _on_event(self, event: pygame.event.Event) -> None:
        for c in self._components:
            if c.enabled:
                c.on_event(event)
        self.on_event(event)

    def _on_destroy(self) -> None:
        for c in self._components:
            c.on_destroy()
        self.on_destroy()

    def __repr__(self) -> str:
        return (
            f"<GameObject '{self.name}' tag='{self.tag}' "
            f"pos=({self.x:.1f}, {self.y:.1f}) "
            f"components={len(self._components)}>"
        )
