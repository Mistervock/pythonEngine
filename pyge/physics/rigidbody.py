"""
pyge/physics/rigidbody.py
"""
from __future__ import annotations
import math
from typing import TYPE_CHECKING
import pygame

from pyge.component import Component
from pyge.game_object import Vector2

if TYPE_CHECKING:
    from pyge.scene import Scene


# ============================================================
# CollisionInfo
# ============================================================

class CollisionInfo:
    __slots__ = ("other", "normal", "penetration")

    def __init__(self, other, normal: tuple, penetration: float) -> None:
        self.other       = other        # другой GameObject
        self.normal      = normal       # (nx, ny) нормаль от other к self
        self.penetration = penetration  # глубина проникновения (пикс)

    def __repr__(self) -> str:
        return f"<CollisionInfo normal={self.normal} pen={self.penetration:.2f}>"


# ============================================================
# PhysicsWorld
# ============================================================

class PhysicsWorld:
    """
    Глобальный физический мир.

    Настройки
    ---------
    PhysicsWorld.gravity    = 980.0   # пикс/с² вниз (float)
    PhysicsWorld.debug_draw = False
    PhysicsWorld.iterations = 3       # итерации решателя коллизий
    """

    gravity:    float = 980.0
    debug_draw: bool  = False
    iterations: int   = 3

    _colliders: list = []
    _prev_pairs: set = set()

    @classmethod
    def register(cls, col) -> None:
        if col not in cls._colliders:
            cls._colliders.append(col)

    @classmethod
    def unregister(cls, col) -> None:
        if col in cls._colliders:
            cls._colliders.remove(col)

    @classmethod
    def clear(cls) -> None:
        cls._colliders.clear()
        cls._prev_pairs.clear()

    @classmethod
    def step(cls, scene: "Scene") -> None:
        from pyge.engine import Time
        dt = Time.delta_time
        if dt <= 0:
            return

        objects = scene.all_objects()

        # 1. Интегрировать Rigidbody2D
        for obj in objects:
            if not obj.active:
                continue
            rb = obj.get_component(Rigidbody2D)
            if rb and rb.enabled and not rb.is_kinematic:
                rb._integrate(dt)

        # 2. Коллизии -- несколько итераций для стабильности
        colliders = [
            c for obj in objects if obj.active
            for c in obj.get_components(BoxCollider2D) + obj.get_components(CircleCollider2D)
            if c.enabled
        ]

        current_pairs: set = set()

        for _ in range(cls.iterations):
            n = len(colliders)
            for i in range(n):
                a = colliders[i]
                for j in range(i + 1, n):
                    b = colliders[j]
                    if a.game_object is b.game_object:
                        continue
                    if a.is_static and b.is_static:
                        continue
                    if not (a.mask & (1 << b.layer)) or not (b.mask & (1 << a.layer)):
                        continue
                    if not a.get_aabb().colliderect(b.get_aabb()):
                        continue

                    info = cls._narrow(a, b)
                    if info is None:
                        continue

                    pair = (id(a), id(b))
                    current_pairs.add(pair)

                    if not a.is_trigger and not b.is_trigger:
                        cls._resolve(a, b, info)

                    # Коллбэки для A
                    _fire(a.game_object, "on_collision_enter" if pair not in cls._prev_pairs
                          else "on_collision_stay", info)
                    # Коллбэки для B (инвертированная нормаль)
                    info_b = CollisionInfo(
                        a.game_object,
                        (-info.normal[0], -info.normal[1]),
                        info.penetration,
                    )
                    _fire(b.game_object, "on_collision_enter" if pair not in cls._prev_pairs
                          else "on_collision_stay", info_b)

        cls._prev_pairs = current_pairs

    # ------ narrow phase ------

    @classmethod
    def _narrow(cls, a, b):
        ta = type(a).__name__
        tb = type(b).__name__
        if ta == "BoxCollider2D"    and tb == "BoxCollider2D":
            return cls._box_box(a, b)
        if ta == "CircleCollider2D" and tb == "CircleCollider2D":
            return cls._circle_circle(a, b)
        if ta == "BoxCollider2D"    and tb == "CircleCollider2D":
            return cls._box_circle(a, b)
        if ta == "CircleCollider2D" and tb == "BoxCollider2D":
            r = cls._box_circle(b, a)
            if r:
                return CollisionInfo(a.game_object, (-r.normal[0], -r.normal[1]), r.penetration)
        return None

    @staticmethod
    def _box_box(a, b):
        ra = a.get_aabb()
        rb = b.get_aabb()
        ox = min(ra.right, rb.right)   - max(ra.left, rb.left)
        oy = min(ra.bottom, rb.bottom) - max(ra.top,  rb.top)
        if ox <= 0 or oy <= 0:
            return None
        if ox < oy:
            nx = 1.0 if ra.centerx < rb.centerx else -1.0
            return CollisionInfo(b.game_object, (nx, 0.0), ox)
        else:
            ny = 1.0 if ra.centery < rb.centery else -1.0
            return CollisionInfo(b.game_object, (0.0, ny), oy)

    @staticmethod
    def _circle_circle(a, b):
        ax = a.transform.x + a.offset.x
        ay = a.transform.y + a.offset.y
        bx = b.transform.x + b.offset.x
        by = b.transform.y + b.offset.y
        dx, dy = bx - ax, by - ay
        dist_sq = dx*dx + dy*dy
        radii   = a.radius + b.radius
        if dist_sq >= radii*radii:
            return None
        dist = math.sqrt(dist_sq) if dist_sq > 1e-9 else 1e-9
        return CollisionInfo(b.game_object, (dx/dist, dy/dist), radii - dist)

    @staticmethod
    def _box_circle(box, circle):
        rect = box.get_aabb()
        cx   = circle.transform.x + circle.offset.x
        cy   = circle.transform.y + circle.offset.y
        r    = circle.radius
        nx   = max(rect.left, min(cx, rect.right))
        ny   = max(rect.top,  min(cy, rect.bottom))
        dx, dy = cx - nx, cy - ny
        dist_sq = dx*dx + dy*dy
        if dist_sq >= r*r:
            return None
        dist = math.sqrt(dist_sq) if dist_sq > 1e-9 else 1e-9
        return CollisionInfo(circle.game_object, (-dx/dist, -dy/dist), r - dist)

    # ------ resolve ------

    @classmethod
    def _resolve(cls, a, b, info: CollisionInfo) -> None:
        rb_a = a.game_object.get_component(Rigidbody2D)
        rb_b = b.game_object.get_component(Rigidbody2D)

        static_a = a.is_static or rb_a is None or rb_a.is_kinematic
        static_b = b.is_static or rb_b is None or rb_b.is_kinematic

        nx, ny = info.normal
        pen    = info.penetration

        # Позиционная коррекция
        correction = max(pen - 0.5, 0.0) * 0.8
        if not static_a and not static_b:
            h = correction / 2.0
            a.game_object.transform.x -= nx * h
            a.game_object.transform.y -= ny * h
            b.game_object.transform.x += nx * h
            b.game_object.transform.y += ny * h
        elif not static_a:
            a.game_object.transform.x -= nx * correction
            a.game_object.transform.y -= ny * correction
        elif not static_b:
            b.game_object.transform.x += nx * correction
            b.game_object.transform.y += ny * correction

        # Импульс
        vax = rb_a.velocity.x if (rb_a and not static_a) else 0.0
        vay = rb_a.velocity.y if (rb_a and not static_a) else 0.0
        vbx = rb_b.velocity.x if (rb_b and not static_b) else 0.0
        vby = rb_b.velocity.y if (rb_b and not static_b) else 0.0

        vel_n = (vbx - vax)*nx + (vby - vay)*ny
        if vel_n > 0:
            return

        e       = min(getattr(a, "restitution", 0.1), getattr(b, "restitution", 0.1))
        inv_a   = (1.0 / rb_a.mass) if (rb_a and not static_a) else 0.0
        inv_b   = (1.0 / rb_b.mass) if (rb_b and not static_b) else 0.0
        inv_sum = inv_a + inv_b
        if inv_sum < 1e-9:
            return

        j = -(1.0 + e) * vel_n / inv_sum
        if rb_a and not static_a:
            rb_a.velocity.x -= j * inv_a * nx
            rb_a.velocity.y -= j * inv_a * ny
        if rb_b and not static_b:
            rb_b.velocity.x += j * inv_b * nx
            rb_b.velocity.y += j * inv_b * ny


