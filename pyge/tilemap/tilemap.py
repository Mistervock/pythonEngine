"""
pyge/tilemap/tilemap.py
=======================
Содержит:
  - Tile          -- описание одного типа тайла
  - Tileset       -- набор тайлов (цветной или из атласа-изображения)
  - Tilemap       -- компонент карты тайлов
  - TilemapLoader -- загрузка / сохранение карт (CSV, dict)

Возможности
-----------
  - Два режима тайлсета: цветной (без изображений) и атлас (spritesheet)
  - Frustum culling -- рендерится только видимая область
  - Поддержка смещения камеры (camera_offset)
  - auto_colliders -- автосоздание BoxCollider2D для непроходимых тайлов
  - Динамическое изменение тайлов через set_cell()
  - CSV-загрузка / сохранение
  - Поиск тайлов по ID (find_cells_by_id)

Быстрый старт -- цветная карта
--------------------------------
from pyge.tilemap.tilemap import Tile, Tileset, Tilemap

tileset = Tileset()
tileset.add_tile(Tile(0, passable=True,  color=(34, 139, 34), name="grass"))
tileset.add_tile(Tile(1, passable=False, color=(80,  60,  40), name="wall"))

MAP = [
    [1,1,1,1,1,1],
    [1,0,0,0,0,1],
    [1,0,1,0,0,1],
    [1,0,0,0,0,1],
    [1,1,1,1,1,1],
]

map_obj = GameObject("Map", x=0, y=0)
tm = Tilemap(tileset=tileset, grid=MAP, tile_size=32, auto_colliders=True)
map_obj.add_component(tm)
scene.add(map_obj)

Быстрый старт -- атлас
------------------------
tileset = Tileset.from_image("assets/tiles.png", tile_w=16, tile_h=16)
tileset.set_passable(0, True)
tileset.set_passable(3, False)

grid = TilemapLoader.from_csv("maps/level1.csv")
tm = Tilemap(tileset=tileset, grid=grid, tile_size=32)
"""

from __future__ import annotations
import csv
import os
from typing import TYPE_CHECKING
import pygame

from pyge.component import Component
from pyge.game_object import Vector2

if TYPE_CHECKING:
    pass


# ============================================================
# Tile
# ============================================================

class Tile:
    """
    Описание одного типа тайла в тайлсете.

    Параметры
    ---------
    tile_id  : int    уникальный ID
    passable : bool   True = можно ходить, False = стена (создаётся коллайдер)
    color    : tuple  (R,G,B) -- цвет в цветном режиме рендера
    name     : str    имя для удобства ("grass", "wall", ...)
    data     : dict   произвольные данные (урон, замедление и т.д.)
    """

    __slots__ = ("tile_id", "passable", "color", "name", "data")

    def __init__(
        self,
        tile_id: int,
        passable: bool = True,
        color: tuple = (180, 180, 180),
        name: str = "",
        data: dict | None = None,
    ) -> None:
        self.tile_id  = tile_id
        self.passable = passable
        self.color    = color
        self.name     = name
        self.data     = data or {}

    def __repr__(self) -> str:
        return f"<Tile id={self.tile_id} '{self.name}' passable={self.passable}>"


# ============================================================
# Tileset
# ============================================================

