"""
pyge_editor.py
==============
Визуальный редактор спрайтов и анимаций для PyGE.

Возможности:
  - Вьюпорт сцены: перетаскивание объектов, zoom, pan
  - Иерархия объектов (добавить / удалить / выбрать)
  - Инспектор: позиция, масштаб, поворот, z_order, тег
  - Импорт спрайтов PNG/JPG (копируются в assets/)
  - Редактор анимаций: кадры, fps, loop, preview
  - Экспорт сцены в scene_data.py

Запуск:
  python pyge_editor.py
  python pyge_editor.py --project /path/to/project
"""

import tkinter as tk
from tkinter import filedialog, messagebox
import os
import sys
import json
import shutil

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ============================================================
# Цвета
# ============================================================
BG       = "#0f1117"
BG2      = "#161b22"
BG3      = "#1f2937"
ACCENT   = "#3b82f6"
ACCENT2  = "#60a5fa"
GREEN    = "#22c55e"
RED      = "#ef4444"
TEXT     = "#f1f5f9"
TEXT2    = "#94a3b8"
TEXT3    = "#475569"
BORDER   = "#2d3748"
HOVER    = "#1e293b"
GRID_COL = "#1a2030"
SEL_COL  = "#3b82f6"

SCENE_W  = 800
SCENE_H  = 600


# ============================================================
# Модель данных
# ============================================================

class AnimClip:
    def __init__(self, name="idle"):
        self.name   = name
        self.frames = []      # list[str] — rel paths
        self.fps    = 8.0
        self.loop   = True

    def to_dict(self):
        return {"name": self.name, "frames": self.frames,
                "fps": self.fps, "loop": self.loop}

    @classmethod
    def from_dict(cls, d):
        c = cls(d["name"])
        c.frames = d.get("frames", [])
        c.fps    = d.get("fps", 8.0)
        c.loop   = d.get("loop", True)
        return c


class SpriteObject:
    _counter = 0

    def __init__(self, name="GameObject", x=400.0, y=300.0):
        SpriteObject._counter += 1
        self.id        = SpriteObject._counter
        self.name      = name
        self.x         = float(x)
        self.y         = float(y)
        self.scale_x   = 1.0
        self.scale_y   = 1.0
        self.rotation  = 0.0
        self.z_order   = 0
        self.tag       = ""
        self.visible   = True
        self.sprite_rel = None
        self.animations = {}       # name -> AnimClip
        self.default_anim = None
        # runtime only
        self._pil  = None
        self._tk   = None

    def to_dict(self):
        return {
            "id": self.id, "name": self.name,
            "x": self.x, "y": self.y,
            "scale_x": self.scale_x, "scale_y": self.scale_y,
            "rotation": self.rotation, "z_order": self.z_order,
            "tag": self.tag, "visible": self.visible,
            "sprite_rel": self.sprite_rel,
            "default_anim": self.default_anim,
            "animations": {k: v.to_dict() for k, v in self.animations.items()},
        }

    @classmethod
    def from_dict(cls, d):
        o = cls(d["name"], d.get("x", 400), d.get("y", 300))
        o.id          = d.get("id", o.id)
        o.scale_x     = d.get("scale_x", 1.0)
        o.scale_y     = d.get("scale_y", 1.0)
        o.rotation    = d.get("rotation", 0.0)
        o.z_order     = d.get("z_order", 0)
        o.tag         = d.get("tag", "")
        o.visible     = d.get("visible", True)
        o.sprite_rel  = d.get("sprite_rel")
        o.default_anim = d.get("default_anim")
        o.animations  = {k: AnimClip.from_dict(v)
                         for k, v in d.get("animations", {}).items()}
        return o


class SceneData:
    def __init__(self):
        self.objects  = []
        self.bg_color = (30, 35, 50)

    def save(self, path):
        data = {
            "bg_color": list(self.bg_color),
            "objects":  [o.to_dict() for o in self.objects],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, path):
        with open(path, "r", encoding="utf-8") as f:
            d = json.load(f)
        self.bg_color = tuple(d.get("bg_color", [30, 35, 50]))
        self.objects  = [SpriteObject.from_dict(o) for o in d.get("objects", [])]


# ============================================================
# Экспорт
# ============================================================

def export_scene(scene: SceneData, project_path: str) -> str:
    lines = [
        '"""scene_data.py — сгенерировано PyGE Editor"""',
        "from pyge.game_object import GameObject",
        "from pyge.rendering.sprite import SpriteRenderer",
        "",
        "def setup_scene(scene) -> None:",
    ]
    if not scene.objects:
        lines.append("    pass")
    for obj in scene.objects:
        v = obj.name.lower().replace(" ", "_").replace("-", "_")
        lines += [
            f"",
            f"    {v} = GameObject('{obj.name}', x={obj.x:.1f}, y={obj.y:.1f},",
            f"        tag='{obj.tag}', z_order={obj.z_order})",
        ]
        if obj.sprite_rel:
            lines += [
                f"    {v}.add_component(SpriteRenderer('{obj.sprite_rel}'))",
                f"    {v}.transform.scale.x = {obj.scale_x:.3f}",
                f"    {v}.transform.scale.y = {obj.scale_y:.3f}",
                f"    {v}.transform.rotation = {obj.rotation:.1f}",
            ]
        if obj.animations:
            lines.append(f"    # animations: {', '.join(obj.animations.keys())}")
        lines.append(f"    scene.add({v})")

    code = "\n".join(lines) + "\n"
    out  = os.path.join(project_path, "scene_data.py")
    with open(out, "w", encoding="utf-8") as f:
        f.write(code)
    return out