def _fire(game_object, method: str, info: CollisionInfo) -> None:
    cb = getattr(game_object, method, None)
    if callable(cb):
        cb(info)
    for comp in game_object._components:
        if comp.enabled:
            cb = getattr(comp, method, None)
            if callable(cb):
                cb(info)


# ============================================================
# Rigidbody2D
# ============================================================

class Rigidbody2D(Component):
    """
    Физическое тело. Используйте вместе с BoxCollider2D / CircleCollider2D.

    Атрибуты
    --------
    velocity : Vector2   скорость в пикс/с

    Методы
    ------
    add_force(fx, fy)    -- сила на текущий кадр
    add_impulse(ix, iy)  -- мгновенный импульс
    stop()               -- обнулить скорость
    """

    def __init__(
        self,
        mass: float = 1.0,
        drag: float = 0.0,
        gravity_scale: float = 1.0,
        is_kinematic: bool = False,
        max_speed: float = 0.0,
    ) -> None:
        super().__init__()
        self.mass          = max(float(mass), 1e-9)
        self.drag          = drag
        self.gravity_scale = gravity_scale
        self.is_kinematic  = is_kinematic
        self.max_speed     = max_speed
        self.velocity      = Vector2(0.0, 0.0)
        self._force_accum  = Vector2(0.0, 0.0)

    def add_force(self, fx: float, fy: float) -> None:
        self._force_accum.x += fx
        self._force_accum.y += fy

    def add_impulse(self, ix: float, iy: float) -> None:
        inv = 1.0 / self.mass
        self.velocity.x += ix * inv
        self.velocity.y += iy * inv

    def stop(self) -> None:
        self.velocity.x     = 0.0
        self.velocity.y     = 0.0
        self._force_accum.x = 0.0
        self._force_accum.y = 0.0

    def _integrate(self, dt: float) -> None:
        # Гравитация (PhysicsWorld.gravity -- float, пикс/с²)
        self._force_accum.y += PhysicsWorld.gravity * self.gravity_scale * self.mass

        inv = 1.0 / self.mass
        self.velocity.x += self._force_accum.x * inv * dt
        self.velocity.y += self._force_accum.y * inv * dt

        if self.drag > 0.0:
            f = max(0.0, 1.0 - self.drag * dt)
            self.velocity.x *= f
            self.velocity.y *= f

        if self.max_speed > 0.0:
            spd = self.velocity.magnitude
            if spd > self.max_speed:
                k = self.max_speed / spd
                self.velocity.x *= k
                self.velocity.y *= k

        self.transform.x += self.velocity.x * dt
        self.transform.y += self.velocity.y * dt

        self._force_accum.x = 0.0
        self._force_accum.y = 0.0


