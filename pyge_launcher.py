"""
pyge_launcher.py
================
UI-лаунчер для движка PyGE.
Создавайте, открывайте и запускайте проекты без написания скриптов вручную.

Запуск:
  python pyge_launcher.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import json
import shutil
import subprocess
import threading
from datetime import datetime


# ============================================================
# Конфиг
# ============================================================

LAUNCHER_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECTS_FILE = os.path.join(LAUNCHER_DIR, ".pyge_projects.json")
PYGE_DIR      = os.path.join(LAUNCHER_DIR, "pyge")

# Шаблоны проектов
TEMPLATES = {
    "Пустой проект": "empty",
    "Платформер":    "platformer",
    "Сцена с UI":    "ui_demo",
}

# Цвета (тёмная тема)
BG        = "#0f1117"
BG2       = "#161b22"
BG3       = "#1f2937"
ACCENT    = "#3b82f6"
ACCENT2   = "#60a5fa"
GREEN     = "#22c55e"
RED       = "#ef4444"
YELLOW    = "#f59e0b"
TEXT      = "#f1f5f9"
TEXT2     = "#94a3b8"
TEXT3     = "#475569"
BORDER    = "#2d3748"
HOVER     = "#1e293b"


# ============================================================
# Шаблоны кода
# ============================================================

TEMPLATE_EMPTY = '''\
"""
{name}
Создан с PyGE Launcher
"""

import pygame
from pyge.engine import Application, Time, Color
from pyge.scene import Scene
from pyge.game_object import GameObject
from pyge.component import Component
from pyge.input import Input


class MainScene(Scene):

    def on_start(self) -> None:
        """Создавайте объекты здесь."""
        pass

    def on_update(self) -> None:
        """Логика каждый кадр."""
        if Input.key_down("escape"):
            self.app.quit()

    def on_render(self, screen: pygame.Surface) -> None:
        """Рисуйте поверх объектов (HUD и т.д.)."""
        font = pygame.font.SysFont(None, 36)
        surf = font.render("{name}", True, (255, 255, 255))
        screen.blit(surf, (20, 20))


if __name__ == "__main__":
    app = Application(
        title    = "{name}",
        width    = 800,
        height   = 600,
        fps      = 60,
        bg_color = (20, 20, 30),
    )
    app.load_scene(MainScene())
    app.run()
'''

TEMPLATE_PLATFORMER = '''\
"""
{name}
Платформер на PyGE
"""

import pygame
from pyge.engine import Application, Time, Color
from pyge.scene import Scene
from pyge.game_object import GameObject
from pyge.component import Component
from pyge.input import Input
from pyge.physics.rigidbody import Rigidbody2D, BoxCollider2D, PhysicsWorld


SPEED    = 220.0
JUMP_VEL = -520.0


class PlayerController(Component):

    def on_start(self) -> None:
        self.rb       = self.get_component(Rigidbody2D)
        self.grounded = False

    def on_collision_enter(self, info) -> None:
        if info.normal[1] < -0.5:
            self.grounded = True

    def on_update(self) -> None:
        dx = Input.axis("horizontal")
        self.rb.velocity.x = dx * SPEED

        if Input.key_down("space") and self.grounded:
            self.rb.velocity.y = JUMP_VEL
            self.grounded = False

        if self.rb.velocity.y > 50:
            self.grounded = False

        if Input.key_down("escape"):
            self.app.quit()

    def on_render(self, screen: pygame.Surface) -> None:
        x = int(self.transform.x)
        y = int(self.transform.y)
        pygame.draw.rect(screen, (80, 140, 255), (x - 16, y - 24, 32, 48))


class PlatformRenderer(Component):
    def __init__(self, w, h, color):
        super().__init__()
        self.w, self.h, self.color = w, h, color

    def on_render(self, screen):
        x = int(self.transform.x - self.w / 2)
        y = int(self.transform.y - self.h / 2)
        pygame.draw.rect(screen, self.color, (x, y, self.w, self.h))


def make_platform(scene, x, y, w, h, color=(80, 60, 40)):
    obj = GameObject(f"plat_{{x}}_{{y}}", x=x, y=y)
    obj.add_component(PlatformRenderer(w, h, color))
    obj.add_component(BoxCollider2D(width=w, height=h, is_static=True))
    scene.add(obj)


class MainScene(Scene):

    def on_awake(self):
        PhysicsWorld.gravity = 1200.0

    def on_start(self):
        # Уровень
        make_platform(self, 400, 584, 800, 32)
        make_platform(self, -16, 300,  32, 600)
        make_platform(self, 816, 300,  32, 600)
        make_platform(self, 200, 430, 160, 20, (100, 160, 80))
        make_platform(self, 500, 350, 200, 20, (100, 160, 80))
        make_platform(self, 370, 260, 140, 20, (80, 140, 60))

        # Игрок
        player = GameObject("Player", x=100, y=520)
        player.add_component(Rigidbody2D(mass=1.0, max_speed=800.0))
        player.add_component(BoxCollider2D(width=30, height=46))
        player.add_component(PlayerController())
        self.add(player)

    def on_render(self, screen):
        font = pygame.font.SysFont(None, 22)
        screen.blit(font.render(f"FPS: {{int(Time.fps)}}", True, (180,180,180)), (8, 8))
        screen.blit(font.render("A/D движение  Space прыжок  Esc выход", True, (120,120,120)), (8, 30))


if __name__ == "__main__":
    app = Application("{name}", 800, 600, fps=60, bg_color=(30, 35, 50))
    app.load_scene(MainScene())
    app.run()
'''

TEMPLATE_UI_DEMO = '''\
"""
{name}
Демо UI-компонентов PyGE
"""

import pygame
from pyge.engine import Application, Time, Color
from pyge.scene import Scene
from pyge.game_object import GameObject
from pyge.component import Component
from pyge.input import Input
from pyge.ui.label import Label
from pyge.ui.button import Button


class MainScene(Scene):

    def on_start(self) -> None:
        # Заголовок
        title = GameObject("Title", x=400, y=80)
        title.add_component(Label(
            text="{name}",
            font_size=48,
            color=(255, 255, 255),
            align="center",
            shadow=True,
        ))
        self.add(title)

        # Кнопка 1
        btn1 = GameObject("Btn1", x=400, y=250)
        btn1.add_component(Button(
            width=220, height=55,
            text="Нажми меня",
            font_size=24,
            pivot=(0.5, 0.5),
            color_normal  = (59, 130, 246),
            color_hover   = (96, 165, 250),
            color_pressed = (37, 99, 235),
            border_radius = 10,
            on_click      = self._on_btn1,
        ))
        self.add(btn1)

        # Кнопка 2
        btn2 = GameObject("Btn2", x=400, y=330)
        btn2.add_component(Button(
            width=220, height=55,
            text="Выход",
            font_size=24,
            pivot=(0.5, 0.5),
            color_normal  = (71, 85, 105),
            color_hover   = (100, 116, 139),
            color_pressed = (51, 65, 85),
            border_radius = 10,
            on_click      = lambda: self.app.quit(),
        ))
        self.add(btn2)

        # Счётчик кликов
        self._clicks = 0
        self._counter_label = Label(
            text="Кликов: 0",
            font_size=28,
            color=(148, 163, 184),
            align="center",
        )
        counter = GameObject("Counter", x=400, y=430)
        counter.add_component(self._counter_label)
        self.add(counter)

    def _on_btn1(self):
        self._clicks += 1
        self._counter_label.text = f"Кликов: {{self._clicks}}"

    def on_update(self):
        if Input.key_down("escape"):
            self.app.quit()


if __name__ == "__main__":
    app = Application("{name}", 800, 600, fps=60, bg_color=(15, 23, 42))
    app.load_scene(MainScene())
    app.run()
'''

TEMPLATE_CODE = {
    "empty":      TEMPLATE_EMPTY,
    "platformer": TEMPLATE_PLATFORMER,
    "ui_demo":    TEMPLATE_UI_DEMO,
}


# ============================================================
# Менеджер проектов
# ============================================================

class ProjectManager:

    def __init__(self):
        self.projects: list[dict] = []
        self._load()

    def _load(self):
        if os.path.exists(PROJECTS_FILE):
            try:
                with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
                    self.projects = json.load(f)
            except Exception:
                self.projects = []

    def _save(self):
        with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.projects, f, ensure_ascii=False, indent=2)

    def create(self, name: str, path: str, template: str) -> dict:
        os.makedirs(path, exist_ok=True)

        # Создать main.py из шаблона
        code = TEMPLATE_CODE[template].replace("{name}", name)
        main_path = os.path.join(path, "main.py")
        with open(main_path, "w", encoding="utf-8") as f:
            f.write(code)

        # Создать assets/
        os.makedirs(os.path.join(path, "assets"), exist_ok=True)

        project = {
            "name":     name,
            "path":     path,
            "template": template,
            "created":  datetime.now().strftime("%Y-%m-%d %H:%M"),
            "last_run": None,
        }
        self.projects.insert(0, project)
        self._save()
        return project

    def remove(self, path: str):
        self.projects = [p for p in self.projects if p["path"] != path]
        self._save()

    def update_last_run(self, path: str):
        for p in self.projects:
            if p["path"] == path:
                p["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._save()

    def add_existing(self, path: str) -> dict:
        name = os.path.basename(path)
        project = {
            "name":     name,
            "path":     path,
            "template": "existing",
            "created":  "—",
            "last_run": None,
        }
        self.projects.insert(0, project)
        self._save()
        return project


# ============================================================
# UI — главное окно
# ============================================================

class LauncherApp:

    def __init__(self):
        self.pm = ProjectManager()

        self.root = tk.Tk()
        self.root.title("PyGE Launcher")
        self.root.geometry("960x620")
        self.root.minsize(800, 500)
        self.root.configure(bg=BG)

        self._selected_path: str | None = None
        self._process: subprocess.Popen | None = None

        self._build_ui()
        self._refresh_list()

    # ------------------------------------------------------------------
    # Построение UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        # ---- Шапка ----
        header = tk.Frame(self.root, bg=BG2, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(
            header, text="⬡  PyGE Launcher",
            bg=BG2, fg=TEXT,
            font=("Consolas", 18, "bold"),
        ).pack(side="left", padx=20, pady=12)

        tk.Label(
            header, text="Python 2D Game Engine",
            bg=BG2, fg=TEXT3,
            font=("Consolas", 10),
        ).pack(side="left", padx=0, pady=16)

        # ---- Основной контейнер ----
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=0, pady=0)

        # Левая панель — список проектов
        left = tk.Frame(body, bg=BG2, width=340)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        # Заголовок списка + кнопки
        list_header = tk.Frame(left, bg=BG2)
        list_header.pack(fill="x", padx=12, pady=(14, 6))

        tk.Label(
            list_header, text="ПРОЕКТЫ",
            bg=BG2, fg=TEXT3,
            font=("Consolas", 9, "bold"),
        ).pack(side="left")

        # Кнопки действий над списком
        actions = tk.Frame(left, bg=BG2)
        actions.pack(fill="x", padx=10, pady=(0, 8))

        self._btn("+ Новый",   actions, self._open_new_dialog,  ACCENT,  "left")
        self._btn("↳ Открыть", actions, self._open_existing,    BG3,     "left")

        # Разделитель
        tk.Frame(left, bg=BORDER, height=1).pack(fill="x", padx=0)

        # Список
        list_frame = tk.Frame(left, bg=BG2)
        list_frame.pack(fill="both", expand=True)

        self.list_canvas = tk.Canvas(list_frame, bg=BG2, highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical",
                                 command=self.list_canvas.yview)
        self.list_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.list_canvas.pack(side="left", fill="both", expand=True)

        self.list_inner = tk.Frame(self.list_canvas, bg=BG2)
        self.list_canvas.create_window((0, 0), window=self.list_inner, anchor="nw")
        self.list_inner.bind("<Configure>", lambda e: self.list_canvas.configure(
            scrollregion=self.list_canvas.bbox("all")))

        # Правая панель — детали проекта
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        tk.Frame(body, bg=BORDER, width=1).place(x=340, y=0, relheight=1.0)

        self.detail_frame = right
        self._show_empty_detail()

    def _btn(self, text, parent, cmd, color, side, width=None):
        b = tk.Button(
            parent, text=text, command=cmd,
            bg=color, fg=TEXT,
            font=("Consolas", 10),
            relief="flat", cursor="hand2",
            padx=10, pady=5,
            activebackground=ACCENT2,
            activeforeground=TEXT,
        )
        b.pack(side=side, padx=(0 if side=="right" else 0, 4), pady=2)
        return b

    # ------------------------------------------------------------------
    # Список проектов
    # ------------------------------------------------------------------

    def _refresh_list(self):
        for w in self.list_inner.winfo_children():
            w.destroy()

        if not self.pm.projects:
            tk.Label(
                self.list_inner,
                text="Нет проектов.\nНажмите «+ Новый»",
                bg=BG2, fg=TEXT3,
                font=("Consolas", 11),
                justify="center",
            ).pack(pady=40)
            return

        for project in self.pm.projects:
            self._project_card(project)

    def _project_card(self, project: dict):
        path     = project["path"]
        name     = project["name"]
        template = project.get("template", "")
        created  = project.get("created", "")

        is_selected = path == self._selected_path
        bg_card = HOVER if is_selected else BG2

        card = tk.Frame(self.list_inner, bg=bg_card, cursor="hand2")
        card.pack(fill="x", padx=0, pady=0)

        # Цветная полоска слева если выбран
        if is_selected:
            tk.Frame(card, bg=ACCENT, width=3).pack(side="left", fill="y")

        inner = tk.Frame(card, bg=bg_card)
        inner.pack(fill="x", padx=12 if not is_selected else 9, pady=10)

        # Иконка шаблона
        icons = {"platformer": "🎮", "ui_demo": "🖼", "empty": "📄", "existing": "📁"}
        icon = icons.get(template, "📄")

        tk.Label(inner, text=icon, bg=bg_card, font=("", 18)).pack(side="left", padx=(0, 10))

        info = tk.Frame(inner, bg=bg_card)
        info.pack(side="left", fill="x", expand=True)

        tk.Label(info, text=name, bg=bg_card, fg=TEXT,
                 font=("Consolas", 12, "bold"), anchor="w").pack(fill="x")

        short_path = path if len(path) < 38 else "…" + path[-36:]
        tk.Label(info, text=short_path, bg=bg_card, fg=TEXT3,
                 font=("Consolas", 9), anchor="w").pack(fill="x")

        if created and created != "—":
            tk.Label(info, text=f"Создан: {created}", bg=bg_card, fg=TEXT3,
                     font=("Consolas", 8), anchor="w").pack(fill="x")

        # Привязка клика
        for widget in [card, inner, info]:
            widget.bind("<Button-1>", lambda e, p=path: self._select_project(p))
            widget.bind("<Enter>",    lambda e, c=card, bi=inner, f=info, s=is_selected:
                        self._card_hover(c, bi, f, True, s))
            widget.bind("<Leave>",    lambda e, c=card, bi=inner, f=info, s=is_selected:
                        self._card_hover(c, bi, f, False, s))

        # Разделитель
        tk.Frame(self.list_inner, bg=BORDER, height=1).pack(fill="x")

    def _card_hover(self, card, inner, info, enter, selected):
        if selected:
            return
        bg = BG3 if enter else BG2
        for w in [card, inner, info]:
            w.configure(bg=bg)
        for child in info.winfo_children():
            try:
                child.configure(bg=bg)
            except Exception:
                pass

    def _select_project(self, path: str):
        self._selected_path = path
        self._refresh_list()
        project = next((p for p in self.pm.projects if p["path"] == path), None)
        if project:
            self._show_detail(project)

    # ------------------------------------------------------------------
    # Панель деталей
    # ------------------------------------------------------------------

    def _show_empty_detail(self):
        for w in self.detail_frame.winfo_children():
            w.destroy()

        tk.Label(
            self.detail_frame,
            text="Выберите проект\nили создайте новый",
            bg=BG, fg=TEXT3,
            font=("Consolas", 14),
            justify="center",
        ).place(relx=0.5, rely=0.45, anchor="center")

    def _show_detail(self, project: dict):
        for w in self.detail_frame.winfo_children():
            w.destroy()

        f = self.detail_frame
        path     = project["path"]
        name     = project["name"]
        template = project.get("template", "")
        created  = project.get("created", "—")
        last_run = project.get("last_run") or "Никогда"

        pad = dict(padx=30, pady=0)

        # Название
        tk.Label(f, text=name, bg=BG, fg=TEXT,
                 font=("Consolas", 22, "bold"), anchor="w").pack(fill="x", padx=30, pady=(28, 4))

        # Мета
        meta_texts = [
            f"📁  {path}",
            f"🗓  Создан: {created}",
            f"▶  Последний запуск: {last_run}",
        ]
        for t in meta_texts:
            tk.Label(f, text=t, bg=BG, fg=TEXT2,
                     font=("Consolas", 10), anchor="w").pack(fill="x", **pad)

        tk.Frame(f, bg=BORDER, height=1).pack(fill="x", padx=30, pady=16)

        # Кнопки действий
        btn_frame = tk.Frame(f, bg=BG)
        btn_frame.pack(fill="x", padx=30)

        run_btn = tk.Button(
            btn_frame, text="▶  Запустить",
            command=lambda: self._run_project(project),
            bg=GREEN, fg="white",
            font=("Consolas", 13, "bold"),
            relief="flat", cursor="hand2",
            padx=22, pady=10,
            activebackground="#16a34a",
            activeforeground="white",
        )
        run_btn.pack(side="left", padx=(0, 8))

        tk.Button(
            btn_frame, text="📝  Открыть main.py",
            command=lambda: self._open_file(os.path.join(path, "main.py")),
            bg=BG3, fg=TEXT,
            font=("Consolas", 11),
            relief="flat", cursor="hand2",
            padx=14, pady=10,
            activebackground=HOVER,
            activeforeground=TEXT,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            btn_frame, text="📂  Папка",
            command=lambda: self._open_folder(path),
            bg=BG3, fg=TEXT,
            font=("Consolas", 11),
            relief="flat", cursor="hand2",
            padx=14, pady=10,
            activebackground=HOVER,
            activeforeground=TEXT,
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            btn_frame, text="🎨  Редактор",
            command=lambda: self._open_editor(path),
            bg="#7c3aed", fg="white",
            font=("Consolas", 11),
            relief="flat", cursor="hand2",
            padx=14, pady=10,
            activebackground="#6d28d9",
            activeforeground="white",
        ).pack(side="left", padx=(0, 8))


        tk.Button(
            btn_frame, text="Logika",
            command=lambda: self._open_logic_editor(path),
            bg="#d97706", fg="white",
            font=("Consolas", 11),
            relief="flat", cursor="hand2",
            padx=14, pady=10,
            activebackground="#b45309",
            activeforeground="white",
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            btn_frame, text="🗑  Удалить",
            command=lambda: self._delete_project(project),
            bg=BG3, fg=RED,
            font=("Consolas", 11),
            relief="flat", cursor="hand2",
            padx=14, pady=10,
            activebackground=HOVER,
            activeforeground=RED,
        ).pack(side="right")

        tk.Frame(f, bg=BORDER, height=1).pack(fill="x", padx=30, pady=16)

        # Превью main.py
        tk.Label(f, text="main.py", bg=BG, fg=TEXT3,
                 font=("Consolas", 9, "bold")).pack(anchor="w", padx=30)

        code_frame = tk.Frame(f, bg=BG3, bd=0)
        code_frame.pack(fill="both", expand=True, padx=30, pady=(4, 20))

        code_scroll = tk.Scrollbar(code_frame)
        code_scroll.pack(side="right", fill="y")

        code_text = tk.Text(
            code_frame,
            bg=BG3, fg="#a5f3fc",
            font=("Consolas", 10),
            relief="flat",
            wrap="none",
            yscrollcommand=code_scroll.set,
            state="normal",
            insertbackground=TEXT,
        )
        code_text.pack(fill="both", expand=True, padx=8, pady=8)
        code_scroll.config(command=code_text.yview)

        main_path = os.path.join(path, "main.py")
        if os.path.exists(main_path):
            with open(main_path, "r", encoding="utf-8") as fp:
                code_text.insert("1.0", fp.read())
        else:
            code_text.insert("1.0", "# main.py не найден")

        code_text.config(state="disabled")

        # Лог запуска
        self._log_text = None
        self._log_frame = tk.Frame(f, bg=BG2)

    # ------------------------------------------------------------------
    # Действия
    # ------------------------------------------------------------------

    def _open_editor(self, path: str):
        launcher_dir = os.path.dirname(os.path.abspath(__file__))
    def _open_logic_editor(self, path):
        launcher_dir = os.path.dirname(os.path.abspath(__file__))
        editor_path  = os.path.join(launcher_dir, "pyge_logic_editor.py")
        if not os.path.exists(editor_path):
            import tkinter.messagebox as mb
            mb.showerror("Ошибка", f"pyge_logic_editor.py не найден:\n{launcher_dir}")
            return
        import subprocess, sys
        subprocess.Popen([sys.executable, editor_path, path])
        editor_path  = os.path.join(launcher_dir, "pyge_editor.py")
        if not os.path.exists(editor_path):
            messagebox.showerror("Ошибка", f"pyge_editor.py не найден:\n{launcher_dir}")
            return
        subprocess.Popen([sys.executable, editor_path, path])

    def _run_project(self, project: dict):
        path     = project["path"]
        main_py  = os.path.join(path, "main.py")

        if not os.path.exists(main_py):
            messagebox.showerror("Ошибка", f"Файл main.py не найден:\n{main_py}")
            return

        # Проверить наличие pyge рядом с проектом
        project_pyge = os.path.join(path, "pyge")
        if not os.path.exists(project_pyge):
            # Попробуем создать symlink или скопировать
            if os.path.exists(PYGE_DIR):
                try:
                    if sys.platform == "win32":
                        # На Windows копируем папку
                        shutil.copytree(PYGE_DIR, project_pyge)
                    else:
                        os.symlink(PYGE_DIR, project_pyge)
                except Exception as e:
                    messagebox.showwarning(
                        "Предупреждение",
                        f"Не удалось скопировать pyge в папку проекта:\n{e}\n\n"
                        f"Убедитесь что папка pyge/ есть в:\n{path}"
                    )

        self.pm.update_last_run(path)

        # Запустить в отдельном процессе
        try:
            if sys.platform == "win32":
                subprocess.Popen(
                    [sys.executable, "main.py"],
                    cwd=path,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                subprocess.Popen(
                    [sys.executable, "main.py"],
                    cwd=path,
                )
        except Exception as e:
            messagebox.showerror("Ошибка запуска", str(e))
            return

        # Обновить last_run в деталях
        project["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self._show_detail(project)

    def _open_file(self, path: str):
        if not os.path.exists(path):
            messagebox.showerror("Ошибка", f"Файл не найден:\n{path}")
            return
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _open_folder(self, path: str):
        if not os.path.exists(path):
            messagebox.showerror("Ошибка", f"Папка не найдена:\n{path}")
            return
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])

    def _delete_project(self, project: dict):
        name = project["name"]
        ans  = messagebox.askyesno(
            "Удалить проект",
            f"Удалить «{name}» из списка?\n\n"
            f"Файлы на диске останутся.",
        )
        if ans:
            self.pm.remove(project["path"])
            self._selected_path = None
            self._refresh_list()
            self._show_empty_detail()

    def _open_existing(self):
        path = filedialog.askdirectory(title="Выберите папку проекта")
        if not path:
            return
        # Проверить main.py
        if not os.path.exists(os.path.join(path, "main.py")):
            messagebox.showwarning(
                "Нет main.py",
                f"В папке не найден main.py:\n{path}\n\n"
                "Проект добавлен, но запуск может не работать.",
            )
        project = self.pm.add_existing(path)
        self._refresh_list()
        self._select_project(path)

    # ------------------------------------------------------------------
    # Диалог создания нового проекта
    # ------------------------------------------------------------------

    def _open_new_dialog(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Новый проект")
        dialog.geometry("480x360")
        dialog.configure(bg=BG2)
        dialog.resizable(False, False)
        dialog.grab_set()

        tk.Label(dialog, text="Новый проект", bg=BG2, fg=TEXT,
                 font=("Consolas", 16, "bold")).pack(pady=(20, 4), padx=24, anchor="w")
        tk.Frame(dialog, bg=BORDER, height=1).pack(fill="x", padx=24, pady=8)

        # Название
        tk.Label(dialog, text="Название:", bg=BG2, fg=TEXT2,
                 font=("Consolas", 10)).pack(anchor="w", padx=24)
        name_var = tk.StringVar(value="MyGame")
        name_entry = tk.Entry(dialog, textvariable=name_var,
                              bg=BG3, fg=TEXT, insertbackground=TEXT,
                              font=("Consolas", 12), relief="flat",
                              bd=0)
        name_entry.pack(fill="x", padx=24, pady=(2, 12), ipady=6)
        name_entry.focus()

        # Путь
        tk.Label(dialog, text="Папка:", bg=BG2, fg=TEXT2,
                 font=("Consolas", 10)).pack(anchor="w", padx=24)

        path_frame = tk.Frame(dialog, bg=BG2)
        path_frame.pack(fill="x", padx=24, pady=(2, 12))

        default_path = os.path.join(os.path.expanduser("~"), "PyGEProjects", "MyGame")
        path_var = tk.StringVar(value=default_path)

        def update_path(*_):
            n = name_var.get().strip() or "MyGame"
            base = os.path.dirname(path_var.get())
            path_var.set(os.path.join(base, n))

        name_var.trace_add("write", update_path)

        path_entry = tk.Entry(path_frame, textvariable=path_var,
                              bg=BG3, fg=TEXT, insertbackground=TEXT,
                              font=("Consolas", 10), relief="flat", bd=0)
        path_entry.pack(side="left", fill="x", expand=True, ipady=5)

        def browse():
            d = filedialog.askdirectory(title="Выберите папку")
            if d:
                path_var.set(os.path.join(d, name_var.get().strip() or "MyGame"))

        tk.Button(path_frame, text="…", command=browse,
                  bg=BG3, fg=TEXT, font=("Consolas", 11),
                  relief="flat", cursor="hand2", padx=8,
                  activebackground=HOVER, activeforeground=TEXT,
                  ).pack(side="left", padx=(4, 0))

        # Шаблон
        tk.Label(dialog, text="Шаблон:", bg=BG2, fg=TEXT2,
                 font=("Consolas", 10)).pack(anchor="w", padx=24)

        template_var = tk.StringVar(value=list(TEMPLATES.keys())[0])
        tmpl_frame = tk.Frame(dialog, bg=BG2)
        tmpl_frame.pack(fill="x", padx=24, pady=(2, 20))

        for label, key in TEMPLATES.items():
            rb = tk.Radiobutton(
                tmpl_frame, text=label,
                variable=template_var, value=label,
                bg=BG2, fg=TEXT,
                selectcolor=BG3,
                activebackground=BG2,
                font=("Consolas", 10),
            )
            rb.pack(side="left", padx=(0, 16))

        # Кнопки
        btn_row = tk.Frame(dialog, bg=BG2)
        btn_row.pack(fill="x", padx=24, pady=4)

        def create():
            name = name_var.get().strip()
            path = path_var.get().strip()
            tmpl = TEMPLATES[template_var.get()]

            if not name:
                messagebox.showerror("Ошибка", "Введите название проекта.", parent=dialog)
                return
            if os.path.exists(os.path.join(path, "main.py")):
                overwrite = messagebox.askyesno(
                    "Папка занята",
                    f"В папке уже есть main.py:\n{path}\n\nПерезаписать?",
                    parent=dialog,
                )
                if not overwrite:
                    return

            project = self.pm.create(name, path, tmpl)
            dialog.destroy()
            self._refresh_list()
            self._select_project(project["path"])

        tk.Button(
            btn_row, text="Создать", command=create,
            bg=ACCENT, fg="white",
            font=("Consolas", 12, "bold"),
            relief="flat", cursor="hand2",
            padx=20, pady=8,
            activebackground=ACCENT2,
            activeforeground="white",
        ).pack(side="right")

        tk.Button(
            btn_row, text="Отмена", command=dialog.destroy,
            bg=BG3, fg=TEXT2,
            font=("Consolas", 11),
            relief="flat", cursor="hand2",
            padx=14, pady=8,
            activebackground=HOVER,
            activeforeground=TEXT,
        ).pack(side="right", padx=(0, 8))

    # ------------------------------------------------------------------

    def run(self):
        self.root.mainloop()


# ============================================================
# Точка входа
# ============================================================

if __name__ == "__main__":
    app = LauncherApp()
    app.run()
