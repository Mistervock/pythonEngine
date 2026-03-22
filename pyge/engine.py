"""
pyge/engine.py
==============
Ядро движка PyGE. Содержит:
  - Application  — создаёт окно, запускает главный цикл, управляет сценами
  - Time         — delta_time, fps, счётчик кадров
  - Color        — удобные константы цветов

Использование в игре
--------------------
from pyge.engine import Application
from pyge.scene import Scene

class MyScene(Scene):
    def on_start(self):
        pass  # создаём объекты здесь

    def on_update(self):
        pass  # логика каждый кадр

if __name__ == "__main__":
    app = Application(title="My Game", width=800, height=600, fps=60)
    app.load_scene(MyScene())
    app.run()
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pygame
from pyge.input import Input

if TYPE_CHECKING:
    from pyge.scene import Scene


# ---------------------------------------------------------------------------
# Time
# ---------------------------------------------------------------------------

class Time:
    """
    Глобальный объект времени. Обновляется один раз за кадр самим Application.

    Атрибуты
    --------
    delta_time : float
        Время (в секундах) между предыдущим и текущим кадром.
    fps : float
        Фактический FPS (скользящее среднее по последним 60 кадрам).
    time_scale : float
        Масштаб времени (1.0 = нормально, 0.0 = пауза, 0.5 = замедление).
    elapsed : float
        Суммарное время с запуска Application, с учётом time_scale.
    real_elapsed : float
        Суммарное реальное время (без учёта time_scale).
    frame_count : int
        Количество прошедших кадров.
    """

    delta_time: float = 0.0
    fps: float = 0.0
    time_scale: float = 1.0
    elapsed: float = 0.0
    real_elapsed: float = 0.0
    frame_count: int = 0

    _fps_samples: list = []
    _fps_sample_size: int = 60

    @classmethod
    def _tick(cls, clock: pygame.time.Clock, target_fps: int) -> None:
        """Вызывается один раз за кадр внутри Application.run()."""
        raw_ms = clock.tick(target_fps)
        raw_dt = raw_ms / 1000.0

        cls.delta_time = raw_dt * cls.time_scale
        cls.elapsed += cls.delta_time
        cls.real_elapsed += raw_dt
        cls.frame_count += 1

        # скользящее среднее FPS
        cls._fps_samples.append(raw_dt)
        if len(cls._fps_samples) > cls._fps_sample_size:
            cls._fps_samples.pop(0)
        avg = sum(cls._fps_samples) / len(cls._fps_samples)
        cls.fps = 1.0 / avg if avg > 0 else 0.0


# ---------------------------------------------------------------------------
# Color
# ---------------------------------------------------------------------------

class Color:
    """Набор стандартных цветов в формате (R, G, B)."""

    BLACK       = (0,   0,   0)
    WHITE       = (255, 255, 255)
    RED         = (220, 50,  50)
    GREEN       = (50,  200, 50)
    BLUE        = (50,  100, 220)
    YELLOW      = (255, 220, 0)
    CYAN        = (0,   220, 220)
    MAGENTA     = (220, 0,   220)
    ORANGE      = (255, 140, 0)
    GRAY        = (128, 128, 128)
    DARK_GRAY   = (64,  64,  64)
    TRANSPARENT = (0,   0,   0,  0)

    @staticmethod
    def lerp(a: tuple, b: tuple, t: float) -> tuple:
        """Линейная интерполяция между двумя цветами. t in [0, 1]."""
        t = max(0.0, min(1.0, t))
        return tuple(int(ca + (cb - ca) * t) for ca, cb in zip(a, b))

    @staticmethod
    def from_hex(hex_str: str) -> tuple:
        """Создать цвет из hex-строки, например '#ff8800' или 'ff8800'."""
        h = hex_str.lstrip('#')
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class Application:
    """
    Точка входа в движок. Создаёт окно pygame и управляет сценами.

    Параметры
    ---------
    title : str
        Заголовок окна.
    width : int
        Ширина окна в пикселях.
    height : int
        Высота окна в пикселях.
    fps : int
        Целевой FPS (по умолчанию 60).
    bg_color : tuple
        Цвет фона по умолчанию (R, G, B).
    resizable : bool
        Разрешить ли изменение размера окна.
    vsync : bool
        Включить ли вертикальную синхронизацию.

    Пример
    ------
    app = Application("Моя игра", 1280, 720, fps=60, bg_color=Color.DARK_GRAY)
    app.load_scene(MainMenuScene())
    app.run()
    """

    # Синглтон — единственный экземпляр, доступен через Application.instance
    instance = None   # type: Application | None

    def __init__(
        self,
        title: str = "PyGE Application",
        width: int = 800,
        height: int = 600,
        fps: int = 60,
        bg_color: tuple = Color.BLACK,
        resizable: bool = False,
        vsync: bool = False,
    ) -> None:
        if Application.instance is not None:
            raise RuntimeError(
                "Application уже создан. "
                "Используйте Application.instance вместо создания нового."
            )
        Application.instance = self

        self.title = title
        self.width = width
        self.height = height
        self.target_fps = fps
        self.bg_color = bg_color

        # Текущая активная сцена и сцена, ожидающая загрузки
        self._current_scene = None   # type: Scene | None
        self._pending_scene  = None  # type: Scene | None

        self._running = False

        # --- Инициализация подсистем pygame ---
        pygame.init()
        pygame.mixer.init()

        flags = pygame.RESIZABLE if resizable else 0
        self.screen: pygame.Surface = pygame.display.set_mode(
            (width, height), flags
        )
        pygame.display.set_caption(title)
        self._clock = pygame.time.Clock()

        print(
            f"[PyGE] Запущено: '{title}'  "
            f"{width}x{height}  @  {fps} FPS"
        )

    # ------------------------------------------------------------------
    # Публичный API — управление сценами
    # ------------------------------------------------------------------

    def load_scene(self, scene) -> None:
        """
        Запланировать загрузку новой сцены.

        Смена сцены происходит в начале следующего кадра — это безопасно,
        даже если вызывать load_scene() прямо внутри on_update().
        """
        self._pending_scene = scene

    # ------------------------------------------------------------------
    # Внутренние методы
    # ------------------------------------------------------------------

    def _apply_pending_scene(self) -> None:
        """Выгружает текущую сцену и загружает ожидающую (если есть)."""
        if self._pending_scene is None:
            return

        # Выгрузить старую сцену
        if self._current_scene is not None:
            self._current_scene._on_unload()

        # Загрузить новую
        self._current_scene = self._pending_scene
        self._pending_scene  = None

        self._current_scene._application = self
        self._current_scene._on_load()

    def _handle_system_events(self, events: list) -> None:
        """Обрабатывает системные события pygame (выход, resize и т.д.)."""
        for event in events:
            if event.type == pygame.QUIT:
                self._running = False
            elif event.type == pygame.VIDEORESIZE:
                self.width, self.height = event.w, event.h

    # ------------------------------------------------------------------
    # Главный цикл
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Запустить главный игровой цикл.

        Порядок за кадр:
          1. Тик времени (Time._tick)
          2. Применить ожидающую смену сцены
          3. Собрать события pygame
          4. Системные события (quit / resize)
          5. Передать события в сцену (Input + on_event)
          6. Обновить сцену (on_update + компоненты)
          7. Очистить экран
          8. Отрендерить сцену (спрайты, тайлмапы, UI)
          9. pygame.display.flip()
        """
        self._running = True
        self._apply_pending_scene()   # загрузить стартовую сцену

        while self._running:
            # 1. Время
            Time._tick(self._clock, self.target_fps)

            # 2. Смена сцены
            self._apply_pending_scene()

            # 3. Сбор событий
            events = pygame.event.get()

            # 4. Системные события
            self._handle_system_events(events)

            # 4а. Обновить Input (однокадровые состояния клавиш/мыши)
            Input._update(events)
            if not self._running:
                break

            scene = self._current_scene

            # 5. События → сцена
            if scene is not None:
                scene._process_events(events)

            # 6. Update
            if scene is not None:
                scene._update()

            # 7. Очистить
            self.screen.fill(self.bg_color)

            # 8. Render
            if scene is not None:
                scene._render(self.screen)

            # 9. Flip
            pygame.display.flip()

        self._shutdown()

    # ------------------------------------------------------------------
    # Завершение
    # ------------------------------------------------------------------

    def quit(self) -> None:
        """Завершить цикл из любого места (например, из кнопки «Выход»)."""
        self._running = False

    def _shutdown(self) -> None:
        """Финальная очистка ресурсов."""
        if self._current_scene is not None:
            self._current_scene._on_unload()
        pygame.quit()
        Application.instance = None
        print("[PyGE] Остановлено.")
        sys.exit(0)

    # ------------------------------------------------------------------
    # Вспомогательные свойства
    # ------------------------------------------------------------------

    @property
    def screen_size(self) -> tuple:
        """Текущий размер окна как (width, height)."""
        return (self.width, self.height)

    @property
    def center(self) -> tuple:
        """Центр экрана в пикселях как (cx, cy)."""
        return (self.width // 2, self.height // 2)

    def __repr__(self) -> str:
        return f"<Application '{self.title}' {self.width}x{self.height}>"