# ============================================================
# Главный редактор
# ============================================================

class PyGEEditor:

    def __init__(self, project_path=None):
        self.project_path = project_path or os.getcwd()
        self.scene_file   = os.path.join(self.project_path, "scene_editor.json")
        self.scene        = SceneData()
        self.selected     = None

        self._zoom     = 1.0
        self._pan_x    = 0.0
        self._pan_y    = 0.0
        self._drag     = None   # (mx,my, ox,oy)
        self._pan_drag = None

        self.root = tk.Tk()
        self.root.title(f"PyGE Editor — {os.path.basename(self.project_path)}")
        self.root.geometry("1280x740")
        self.root.configure(bg=BG)

        self._build_ui()
        self._load_if_exists()
        self._redraw()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        # Тулбар
        tb = tk.Frame(self.root, bg=BG2, height=44)
        tb.pack(fill="x")
        tb.pack_propagate(False)

        def tbtn(txt, cmd, color=BG3):
            b = tk.Button(tb, text=txt, command=cmd,
                          bg=color, fg=TEXT, font=("Consolas", 10),
                          relief="flat", cursor="hand2", padx=10, pady=7,
                          activebackground=HOVER, activeforeground=TEXT)
            b.pack(side="left", padx=2, pady=4)
            return b

        tbtn("+ Объект",     self._add_object)
        tbtn("🖼 Спрайт",    self._assign_sprite)
        tbtn("🎬 Анимация",  self._open_anim_editor)
        tk.Frame(tb, bg=BORDER, width=1).pack(side="left", fill="y", padx=4, pady=6)
        tbtn("💾 Сохранить", self._save, GREEN)
        tbtn("⬡→.py Экспорт", self._export)
        tk.Frame(tb, bg=BORDER, width=1).pack(side="left", fill="y", padx=4, pady=6)
        tbtn("🔍+", lambda: self._zoom_by(1.2))
        tbtn("🔍-", lambda: self._zoom_by(1/1.2))
        tbtn("⌂",  self._reset_view)

        self.root.bind("<Control-s>", lambda e: self._save())
        self.root.bind("<Delete>",    lambda e: self._delete_selected())

        # Три колонки
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True)

        # Левая — иерархия
        self._left = tk.Frame(body, bg=BG2, width=200)
        self._left.pack(side="left", fill="y")
        self._left.pack_propagate(False)
        tk.Label(self._left, text="ИЕРАРХИЯ", bg=BG2, fg=TEXT3,
                 font=("Consolas", 9, "bold")).pack(anchor="w", padx=10, pady=(10,4))
        tk.Frame(self._left, bg=BORDER, height=1).pack(fill="x")
        self._hier_inner = tk.Frame(self._left, bg=BG2)
        self._hier_inner.pack(fill="both", expand=True)

        # Центр — канвас
        center = tk.Frame(body, bg=BG)
        center.pack(side="left", fill="both", expand=True)

        self._coord_lbl = tk.Label(center, text="x:0 y:0", bg=BG3, fg=TEXT3,
                                   font=("Consolas", 9))
        self._coord_lbl.pack(side="bottom", anchor="w", padx=4, pady=2)
        tk.Label(center,
                 text="ЛКМ выбор/drag  |  ПКМ+drag пан  |  Колесо zoom  |  Del удалить",
                 bg=BG, fg=TEXT3, font=("Consolas", 8)).pack(side="bottom", anchor="w", padx=4)

        self.canvas = tk.Canvas(center, bg="#0a0e18", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>",   self._lmb_press)
        self.canvas.bind("<B1-Motion>",       self._lmb_drag)
        self.canvas.bind("<ButtonRelease-1>", lambda e: setattr(self, "_drag", None))
        self.canvas.bind("<ButtonPress-3>",   self._rmb_press)
        self.canvas.bind("<B3-Motion>",       self._rmb_drag)
        self.canvas.bind("<ButtonRelease-3>", lambda e: setattr(self, "_pan_drag", None))
        self.canvas.bind("<MouseWheel>",      lambda e: self._zoom_by(1.1 if e.delta > 0 else 1/1.1))
        self.canvas.bind("<Button-4>",        lambda e: self._zoom_by(1.1))
        self.canvas.bind("<Button-5>",        lambda e: self._zoom_by(1/1.1))
        self.canvas.bind("<Motion>",          self._mouse_move)
        self.canvas.bind("<Configure>",       lambda e: self._redraw())
        self.canvas.focus_set()

        # Правая — инспектор
        self._right = tk.Frame(body, bg=BG2, width=270)
        self._right.pack(side="left", fill="y")
        self._right.pack_propagate(False)
        tk.Label(self._right, text="ИНСПЕКТОР", bg=BG2, fg=TEXT3,
                 font=("Consolas", 9, "bold")).pack(anchor="w", padx=10, pady=(10,4))
        tk.Frame(self._right, bg=BORDER, height=1).pack(fill="x")
        self._insp = tk.Frame(self._right, bg=BG2)
        self._insp.pack(fill="both", expand=True, padx=8, pady=6)

        self._insp_empty()

    # ------------------------------------------------------------------
    # Иерархия
    # ------------------------------------------------------------------

    def _refresh_hier(self):
        for w in self._hier_inner.winfo_children():
            w.destroy()
        if not self.scene.objects:
            tk.Label(self._hier_inner, text="Нет объектов",
                     bg=BG2, fg=TEXT3, font=("Consolas", 10)).pack(pady=20)
            return
        for obj in self.scene.objects:
            sel = obj is self.selected
            bg  = HOVER if sel else BG2
            row = tk.Frame(self._hier_inner, bg=bg, cursor="hand2")
            row.pack(fill="x")
            if sel:
                tk.Frame(row, bg=ACCENT, width=3).pack(side="left", fill="y")
            icon = "👁" if obj.visible else "🚫"
            tk.Label(row, text=f"{icon}  {obj.name}",
                     bg=bg, fg=TEXT if sel else TEXT2,
                     font=("Consolas", 10), anchor="w"
                     ).pack(fill="x", padx=6, pady=6)
            row.bind("<Button-1>", lambda e, o=obj: self._select(o))
            tk.Frame(self._hier_inner, bg=BORDER, height=1).pack(fill="x")

    # ------------------------------------------------------------------
    # Инспектор
    # ------------------------------------------------------------------

    def _insp_empty(self):
        for w in self._insp.winfo_children():
            w.destroy()
        tk.Label(self._insp, text="Выберите объект",
                 bg=BG2, fg=TEXT3, font=("Consolas", 10)).pack(pady=20)

    def _insp_obj(self, obj: SpriteObject):
        for w in self._insp.winfo_children():
            w.destroy()
        f = self._insp

        def sep():
            tk.Frame(f, bg=BORDER, height=1).pack(fill="x", pady=4)

        def lbl(t):
            tk.Label(f, text=t, bg=BG2, fg=TEXT3,
                     font=("Consolas", 8, "bold")).pack(anchor="w", pady=(6,1))

        def row_field(label, var):
            r = tk.Frame(f, bg=BG2)
            r.pack(fill="x", pady=1)
            tk.Label(r, text=label, bg=BG2, fg=TEXT2,
                     font=("Consolas", 9), width=9, anchor="w").pack(side="left")
            e = tk.Entry(r, textvariable=var, bg=BG3, fg=TEXT,
                         insertbackground=TEXT, font=("Consolas", 10),
                         relief="flat", bd=0)
            e.pack(side="left", fill="x", expand=True, ipady=3)

        lbl("ОБЪЕКТ")
        nv = tk.StringVar(value=obj.name)
        tv = tk.StringVar(value=obj.tag)
        row_field("Имя",  nv)
        row_field("Тег",  tv)

        lbl("ТРАНСФОРМ")
        xv  = tk.DoubleVar(value=round(obj.x, 1))
        yv  = tk.DoubleVar(value=round(obj.y, 1))
        sxv = tk.DoubleVar(value=round(obj.scale_x, 3))
        syv = tk.DoubleVar(value=round(obj.scale_y, 3))
        rv  = tk.DoubleVar(value=round(obj.rotation, 1))
        zv  = tk.IntVar(value=obj.z_order)
        row_field("X",        xv)
        row_field("Y",        yv)
        row_field("Scale X",  sxv)
        row_field("Scale Y",  syv)
        row_field("Поворот",  rv)
        row_field("Z Order",  zv)

        def apply():
            try:
                obj.name     = nv.get().strip() or obj.name
                obj.tag      = tv.get().strip()
                obj.x        = float(xv.get())
                obj.y        = float(yv.get())
                obj.scale_x  = float(sxv.get())
                obj.scale_y  = float(syv.get())
                obj.rotation = float(rv.get())
                obj.z_order  = int(zv.get())
                self._redraw()
                self._refresh_hier()
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

        tk.Button(f, text="✓ Применить", command=apply,
                  bg=ACCENT, fg="white", font=("Consolas", 10),
                  relief="flat", cursor="hand2", pady=5,
                  activebackground=ACCENT2).pack(fill="x", pady=(6,2))

        sep()
        lbl("СПРАЙТ")
        sp_name = os.path.basename(obj.sprite_rel) if obj.sprite_rel else "— нет —"
        tk.Label(f, text=sp_name, bg=BG3, fg=TEXT2,
                 font=("Consolas", 9), anchor="w").pack(fill="x", ipady=3)
        sr = tk.Frame(f, bg=BG2)
        sr.pack(fill="x", pady=2)
        tk.Button(sr, text="Назначить",
                  command=lambda: (self._assign_sprite(obj), self._insp_obj(obj)),
                  bg=BG3, fg=TEXT, font=("Consolas", 9),
                  relief="flat", cursor="hand2", padx=6,
                  activebackground=HOVER).pack(side="left", padx=(0,4))
        if obj.sprite_rel:
            tk.Button(sr, text="Убрать",
                      command=lambda: (setattr(obj, "sprite_rel", None),
                                       setattr(obj, "_pil", None),
                                       setattr(obj, "_tk", None),
                                       self._insp_obj(obj), self._redraw()),
                      bg=BG3, fg=RED, font=("Consolas", 9),
                      relief="flat", cursor="hand2", padx=6,
                      activebackground=HOVER).pack(side="left")

        sep()
        lbl("АНИМАЦИИ")
        if obj.animations:
            for aname, clip in obj.animations.items():
                ar = tk.Frame(f, bg=BG3)
                ar.pack(fill="x", pady=1)
                is_def = aname == obj.default_anim
                tk.Label(ar, text=f"{'▶ ' if is_def else '  '}{aname}  ({len(clip.frames)}кадр, {clip.fps}fps)",
                         bg=BG3, fg=ACCENT if is_def else TEXT2,
                         font=("Consolas", 8), anchor="w").pack(side="left", padx=6, pady=3)
                tk.Button(ar, text="ред.",
                          command=lambda n=aname: self._open_anim_editor(obj, n),
                          bg=BG3, fg=TEXT3, font=("Consolas", 8),
                          relief="flat", cursor="hand2",
                          activebackground=HOVER).pack(side="right", padx=4)
        else:
            tk.Label(f, text="Нет анимаций", bg=BG2, fg=TEXT3,
                     font=("Consolas", 9)).pack(anchor="w")
        tk.Button(f, text="+ Новая анимация",
                  command=lambda: self._open_anim_editor(obj),
                  bg=BG3, fg=TEXT, font=("Consolas", 9),
                  relief="flat", cursor="hand2", pady=4,
                  activebackground=HOVER).pack(fill="x", pady=(4,2))

        sep()
        tk.Button(f, text="🗑 Удалить объект",
                  command=self._delete_selected,
                  bg=BG3, fg=RED, font=("Consolas", 9),
                  relief="flat", cursor="hand2", pady=4,
                  activebackground=HOVER).pack(fill="x")

    # ------------------------------------------------------------------
    # Канвас
    # ------------------------------------------------------------------

    def _w2s(self, wx, wy):
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        sx = (wx - SCENE_W/2) * self._zoom + cw/2 + self._pan_x
        sy = (wy - SCENE_H/2) * self._zoom + ch/2 + self._pan_y
        return sx, sy

    def _s2w(self, sx, sy):
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        wx = (sx - cw/2 - self._pan_x) / self._zoom + SCENE_W/2
        wy = (sy - ch/2 - self._pan_y) / self._zoom + SCENE_H/2
        return wx, wy

    def _redraw(self):
        c = self.canvas
        c.delete("all")
        cw, ch = c.winfo_width(), c.winfo_height()
        if cw < 2:
            return

        # Сетка
        step = max(8, int(32 * self._zoom))
        x0s, y0s = self._w2s(0, 0)
        for x in range(int(x0s % step), cw, step):
            c.create_line(x, 0, x, ch, fill=GRID_COL)
        for y in range(int(y0s % step), ch, step):
            c.create_line(0, y, cw, y, fill=GRID_COL)

        # Рамка сцены
        x0, y0 = self._w2s(0, 0)
        x1, y1 = self._w2s(SCENE_W, SCENE_H)
        r, g, b = self.scene.bg_color
        c.create_rectangle(x0, y0, x1, y1,
                            fill=f"#{r:02x}{g:02x}{b:02x}",
                            outline=ACCENT2)

        # Объекты
        for obj in sorted(self.scene.objects, key=lambda o: o.z_order):
            if obj.visible:
                self._draw_obj(obj)

        c.create_text(8, ch - 16,
                      text=f"zoom {self._zoom:.2f}x  |  {len(self.scene.objects)} objects",
                      anchor="sw", fill=TEXT3, font=("Consolas", 9))

    def _draw_obj(self, obj: SpriteObject):
        c  = self.canvas
        sx, sy = self._w2s(obj.x, obj.y)
        sel = obj is self.selected

        drawn = False
        if obj._pil and PIL_AVAILABLE:
            try:
                img = obj._pil
                w   = max(1, int(img.width  * obj.scale_x * self._zoom))
                h   = max(1, int(img.height * obj.scale_y * self._zoom))
                resized = img.resize((w, h), Image.NEAREST)
                if obj.rotation % 360 != 0:
                    resized = resized.rotate(-obj.rotation, expand=True)
                tk_img = ImageTk.PhotoImage(resized)
                obj._tk = tk_img
                c.create_image(sx, sy, image=tk_img, anchor="center")
                if sel:
                    c.create_rectangle(sx - w/2 - 3, sy - h/2 - 3,
                                       sx + w/2 + 3, sy + h/2 + 3,
                                       outline=SEL_COL, width=2, dash=(4,3))
                drawn = True
            except Exception:
                pass

        if not drawn:
            hw = int(24 * obj.scale_x * self._zoom)
            hh = int(24 * obj.scale_y * self._zoom)
            fill = "#1e3a5f" if not sel else "#1e3a8a"
            dash = (4,3) if not obj.sprite_rel else ()
            c.create_rectangle(sx-hw, sy-hh, sx+hw, sy+hh,
                                fill=fill, outline=SEL_COL if sel else "#3b6ea8",
                                width=2 if sel else 1, dash=dash)
            if not obj.sprite_rel:
                c.create_text(sx, sy, text="📄",
                              font=("", max(8, int(14*self._zoom))))

        c.create_oval(sx-3, sy-3, sx+3, sy+3,
                      fill=ACCENT if sel else TEXT3, outline="")
        c.create_text(sx, sy + max(14, int(26*self._zoom)),
                      text=obj.name,
                      fill=TEXT if sel else TEXT2,
                      font=("Consolas", max(7, int(9*self._zoom))))

    # ------------------------------------------------------------------
    # Мышь
    # ------------------------------------------------------------------

    def _lmb_press(self, e):
        self.canvas.focus_set()
        wx, wy = self._s2w(e.x, e.y)
        hit = self._hit(wx, wy)
        self._select(hit)
        if hit:
            self._drag = (e.x, e.y, hit.x, hit.y)

    def _lmb_drag(self, e):
        if self._drag and self.selected:
            dx = (e.x - self._drag[0]) / self._zoom
            dy = (e.y - self._drag[1]) / self._zoom
            self.selected.x = round(self._drag[2] + dx, 1)
            self.selected.y = round(self._drag[3] + dy, 1)
            self._redraw()
            self._insp_obj(self.selected)

    def _rmb_press(self, e):
        self._pan_drag = (e.x, e.y, self._pan_x, self._pan_y)

    def _rmb_drag(self, e):
        if self._pan_drag:
            self._pan_x = self._pan_drag[2] + e.x - self._pan_drag[0]
            self._pan_y = self._pan_drag[3] + e.y - self._pan_drag[1]
            self._redraw()

    def _mouse_move(self, e):
        wx, wy = self._s2w(e.x, e.y)
        self._coord_lbl.config(text=f"x: {wx:.0f}  y: {wy:.0f}")

    def _zoom_by(self, factor):
        self._zoom = max(0.1, min(8.0, self._zoom * factor))
        self._redraw()

    def _reset_view(self):
        self._zoom = 1.0
        self._pan_x = self._pan_y = 0.0
        self._redraw()

    def _hit(self, wx, wy):
        for obj in reversed(self.scene.objects):
            if not obj.visible:
                continue
            hw = (obj._pil.width  * obj.scale_x / 2) if obj._pil else 24 * obj.scale_x
            hh = (obj._pil.height * obj.scale_y / 2) if obj._pil else 24 * obj.scale_y
            if abs(wx - obj.x) <= hw and abs(wy - obj.y) <= hh:
                return obj
        return None

    # ------------------------------------------------------------------
    # Действия
    # ------------------------------------------------------------------

    def _select(self, obj):
        self.selected = obj
        self._refresh_hier()
        self._insp_obj(obj) if obj else self._insp_empty()
        self._redraw()

    def _add_object(self):
        obj = SpriteObject(f"Object_{len(self.scene.objects)+1}",
                           x=SCENE_W/2, y=SCENE_H/2)
        self.scene.objects.append(obj)
        self._select(obj)

    def _delete_selected(self):
        if self.selected and self.selected in self.scene.objects:
            self.scene.objects.remove(self.selected)
            self._select(None)

    def _assign_sprite(self, obj=None):
        target = obj or self.selected
        if not target:
            messagebox.showinfo("Нет объекта", "Сначала выберите объект.")
            return
        path = filedialog.askopenfilename(
            title="Выбрать спрайт",
            filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp"), ("Все", "*.*")],
            initialdir=os.path.join(self.project_path, "assets"),
        )
        if not path:
            return
        assets = os.path.join(self.project_path, "assets")
        os.makedirs(assets, exist_ok=True)
        fname = os.path.basename(path)
        dst   = os.path.join(assets, fname)
        if os.path.abspath(path) != os.path.abspath(dst):
            shutil.copy2(path, dst)
        target.sprite_rel = f"assets/{fname}"
        if PIL_AVAILABLE:
            try:
                target._pil = Image.open(dst).convert("RGBA")
                target._tk  = ImageTk.PhotoImage(target._pil)
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))
        self._redraw()
        if self.selected is target:
            self._insp_obj(target)

    # ------------------------------------------------------------------
    # Редактор анимаций
    # ------------------------------------------------------------------

    def _open_anim_editor(self, obj=None, clip_name=None):
        target = obj or self.selected
        if not target:
            messagebox.showinfo("Нет объекта", "Сначала выберите объект.")
            return

        win = tk.Toplevel(self.root)
        win.title(f"Анимации — {target.name}")
        win.geometry("860x580")
        win.configure(bg=BG2)
        win.grab_set()

        current = {"clip": None}  # ссылка на выбранный AnimClip
        preview  = {"playing": False, "idx": 0, "timer": None, "imgs": []}

        # ---- Левая: список клипов ----
        lf = tk.Frame(win, bg=BG2, width=190)
        lf.pack(side="left", fill="y")
        lf.pack_propagate(False)
        tk.Label(lf, text="КЛИПЫ", bg=BG2, fg=TEXT3,
                 font=("Consolas", 9, "bold")).pack(anchor="w", padx=10, pady=(10,4))
        tk.Frame(lf, bg=BORDER, height=1).pack(fill="x")
        clips_inner = tk.Frame(lf, bg=BG2)
        clips_inner.pack(fill="both", expand=True)

        # ---- Правая: редактор ----
        rf = tk.Frame(win, bg=BG)
        rf.pack(side="left", fill="both", expand=True)
        editor_inner = tk.Frame(rf, bg=BG)
        editor_inner.pack(fill="both", expand=True)

        def stop_preview():
            preview["playing"] = False
            if preview["timer"]:
                try:
                    win.after_cancel(preview["timer"])
                except Exception:
                    pass

        win.protocol("WM_DELETE_WINDOW", lambda: (stop_preview(), win.destroy()))

        def refresh_clips():
            for w in clips_inner.winfo_children():
                w.destroy()
            for cname in target.animations:
                sel = (current["clip"] and current["clip"].name == cname)
                bg  = HOVER if sel else BG2
                row = tk.Frame(clips_inner, bg=bg, cursor="hand2")
                row.pack(fill="x")
                if sel:
                    tk.Frame(row, bg=ACCENT, width=3).pack(side="left", fill="y")
                tk.Label(row, text=cname, bg=bg, fg=TEXT if sel else TEXT2,
                         font=("Consolas", 10), anchor="w"
                         ).pack(fill="x", padx=6, pady=6)
                row.bind("<Button-1>", lambda e, n=cname: open_clip(n))
                tk.Frame(clips_inner, bg=BORDER, height=1).pack(fill="x")

            bb = tk.Frame(lf, bg=BG2)
            bb.pack(side="bottom", fill="x", padx=8, pady=8)
            tk.Button(bb, text="+ Новый клип", command=new_clip,
                      bg=ACCENT, fg="white", font=("Consolas", 10),
                      relief="flat", cursor="hand2", pady=6,
                      activebackground=ACCENT2).pack(fill="x", pady=2)
            if current["clip"]:
                tk.Button(bb, text="🗑 Удалить клип", command=del_clip,
                          bg=BG3, fg=RED, font=("Consolas", 9),
                          relief="flat", cursor="hand2", pady=4,
                          activebackground=HOVER).pack(fill="x")

        def open_clip(name):
            stop_preview()
            clip = target.animations.get(name)
            if not clip:
                return
            current["clip"] = clip
            refresh_clips()

            for w in editor_inner.winfo_children():
                w.destroy()

            # Настройки клипа
            top = tk.Frame(editor_inner, bg=BG)
            top.pack(fill="x", padx=16, pady=12)

            nv   = tk.StringVar(value=clip.name)
            fpsv = tk.DoubleVar(value=clip.fps)
            lpv  = tk.BooleanVar(value=clip.loop)
            defv = tk.BooleanVar(value=(target.default_anim == name))

            def fld(parent, label, var, w=12):
                tk.Label(parent, text=label, bg=BG, fg=TEXT2,
                         font=("Consolas", 9)).pack(side="left")
                tk.Entry(parent, textvariable=var, bg=BG3, fg=TEXT,
                         insertbackground=TEXT, font=("Consolas", 10),
                         relief="flat", width=w).pack(side="left", padx=(3,14), ipady=3)

            fld(top, "Имя:",  nv, 14)
            fld(top, "FPS:",  fpsv, 6)
            tk.Checkbutton(top, text="Loop", variable=lpv,
                           bg=BG, fg=TEXT2, selectcolor=BG3,
                           activebackground=BG, font=("Consolas", 9)
                           ).pack(side="left", padx=(0,10))
            tk.Checkbutton(top, text="По умолчанию", variable=defv,
                           bg=BG, fg=TEXT2, selectcolor=BG3,
                           activebackground=BG, font=("Consolas", 9)
                           ).pack(side="left", padx=(0,10))

            def save_clip():
                new_name = nv.get().strip() or clip.name
                if new_name != clip.name:
                    if new_name in target.animations:
                        messagebox.showerror("Ошибка", f"Клип '{new_name}' уже есть.", parent=win)
                        return
                    target.animations[new_name] = target.animations.pop(clip.name)
                    clip.name = new_name
                clip.fps  = max(0.1, float(fpsv.get()))
                clip.loop = lpv.get()
                if defv.get():
                    target.default_anim = clip.name
                elif target.default_anim == clip.name:
                    target.default_anim = None
                refresh_clips()
                open_clip(clip.name)
                self._insp_obj(target)

            tk.Button(top, text="✓ Сохранить", command=save_clip,
                      bg=GREEN, fg="white", font=("Consolas", 10),
                      relief="flat", cursor="hand2", padx=8,
                      activebackground="#16a34a").pack(side="left")

            tk.Frame(editor_inner, bg=BORDER, height=1).pack(fill="x")

            # Кадры
            mid = tk.Frame(editor_inner, bg=BG)
            mid.pack(fill="both", expand=True, padx=16, pady=8)

            tk.Label(mid, text=f"КАДРЫ  ({len(clip.frames)})",
                     bg=BG, fg=TEXT3, font=("Consolas", 9, "bold")).pack(anchor="w", pady=(0,4))

            frames_wrap = tk.Frame(mid, bg=BG3)
            frames_wrap.pack(fill="both", expand=True)

            fsb = tk.Scrollbar(frames_wrap, orient="horizontal")
            fsb.pack(side="bottom", fill="x")
            fcv = tk.Canvas(frames_wrap, bg=BG3, height=118,
                            highlightthickness=0, xscrollcommand=fsb.set)
            fcv.pack(fill="both", expand=True)
            fsb.config(command=fcv.xview)

            _tk_imgs = []

            def render_frames():
                fcv.delete("all")
                _tk_imgs.clear()
                x = 8
                for i, frel in enumerate(clip.frames):
                    full = os.path.join(self.project_path, frel) if not os.path.isabs(frel) else frel
                    if PIL_AVAILABLE and os.path.exists(full):
                        try:
                            img = Image.open(full).convert("RGBA")
                            img.thumbnail((72, 72))
                            tkimg = ImageTk.PhotoImage(img)
                            _tk_imgs.append(tkimg)
                            fcv.create_image(x+36, 8, anchor="n", image=tkimg)
                        except Exception:
                            _tk_imgs.append(None)
                            fcv.create_rectangle(x, 8, x+72, 80, fill=BG2, outline=BORDER)
                            fcv.create_text(x+36, 44, text="?", fill=TEXT3, font=("Consolas", 16))
                    else:
                        _tk_imgs.append(None)
                        fcv.create_rectangle(x, 8, x+72, 80, fill=BG2, outline=BORDER)
                        fcv.create_text(x+36, 44, text="?", fill=TEXT3, font=("Consolas", 16))

                    fcv.create_text(x+36, 84, text=f"#{i}", fill=TEXT3, font=("Consolas", 7))
                    fcv.create_text(x+36, 94, text=os.path.basename(frel)[:9],
                                    fill=TEXT3, font=("Consolas", 7))
                    del_b = tk.Button(frames_wrap, text="×", font=("Consolas", 7),
                                      bg=BG3, fg=RED, relief="flat", cursor="hand2",
                                      activebackground=HOVER,
                                      command=lambda i=i: (clip.frames.pop(i), render_frames()))
                    fcv.create_window(x+36, 108, window=del_b, width=18, height=12)
                    x += 84

                fcv.configure(scrollregion=(0, 0, max(x+8, fcv.winfo_width()), 120))
                update_prev()

            def add_frames():
                paths = filedialog.askopenfilenames(
                    title="Добавить кадры",
                    filetypes=[("Изображения", "*.png *.jpg *.jpeg *.bmp"), ("Все", "*.*")],
                    initialdir=os.path.join(self.project_path, "assets"),
                    parent=win,
                )
                if not paths:
                    return
                assets = os.path.join(self.project_path, "assets")
                os.makedirs(assets, exist_ok=True)
                for p in sorted(paths):
                    fn  = os.path.basename(p)
                    dst = os.path.join(assets, fn)
                    if os.path.abspath(p) != os.path.abspath(dst):
                        shutil.copy2(p, dst)
                    rel = f"assets/{fn}"
                    if rel not in clip.frames:
                        clip.frames.append(rel)
                render_frames()

            # Preview
            prev_row = tk.Frame(editor_inner, bg=BG2, height=110)
            prev_row.pack(fill="x", padx=16, pady=(4,8))
            prev_row.pack_propagate(False)

            prev_img = tk.Label(prev_row, bg=BG3, text="нет кадров",
                                fg=TEXT3, font=("Consolas", 9), width=9)
            prev_img.pack(side="left", padx=8, pady=8)

            prev_info = tk.Label(prev_row, bg=BG2, fg=TEXT2,
                                 font=("Consolas", 9), text="")
            prev_info.pack(side="left", padx=8)

            def update_prev():
                preview["imgs"] = []
                if not clip.frames:
                    prev_img.config(image="", text="нет кадров")
                    prev_info.config(text="")
                    return
                idx  = preview["idx"] % len(clip.frames)
                frel = clip.frames[idx]
                full = os.path.join(self.project_path, frel) if not os.path.isabs(frel) else frel
                prev_info.config(text=f"кадр {idx+1}/{len(clip.frames)}\n{os.path.basename(frel)}")
                if PIL_AVAILABLE and os.path.exists(full):
                    try:
                        img = Image.open(full).convert("RGBA")
                        img.thumbnail((88, 88))
                        tkimg = ImageTk.PhotoImage(img)
                        prev_img._tkimg = tkimg
                        prev_img.config(image=tkimg, text="")
                        return
                    except Exception:
                        pass
                prev_img.config(image="", text="?")

            def tick_prev():
                if not preview["playing"] or not clip.frames:
                    return
                preview["idx"] = (preview["idx"] + 1) % len(clip.frames)
                update_prev()
                delay = max(40, int(1000 / max(0.1, clip.fps)))
                preview["timer"] = win.after(delay, tick_prev)

            def toggle_prev():
                preview["playing"] = not preview["playing"]
                play_b.config(text="⏸" if preview["playing"] else "▶")
                if preview["playing"]:
                    tick_prev()

            play_b = tk.Button(prev_row, text="▶", command=toggle_prev,
                               bg=BG3, fg=GREEN, font=("Consolas", 14),
                               relief="flat", cursor="hand2", padx=10,
                               activebackground=HOVER)
            play_b.pack(side="left", padx=4)

            # Кнопка добавить кадры
            ctrl = tk.Frame(mid, bg=BG)
            ctrl.pack(fill="x", pady=(6,2))
            tk.Button(ctrl, text="+ Добавить кадры", command=add_frames,
                      bg=ACCENT, fg="white", font=("Consolas", 10),
                      relief="flat", cursor="hand2", padx=12, pady=5,
                      activebackground=ACCENT2).pack(side="left")

            render_frames()

        def new_clip():
            i = 1
            while f"clip_{i}" in target.animations:
                i += 1
            name = f"clip_{i}"
            target.animations[name] = AnimClip(name)
            open_clip(name)
            refresh_clips()

        def del_clip():
            clip = current["clip"]
            if not clip:
                return
            if messagebox.askyesno("Удалить", f"Удалить клип «{clip.name}»?", parent=win):
                stop_preview()
                target.animations.pop(clip.name, None)
                if target.default_anim == clip.name:
                    target.default_anim = None
                current["clip"] = None
                for w in editor_inner.winfo_children():
                    w.destroy()
                refresh_clips()
                self._insp_obj(target)

        # Открыть нужный клип
        start = clip_name or (next(iter(target.animations), None))
        if start:
            open_clip(start)
        refresh_clips()

    # ------------------------------------------------------------------
    # Сохранение / загрузка / экспорт
    # ------------------------------------------------------------------

    def _save(self):
        self.scene.save(self.scene_file)
        self.root.title(f"PyGE Editor — {os.path.basename(self.project_path)} [✓ сохранено]")

    def _load_if_exists(self):
        if not os.path.exists(self.scene_file):
            return
        try:
            self.scene.load(self.scene_file)
            for obj in self.scene.objects:
                if obj.sprite_rel and PIL_AVAILABLE:
                    full = os.path.join(self.project_path, obj.sprite_rel)
                    if os.path.exists(full):
                        try:
                            obj._pil = Image.open(full).convert("RGBA")
                            obj._tk  = ImageTk.PhotoImage(obj._pil)
                        except Exception:
                            pass
            self._refresh_hier()
        except Exception as e:
            messagebox.showwarning("Предупреждение", f"Не удалось загрузить сцену:\n{e}")

    def _export(self):
        out = export_scene(self.scene, self.project_path)
        messagebox.showinfo(
            "Экспорт завершён",
            f"Создан файл:\n{out}\n\n"
            "Добавьте в main.py:\n"
            "  from scene_data import setup_scene\n\n"
            "И в on_start():\n"
            "  setup_scene(self)",
        )

    def run(self):
        self.root.mainloop()


# ============================================================
# Точка входа
# ============================================================

if __name__ == "__main__":
    path = None
    args = sys.argv[1:]
    if "--project" in args:
        idx  = args.index("--project")
        path = args[idx + 1] if idx + 1 < len(args) else None
    elif args:
        path = args[0]

    if not PIL_AVAILABLE:
        print("[PyGE Editor] Для отображения спрайтов установите Pillow:")
        print("  pip install Pillow")

    PyGEEditor(project_path=path).run()
