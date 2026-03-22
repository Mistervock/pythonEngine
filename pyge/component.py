"""
pyge/component.py
=================
Базовый класс Component -- строительный блок любого поведения в PyGE.

Все компоненты движка (SpriteRenderer, Rigidbody2D, Animator, Button ...)
наследуются от этого класса.

Жизненный цикл компонента
--------------------------
  on_awake()         -- при добавлении в объект / загрузке сцены
  on_start()         -- первый кадр (все объекты сцены уже существуют)
  on_update()        -- каждый кадр (логика, физика, ввод)
  on_render(screen)  -- каждый кадр (рисование)
  on_event(event)    -- каждое pygame-событие текущего кадра
  on_destroy()       -- при удалении объекта из сцены

Пример -- создание своего компонента
-------------------------------------
from pyge.component import Component
from pyge.engine import Time

class Rotator(Component):
    def __init__(self, speed: float = 90.0) -> None:
        super().__init__()
        self.speed = speed   # градусов в секунду

    def on_update(self) -> None:
        self.transform.rotation += self.speed * Time.delta_time

# Использование:
obj = GameObject("Wheel", x=400, y=300)
obj.add_component(Rotator(speed=180))
scene.add(obj)
"""

from __future__ import annotations
from typing import TYPE_CHECKING
import pygame

if TYPE_CHECKING:
    from pyge.game_object import GameObject, Transform, Vector2
    from pyge.scene import Scene
    from pyge.engine import Application


class Component:
    """
    Базовый класс для всех компонентов движка.

    Атрибуты
    --------
    enabled : bool
        Если False -- on_update, on_render и on_event не вызываются.
        on_awake / on_start / on_destroy вызываются всегда.

    Свойства (доступны внутри методов компонента)
    ----------------------------------------------
    game_object  -- GameObject, которому принадлежит компонент
    transform    -- его Transform (позиция / поворот / масштаб)
    scene        -- текущая Scene
    app          -- Application (singleton)
    """

    def __init__(self) -> None:
        self.enabled: bool = True
        self._game_object = None   # type: GameObject | None

    # ------------------------------------------------------------------
    # Удобные свойства
    # ------------------------------------------------------------------

    @property
    def game_object(self) -> "GameObject":
        if self._game_object is None:
            raise RuntimeError(
                f"{self.__class__.__name__}: компонент ещё не прикреплён к GameObject."
            )
        return self._game_object

    @property
    def transform(self) -> "Transform":
        """Быстрый доступ к transform владельца."""
        return self.game_object.transform

    @property
    def scene(self) -> "Scene":
        """Сцена, в которой находится владелец."""
        return self.game_object.scene

    @property
    def app(self) -> "Application":
        """Ссылка на Application."""
        return self.game_object.scene.app

    # ------------------------------------------------------------------
    # Поиск других компонентов -- удобные хелперы
    # ------------------------------------------------------------------

    def get_component(self, component_type: type):
        """
        Найти компонент того же GameObject.

        Пример:
            rb = self.get_component(Rigidbody2D)
        """
        return self.game_object.get_component(component_type)

    def get_components(self, component_type: type) -> list:
        """Все компоненты заданного типа на том же GameObject."""
        return self.game_object.get_components(component_type)

    def has_component(self, component_type: type) -> bool:
        return self.game_object.has_component(component_type)

    # ------------------------------------------------------------------
    # Жизненный цикл -- переопределяйте в своих компонентах
    # ------------------------------------------------------------------

    def on_awake(self) -> None:
        """
        Вызывается один раз при добавлении компонента в объект.
        Используйте для инициализации переменных.
        В этот момент сцена уже загружена, но другие объекты
        могут ещё не существовать -- для поиска используйте on_start.
        """

    def on_start(self) -> None:
        """
        Вызывается один раз в первом кадре.
        Все объекты сцены уже созданы -- можно безопасно
        искать их через self.scene.find() и self.get_component().
        """

    def on_update(self) -> None:
        """
        Вызывается каждый кадр пока enabled = True.
        Здесь пишется логика компонента: движение, ИИ, ввод и т.д.
        Используйте Time.delta_time для независимости от FPS.
        """

    def on_render(self, screen: pygame.Surface) -> None:
        """
        Вызывается каждый кадр пока enabled = True, после on_update.
        Здесь рисуется визуал компонента на переданном Surface.
        """

    def on_event(self, event: pygame.event.Event) -> None:
        """
        Вызывается для каждого pygame-события (нажатие клавиши,
        клик мыши и т.д.) пока enabled = True.
        """

    def on_destroy(self) -> None:
        """
        Вызывается при удалении GameObject из сцены.
        Освобождайте здесь ресурсы (звуки, поверхности и т.д.).
        """

    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        owner = self._game_object.name if self._game_object else "detached"
        return f"<{self.__class__.__name__} on='{owner}' enabled={self.enabled}>"
