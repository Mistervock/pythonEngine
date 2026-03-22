"""
pyge/scene.py
=============
Scene         -- базовый класс сцены
SceneManager  -- глобальный реестр сцен по имени
"""

from __future__ import annotations
from typing import TYPE_CHECKING
import pygame

if TYPE_CHECKING:
    from pyge.engine import Application
    from pyge.game_object import GameObject


class Scene:
    def __init__(self, name: str = "") -> None:
        self.name: str = name or self.__class__.__name__
        self._application = None
        self._objects: list = []
        self._pending_add: list = []
        self._pending_remove: list = []
        self._started: bool = False

    # ------------------------------------------------------------------
    # Свойства
    # ------------------------------------------------------------------

    @property
    def app(self):
        if self._application is None:
            raise RuntimeError("Scene не загружена в Application.")
        return self._application

    @property
    def screen(self) -> pygame.Surface:
        return self.app.screen

    # ------------------------------------------------------------------
    # Управление объектами
    # ------------------------------------------------------------------

    def add(self, obj) -> object:
        """Добавить GameObject (отложенно — в начале следующего кадра)."""
        obj._scene = self
        self._pending_add.append(obj)
        return obj

    def remove(self, obj) -> None:
        """Удалить GameObject (отложенно)."""
        self._pending_remove.append(obj)

    def find(self, name: str):
        for obj in self._objects:
            if obj.name == name:
                return obj
        return None

    def find_all(self, name: str) -> list:
        return [o for o in self._objects if o.name == name]

    def find_by_tag(self, tag: str):
        for obj in self._objects:
            if obj.tag == tag:
                return obj
        return None

    def find_all_by_tag(self, tag: str) -> list:
        return [o for o in self._objects if o.tag == tag]

    def all_objects(self) -> list:
        return list(self._objects)

    def clear(self) -> None:
        for obj in self._objects:
            obj._on_destroy()
        self._objects.clear()
        self._pending_add.clear()
        self._pending_remove.clear()

    # ------------------------------------------------------------------
    # Жизненный цикл -- переопределяйте
    # ------------------------------------------------------------------

    def on_awake(self) -> None:
        """Вызывается один раз при загрузке сцены, до on_start."""

    def on_start(self) -> None:
        """Первый кадр -- создавайте объекты здесь."""

    def on_update(self) -> None:
        """Каждый кадр после обновления всех GameObject."""

    def on_render(self, screen: pygame.Surface) -> None:
        """Каждый кадр после рендера всех GameObject (HUD и т.д.)."""

    def on_event(self, event: pygame.event.Event) -> None:
        """Каждое pygame-событие."""

    def on_destroy(self) -> None:
        """При выгрузке сцены."""

    # ------------------------------------------------------------------
    # Внутренние методы (вызывает движок)
    # ------------------------------------------------------------------

    def _on_load(self) -> None:
        self._started = False
        self.on_awake()

    def _on_unload(self) -> None:
        self.on_destroy()
        self.clear()

    def _flush_pending(self) -> None:
        for obj in self._pending_remove:
            if obj in self._objects:
                obj._on_destroy()
                self._objects.remove(obj)
        self._pending_remove.clear()

        for obj in self._pending_add:
            self._objects.append(obj)
            obj._on_awake()
        self._pending_add.clear()

    def _process_events(self, events: list) -> None:
        for event in events:
            self.on_event(event)
            for obj in self._objects:
                if obj.active:
                    obj._on_event(event)

    def _update(self) -> None:
        self._flush_pending()

        if not self._started:
            self._started = True
            self.on_start()
            self._flush_pending()

        for obj in self._objects:
            if obj.active:
                obj._update()

        # Физический шаг -- передаём СЦЕНУ, не delta_time
        try:
            from pyge.physics.rigidbody import PhysicsWorld
            PhysicsWorld.step(self)
        except ImportError:
            pass

        self.on_update()

    def _render(self, screen: pygame.Surface) -> None:
        for obj in sorted(self._objects, key=lambda o: o.z_order):
            if obj.active and obj.visible:
                obj._render(screen)
        self.on_render(screen)

    def __repr__(self) -> str:
        return f"<Scene '{self.name}' objects={len(self._objects)}>"


# ---------------------------------------------------------------------------
# SceneManager
# ---------------------------------------------------------------------------

class SceneManager:
    """
    Глобальный реестр сцен по имени.

    SceneManager.register("menu", MainMenuScene())
    SceneManager.load("menu")
    """

    _registry: dict = {}

    @classmethod
    def register(cls, name: str, scene) -> None:
        scene.name = name
        cls._registry[name] = scene

    @classmethod
    def load(cls, name: str) -> None:
        from pyge.engine import Application
        if Application.instance is None:
            raise RuntimeError("Application не запущен.")
        if name not in cls._registry:
            raise KeyError(f"Сцена '{name}' не зарегистрирована.")
        Application.instance.load_scene(cls._registry[name])

    @classmethod
    def get(cls, name: str):
        if name not in cls._registry:
            raise KeyError(f"Сцена '{name}' не найдена.")
        return cls._registry[name]

    @classmethod
    def registered_names(cls) -> list:
        return list(cls._registry.keys())