# ============================================================
# BoxCollider2D
# ============================================================

class BoxCollider2D(Component):
    def __init__(
        self,
        width: float = 32.0,
        height: float = 32.0,
        offset: Vector2 | None = None,
        is_static: bool = False,
        is_trigger: bool = False,
        layer: int = 0,
        mask: int = 0xFFFFFFFF,
        restitution: float = 0.1,
        debug: bool = False,
    ) -> None:
        super().__init__()
        self.width       = float(width)
        self.height      = float(height)
        self.offset      = offset if offset is not None else Vector2(0.0, 0.0)
        self.is_static   = is_static
        self.is_trigger  = is_trigger
        self.layer       = layer
        self.mask        = mask
        self.restitution = restitution
        self.debug       = debug

    def get_aabb(self) -> pygame.Rect:
        tx = self.transform.x + self.offset.x
        ty = self.transform.y + self.offset.y
        return pygame.Rect(
            int(tx - self.width  / 2),
            int(ty - self.height / 2),
            int(self.width),
            int(self.height),
        )

    def on_awake(self) -> None:
        PhysicsWorld.register(self)

    def on_destroy(self) -> None:
        PhysicsWorld.unregister(self)

    def on_render(self, screen: pygame.Surface) -> None:
        if self.debug or PhysicsWorld.debug_draw:
            color = (255, 120, 0) if self.is_static else (0, 200, 255)
            if self.is_trigger:
                color = (180, 0, 255)
            pygame.draw.rect(screen, color, self.get_aabb(), 1)


# ============================================================
# CircleCollider2D
# ============================================================

class CircleCollider2D(Component):
    def __init__(
        self,
        radius: float = 16.0,
        offset: Vector2 | None = None,
        is_static: bool = False,
        is_trigger: bool = False,
        layer: int = 0,
        mask: int = 0xFFFFFFFF,
        restitution: float = 0.1,
        debug: bool = False,
    ) -> None:
        super().__init__()
        self.radius      = float(radius)
        self.offset      = offset if offset is not None else Vector2(0.0, 0.0)
        self.is_static   = is_static
        self.is_trigger  = is_trigger
        self.layer       = layer
        self.mask        = mask
        self.restitution = restitution
        self.debug       = debug

    def get_aabb(self) -> pygame.Rect:
        tx = self.transform.x + self.offset.x
        ty = self.transform.y + self.offset.y
        r  = int(self.radius)
        return pygame.Rect(int(tx) - r, int(ty) - r, r * 2, r * 2)

    def on_awake(self) -> None:
        PhysicsWorld.register(self)

    def on_destroy(self) -> None:
        PhysicsWorld.unregister(self)

    def on_render(self, screen: pygame.Surface) -> None:
        if self.debug or PhysicsWorld.debug_draw:
            tx = int(self.transform.x + self.offset.x)
            ty = int(self.transform.y + self.offset.y)
            color = (255, 120, 0) if self.is_static else (0, 200, 255)
            if self.is_trigger:
                color = (180, 0, 255)
            pygame.draw.circle(screen, color, (tx, ty), int(self.radius), 1)