class Tileset:
    """
    Набор тайлов. Два режима:

    Режим 1 -- цветной (без изображения):
        ts = Tileset()
        ts.add_tile(Tile(0, passable=True,  color=(34,139,34)))
        ts.add_tile(Tile(1, passable=False, color=(80, 60, 40)))

    Режим 2 -- атлас (spritesheet):
        ts = Tileset.from_image("assets/tiles.png", tile_w=16, tile_h=16)
        ts.set_passable(0, True)
        ts.set_passable(1, False)

    В режиме атласа тайлы нумеруются слева-направо, сверху-вниз.
    """

    def __init__(self) -> None:
        self._tiles:  dict = {}   # tile_id -> Tile
        self._image:  pygame.Surface | None = None
        self._tile_w: int = 0
        self._tile_h: int = 0
        self._frames: dict = {}   # tile_id -> Surface (вырезанный фрейм)

    # --- цветной режим ---

    def add_tile(self, tile: Tile) -> None:
        self._tiles[tile.tile_id] = tile

    def get_tile(self, tile_id: int) -> Tile | None:
        return self._tiles.get(tile_id)

    def set_passable(self, tile_id: int, passable: bool) -> None:
        """Установить проходимость. Создаёт Tile если его нет."""
        if tile_id not in self._tiles:
            self._tiles[tile_id] = Tile(tile_id)
        self._tiles[tile_id].passable = passable

    # --- режим атласа ---

    @classmethod
    def from_image(cls, image_path: str, tile_w: int, tile_h: int) -> "Tileset":
        """
        Создать тайлсет из изображения-атласа.

        image_path : путь к файлу
        tile_w     : ширина одного тайла (пикс)
        tile_h     : высота одного тайла (пикс)
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Tileset: файл не найден '{image_path}'")

        ts = cls()
        img = pygame.image.load(image_path).convert_alpha()
        ts._image  = img
        ts._tile_w = tile_w
        ts._tile_h = tile_h

        cols = img.get_width()  // tile_w
        rows = img.get_height() // tile_h

        for row in range(rows):
            for col in range(cols):
                tid   = row * cols + col
                rect  = pygame.Rect(col * tile_w, row * tile_h, tile_w, tile_h)
                frame = pygame.Surface((tile_w, tile_h), pygame.SRCALPHA)
                frame.blit(img, (0, 0), rect)
                ts._frames[tid] = frame
                ts._tiles[tid]  = Tile(tile_id=tid, passable=True)

        return ts

    def get_frame(self, tile_id: int) -> pygame.Surface | None:
        return self._frames.get(tile_id)

    @property
    def has_image(self) -> bool:
        return self._image is not None

    @property
    def tile_w(self) -> int:
        return self._tile_w

    @property
    def tile_h(self) -> int:
        return self._tile_h


# ============================================================
# Tilemap
# ============================================================

class Tilemap(Component):
    """
    Компонент тайловой карты. Добавляется на GameObject.

    Параметры
    ---------
    tileset       : Tileset            набор тайлов
    grid          : list[list[int]]    2D-сетка ID тайлов (-1 = пустой тайл)
    tile_size     : int                размер тайла на экране (пикс)
    camera_offset : Vector2 | None     смещение камеры (обновляйте каждый кадр)
    auto_colliders: bool               создавать BoxCollider2D для стен
    debug         : bool               рисовать сетку

    Методы
    ------
    tm.get_tile_at_cell(col, row)  -> Tile | None
    tm.get_tile_at_world(wx, wy)   -> Tile | None
    tm.set_cell(col, row, tile_id) -> None
    tm.world_to_cell(wx, wy)       -> (col, row)
    tm.cell_to_world(col, row)     -> (wx, wy)  левый верх тайла
    tm.is_passable(wx, wy)         -> bool
    tm.find_cells_by_id(tile_id)   -> list[(col, row)]
    tm.map_width()                 -> int  (пикс)
    tm.map_height()                -> int  (пикс)
    """

    def __init__(
        self,
        tileset: Tileset,
        grid: list,
        tile_size: int = 32,
        camera_offset: Vector2 | None = None,
        auto_colliders: bool = False,
        debug: bool = False,
    ) -> None:
        super().__init__()
        self.tileset        = tileset
        self._grid          = [list(row) for row in grid]
        self.tile_size      = tile_size
        self.camera_offset  = camera_offset or Vector2(0.0, 0.0)
        self.auto_colliders = auto_colliders
        self.debug          = debug

        self.rows = len(self._grid)
        self.cols = max((len(r) for r in self._grid), default=0)

        self._scaled_frames: dict = {}
        self._wall_objects:  list = []

    # ------------------------------------------------------------------
    # Жизненный цикл
    # ------------------------------------------------------------------

    def on_awake(self) -> None:
        self._build_scaled_frames()
        if self.auto_colliders:
            self._build_colliders()

    def on_render(self, screen: pygame.Surface) -> None:
        ts = self.tile_size
        ox = int(self.transform.x - self.camera_offset.x)
        oy = int(self.transform.y - self.camera_offset.y)
        sw = screen.get_width()
        sh = screen.get_height()

        # Frustum culling -- только видимые тайлы
        col_start = max(0, (-ox) // ts)
        col_end   = min(self.cols, col_start + sw // ts + 2)
        row_start = max(0, (-oy) // ts)
        row_end   = min(self.rows, row_start + sh // ts + 2)

        for row in range(row_start, row_end):
            for col in range(col_start, col_end):
                if col >= len(self._grid[row]):
                    continue
                tid = self._grid[row][col]
                if tid < 0:
                    continue   # пустой тайл

                dx = ox + col * ts
                dy = oy + row * ts

                if self.tileset.has_image:
                    frame = self._scaled_frames.get(tid)
                    if frame:
                        screen.blit(frame, (dx, dy))
                    else:
                        # placeholder для неизвестного ID
                        pygame.draw.rect(screen, (255, 0, 200), (dx, dy, ts, ts))
                else:
                    tile  = self.tileset.get_tile(tid)
                    color = tile.color if tile else (255, 0, 200)
                    pygame.draw.rect(screen, color, (dx, dy, ts, ts))

                if self.debug:
                    pygame.draw.rect(screen, (40, 40, 40), (dx, dy, ts, ts), 1)

    # ------------------------------------------------------------------
    # Публичный API
    # ------------------------------------------------------------------

    def get_tile_at_cell(self, col: int, row: int) -> Tile | None:
        """Tile по координатам клетки."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            if col < len(self._grid[row]):
                return self.tileset.get_tile(self._grid[row][col])
        return None

    def get_tile_at_world(self, wx: float, wy: float) -> Tile | None:
        """Tile по мировым координатам."""
        col, row = self.world_to_cell(wx, wy)
        return self.get_tile_at_cell(col, row)

    def set_cell(self, col: int, row: int, tile_id: int) -> None:
        """Изменить тайл на карте."""
        if 0 <= row < self.rows and 0 <= col < self.cols:
            if col < len(self._grid[row]):
                self._grid[row][col] = tile_id

    def world_to_cell(self, wx: float, wy: float) -> tuple:
        """Мировые координаты -> (col, row)."""
        ts  = self.tile_size
        col = int((wx - self.transform.x) // ts)
        row = int((wy - self.transform.y) // ts)
        return col, row

    def cell_to_world(self, col: int, row: int) -> tuple:
        """(col, row) -> мировые координаты левого верхнего угла тайла."""
        return (
            self.transform.x + col * self.tile_size,
            self.transform.y + row * self.tile_size,
        )

    def is_passable(self, wx: float, wy: float) -> bool:
        """True если тайл в точке (wx, wy) проходим."""
        tile = self.get_tile_at_world(wx, wy)
        return tile.passable if tile is not None else False

    def find_cells_by_id(self, tile_id: int) -> list:
        """Найти все клетки с данным ID. Возвращает [(col, row), ...]."""
        result = []
        for row in range(self.rows):
            for col in range(len(self._grid[row])):
                if self._grid[row][col] == tile_id:
                    result.append((col, row))
        return result

    def map_width(self) -> int:
        """Ширина карты в пикселях."""
        return self.cols * self.tile_size

    def map_height(self) -> int:
        """Высота карты в пикселях."""
        return self.rows * self.tile_size

    def get_grid(self) -> list:
        """Вернуть копию текущей сетки."""
        return [list(row) for row in self._grid]

    # ------------------------------------------------------------------
    # Внутренние
    # ------------------------------------------------------------------

    def _build_scaled_frames(self) -> None:
        if not self.tileset.has_image:
            return
        ts = self.tile_size
        tw = self.tileset.tile_w
        th = self.tileset.tile_h
        for tid, frame in self.tileset._frames.items():
            if tw == ts and th == ts:
                self._scaled_frames[tid] = frame
            else:
                self._scaled_frames[tid] = pygame.transform.scale(frame, (ts, ts))

    def _build_colliders(self) -> None:
        """Создать статические BoxCollider2D для каждой непроходимой клетки."""
        from pyge.physics.rigidbody import BoxCollider2D
        from pyge.game_object import GameObject as GO
        ts = self.tile_size

        for row in range(self.rows):
            for col in range(len(self._grid[row])):
                tid  = self._grid[row][col]
                tile = self.tileset.get_tile(tid)
                if tile is None or tile.passable:
                    continue

                wx, wy = self.cell_to_world(col, row)
                cx = wx + ts / 2
                cy = wy + ts / 2

                wall = GO(f"_wall_{col}_{row}", x=cx, y=cy)
                wall.add_component(BoxCollider2D(width=ts, height=ts, is_static=True))

                try:
                    self.game_object.scene.add(wall)
                    self._wall_objects.append(wall)
                except Exception:
                    pass  # объект ещё не в сцене

    def on_destroy(self) -> None:
        for obj in self._wall_objects:
            try:
                self.game_object.scene.remove(obj)
            except Exception:
                pass
        self._wall_objects.clear()

    def __repr__(self) -> str:
        return f"<Tilemap {self.cols}x{self.rows} tile_size={self.tile_size}>"


# ============================================================
# TilemapLoader
# ============================================================

class TilemapLoader:
    """
    Загрузка и сохранение карт.

    Методы
    ------
    TilemapLoader.from_csv(path)         -> list[list[int]]
    TilemapLoader.to_csv(grid, path)     -> None
    TilemapLoader.from_dict(data)        -> (grid, tile_size)
    """

    @staticmethod
    def from_csv(path: str, delimiter: str = ",") -> list:
        """
        Загрузить сетку из CSV-файла.

        Формат:
            1,1,1,1,1
            1,0,0,0,1
            1,1,1,1,1

        Возвращает list[list[int]].
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"TilemapLoader: файл не найден '{path}'")
        grid = []
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.reader(f, delimiter=delimiter):
                clean = [c.strip() for c in row if c.strip() != ""]
                if clean:
                    grid.append([int(v) for v in clean])
        return grid

    @staticmethod
    def to_csv(grid: list, path: str, delimiter: str = ",") -> None:
        """Сохранить сетку в CSV-файл."""
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter=delimiter)
            for row in grid:
                writer.writerow(row)

    @staticmethod
    def from_dict(data: dict) -> tuple:
        """
        Загрузить карту из словаря.

        Формат:
            {
                "tile_size": 32,
                "grid": [[1,1,1],[1,0,1],[1,1,1]]
            }

        Возвращает (grid, tile_size).
        """
        return data.get("grid", []), data.get("tile_size", 32)
