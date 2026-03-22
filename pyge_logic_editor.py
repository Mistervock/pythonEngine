"""
pyge_logic_editor.py
====================
Визуальный редактор коллизий и поведений PyGE.

Вкладка «Коллизии»:
  - Визуально добавить BoxCollider2D / CircleCollider2D на объект
  - Настроить размер, смещение, is_static, is_trigger, layer/mask
  - Превью прямо на канвасе

Вкладка «Поведения»:
  - Выбрать объект и назначить ему готовые блоки поведения:
      Movement (WASD/стрелки), Jump, Follow, Rotate, Patrol,
      Health, Damage, Destroy on collision, Custom code
  - Настроить параметры каждого блока
  - Экспорт всего в готовый Python-компонент

Запуск:
  python pyge_logic_editor.py [папка_проекта]
  или из лаунчера через кнопку «Логика»
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os, sys, json, copy
from PIL import Image, ImageTk

# ──────────────────────────────────────────────
#  Цвета
# ──────────────────────────────────────────────
BG      = "#0d1117"
BG2     = "#161b22"
BG3     = "#1f2937"
BG4     = "#111827"
ACCENT  = "#3b82f6"
ACCENT2 = "#60a5fa"
GREEN   = "#22c55e"
RED     = "#ef4444"
YELLOW  = "#f59e0b"
ORANGE  = "#f97316"
PURPLE  = "#a855f7"
TEAL    = "#14b8a6"
TEXT    = "#f1f5f9"
TEXT2   = "#94a3b8"
TEXT3   = "#475569"
BORDER  = "#2d3748"
HOVER   = "#1e293b"
SEL     = "#1d4ed8"

# ──────────────────────────────────────────────
#  Каталог готовых поведений
# ──────────────────────────────────────────────

BEHAVIORS = {
    "Движение (WASD)": {
        "id":    "movement",
        "color": GREEN,
        "icon":  "🕹",
        "desc":  "Двигает объект по осям через Input.axis",
        "params": [
            {"name": "speed",        "label": "Скорость (пикс/с)", "type": "float", "default": 200.0},
            {"name": "keys",         "label": "Раскладка",         "type": "choice",
             "choices": ["WASD", "Стрелки", "WASD + Стрелки"],    "default": "WASD + Стрелки"},
            {"name": "use_rigidbody","label": "Через Rigidbody",   "type": "bool",  "default": True},
        ],
        "code": '''
class Movement(Component):
    def on_start(self):
        self.rb = self.get_component(Rigidbody2D)

    def on_update(self):
        dx = Input.axis("horizontal")
        dy = Input.axis("vertical")
        if self.rb:
            self.rb.velocity.x = dx * {speed}
        else:
            self.transform.x += dx * {speed} * Time.delta_time
            self.transform.y += dy * {speed} * Time.delta_time
''',
    },

    "Прыжок": {
        "id":    "jump",
        "color": ACCENT,
        "icon":  "⬆",
        "desc":  "Прыжок по Space / нажатию кнопки",
        "params": [
            {"name": "jump_force",  "label": "Сила прыжка",     "type": "float",  "default": -520.0},
            {"name": "jump_key",    "label": "Клавиша прыжка",  "type": "str",    "default": "space"},
            {"name": "can_double",  "label": "Двойной прыжок",  "type": "bool",   "default": False},
        ],
        "code": '''
class Jump(Component):
    def on_start(self):
        self.rb       = self.get_component(Rigidbody2D)
        self.grounded = False
        self._jumps   = 0
        self._max     = 2 if {can_double} else 1

    def on_collision_enter(self, info):
        if info.normal[1] < -0.5:
            self.grounded = True
            self._jumps   = 0

    def on_update(self):
        if self.rb.velocity.y > 50:
            self.grounded = False
        if Input.key_down("{jump_key}") and (self.grounded or self._jumps < self._max):
            self.rb.velocity.y = {jump_force}
            self.grounded = False
            self._jumps  += 1
''',
    },

    "Вращение": {
        "id":    "rotate",
        "color": YELLOW,
        "icon":  "🔄",
        "desc":  "Постоянно вращает объект",
        "params": [
            {"name": "speed", "label": "Скорость (°/с)", "type": "float", "default": 90.0},
        ],
        "code": '''
class Rotator(Component):
    def on_update(self):
        self.transform.rotation += {speed} * Time.delta_time
''',
    },

    "Следование за объектом": {
        "id":    "follow",
        "color": TEAL,
        "icon":  "🎯",
        "desc":  "Плавно следует за объектом с заданным тегом",
        "params": [
            {"name": "target_tag", "label": "Тег цели",      "type": "str",   "default": "player"},
            {"name": "speed",      "label": "Скорость",       "type": "float", "default": 150.0},
            {"name": "offset_x",   "label": "Смещение X",     "type": "float", "default": 0.0},
            {"name": "offset_y",   "label": "Смещение Y",     "type": "float", "default": -100.0},
            {"name": "smooth",     "label": "Сглаживание",    "type": "float", "default": 5.0},
        ],
        "code": '''
class Follow(Component):
    def on_update(self):
        target = self.scene.find_by_tag("{target_tag}")
        if target is None:
            return
        tx = target.transform.x + {offset_x}
        ty = target.transform.y + {offset_y}
        self.transform.x += (tx - self.transform.x) * {smooth} * Time.delta_time
        self.transform.y += (ty - self.transform.y) * {smooth} * Time.delta_time
''',
    },

    "Патруль": {
        "id":    "patrol",
        "color": ORANGE,
        "icon":  "↔",
        "desc":  "Ходит туда-обратно между двумя точками",
        "params": [
            {"name": "dist",  "label": "Расстояние (пикс)", "type": "float", "default": 200.0},
            {"name": "speed", "label": "Скорость",           "type": "float", "default": 100.0},
            {"name": "axis",  "label": "Ось",                "type": "choice",
             "choices": ["horizontal", "vertical"],          "default": "horizontal"},
        ],
        "code": '''
class Patrol(Component):
    def on_start(self):
        self._start_x = self.transform.x
        self._start_y = self.transform.y
        self._dir     = 1.0

    def on_update(self):
        if "{axis}" == "horizontal":
            self.transform.x += self._dir * {speed} * Time.delta_time
            diff = self.transform.x - self._start_x
        else:
            self.transform.y += self._dir * {speed} * Time.delta_time
            diff = self.transform.y - self._start_y
        if abs(diff) >= {dist}:
            self._dir *= -1
''',
    },

    "Здоровье": {
        "id":    "health",
        "color": RED,
        "icon":  "❤",
        "desc":  "Компонент здоровья с уроном и смертью",
        "params": [
            {"name": "max_hp",       "label": "Макс. здоровье",   "type": "int",   "default": 100},
            {"name": "damage_tag",   "label": "Тег урона",         "type": "str",   "default": "bullet"},
            {"name": "damage",       "label": "Урон за касание",   "type": "int",   "default": 10},
            {"name": "invincible_t", "label": "Неуязвимость (с)",  "type": "float", "default": 0.5},
            {"name": "on_death",     "label": "При смерти",        "type": "choice",
             "choices": ["Удалить объект", "Перезапустить сцену", "Ничего"],
             "default": "Удалить объект"},
        ],
        "code": '''
class Health(Component):
    def on_start(self):
        self.hp          = {max_hp}
        self._invincible = 0.0

    def on_update(self):
        if self._invincible > 0:
            self._invincible -= Time.delta_time

    def take_damage(self, amount):
        if self._invincible > 0:
            return
        self.hp -= amount
        self._invincible = {invincible_t}
        if self.hp <= 0:
            self._die()

    def _die(self):
        action = "{on_death}"
        if action == "Удалить объект":
            self.scene.remove(self.game_object)
        elif action == "Перезапустить сцену":
            import importlib, sys
            self.app.load_scene(type(self.scene)())

    def on_collision_enter(self, info):
        if info.other.tag == "{damage_tag}":
            self.take_damage({damage})
''',
    },

    "Уничтожить при коллизии": {
        "id":    "destroy_on_col",
        "color": ORANGE,
        "icon":  "💥",
        "desc":  "Удаляет объект при столкновении с тегом",
        "params": [
            {"name": "target_tag", "label": "Тег цели",            "type": "str",  "default": "player"},
            {"name": "destroy_self","label": "Уничтожить себя",     "type": "bool", "default": True},
            {"name": "destroy_other","label":"Уничтожить другого",   "type": "bool", "default": False},
        ],
        "code": '''
class DestroyOnCollision(Component):
    def on_collision_enter(self, info):
        if info.other.tag == "{target_tag}":
            if {destroy_other}:
                self.scene.remove(info.other)
            if {destroy_self}:
                self.scene.remove(self.game_object)
''',
    },

    "Анимация при движении": {
        "id":    "anim_move",
        "color": PURPLE,
        "icon":  "🎬",
        "desc":  "Переключает анимации idle/run в зависимости от скорости",
        "params": [
            {"name": "anim_idle",  "label": "Анимация покоя",   "type": "str", "default": "idle"},
            {"name": "anim_run",   "label": "Анимация бега",     "type": "str", "default": "run"},
            {"name": "threshold",  "label": "Порог скорости",    "type": "float", "default": 10.0},
        ],
        "code": '''
class AnimationController(Component):
    def on_start(self):
        self.rb       = self.get_component(Rigidbody2D)
        self._current = None

    def _set_anim(self, name):
        if self._current == name:
            return
        self._current = name
        sr = self.get_component(SpriteRenderer)
        if sr:
            sr.set_source(f"assets/{{name}}.png")

    def on_update(self):
        spd = abs(self.rb.velocity.x) if self.rb else 0
        if spd > {threshold}:
            self._set_anim("{anim_run}")
        else:
            self._set_anim("{anim_idle}")
''',
    },

    "Пользовательский код": {
        "id":    "custom",
        "color": TEXT2,
        "icon":  "⌨",
        "desc":  "Напишите свой компонент вручную",
        "params": [
            {"name": "class_name", "label": "Имя класса",  "type": "str", "default": "MyComponent"},
            {"name": "code",       "label": "Код (on_update)", "type": "text",
             "default": "        # self.transform.x += 100 * Time.delta_time\n        pass"},
        ],
        "code": '''
class {class_name}(Component):
    def on_start(self):
        pass

    def on_update(self):
{code}
''',
    },
}

# ──────────────────────────────────────────────
#  Модели данных
# ──────────────────────────────────────────────

class ColliderData:
    def __init__(self, kind="box", w=64, h=64, r=32,
                 ox=0.0, oy=0.0, is_static=False,
                 is_trigger=False, layer=0, mask=0xFFFFFFFF,
                 restitution=0.1):
        self.kind        = kind          # "box" | "circle"
        self.w           = w
        self.h           = h
        self.r           = r
        self.ox          = ox
        self.oy          = oy
        self.is_static   = is_static
        self.is_trigger  = is_trigger
        self.layer       = layer
        self.mask        = mask
        self.restitution = restitution

    def to_dict(self):  return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d):
        c = cls.__new__(cls)
        c.__dict__.update(d)
        return c


class ObjectLogic:
    """Логика одного объекта: коллайдеры + поведения."""
    def __init__(self, name, image_path="", x=0.0, y=0.0):
        self.name        = name
        self.image_path  = image_path
        self.x           = x
        self.y           = y
        self.colliders: list[ColliderData] = []
        self.behaviors:  list[dict]        = []   # {behavior_id, params}

    def to_dict(self):
        return {
            "name":       self.name,
            "image_path": self.image_path,
            "x":          self.x,
            "y":          self.y,
            "colliders":  [c.to_dict() for c in self.colliders],
            "behaviors":  self.behaviors,
        }

    @classmethod
    def from_dict(cls, d):
        obj = cls(d["name"], d.get("image_path",""), d.get("x",0), d.get("y",0))
        obj.colliders = [ColliderData.from_dict(c) for c in d.get("colliders", [])]
        obj.behaviors = d.get("behaviors", [])
        return obj


class LogicProject:
    def __init__(self, project_dir):
        self.project_dir = project_dir
        self.objects: list[ObjectLogic] = []
        self._path = os.path.join(project_dir, ".pyge_logic.json")

    def save(self):
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump([o.to_dict() for o in self.objects], f, indent=2, ensure_ascii=False)

    def load(self):
        if not os.path.exists(self._path):
            # Попробуем импортировать из editor-файла
            editor_path = os.path.join(self.project_dir, ".pyge_editor.json")
            if os.path.exists(editor_path):
                with open(editor_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for obj_d in data.get("objects", []):
                    self.objects.append(ObjectLogic(
                        name=obj_d.get("name","Object"),
                        image_path=obj_d.get("image_path",""),
                        x=obj_d.get("x",0),
                        y=obj_d.get("y",0),
                    ))
            return
        with open(self._path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.objects = [ObjectLogic.from_dict(d) for d in data]


# ──────────────────────────────────────────────
#  Утилиты PIL
# ──────────────────────────────────────────────
_pil_cache: dict = {}

def load_pil(path):
    if path in _pil_cache:
        return _pil_cache[path]
    if not path or not os.path.exists(path):
        return None
    try:
        img = Image.open(path).convert("RGBA")
        _pil_cache[path] = img
        return img
    except Exception:
        return None

def pil_to_tk(img):
    return ImageTk.PhotoImage(img)


# ──────────────────────────────────────────────
#  Главное окно
# ──────────────────────────────────────────────

class LogicEditor:

    CANVAS_W = 600
    CANVAS_H = 500

    def __init__(self, project_dir: str):
        self.project_dir = project_dir
        self.lp = LogicProject(project_dir)
        self.lp.load()

        self.root = tk.Tk()
        self.root.title(f"PyGE Logic Editor  —  {os.path.basename(project_dir)}")
        self.root.geometry("1300x780")
        self.root.minsize(1100, 680)
        self.root.configure(bg=BG)

        self._selected_obj: ObjectLogic | None = None
        self._selected_col: ColliderData | None = None
        self._drag_col      = None
        self._drag_start    = None
        self._tk_images     = {}
        self._canvas_scale  = 1.0

        self._build_ui()
        if self.lp.objects:
            self._select_object(self.lp.objects[0])

    # ══════════════════════════════════════════
    #  UI
    # ══════════════════════════════════════════

    def _build_ui(self):
        # Шапка
        hdr = tk.Frame(self.root, bg=BG2, height=48)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="⬡ PyGE Logic Editor",
                 bg=BG2, fg=TEXT, font=("Consolas", 15, "bold")).pack(side="left", padx=16, pady=10)
        tk.Label(hdr, text=os.path.basename(project_dir) if 'project_dir' in dir() else "",
                 bg=BG2, fg=TEXT3, font=("Consolas", 10)).pack(side="left")

        for label, cmd, color in [
            ("💾 Сохранить",      self._save,         BG3),
            ("📋 Экспорт кода",   self._export_code,  ACCENT),
        ]:
            tk.Button(hdr, text=label, command=cmd,
                      bg=color, fg=TEXT, font=("Consolas", 10),
                      relief="flat", cursor="hand2", padx=12, pady=4,
                      activebackground=BG4, activeforeground=TEXT,
                      ).pack(side="right", padx=4, pady=8)

        # Вкладки
        tab_bar = tk.Frame(self.root, bg=BG2, height=36)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)

        self._tab_btns   = {}
        self._tab_frames = {}

        for key, label in [("colliders", "🔷  Коллизии"), ("behaviors", "⚡  Поведения")]:
            b = tk.Button(tab_bar, text=label,
                          command=lambda k=key: self._switch_tab(k),
                          bg=ACCENT if key == "colliders" else BG2,
                          fg=TEXT, font=("Consolas", 10),
                          relief="flat", cursor="hand2", padx=18, pady=6,
                          activebackground=BG3, activeforeground=TEXT)
            b.pack(side="left")
            self._tab_btns[key] = b

        tk.Frame(self.root, bg=BORDER, height=1).pack(fill="x")

        self._content = tk.Frame(self.root, bg=BG)
        self._content.pack(fill="both", expand=True)

        self._build_collider_tab()
        self._build_behavior_tab()
        self._switch_tab("colliders")

    def _switch_tab(self, key):
        for f in self._tab_frames.values():
            f.pack_forget()
        self._tab_frames[key].pack(fill="both", expand=True)
        for k, b in self._tab_btns.items():
            b.configure(bg=ACCENT if k == key else BG2)

    # ══════════════════════════════════════════
    #  Вкладка КОЛЛИЗИИ
    # ══════════════════════════════════════════

    def _build_collider_tab(self):
        frame = tk.Frame(self._content, bg=BG)
        self._tab_frames["colliders"] = frame

        # Левая — объекты
        left = tk.Frame(frame, bg=BG2, width=190)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        tk.Label(left, text="ОБЪЕКТЫ", bg=BG2, fg=TEXT3,
                 font=("Consolas", 8, "bold")).pack(anchor="w", padx=10, pady=(10,4))

        btn_row = tk.Frame(left, bg=BG2)
        btn_row.pack(fill="x", padx=6, pady=(0,6))
        tk.Button(btn_row, text="+ Объект",
                  command=self._add_object,
                  bg=ACCENT, fg=TEXT, font=("Consolas", 9),
                  relief="flat", cursor="hand2", padx=8, pady=3,
                  activebackground=ACCENT2, activeforeground=TEXT,
                  ).pack(side="left")
        tk.Button(btn_row, text="🗑",
                  command=self._delete_object,
                  bg=BG3, fg=RED, font=("Consolas", 9),
                  relief="flat", cursor="hand2", padx=8, pady=3,
                  activebackground=BG4, activeforeground=RED,
                  ).pack(side="left", padx=(4,0))

        tk.Frame(left, bg=BORDER, height=1).pack(fill="x")

        self._obj_lb = tk.Listbox(left, bg=BG2, fg=TEXT,
                                   selectbackground=SEL, selectforeground=TEXT,
                                   font=("Consolas", 10), relief="flat", bd=0,
                                   activestyle="none", highlightthickness=0)
        self._obj_lb.pack(fill="both", expand=True)
        self._obj_lb.bind("<<ListboxSelect>>", self._on_obj_lb_select)

        tk.Frame(frame, bg=BORDER, width=1).pack(side="left", fill="y")

        # Центр — канвас
        center = tk.Frame(frame, bg=BG4)
        center.pack(side="left", fill="both", expand=True)

        col_toolbar = tk.Frame(center, bg=BG3, height=36)
        col_toolbar.pack(fill="x")
        col_toolbar.pack_propagate(False)

        tk.Label(col_toolbar, text="Добавить коллайдер:",
                 bg=BG3, fg=TEXT3, font=("Consolas", 9)).pack(side="left", padx=8, pady=6)

        tk.Button(col_toolbar, text="⬜ Box",
                  command=lambda: self._add_collider("box"),
                  bg=ACCENT, fg=TEXT, font=("Consolas", 9),
                  relief="flat", cursor="hand2", padx=10, pady=3,
                  activebackground=ACCENT2, activeforeground=TEXT,
                  ).pack(side="left", padx=4)

        tk.Button(col_toolbar, text="⭕ Circle",
                  command=lambda: self._add_collider("circle"),
                  bg=TEAL, fg=TEXT, font=("Consolas", 9),
                  relief="flat", cursor="hand2", padx=10, pady=3,
                  activebackground="#0d9488", activeforeground=TEXT,
                  ).pack(side="left", padx=4)

        tk.Button(col_toolbar, text="🗑 Удалить выбранный",
                  command=self._delete_collider,
                  bg=BG3, fg=RED, font=("Consolas", 9),
                  relief="flat", cursor="hand2", padx=10, pady=3,
                  activebackground=BG4, activeforeground=RED,
                  ).pack(side="left", padx=4)

        # Канвас
        canv_frame = tk.Frame(center, bg=BG4)
        canv_frame.pack(fill="both", expand=True, padx=8, pady=8)

        self._col_canvas = tk.Canvas(canv_frame, bg="#080d14",
                                      width=self.CANVAS_W, height=self.CANVAS_H,
                                      highlightthickness=1,
                                      highlightbackground=BORDER,
                                      cursor="crosshair")
        self._col_canvas.pack(expand=True)

        self._col_canvas.bind("<ButtonPress-1>",   self._col_press)
        self._col_canvas.bind("<B1-Motion>",        self._col_drag)
        self._col_canvas.bind("<ButtonRelease-1>",  self._col_release)

        tk.Frame(frame, bg=BORDER, width=1).pack(side="left", fill="y")

        # Правая — свойства коллайдера
        right = tk.Frame(frame, bg=BG2, width=240)
        right.pack(side="left", fill="y")
        right.pack_propagate(False)

        tk.Label(right, text="КОЛЛАЙДЕР", bg=BG2, fg=TEXT3,
                 font=("Consolas", 8, "bold")).pack(anchor="w", padx=10, pady=(10,4))
        tk.Frame(right, bg=BORDER, height=1).pack(fill="x")

        self._col_props = tk.Frame(right, bg=BG2)
        self._col_props.pack(fill="both", expand=True, padx=8, pady=8)
        tk.Label(self._col_props, text="Выберите коллайдер",
                 bg=BG2, fg=TEXT3, font=("Consolas", 10)).pack(pady=20)

        self._refresh_obj_list()

    def _refresh_obj_list(self):
        self._obj_lb.delete(0, tk.END)
        for obj in self.lp.objects:
            marker = "▶ " if (self._selected_obj and self._selected_obj.name == obj.name) else "  "
            n_col = len(obj.colliders)
            n_beh = len(obj.behaviors)
            self._obj_lb.insert(tk.END, f"{marker}{obj.name}  [{n_col}col {n_beh}beh]")

    def _on_obj_lb_select(self, event):
        sel = self._obj_lb.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self.lp.objects):
            self._select_object(self.lp.objects[idx])

    def _select_object(self, obj: ObjectLogic):
        self._selected_obj = obj
        self._selected_col = None
        self._refresh_obj_list()
        self._redraw_colliders()
        self._show_col_props(None)

    def _add_object(self):
        win = tk.Toplevel(self.root)
        win.title("Новый объект")
        win.geometry("360x180")
        win.configure(bg=BG2)
        win.grab_set()

        tk.Label(win, text="Имя объекта:", bg=BG2, fg=TEXT2,
                 font=("Consolas", 10)).pack(anchor="w", padx=20, pady=(20,2))
        name_v = tk.StringVar(value=f"Object_{len(self.lp.objects)+1}")
        tk.Entry(win, textvariable=name_v, bg=BG3, fg=TEXT,
                 insertbackground=TEXT, font=("Consolas", 12),
                 relief="flat", bd=0).pack(fill="x", padx=20, ipady=6)

        tk.Label(win, text="Изображение (опционально):", bg=BG2, fg=TEXT2,
                 font=("Consolas", 10)).pack(anchor="w", padx=20, pady=(10,2))
        img_v = tk.StringVar()
        img_row = tk.Frame(win, bg=BG2)
        img_row.pack(fill="x", padx=20)
        tk.Entry(img_row, textvariable=img_v, bg=BG3, fg=TEXT,
                 insertbackground=TEXT, font=("Consolas", 10),
                 relief="flat", bd=0).pack(side="left", fill="x", expand=True, ipady=4)
        def browse():
            p = filedialog.askopenfilename(
                initialdir=os.path.join(self.project_dir, "assets"),
                filetypes=[("Изображения","*.png *.jpg *.bmp"),("Все","*.*")],
                parent=win)
            if p:
                try:
                    img_v.set(os.path.relpath(p, self.project_dir))
                except ValueError:
                    img_v.set(p)
        tk.Button(img_row, text="…", command=browse,
                  bg=BG3, fg=TEXT, font=("Consolas",10),
                  relief="flat", cursor="hand2", padx=6,
                  activebackground=HOVER, activeforeground=TEXT,
                  ).pack(side="left", padx=(4,0))

        def create():
            n = name_v.get().strip()
            if not n:
                return
            obj = ObjectLogic(name=n, image_path=img_v.get())
            self.lp.objects.append(obj)
            win.destroy()
            self._select_object(obj)

        tk.Button(win, text="Создать", command=create,
                  bg=ACCENT, fg="white", font=("Consolas",11,"bold"),
                  relief="flat", cursor="hand2", padx=16, pady=6,
                  activebackground=ACCENT2, activeforeground="white",
                  ).pack(pady=12)

    def _delete_object(self):
        if not self._selected_obj:
            return
        self.lp.objects = [o for o in self.lp.objects if o.name != self._selected_obj.name]
        self._selected_obj = None
        self._selected_col = None
        self._refresh_obj_list()
        self._redraw_colliders()

    # ── Коллайдеры ──

    def _add_collider(self, kind: str):
        if not self._selected_obj:
            messagebox.showinfo("Нет объекта", "Сначала выберите объект.")
            return
        col = ColliderData(kind=kind, w=64, h=64, r=32)
        self._selected_obj.colliders.append(col)
        self._selected_col = col
        self._redraw_colliders()
        self._show_col_props(col)
        self._refresh_obj_list()

    def _delete_collider(self):
        if not self._selected_obj or not self._selected_col:
            return
        self._selected_obj.colliders = [
            c for c in self._selected_obj.colliders if c is not self._selected_col
        ]
        self._selected_col = None
        self._redraw_colliders()
        self._show_col_props(None)
        self._refresh_obj_list()

    def _redraw_colliders(self):
        c = self._col_canvas
        c.delete("all")

        cw, ch = self.CANVAS_W, self.CANVAS_H

        # Шахматный фон
        cell = 20
        for row in range(ch // cell + 1):
            for col in range(cw // cell + 1):
                color = "#0d1829" if (row+col)%2==0 else "#101e30"
                c.create_rectangle(col*cell, row*cell,
                                   col*cell+cell, row*cell+cell,
                                   fill=color, outline="")

        # Центр
        cx, cy = cw//2, ch//2

        # Оси
        c.create_line(cx, 0, cx, ch, fill="#1e3a5f", dash=(4,4))
        c.create_line(0, cy, cw, cy, fill="#1e3a5f", dash=(4,4))

        if not self._selected_obj:
            c.create_text(cx, cy, text="Выберите объект",
                          fill=TEXT3, font=("Consolas", 13))
            return

        obj = self._selected_obj

        # Спрайт объекта (если есть)
        if obj.image_path:
            abs_path = os.path.join(self.project_dir, obj.image_path)
            img = load_pil(abs_path)
            if img:
                scale = min(200/max(img.width,1), 200/max(img.height,1), 2.0)
                w2 = max(1, int(img.width * scale))
                h2 = max(1, int(img.height * scale))
                img2 = img.resize((w2, h2), Image.NEAREST)
                # Полупрозрачный
                r,g,b,a = img2.split()
                a = a.point(lambda p: int(p*0.5))
                img2 = Image.merge("RGBA", (r,g,b,a))
                tk_img = pil_to_tk(img2)
                self._tk_images["sprite"] = tk_img
                c.create_image(cx, cy, image=tk_img, anchor="center")

        # Имя
        c.create_text(cx, 18, text=obj.name, fill=TEXT2, font=("Consolas", 11, "bold"))

        # Коллайдеры
        for col_data in obj.colliders:
            is_sel = col_data is self._selected_col
            color_box  = ACCENT  if not is_sel else YELLOW
            color_circ = TEAL    if not is_sel else YELLOW
            width = 2 if is_sel else 1

            ox = cx + col_data.ox
            oy = cy + col_data.oy

            if col_data.kind == "box":
                hw, hh = col_data.w/2, col_data.h/2
                fill = "#1d4ed820" if col_data.is_static else "#1d4ed810"
                if col_data.is_trigger:
                    fill = "#7c3aed15"
                    color_box = PURPLE
                c.create_rectangle(ox-hw, oy-hh, ox+hw, oy+hh,
                                   outline=color_box, fill=fill, width=width)
                # Ручки углов
                if is_sel:
                    for hx, hy in [(ox-hw,oy-hh),(ox+hw,oy-hh),
                                   (ox-hw,oy+hh),(ox+hw,oy+hh)]:
                        c.create_rectangle(hx-4,hy-4,hx+4,hy+4,
                                           fill=YELLOW, outline=BG)
                # Центр
                c.create_oval(ox-3,oy-3,ox+3,oy+3, fill=color_box, outline="")
                label = "static" if col_data.is_static else ("trigger" if col_data.is_trigger else "box")
                c.create_text(ox, oy-hh-8, text=label, fill=color_box,
                              font=("Consolas", 8))

            elif col_data.kind == "circle":
                r = col_data.r
                fill = "#14b8a615" if not col_data.is_trigger else "#7c3aed15"
                color = color_circ if not col_data.is_trigger else PURPLE
                c.create_oval(ox-r, oy-r, ox+r, oy+r,
                              outline=color, fill=fill, width=width)
                if is_sel:
                    # Ручка радиуса
                    c.create_oval(ox+r-4,oy-4,ox+r+4,oy+4,
                                  fill=YELLOW, outline=BG)
                c.create_oval(ox-3,oy-3,ox+3,oy+3, fill=color, outline="")
                c.create_text(ox, oy-r-8, text="circle",
                              fill=color, font=("Consolas", 8))

    def _col_press(self, event):
        if not self._selected_obj:
            return
        cx, cy = self.CANVAS_W//2, self.CANVAS_H//2

        hit = None
        for col_data in reversed(self._selected_obj.colliders):
            ox = cx + col_data.ox
            oy = cy + col_data.oy
            if col_data.kind == "box":
                hw, hh = col_data.w/2, col_data.h/2
                if ox-hw <= event.x <= ox+hw and oy-hh <= event.y <= oy+hh:
                    hit = col_data
                    break
            elif col_data.kind == "circle":
                if (event.x-ox)**2 + (event.y-oy)**2 <= col_data.r**2:
                    hit = col_data
                    break

        self._selected_col = hit
        self._drag_col   = hit
        self._drag_start = (event.x, event.y)
        if hit:
            self._drag_col_orig = (hit.ox, hit.oy)
        self._redraw_colliders()
        self._show_col_props(hit)

    def _col_drag(self, event):
        if not self._drag_col or not self._drag_start:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        self._drag_col.ox = round(self._drag_col_orig[0] + dx, 1)
        self._drag_col.oy = round(self._drag_col_orig[1] + dy, 1)
        self._redraw_colliders()
        self._show_col_props(self._drag_col)

    def _col_release(self, event):
        self._drag_col   = None
        self._drag_start = None

    def _show_col_props(self, col: ColliderData | None):
        for w in self._col_props.winfo_children():
            w.destroy()

        if col is None:
            tk.Label(self._col_props, text="Выберите коллайдер",
                     bg=BG2, fg=TEXT3, font=("Consolas", 10)).pack(pady=20)
            return

        f = self._col_props

        def row(label, getter, setter, type_=float):
            tk.Label(f, text=label, bg=BG2, fg=TEXT3,
                     font=("Consolas", 8)).pack(anchor="w", pady=(4,0))
            v = tk.StringVar(value=str(getter()))
            tk.Entry(f, textvariable=v, bg=BG3, fg=TEXT,
                     insertbackground=TEXT, font=("Consolas", 10),
                     relief="flat", bd=0).pack(fill="x", ipady=3)
            def on(*_):
                try:
                    setter(type_(v.get()))
                    self._redraw_colliders()
                except ValueError:
                    pass
            v.trace_add("write", on)

        def check(label, getter, setter):
            v = tk.BooleanVar(value=getter())
            tk.Checkbutton(f, text=label, variable=v,
                           command=lambda: (setter(v.get()), self._redraw_colliders()),
                           bg=BG2, fg=TEXT, selectcolor=BG3,
                           activebackground=BG2, font=("Consolas",9), anchor="w",
                           ).pack(anchor="w", pady=2)

        kind_color = ACCENT if col.kind == "box" else TEAL
        tk.Label(f, text=f"{'⬜ BoxCollider2D' if col.kind=='box' else '⭕ CircleCollider2D'}",
                 bg=BG2, fg=kind_color, font=("Consolas", 11, "bold")).pack(anchor="w", pady=(0,6))

        row("Смещение X", lambda: col.ox, lambda v: setattr(col, "ox", v))
        row("Смещение Y", lambda: col.oy, lambda v: setattr(col, "oy", v))

        if col.kind == "box":
            row("Ширина",  lambda: col.w, lambda v: setattr(col, "w", max(1, v)))
            row("Высота",  lambda: col.h, lambda v: setattr(col, "h", max(1, v)))
        else:
            row("Радиус",  lambda: col.r, lambda v: setattr(col, "r", max(1, v)))

        row("Упругость (0-1)", lambda: col.restitution,
            lambda v: setattr(col, "restitution", max(0, min(1, v))))

        tk.Frame(f, bg=BORDER, height=1).pack(fill="x", pady=6)

        check("Статичный (is_static)",   lambda: col.is_static,  lambda v: setattr(col,"is_static",v))
        check("Триггер (is_trigger)",    lambda: col.is_trigger, lambda v: setattr(col,"is_trigger",v))

        row("Слой (layer 0-31)", lambda: col.layer,
            lambda v: setattr(col,"layer", int(max(0,min(31,v)))), int)

    # ══════════════════════════════════════════
    #  Вкладка ПОВЕДЕНИЯ
    # ══════════════════════════════════════════

    def _build_behavior_tab(self):
        frame = tk.Frame(self._content, bg=BG)
        self._tab_frames["behaviors"] = frame

        # Левая — объекты
        left = tk.Frame(frame, bg=BG2, width=190)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        tk.Label(left, text="ОБЪЕКТЫ", bg=BG2, fg=TEXT3,
                 font=("Consolas", 8, "bold")).pack(anchor="w", padx=10, pady=(10,4))
        tk.Frame(left, bg=BORDER, height=1).pack(fill="x")

        self._beh_obj_lb = tk.Listbox(left, bg=BG2, fg=TEXT,
                                       selectbackground=SEL, selectforeground=TEXT,
                                       font=("Consolas", 10), relief="flat", bd=0,
                                       activestyle="none", highlightthickness=0)
        self._beh_obj_lb.pack(fill="both", expand=True)
        self._beh_obj_lb.bind("<<ListboxSelect>>", self._on_beh_obj_select)

        tk.Frame(frame, bg=BORDER, width=1).pack(side="left", fill="y")

        # Центр — каталог поведений
        center = tk.Frame(frame, bg=BG)
        center.pack(side="left", fill="both", expand=True)

        tk.Label(center, text="ДОСТУПНЫЕ ПОВЕДЕНИЯ",
                 bg=BG, fg=TEXT3, font=("Consolas", 8, "bold")).pack(anchor="w", padx=12, pady=(10,6))

        # Канвас со скроллом для каталога
        cat_frame = tk.Frame(center, bg=BG)
        cat_frame.pack(fill="both", expand=True, padx=8)

        cat_scroll = tk.Scrollbar(cat_frame)
        cat_scroll.pack(side="right", fill="y")

        self._cat_canvas = tk.Canvas(cat_frame, bg=BG,
                                      yscrollcommand=cat_scroll.set,
                                      highlightthickness=0)
        self._cat_canvas.pack(fill="both", expand=True)
        cat_scroll.config(command=self._cat_canvas.yview)

        self._cat_inner = tk.Frame(self._cat_canvas, bg=BG)
        self._cat_canvas.create_window((0,0), window=self._cat_inner, anchor="nw")
        self._cat_inner.bind("<Configure>", lambda e: self._cat_canvas.configure(
            scrollregion=self._cat_canvas.bbox("all")))

        self._build_behavior_catalog()

        tk.Frame(frame, bg=BORDER, width=1).pack(side="left", fill="y")

        # Правая — назначенные поведения
        right = tk.Frame(frame, bg=BG2, width=310)
        right.pack(side="left", fill="y")
        right.pack_propagate(False)

        tk.Label(right, text="НАЗНАЧЕНО", bg=BG2, fg=TEXT3,
                 font=("Consolas", 8, "bold")).pack(anchor="w", padx=10, pady=(10,4))
        tk.Frame(right, bg=BORDER, height=1).pack(fill="x")

        self._assigned_frame = tk.Frame(right, bg=BG2)
        self._assigned_frame.pack(fill="both", expand=True)

        tk.Label(self._assigned_frame, text="Выберите объект",
                 bg=BG2, fg=TEXT3, font=("Consolas",10)).pack(pady=20)

        self._refresh_beh_obj_list()

    def _build_behavior_catalog(self):
        cols = 2
        for i, (name, beh) in enumerate(BEHAVIORS.items()):
            row_  = i // cols
            col_  = i %  cols
            color = beh["color"]
            icon  = beh["icon"]
            desc  = beh["desc"]

            card = tk.Frame(self._cat_inner, bg=BG3,
                            relief="flat", bd=0)
            card.grid(row=row_, column=col_, padx=6, pady=6, sticky="nsew")
            self._cat_inner.columnconfigure(col_, weight=1)

            # Цветная полоска
            tk.Frame(card, bg=color, height=3).pack(fill="x")

            inner = tk.Frame(card, bg=BG3)
            inner.pack(fill="x", padx=10, pady=8)

            hdr = tk.Frame(inner, bg=BG3)
            hdr.pack(fill="x")
            tk.Label(hdr, text=icon, bg=BG3, font=("",16)).pack(side="left")
            tk.Label(hdr, text=name, bg=BG3, fg=TEXT,
                     font=("Consolas",10,"bold"), wraplength=150,
                     justify="left").pack(side="left", padx=6)

            tk.Label(inner, text=desc, bg=BG3, fg=TEXT3,
                     font=("Consolas",8), wraplength=190,
                     justify="left").pack(fill="x", pady=(2,6))

            add_btn = tk.Button(inner, text="+ Добавить",
                                command=lambda n=name: self._add_behavior(n),
                                bg=color, fg="white",
                                font=("Consolas",9),
                                relief="flat", cursor="hand2",
                                padx=8, pady=3,
                                activebackground=BG4, activeforeground="white")
            add_btn.pack(anchor="w")

    def _refresh_beh_obj_list(self):
        self._beh_obj_lb.delete(0, tk.END)
        for obj in self.lp.objects:
            marker = "▶ " if (self._selected_obj and self._selected_obj.name == obj.name) else "  "
            self._beh_obj_lb.insert(tk.END, f"{marker}{obj.name}")

    def _on_beh_obj_select(self, event):
        sel = self._beh_obj_lb.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self.lp.objects):
            self._selected_obj = self.lp.objects[idx]
            self._refresh_beh_obj_list()
            self._show_assigned()
            self._refresh_obj_list()

    def _add_behavior(self, behavior_name: str):
        if not self._selected_obj:
            messagebox.showinfo("Нет объекта", "Сначала выберите объект.")
            return
        beh_def = BEHAVIORS[behavior_name]
        # Параметры по умолчанию
        params = {p["name"]: p["default"] for p in beh_def["params"]}
        self._selected_obj.behaviors.append({
            "name":   behavior_name,
            "id":     beh_def["id"],
            "params": params,
        })
        self._show_assigned()
        self._refresh_obj_list()
        self._refresh_beh_obj_list()

    def _show_assigned(self):
        for w in self._assigned_frame.winfo_children():
            w.destroy()

        if not self._selected_obj:
            tk.Label(self._assigned_frame, text="Выберите объект",
                     bg=BG2, fg=TEXT3, font=("Consolas",10)).pack(pady=20)
            return

        obj = self._selected_obj

        if not obj.behaviors:
            tk.Label(self._assigned_frame,
                     text=f"{obj.name}\n\nНет поведений.\nДобавьте из каталога →",
                     bg=BG2, fg=TEXT3, font=("Consolas",10), justify="center").pack(pady=20)
            return

        tk.Label(self._assigned_frame, text=f"  {obj.name}",
                 bg=BG2, fg=TEXT, font=("Consolas",11,"bold")).pack(anchor="w", padx=8, pady=(6,4))

        scroll_frame = tk.Frame(self._assigned_frame, bg=BG2)
        scroll_frame.pack(fill="both", expand=True)

        sb = tk.Scrollbar(scroll_frame)
        sb.pack(side="right", fill="y")
        cv = tk.Canvas(scroll_frame, bg=BG2, yscrollcommand=sb.set, highlightthickness=0)
        cv.pack(fill="both", expand=True)
        sb.config(command=cv.yview)
        inner = tk.Frame(cv, bg=BG2)
        cv.create_window((0,0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))

        for i, beh in enumerate(obj.behaviors):
            self._behavior_card(inner, obj, beh, i)

    def _behavior_card(self, parent, obj: ObjectLogic, beh: dict, idx: int):
        beh_def = BEHAVIORS.get(beh["name"], {})
        color   = beh_def.get("color", TEXT3)
        icon    = beh_def.get("icon",  "?")

        card = tk.Frame(parent, bg=BG3, relief="flat")
        card.pack(fill="x", padx=6, pady=4)
        tk.Frame(card, bg=color, width=4).pack(side="left", fill="y")

        body = tk.Frame(card, bg=BG3)
        body.pack(fill="x", expand=True, padx=8, pady=6)

        # Заголовок + кнопка удаления
        hdr = tk.Frame(body, bg=BG3)
        hdr.pack(fill="x")
        tk.Label(hdr, text=f"{icon}  {beh['name']}", bg=BG3, fg=color,
                 font=("Consolas",10,"bold")).pack(side="left")
        tk.Button(hdr, text="✕",
                  command=lambda i=idx: self._remove_behavior(obj, i),
                  bg=BG3, fg=RED, font=("Consolas",9),
                  relief="flat", cursor="hand2",
                  activebackground=BG4, activeforeground=RED,
                  ).pack(side="right")

        # Параметры
        params_def = beh_def.get("params", [])
        for p_def in params_def:
            pname  = p_def["name"]
            plabel = p_def["label"]
            ptype  = p_def["type"]
            val    = beh["params"].get(pname, p_def["default"])

            tk.Label(body, text=plabel, bg=BG3, fg=TEXT3,
                     font=("Consolas",8)).pack(anchor="w", pady=(3,0))

            if ptype == "choice":
                v = tk.StringVar(value=str(val))
                cb = ttk.Combobox(body, textvariable=v,
                                  values=p_def["choices"],
                                  font=("Consolas",9), state="readonly", width=22)
                cb.pack(anchor="w")
                def on_choice(_, pn=pname, var=v, b=beh):
                    b["params"][pn] = var.get()
                v.trace_add("write", on_choice)

            elif ptype == "bool":
                v = tk.BooleanVar(value=bool(val))
                tk.Checkbutton(body, variable=v,
                               command=lambda pn=pname, var=v, b=beh:
                                   b["params"].__setitem__(pn, var.get()),
                               bg=BG3, fg=TEXT, selectcolor=BG4,
                               activebackground=BG3, font=("Consolas",9)).pack(anchor="w")

            elif ptype == "text":
                v = tk.StringVar(value=str(val))
                txt = tk.Text(body, bg=BG4, fg=ACCENT2,
                              insertbackground=TEXT, font=("Consolas",9),
                              relief="flat", bd=0, height=4, wrap="none")
                txt.pack(fill="x", pady=2)
                txt.insert("1.0", str(val))
                def on_text(event, pn=pname, t=txt, b=beh):
                    b["params"][pn] = t.get("1.0","end-1c")
                txt.bind("<KeyRelease>", on_text)

            else:
                v = tk.StringVar(value=str(val))
                e = tk.Entry(body, textvariable=v, bg=BG4, fg=TEXT,
                             insertbackground=TEXT, font=("Consolas",9),
                             relief="flat", bd=0)
                e.pack(fill="x", ipady=3)
                def on_entry(*_, pn=pname, var=v, b=beh, pt=ptype):
                    raw = var.get()
                    try:
                        if pt == "int":
                            b["params"][pn] = int(raw)
                        elif pt == "float":
                            b["params"][pn] = float(raw)
                        else:
                            b["params"][pn] = raw
                    except ValueError:
                        pass
                v.trace_add("write", on_entry)

    def _remove_behavior(self, obj: ObjectLogic, idx: int):
        if 0 <= idx < len(obj.behaviors):
            obj.behaviors.pop(idx)
        self._show_assigned()
        self._refresh_obj_list()
        self._refresh_beh_obj_list()

    # ══════════════════════════════════════════
    #  Сохранение и экспорт
    # ══════════════════════════════════════════

    def _save(self):
        self.lp.save()
        messagebox.showinfo("Сохранено", "Коллизии и поведения сохранены.")

    def _export_code(self):
        lines = [
            "# ── Сгенерировано PyGE Logic Editor ─────────────────",
            "# Вставьте импорты в начало файла, классы — перед сценой,",
            "# а код on_start() — в метод on_start() вашей сцены.",
            "",
            "# ── ИМПОРТЫ ──────────────────────────────────────────",
            "from pyge.engine import Time",
            "from pyge.component import Component",
            "from pyge.input import Input",
            "from pyge.physics.rigidbody import Rigidbody2D, BoxCollider2D, CircleCollider2D",
            "from pyge.rendering.sprite import SpriteRenderer",
            "",
        ]

        component_lines = ["# ── КОМПОНЕНТЫ ───────────────────────────────────────"]
        start_lines     = ["# ── on_start() ───────────────────────────────────────"]

        seen_classes: set = set()

        for obj in self.lp.objects:
            start_lines.append(f"")
            start_lines.append(f"# {obj.name}")
            var = obj.name.lower().replace(" ","_").replace("-","_")
            start_lines.append(f'{var} = GameObject("{obj.name}", x={obj.x}, y={obj.y})')

            # Спрайт
            if obj.image_path:
                start_lines.append(f'{var}.add_component(SpriteRenderer(source="{obj.image_path}", pivot=(0.5,0.5)))')

            # Коллайдеры
            for col in obj.colliders:
                if col.kind == "box":
                    start_lines.append(
                        f'{var}.add_component(BoxCollider2D('
                        f'width={col.w}, height={col.h}, '
                        f'offset=Vector2({col.ox},{col.oy}), '
                        f'is_static={col.is_static}, '
                        f'is_trigger={col.is_trigger}, '
                        f'layer={col.layer}, '
                        f'restitution={col.restitution}))'
                    )
                else:
                    start_lines.append(
                        f'{var}.add_component(CircleCollider2D('
                        f'radius={col.r}, '
                        f'offset=Vector2({col.ox},{col.oy}), '
                        f'is_static={col.is_static}, '
                        f'is_trigger={col.is_trigger}, '
                        f'layer={col.layer}, '
                        f'restitution={col.restitution}))'
                    )

            # Поведения
            for beh in obj.behaviors:
                beh_def    = BEHAVIORS.get(beh["name"], {})
                params     = beh["params"]
                code_tmpl  = beh_def.get("code", "")
                class_name = None

                # Форматируем шаблон
                fmt_params = {}
                for k, v in params.items():
                    if isinstance(v, str):
                        fmt_params[k] = v
                    else:
                        fmt_params[k] = str(v)

                try:
                    code = code_tmpl.format(**fmt_params)
                except KeyError:
                    code = code_tmpl

                # Извлечь имя класса
                for line in code.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("class "):
                        class_name = stripped.split("(")[0].replace("class ","").strip()
                        break

                if class_name and class_name not in seen_classes:
                    component_lines.append(code)
                    seen_classes.add(class_name)

                if class_name:
                    # Уникальное имя экземпляра
                    inst_name = f"{var}_{class_name.lower()}"
                    start_lines.append(f'{var}.add_component({class_name}())')

            start_lines.append(f'self.add({var})')

        all_lines = (lines + component_lines + [""] + start_lines)
        code_out  = "\n".join(all_lines)

        # Показать
        win = tk.Toplevel(self.root)
        win.title("Экспорт кода")
        win.geometry("760x560")
        win.configure(bg=BG2)

        tk.Label(win, text="Скопируйте и вставьте в ваш проект:",
                 bg=BG2, fg=TEXT, font=("Consolas",11)).pack(padx=16, pady=(12,4), anchor="w")

        txt = tk.Text(win, bg=BG3, fg="#a5f3fc", font=("Consolas",10),
                      relief="flat", wrap="none")
        txt.pack(fill="both", expand=True, padx=12, pady=(0,8))
        txt.insert("1.0", code_out)
        txt.config(state="disabled")

        def copy_all():
            self.root.clipboard_clear()
            self.root.clipboard_append(code_out)
            messagebox.showinfo("Скопировано", "Код скопирован в буфер.", parent=win)

        tk.Button(win, text="📋 Копировать всё", command=copy_all,
                  bg=ACCENT, fg="white", font=("Consolas",11),
                  relief="flat", cursor="hand2", padx=14, pady=6,
                  activebackground=ACCENT2, activeforeground="white",
                  ).pack(pady=(0,12))

    def run(self):
        self.root.mainloop()


# ──────────────────────────────────────────────
#  Точка входа
# ──────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) > 1:
        project_dir = sys.argv[1]
    else:
        root = tk.Tk()
        root.withdraw()
        project_dir = filedialog.askdirectory(title="Выберите папку проекта PyGE")
        root.destroy()
        if not project_dir:
            sys.exit(0)

    app = LogicEditor(project_dir)
    app.run()
