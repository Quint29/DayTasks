# -*- coding: utf-8 -*-
"""DayTasks — настольный канбан для ежедневных задач.

Колонки: Новые / В работе / Выполнено.
Важность: Высокая (красный) / Средняя (жёлтый) / Низкая (зелёный) —
кружок справа сверху на карточке.
Дедлайн: просроченная задача подсвечивается тускло-красным целиком.
Карточки перетаскиваются мышкой между колонками.
Данные хранятся в %APPDATA%\\DayTasks\\tasks.json

Запуск: python daytasks.py [--demo | --selftest]
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
import time
import uuid

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox

APP_TITLE = "DayTasks"

STATUSES = ["new", "progress", "done"]
STATUS_TITLES = {"new": "НОВЫЕ", "progress": "В РАБОТЕ", "done": "ВЫПОЛНЕНО"}
STATUS_NAMES = {"new": "Новые", "progress": "В работе", "done": "Выполнено"}

IMPORTANCE = {
    "high": ("Высокая", "#e53935"),
    "medium": ("Средняя", "#fdd835"),
    "low": ("Низкая", "#43a047"),
}
IMPORTANCE_BY_NAME = {v[0]: k for k, v in IMPORTANCE.items()}

# режимы сортировки карточек
SORT_LABELS = {"Без сортировки": "default", "По наименованию": "name"}

# Палитра (тёмная тема)
COL_BG = "#2d2d2d"
COL_BG_HOVER = "#3a3a3a"
CARD_BG = "#373737"
CARD_BG_HOVER = "#404040"
CARD_OVERDUE = "#4e2626"          # тускло-красный для просрочки
CARD_OVERDUE_HOVER = "#5c2c2c"
TEXT_MAIN = "#ececec"
TEXT_MUTED = "#9e9e9e"
TEXT_DEADLINE = "#8f8f8f"
TEXT_OVERDUE = "#ff9a8d"
COL_ACCENT = "#4a8fd9"            # рамка выделенной карточки

# --- палитры тем (ключи совпадают с константами выше) ---
THEMES = {
    "dark": {
        "BG_WIN": "#242424",
        "BG_DIALOG": "#2b2b2b",
        "COL_BG": "#2d2d2d",
        "COL_BG_HOVER": "#3a3a3a",
        "CARD_BG": "#373737",
        "CARD_BG_HOVER": "#404040",
        "CARD_OVERDUE": "#4e2626",
        "CARD_OVERDUE_HOVER": "#5c2c2c",
        "TEXT_MAIN": "#ececec",
        "TEXT_MUTED": "#9e9e9e",
        "TEXT_DEADLINE": "#8f8f8f",
        "TEXT_OVERDUE": "#ff9a8d",
        "COL_ACCENT": "#4a8fd9",
        "TEXT_DESC": "#b5b5b5",
        "TEXT_HEAD": "#a8adb3",
        "TEXT_EMPTY": "#6d6d6d",
        "BTN2_BG": "#3f3f3f",
        "BTN2_HOVER": "#4a4a4a",
        "BTN2_BORDER": "#4a4a4a",
        "GHOST_BG": "#3f3f3f",
    },
    "light": {
        "BG_WIN": "#f2f2f2",
        "BG_DIALOG": "#fafafa",
        "COL_BG": "#e8e8e8",
        "COL_BG_HOVER": "#dcdcdc",
        "CARD_BG": "#ffffff",
        "CARD_BG_HOVER": "#f5f5f5",
        "CARD_OVERDUE": "#f4d4d4",
        "CARD_OVERDUE_HOVER": "#eec2c2",
        "TEXT_MAIN": "#1e1e1e",
        "TEXT_MUTED": "#5f5f5f",
        "TEXT_DEADLINE": "#7a7a7a",
        "TEXT_OVERDUE": "#c62828",
        "COL_ACCENT": "#4a8fd9",
        "TEXT_DESC": "#454545",
        "TEXT_HEAD": "#5a6068",
        "TEXT_EMPTY": "#9a9a9a",
        "BTN2_BG": "#e3e3e3",
        "BTN2_HOVER": "#d6d6d6",
        "BTN2_BORDER": "#bdbdbd",
        "GHOST_BG": "#ffffff",
    },
}


def apply_palette(mode: str):
    """Подставить активную палитру в одноимённые константы модуля."""
    pal = THEMES.get(mode, THEMES["dark"])
    globals().update(pal)


def settings_path() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "DayTasks", "settings.json")


def load_settings() -> dict:
    try:
        with open(settings_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_settings(values: dict):
    try:
        os.makedirs(os.path.dirname(settings_path()), exist_ok=True)
        with open(settings_path(), "w", encoding="utf-8") as f:
            json.dump(values, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


apply_palette("dark")  # стартовая палитра — тёмная

DRAG_THRESHOLD = 6  # пикселей, прежде чем считать движение перетаскиванием


# ----------------------------------------------------------------------------
# Хранилище
# ----------------------------------------------------------------------------

def default_data_path() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "DayTasks", "tasks.json")


def app_icon_path() -> str:
    """Путь к иконке: рядом с exe/скриптом (работает и в PyInstaller onefile)."""
    base = getattr(sys, "_MEIPASS", None) or os.path.dirname(
        os.path.abspath(sys.argv[0] or "."))
    for name in ("icon.ico", os.path.join("assets", "icon.ico"),
                 "icon.png", os.path.join("assets", "icon.png")):
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    return ""


def set_app_icon(window) -> None:
    """Назначить иконку окну Tk; тихо пропустить, если файл недоступен."""
    path = app_icon_path()
    if not path:
        return
    try:
        if path.lower().endswith(".ico"):
            window.iconbitmap(path)
        else:
            window.iconphoto(True, tk.PhotoImage(file=path))
    except Exception:
        pass


def temp_data_path(name: str) -> str:
    return os.path.join(tempfile.gettempdir(), name)


class Store:
    """Сохранение/загрузка задач в JSON-файл."""

    def __init__(self, path: str):
        self.path = path

    def load(self) -> list:
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            tasks = data.get("tasks", [])
            return tasks if isinstance(tasks, list) else []
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return []

    def save(self, tasks: list) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"tasks": tasks}, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)


# ----------------------------------------------------------------------------
# Вспомогательные функции
# ----------------------------------------------------------------------------

def parse_date(value):
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def fmt_date(d: dt.date) -> str:
    return d.strftime("%d.%m.%Y")


def is_overdue(task: dict, today: dt.date) -> bool:
    dl = parse_date(task.get("deadline"))
    return bool(dl and dl < today and task.get("status") != "done")


def card_colors(task: dict, today: dt.date):
    overdue = is_overdue(task, today)
    if overdue:
        return CARD_OVERDUE, CARD_OVERDUE_HOVER, True
    return CARD_BG, CARD_BG_HOVER, False


def sort_key(task: dict, today: dt.date):
    """Просроченные сверху, затем по дедлайну, внутри — новые раньше."""
    dl = parse_date(task.get("deadline"))
    overdue = bool(dl and dl < today and task.get("status") != "done")
    try:
        created_ts = dt.datetime.fromisoformat(task.get("created") or "").timestamp()
    except (ValueError, OSError):
        created_ts = 0.0
    return (0 if overdue else 1, dl.toordinal() if dl else 9_999_999, -created_ts)


def new_task(title: str, description: str, status: str,
             importance: str, deadline: str) -> dict:
    return {
        "id": uuid.uuid4().hex[:12],
        "title": title,
        "description": description,
        "status": status,
        "importance": importance,
        "deadline": deadline or "",
        "created": dt.datetime.now().isoformat(timespec="seconds"),
    }


def _descendants(w) -> list:
    out = []
    for child in w.winfo_children():
        out.append(child)
        out.extend(_descendants(child))
    return out


# ----------------------------------------------------------------------------
# Горячие клавиши текстовых полей: выделение, отмена, буфер (любая раскладка)
# ----------------------------------------------------------------------------

class TextEditorController:
    """Навешивает на Entry/Textbox виндовс-привычные правки.

    Ctrl+C/V/X шлём в буфер сами (работает на любой раскладке, т.к. событие
    ловится по keycode V), Ctrl+A — выделение всего, Ctrl+Z/Y — отмена/повтор
    с собственной историей.
    """

    def __init__(self):
        self._undo: dict = {}
        self._redo: dict = {}
        self._guard = set()

    # ------------------------------------------------------------- identity

    @staticmethod
    def _key(widget):
        # customtkinter 5.x: _entry_widget; 6.x: _entry (у Entry), _textbox (у Textbox)
        for attr in ("_entry_widget", "_entry", "_textbox"):
            inner = getattr(widget, attr, None)
            if inner is not None:
                return inner
        return widget

    @staticmethod
    def _is_entry(w) -> bool:
        return isinstance(w, (tk.Entry, ctk.CTkEntry))

    @staticmethod
    def _is_text(w) -> bool:
        return isinstance(w, (tk.Text, ctk.CTkTextbox))

    # --------------------------------------------------------- helpers

    def _content(self, w) -> str:
        if self._is_entry(w):
            return w.get()
        return w.get("1.0", "end-1c")

    def _set_content(self, w, value: str):
        self._guard.add(id(w))
        try:
            if self._is_entry(w):
                state = w.cget("state")
                if str(state) == "disabled":
                    return
                w.delete(0, "end")
                w.insert(0, value)
            else:
                w.delete("1.0", "end")
                w.insert("1.0", value)
        finally:
            self._guard.discard(id(w))

    def _has_selection(self, w) -> bool:
        try:
            if self._is_entry(w):
                return bool(w.selection_present())
            return bool(w.tag_ranges("sel"))
        except Exception:
            return False

    def _selected_text(self, w) -> str:
        if not self._has_selection(w):
            return ""
        try:
            if self._is_entry(w):
                return w.selection_get()
            return w.get(tk.SEL_FIRST, tk.SEL_LAST)
        except Exception:
            return ""

    def _delete_selection(self, w):
        if self._has_selection(w):
            w.delete(tk.SEL_FIRST, tk.SEL_LAST)

    def _cursor_index(self, w):
        return w.index(tk.INSERT)

    def _snapshot(self, w):
        return (self._content(w), self._cursor_index(w))

    def _push_undo(self, w):
        u = self._undo.setdefault(self._key(w), [])
        snap = self._snapshot(w)
        if not u or u[-1] != snap:
            u.append(snap)
            if len(u) > 100:
                u.pop(0)
        self._redo.pop(self._key(w), None)

    def _remember_typing(self, w):
        """Пишем историю отмен по мере ввода, но не чаще раза в 400 мс."""
        if id(w) in self._guard:
            return
        now = time.monotonic()
        last_t = getattr(w, "_edit_ts", 0.0)
        entry = self._key(w)
        u = self._undo.setdefault(entry, [])
        if not u:
            u.append(self._snapshot(w))
        elif now - last_t > 0.4:
            u.append(self._snapshot(w))
            if len(u) > 100:
                u.pop(0)
        w._edit_ts = now

    # -------------------------------------------------------- undo / redo

    def undo(self, w):
        if id(w) in self._guard:
            return
        entry = self._key(w)
        u = self._undo.setdefault(entry, [])
        if len(u) < 2:
            return
        r = self._redo.setdefault(entry, [])
        r.append(self._snapshot(w))
        u.pop()
        content, pos = u[-1]
        self._set_content(w, content)
        self._restore_pos(w, pos)

    def redo(self, w):
        if id(w) in self._guard:
            return
        entry = self._key(w)
        r = self._redo.get(entry) or []
        if not r:
            return
        content, pos = r.pop()
        self._undo.setdefault(entry, []).append(self._snapshot(w))
        self._set_content(w, content)
        self._restore_pos(w, pos)

    def _restore_pos(self, w, pos):
        try:
            if self._is_entry(w):
                w.icursor(min(int(pos), len(self._content(w))))
            else:
                w.mark_set(tk.INSERT, pos)
        except Exception:
            pass

    # ------------------------------------------------------------ commands

    def select_all(self, w):
        if self._is_entry(w):
            w.select_range(0, "end")
            w.icursor("end")
        else:
            w.tag_add("sel", "1.0", "end-1c")

    def copy_clip(self, w):
        text = self._selected_text(w)
        if not text:
            text = self._content(w)
        if text:
            self.app_clipboard_set(w, text)

    def cut_clip(self, w):
        text = self._selected_text(w) or self._content(w)
        if not text:
            return
        self.app_clipboard_set(w, text)
        self._push_undo(w)
        if self._has_selection(w):
            self._delete_selection(w)
        else:
            self._set_content(w, "")

    def paste_clip(self, w):
        try:
            text = w.clipboard_get()
        except Exception:
            return
        self._push_undo(w)
        if self._has_selection(w):
            self._delete_selection(w)
        w.insert(tk.INSERT, text)
        self._push_undo(w)

    @staticmethod
    def app_clipboard_set(w, text: str):
        w.clipboard_clear()
        w.clipboard_append(text)

    # ----------------------------------------------------------- bindings

    def attach(self, widget):
        """Навесить обработчики на Entry/Textbox (+внутренний Entry CTk)."""
        targets = {widget}
        inner = getattr(widget, "_entry", None) or getattr(widget, "_entry_widget", None) \
            or getattr(widget, "_textbox", None)
        if inner is not None:
            targets.add(inner)

        def on_key_for_widget(event, wd=widget):
            return self._on_key(event, wd)

        def on_focus_for_widget(event, wd=widget):
            return self._on_focus(wd)

        for t in targets:
            t.bind("<Key>", on_key_for_widget, add="+")
            t.bind("<FocusIn>", on_focus_for_widget, add="+")

    def _on_focus(self, widget):
        entry = self._key(widget)
        if not self._undo.get(entry):
            self._undo.setdefault(entry, [self._snapshot(widget)])

    def _on_key(self, event, widget=None):
        w = self._key(widget if widget is not None else event.widget)
        ctrl = bool(event.state & 0x0004)
        if not ctrl:
            if widget is not None and not getattr(widget, "_ctk_textbox", False):
                self._remember_typing(widget)
            return None
        code = getattr(event, "keycode", 0)
        # Windows keycode: V=86, C=67, X=88, Z=90, Y=89, A=65 (независимо от раскладки)
        if code == 65:
            self.select_all(w)
            return "break"
        if code == 86:
            self.paste_clip(w)
            return "break"
        if code == 67:
            self.copy_clip(w)
            return "break"
        if code == 88:
            self.cut_clip(w)
            return "break"
        if code == 90:
            self.undo(w)
            return "break"
        if code == 89:
            self.redo(w)
            return "break"
        return None


# ----------------------------------------------------------------------------
# Диалог задачи (создание / просмотр / редактирование)
# ----------------------------------------------------------------------------

class TaskDialog(ctk.CTkToplevel):
    def __init__(self, master, app: "App", task: dict | None = None,
                 status: str = "new"):
        super().__init__(master)
        self.app = app
        self.task = task
        self.status = task["status"] if task else status
        self.overdue_base = None
        self.editor = TextEditorController()
        self._fade_job = None
        self._closing = False

        w, h = 520, 640
        try:
            px = master.winfo_rootx() + (master.winfo_width() - w) // 2
            py = master.winfo_rooty() + (master.winfo_height() - h) // 2
        except Exception:
            px = py = 80
        # окно собирается скрытым в нужной позиции и показывается после
        # полной отрисовки — без «прыжка» из угла и перерисовки на глазах
        self.withdraw()
        self.geometry(f"{w}x{h}+{max(px, 0)}+{max(py, 20)}")
        self.resizable(False, False)
        self.title("Карточка задачи" if task else "Новая задача")
        self.configure(fg_color=BG_DIALOG)
        set_app_icon(self)
        self.transient(master)
        self.after(120, self._grab)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=22, pady=(16, 18))

        lbl = lambda text: ctk.CTkLabel(
            body, text=text, text_color=TEXT_MUTED, anchor="w",
            font=ctk.CTkFont(size=12))

        # --- название ---
        lbl("Название").pack(fill="x", pady=(0, 3))
        self.e_title = ctk.CTkEntry(body, font=ctk.CTkFont(size=14), height=34)
        self.e_title.pack(fill="x", pady=(0, 12))

        # --- описание ---
        lbl("Описание").pack(fill="x", pady=(0, 3))
        self.tb_desc = ctk.CTkTextbox(body, height=120, font=ctk.CTkFont(size=13))
        self.tb_desc.pack(fill="x", pady=(0, 12))
        self.tb_desc._ctk_textbox = True

        self.editor.attach(self.e_title)
        self.editor.attach(self.tb_desc)

        # --- важность ---
        lbl("Важность").pack(fill="x", pady=(0, 3))
        self.seg_imp = ctk.CTkSegmentedButton(
            body, values=["Низкая", "Средняя", "Высокая"], height=32)
        self.seg_imp.pack(fill="x", pady=(0, 12))

        # --- дедлайн ---
        lbl("Дедлайн — ДД.ММ.ГГГГ (можно оставить пустым)").pack(fill="x", pady=(0, 3))
        self.e_deadline = ctk.CTkEntry(body, height=34,
                                       placeholder_text="например, 25.09.2026")
        self.e_deadline.pack(fill="x")
        quick = ctk.CTkFrame(body, fg_color="transparent")
        quick.pack(fill="x", pady=(6, 0))
        for days, caption in ((1, "+1 день"), (3, "+3 дня"), (7, "+7 дней")):
            ctk.CTkButton(
                quick, text=caption, width=90, height=26,
                fg_color="transparent", border_width=1,
                border_color=BTN2_BORDER,
                text_color=TEXT_MUTED, hover_color=BTN2_HOVER,
                command=lambda d=days: self._quick_deadline(d)
            ).pack(side="left", padx=(0, 8))

        self.l_error = ctk.CTkLabel(body, text="", text_color="#ff8a80",
                                    anchor="w", font=ctk.CTkFont(size=12))
        self.l_error.pack(fill="x", pady=(8, 0))

        # --- кнопки ---
        if task:
            self.l_status = ctk.CTkLabel(
                body, text=f"Статус: {STATUS_NAMES[self.status]}",
                text_color=TEXT_MUTED, anchor="w", font=ctk.CTkFont(size=12))
            self.l_status.pack(fill="x", pady=(14, 4))

            moves = ctk.CTkFrame(body, fg_color="transparent")
            moves.pack(fill="x", pady=(0, 10))
            idx = STATUSES.index(self.status)
            if idx > 0:
                prev = STATUSES[idx - 1]
                ctk.CTkButton(moves, text=f"← В «{STATUS_NAMES[prev]}»",
                              height=32, fg_color=BTN2_BG, hover_color=BTN2_HOVER,
                              command=lambda: self._move(prev)).pack(side="left")
            if idx < len(STATUSES) - 1:
                nxt = STATUSES[idx + 1]
                ctk.CTkButton(moves, text=f"В «{STATUS_NAMES[nxt]}» →",
                              height=32, fg_color=BTN2_BG, hover_color=BTN2_HOVER,
                              command=lambda: self._move(nxt)).pack(side="right")

            ctk.CTkButton(body, text="Сохранить", height=38,
                          font=ctk.CTkFont(size=14, weight="bold"),
                          command=self._save).pack(fill="x", pady=(0, 8))

            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x")
            ctk.CTkButton(row, text="Удалить задачу", height=34, width=150,
                          fg_color="#8c2f2f", hover_color="#a83a3a",
                          command=self._delete).pack(side="left")
            ctk.CTkButton(row, text="Закрыть", height=34, width=110,
                          fg_color="transparent", border_width=1,
                          border_color=BTN2_BORDER, text_color=TEXT_MUTED,
                          hover_color=BTN2_HOVER,
                          command=self.close_smooth).pack(side="right")
        else:
            ctk.CTkButton(body, text="Добавить задачу", height=40,
                          font=ctk.CTkFont(size=14, weight="bold"),
                          command=self._save).pack(fill="x", pady=(14, 8))
            ctk.CTkButton(body, text="Отмена", height=32,
                          fg_color="transparent", border_width=1,
                          border_color=BTN2_BORDER, text_color=TEXT_MUTED,
                          hover_color=BTN2_HOVER,
                          command=self.close_smooth).pack(fill="x")

        self._fill(task)
        self.after(150, lambda: self.e_title.focus_set())

        # горячие клавиши диалога: Esc — закрыть, Ctrl+Enter — сохранить
        # (привязка на окне срабатывает и при фокусе в полях ввода)
        self.bind("<Escape>", lambda e: self.close_smooth(), add="+")
        self.bind("<Control-Return>", lambda e: self._save(), add="+")

        # плавное появление: контент собран, показываем с коротким fade-in
        self.after(30, self._smooth_show)

    def _smooth_show(self):
        """Показать окно в позиции и мягко проявить за ~120 мс."""
        if not self.winfo_exists():
            return
        self.deiconify()
        steps = 6
        def _step(i=0):
            if not self.winfo_exists():
                return
            if i >= steps:
                try:
                    self.attributes("-alpha", 1.0)
                except Exception:
                    pass
                self._fade_job = None
                return
            try:
                self.attributes("-alpha", 0.35 + 0.65 * (i + 1) / steps)
            except Exception:
                pass
            self._fade_job = self.after(16, lambda: _step(i + 1))
        _step()

    def close_smooth(self):
        """Плавное закрытие: затухание ~110 мс, затем destroy."""
        if self._closing or not self.winfo_exists():
            return
        self._closing = True
        steps = 5

        def _out(i=0):
            if not self.winfo_exists():
                return
            if i >= steps:
                self.destroy()
                return
            try:
                self.attributes("-alpha", 1.0 - (i + 1) / (steps + 0.5))
            except Exception:
                pass
            self._fade_job = self.after(14, lambda: _out(i + 1))

        _out()

    def destroy(self):
        # не оставляем висящий таймер анимации
        if self._fade_job:
            try:
                self.after_cancel(self._fade_job)
            except Exception:
                pass
            self._fade_job = None
        super().destroy()

    # ------------------------------------------------------------------ util

    def _grab(self):
        if not self.winfo_exists():
            return
        try:
            self.grab_set()
            self.focus_force()
        except Exception:
            self.after(120, self._grab)

    def _fill(self, task: dict | None):
        if not task:
            self.seg_imp.set("Средняя")
            return
        self.e_title.insert(0, task.get("title", ""))
        if task.get("description"):
            self.tb_desc.insert("1.0", task["description"])
        self.seg_imp.set(IMPORTANCE.get(task.get("importance"), ("Средняя", ""))[0])
        dl = parse_date(task.get("deadline"))
        if dl:
            self.e_deadline.insert(0, fmt_date(dl))

    def _quick_deadline(self, days: int):
        target = dt.date.today() + dt.timedelta(days=days)
        self.e_deadline.delete(0, "end")
        self.e_deadline.insert(0, fmt_date(target))

    def _error(self, text: str):
        self.l_error.configure(text=text)

    # --------------------------------------------------------------- actions

    def _collect(self) -> dict | None:
        title = self.e_title.get().strip()
        if not title:
            self._error("Укажите название задачи.")
            return None
        dl_text = self.e_deadline.get().strip()
        deadline = ""
        if dl_text:
            try:
                deadline = dt.datetime.strptime(dl_text, "%d.%m.%Y").date().isoformat()
            except ValueError:
                self._error("Дедлайн должен быть в формате ДД.ММ.ГГГГ, например 25.09.2026.")
                return None
        return {
            "title": title,
            "description": self.tb_desc.get("1.0", "end-1c").strip(),
            "importance": IMPORTANCE_BY_NAME.get(self.seg_imp.get(), "medium"),
            "deadline": deadline,
        }

    def _save(self):
        data = self._collect()
        if data is None:
            return
        self.app.upsert_task(self.task, data)
        self.close_smooth()

    def _delete(self):
        if not messagebox.askyesno(APP_TITLE,
                                   "Удалить задачу «%s»?" % self.task["title"]):
            return
        self.app.delete_task(self.task["id"], confirm=False)
        self.close_smooth()

    def _move(self, status: str):
        self.app.move_task(self.task["id"], status)
        self.close_smooth()


# ----------------------------------------------------------------------------
# Главное окно
# ----------------------------------------------------------------------------

class App(ctk.CTk):
    def __init__(self, store: Store, demo: bool = False):
        super().__init__()
        self.store = store
        self.tasks = store.load()
        if demo:
            self.tasks = demo_tasks()

        # тема из настроек до создания виджетов
        self.theme = (load_settings().get("theme")
                      if isinstance(load_settings(), dict) else None) or "dark"
        apply_palette(self.theme)

        self.title(APP_TITLE)
        self.geometry("1220x720")
        self.minsize(560, 320)
        ctk.set_appearance_mode("dark" if self.theme == "dark" else "light")
        self.configure(fg_color=THEMES[self.theme]["BG_WIN"])
        set_app_icon(self)

        self._press = None
        self._hover = None
        self.ghost = None
        self.selected_id = None
        self._ghost_job = None
        self._theme_job = None
        self.sort_mode = "default"

        self._build_toolbar()
        self._build_columns()
        self._bind_global_keys()
        self.render()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------- горячие клавиши

    def _bind_global_keys(self):
        # Ctrl+N — новая задача, F5 — перечитать из файла, Delete — удалить
        # выделенную карточку (привязки на окне срабатывают при любом фокусе)
        self.bind("<Control-n>", lambda e: TaskDialog(self, self), add="+")
        self.bind("<Control-N>", lambda e: TaskDialog(self, self), add="+")
        self.bind("<F5>", lambda e: self.reload_from_store(), add="+")
        self.bind("<Delete>", self._delete_selected, add="+")
        self.bind("<Escape>", lambda e: self._clear_selection(), add="+")

    # ------------------------------------------------------------- интерфейс

    def _build_toolbar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=18, pady=(14, 10))

        ctk.CTkLabel(bar, text="DayTasks",
                     font=ctk.CTkFont(size=22, weight="bold"),
                     text_color=TEXT_MAIN).pack(side="left")

        # переключатель сортировки карточек (по центру панели)
        sort_box = ctk.CTkFrame(bar, fg_color="transparent")
        sort_box.pack(side="left", padx=24)
        ctk.CTkLabel(sort_box, text="Сортировка:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        self.seg_sort = ctk.CTkSegmentedButton(
            sort_box, values=list(SORT_LABELS.keys()), height=30,
            font=ctk.CTkFont(size=12), command=self._on_sort_change)
        self.seg_sort.set("Без сортировки")
        self.seg_sort.pack(side="left")

        # переключатель темы — справа от сортировки, тот же стиль
        theme_box = ctk.CTkFrame(bar, fg_color="transparent")
        theme_box.pack(side="left")
        ctk.CTkLabel(theme_box, text="Тема:", text_color=TEXT_MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        self.seg_theme = ctk.CTkSegmentedButton(
            theme_box, values=["Тёмная", "Светлая"], height=30,
            font=ctk.CTkFont(size=12), command=self._on_theme_change)
        self.seg_theme.set("Тёмная" if self.theme == "dark" else "Светлая")
        self.seg_theme.pack(side="left")

        ctk.CTkButton(bar, text="+  Новая задача", height=36, width=150,
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=lambda: TaskDialog(self, self)).pack(side="right")

    def _on_theme_change(self, value: str):
        new_mode = "light" if value == "Светлая" else "dark"
        if new_mode != self.theme:
            self.set_theme(new_mode)

    def set_theme(self, mode: str, smooth: bool = True):
        """Сменить тему. Плавно: короткое затухание окна -> перекраска ->
        проявление. Перекраска происходит «под прикрытием» fade."""
        if getattr(self, "_theme_job", None):
            # предыдущая анимация ещё идёт — отменяем её
            try:
                self.after_cancel(self._theme_job)
            except Exception:
                pass
            self._theme_job = None
        self.theme = mode
        save_settings({"theme": mode})
        if smooth:
            self._theme_fade(mode)
        else:
            self._apply_theme(mode)

    def _theme_fade(self, mode: str):
        steps = 4

        def _out(i=0):
            if not self.winfo_exists():
                return
            if i >= steps:
                self._apply_theme(mode)
                self._theme_in(mode)
                return
            try:
                self.attributes("-alpha", 1.0 - 0.35 * (i + 1) / steps)
            except Exception:
                pass
            self._theme_job = self.after(14, lambda: _out(i + 1))

        _out()

    def _theme_in(self, mode: str):
        steps = 5

        def _in(i=0):
            if not self.winfo_exists():
                return
            try:
                self.attributes("-alpha", 0.65 + 0.35 * (i + 1) / steps)
                if i >= steps - 1:
                    self._theme_job = None
                    return
            except Exception:
                pass
            self._theme_job = self.after(14, lambda: _in(i + 1))

        _in()

    def _apply_theme(self, mode: str):
        apply_palette(mode)
        ctk.set_appearance_mode("dark" if mode == "dark" else "light")
        self.configure(fg_color=THEMES[mode]["BG_WIN"])
        # колонки создаются один раз — обновляем их фоны вручную
        for st in STATUSES:
            self.cols[st]["outer"].configure(fg_color=COL_BG)
            self.cols[st]["list"].configure(fg_color=COL_BG)
        self._set_hover(None)
        self.render()

    def _on_sort_change(self, value: str):
        mode = SORT_LABELS.get(value, "default")
        if mode != self.sort_mode:
            self.sort_mode = mode
            self.render()

    def _build_columns(self):
        board = ctk.CTkFrame(self, fg_color="transparent")
        board.pack(fill="both", expand=True, padx=0, pady=(0, 0))
        self.board = board

        self.cols = {}
        for i, status in enumerate(STATUSES):
            board.grid_columnconfigure(i, weight=1, uniform="col")
            board.grid_rowconfigure(0, weight=1)
            outer = ctk.CTkFrame(board, fg_color=COL_BG, corner_radius=0)
            pad_right = 1 if i < len(STATUSES) - 1 else 0
            outer.grid(row=0, column=i, sticky="nsew",
                       padx=(0, pad_right), pady=0)
            outer.grid_rowconfigure(1, weight=1)
            outer.grid_columnconfigure(0, weight=1)

            head = ctk.CTkFrame(outer, fg_color="transparent")
            head.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))

            title = ctk.CTkLabel(head, text=STATUS_TITLES[status],
                                 font=ctk.CTkFont(size=13, weight="bold"),
                                 text_color=TEXT_HEAD, anchor="w")
            title.pack(side="left")

            # плюс создания задачи — только у колонки «НОВЫЕ»:
            # новые задачи всегда начинаются там
            if status == "new":
                ctk.CTkButton(head, text="+", width=26, height=26,
                              fg_color="transparent", hover_color=BTN2_HOVER,
                              text_color=TEXT_MUTED,
                              command=lambda: TaskDialog(self, self)
                              ).pack(side="right")

            listing = ctk.CTkScrollableFrame(outer, fg_color=COL_BG,
                                             corner_radius=0)
            listing.grid(row=1, column=0, sticky="nsew", padx=(2, 2), pady=(2, 8))
            # клик по пустому месту колонки снимает выделение
            listing.bind("<Button-1>", self._clear_selection, add="+")

            self.cols[status] = {"outer": outer, "label": title,
                                 "list": listing, "widgets": []}

    def _clear_selection(self, event=None):
        if self.selected_id:
            self.select_card(None)
        return None

    # ----------------------------------------------------------- отрисовка

    def render(self):
        today = dt.date.today()
        all_ids = {t["id"] for t in self.tasks}
        if self.selected_id and self.selected_id not in all_ids:
            self.selected_id = None  # выделенная задача удалена извне
        for status in STATUSES:
            col = self.cols[status]
            for widget in col["widgets"]:
                widget.destroy()
            col["widgets"] = []

            tasks = [t for t in self.tasks if t["status"] == status]
            if self.sort_mode == "name":
                # сортировка по наименованию (без учёта регистра)
                tasks.sort(key=lambda t: (t.get("title") or "").lower())
            else:
                # «Без сортировки» — умный порядок: просрочка сверху,
                # затем по дедлайну, внутри — новые раньше
                tasks.sort(key=lambda t: sort_key(t, today))
            col["label"].configure(
                text=f"{STATUS_TITLES[status]} · {len(tasks)}")

            if not tasks:
                ph = ctk.CTkLabel(col["list"], text="Пусто",
                                  text_color=TEXT_EMPTY,
                                  font=ctk.CTkFont(size=13))
                ph.pack(pady=26)
                col["widgets"].append(ph)
                continue
            for task in tasks:
                card = self._make_card(col["list"], task, today)
                card.pack(fill="x", padx=8, pady=5)
                col["widgets"].append(card)

    def _make_card(self, parent, task: dict, today: dt.date) -> ctk.CTkFrame:
        base, hover, overdue = card_colors(task, today)
        imp_color = IMPORTANCE.get(task.get("importance"), IMPORTANCE["low"])[1]

        card = ctk.CTkFrame(parent, fg_color=base, corner_radius=10, cursor="hand2")
        card.task_id = task["id"]
        card.status = task["status"]
        card.colors = (base, hover)
        card.selected = (task["id"] == self.selected_id)
        if card.selected:
            card.configure(border_width=2, border_color=COL_ACCENT)
        card.grid_columnconfigure(0, weight=1)

        title = task.get("title", "Без названия")
        l_title = ctk.CTkLabel(card, text=title, anchor="w", justify="left",
                               wraplength=300, text_color=TEXT_MAIN,
                               font=ctk.CTkFont(size=14, weight="bold")
                               )
        l_title.pack(fill="x", padx=14, pady=(12, 2))

        desc = (task.get("description") or "").strip()
        first = next((ln.strip() for ln in desc.splitlines() if ln.strip()), "")
        if len(first) > 90:
            first = first[:87] + "…"
        if first:
            l_desc = ctk.CTkLabel(card, text=first, anchor="w", justify="left",
                                  wraplength=300, text_color=TEXT_DESC,
                                  font=ctk.CTkFont(size=12)
                                  )
            l_desc.pack(fill="x", padx=14, pady=(0, 2))
        else:
            l_desc = None

        # перенос текста — по фактической ширине карточки, а не жёсткие 300px:
        # пока строка помещается, она не переносится
        def _bind_wrap(label, reserve):
            if label is None:
                return

            def _recalc(event=None, label=label, reserve=reserve):
                wrap = max(120, card.winfo_width() - 14 - 14 - reserve)
                try:
                    if label.cget("wraplength") != wrap:
                        label.configure(wraplength=wrap)
                except Exception:
                    pass

            card.bind("<Configure>", _recalc, add="+")
            label.bind("<Configure>", _recalc, add="+")

        _bind_wrap(l_title, reserve=22)
        _bind_wrap(l_desc, reserve=22)

        dl = parse_date(task.get("deadline"))
        if dl:
            if overdue:
                deadline_text = f"ПРОСРОЧЕНО · было до {fmt_date(dl)}"
                deadline_color = TEXT_OVERDUE
            else:
                deadline_text = f"До {fmt_date(dl)}"
                deadline_color = TEXT_DEADLINE
            ctk.CTkLabel(card, text=deadline_text, anchor="w",
                         text_color=deadline_color,
                         font=ctk.CTkFont(size=12)
                         ).pack(fill="x", padx=14, pady=(2, 12))
        else:
            spacer = ctk.CTkLabel(card, text="", height=6)
            spacer.pack()

        # кружок важности — правый верхний угол
        circle = tk.Canvas(card, width=14, height=14, highlightthickness=0,
                           bg=base, bd=0)
        circle.create_oval(1, 1, 13, 13, fill=imp_color, outline="")
        circle.place(relx=1.0, x=-13, y=13, anchor="ne")
        card.circle = circle

        # кнопка удаления — правый нижний угол
        ctk.CTkButton(card, text="✕", width=24, height=24,
                      fg_color="transparent", hover_color="#8c2f2f",
                      text_color=TEXT_MUTED, corner_radius=6,
                      command=lambda: self.delete_task(task["id"])
                      ).place(relx=1.0, x=-10, y=-10, anchor="se")

        self._bind_card(card)
        return card

    # ------------------------------------------------------------ действия

    def _task_by_id(self, task_id: str) -> dict | None:
        return next((t for t in self.tasks if t["id"] == task_id), None)

    def upsert_task(self, task: dict | None, data: dict):
        if task is None:
            self.tasks.append(new_task(
                data["title"], data["description"],
                "new", data["importance"], data["deadline"]))
        else:
            task.update(data)
        self._persist_and_render()

    def move_task(self, task_id: str, status: str):
        task = self._task_by_id(task_id)
        if task and status in STATUSES:
            task["status"] = status
            self._persist_and_render()

    def delete_task(self, task_id: str, confirm: bool = True):
        task = self._task_by_id(task_id)
        if not task:
            return
        if confirm and not messagebox.askyesno(
                APP_TITLE, f"Удалить задачу «{task['title']}»?"):
            return
        self.tasks.remove(task)
        self._persist_and_render()

    def open_task(self, task_id: str):
        task = self._task_by_id(task_id)
        if not task:
            return
        # не открываем второе окно той же задачи — поднимаем существующее
        dialogs = getattr(self, "_dialogs", None)
        if dialogs is None:
            dialogs = self._dialogs = {}
        dlg = dialogs.get(task_id)
        if dlg is not None and dlg.winfo_exists():
            try:
                dlg._grab()
            except Exception:
                pass
            return
        dialogs[task_id] = TaskDialog(self, self, task=task)

    def reload_from_store(self):
        """F5: перечитать задачи из файла (сбрасывает несохранённых изменений
        в памяти нет — всё сохраняется сразу, поэтому это просто перечитка)."""
        self.tasks = self.store.load()
        self.selected_id = None
        self.render()

    # ------------------------------------------------- выделение карточек

    def select_card(self, task_id: str | None):
        if self.selected_id == task_id:
            return
        self.selected_id = task_id
        self._apply_selection_borders()

    def _apply_selection_borders(self):
        """Рамки выделения обновляем НА МЕСТЕ, без render().

        Полная перерисовка между первым и вторым кликом уничтожает карточки:
        двойной клик тогда не срабатывает (второй клик попадает в новосозданный
        виджет), а перетаскивание теряет захват мыши.
        """
        for status in STATUSES:
            for w in self.cols[status]["widgets"]:
                tid = getattr(w, "task_id", None)
                if not tid:
                    continue
                now = (tid == self.selected_id)
                if getattr(w, "selected", False) != now:
                    w.selected = now
                    if now:
                        w.configure(border_width=2, border_color=COL_ACCENT)
                    else:
                        w.configure(border_width=0)

    def _delete_selected(self, event=None):
        if not self.selected_id:
            return
        self.delete_task(self.selected_id)
        self.selected_id = None

    def _persist_and_render(self):
        self.store.save(self.tasks)
        self.render()

    def _on_close(self):
        self.store.save(self.tasks)
        self.destroy()

    # --------------------------------------------------- drag & drop карточек

    def _bind_card(self, card: ctk.CTkFrame):
        for w in [card, *_descendants(card)]:
            if isinstance(w, ctk.CTkButton):
                continue
            w.bind("<Button-1>", self._drag_start, add="+")
            w.bind("<B1-Motion>", self._drag_motion, add="+")
            w.bind("<ButtonRelease-1>", self._drag_release, add="+")
            # двойной клик открывает карточку; срабатывает и на дочерних
            # виджетах, т.к. Tk доставляет <Double-Button-1> по bindtags
            w.bind("<Double-Button-1>", self._open_from_event, add="+")
            # Enter/Leave на КАЖДОМ дочернем виджете: подсветка держится,
            # пока курсор в пределах карточки, где бы он ни был
            w.bind("<Enter>", lambda e, c=card: self._card_enter(c), add="+")
            w.bind("<Leave>", lambda e, c=card: self._card_leave(c), add="+")

    def _card_enter(self, card: ctk.CTkFrame):
        self._card_bg(card, hover=True)

    def _card_leave(self, card: ctk.CTkFrame):
        """Leave срабатывает и при переходе курсора на дочерний виджет
        (метку, кружок). Проверяем фактическое положение курсора: если он
        всё ещё в пределах карточки — подсветку не гасим (нет мерцания)."""

        def _verify():
            if not card.winfo_exists():
                return
            px = card.winfo_pointerx()
            py = card.winfo_pointery()
            x1, y1 = card.winfo_rootx(), card.winfo_rooty()
            inside = (x1 <= px < x1 + card.winfo_width()
                      and y1 <= py < y1 + card.winfo_height())
            self._card_bg(card, hover=inside)

        card.after(10, _verify)

    def _open_from_event(self, event):
        card = self._card_of(event.widget)
        if card is not None:
            self.open_task(card.task_id)
        return "break"

    def _card_bg(self, card: ctk.CTkFrame, hover: bool):
        """Цвет фона карточки: выделенная не перекрашивается при наведении."""
        if getattr(card, "selected", False):
            base, hover_col = card.colors
            card.configure(fg_color=hover_col if hover else base)
        else:
            card.configure(fg_color=card.colors[1 if hover else 0])

    def _card_of(self, widget):
        w = widget
        while w is not None:
            if getattr(w, "task_id", None):
                return w
            w = getattr(w, "master", None)
        return None

    def _column_at(self, x_root: int, y_root: int) -> str | None:
        for status in STATUSES:
            f = self.cols[status]["outer"]
            if (f.winfo_rootx() <= x_root < f.winfo_rootx() + f.winfo_width()
                    and f.winfo_rooty() <= y_root < f.winfo_rooty() + f.winfo_height()):
                return status
        return None

    def _set_hover(self, status: str | None):
        self._hover = status
        for st, col in self.cols.items():
            col["outer"].configure(
                fg_color=COL_BG_HOVER if st == status else COL_BG)

    def _make_ghost(self, title: str):
        ghost = tk.Toplevel(self)
        ghost.wm_overrideredirect(True)
        ghost.wm_withdraw()
        ghost.configure(bg=GHOST_BG)
        try:
            ghost.attributes("-alpha", 0.0)
            ghost.attributes("-topmost", True)
        except Exception:
            pass
        frame = ctk.CTkFrame(ghost, fg_color=GHOST_BG, corner_radius=8)
        frame.pack(padx=1, pady=1)
        ctk.CTkLabel(frame, text=title, justify="left", wraplength=250,
                     text_color=TEXT_MAIN,
                     font=ctk.CTkFont(size=13, weight="bold")
                     ).pack(padx=14, pady=9, anchor="w")
        # отображаем после того, как контент рассчитан, — без «прыжка» из угла
        ghost.update_idletasks()
        ghost.deiconify()
        return ghost

    def _ghost_fade_in(self, ghost):
        """Мягкое проявление призрака при старте перетаскивания."""
        def _in(i=1):
            if not ghost.winfo_exists():
                return
            try:
                ghost.attributes("-alpha", min(0.88, 0.22 * i))
            except Exception:
                pass
            if i < 4:
                ghost.after(15, lambda: _in(i + 1))
        _in()

    def _ghost_fade_out(self, ghost):
        """Мягкое растворение призрака при броске (окно исчезает само)."""
        def _out(i=1):
            if not ghost.winfo_exists():
                return
            if i > 3:
                ghost.destroy()
                return
            try:
                ghost.attributes("-alpha", max(0.0, 0.88 - 0.3 * i))
            except Exception:
                pass
            ghost.after(14, lambda: _out(i + 1))
        _out()

    def _ghost_step(self):
        """Плавное следование призрака за курсором (интерполяция 30%)."""
        if not self._press or "ghost" not in (self._press or {}):
            self._ghost_job = None
            return
        press = self._press
        ghost = press["ghost"]
        if not ghost.winfo_exists():
            self._ghost_job = None
            return
        tx, ty = press["mx"], press["my"]
        if tx is None:
            self._ghost_job = None
            return
        gx = ghost.winfo_x()
        gy = ghost.winfo_y()
        nx = gx + int((tx - gx) * 0.30)
        ny = gy + int((ty - gy) * 0.30)
        if abs(tx - gx) <= 1 and abs(ty - gy) <= 1:
            if (gx, gy) != (tx, ty):
                ghost.geometry(f"+{tx}+{ty}")
            self._ghost_job = None
            return
        ghost.geometry(f"+{nx}+{ny}")
        self._ghost_job = self.after(12, self._ghost_step)

    def _ghost_kick(self):
        if not self._ghost_job:
            self._ghost_job = self.after(12, self._ghost_step)

    def _drag_start(self, event):
        card = self._card_of(event.widget)
        if card is None:
            self._press = None
            return "break"
        self._press = {"x": event.x_root, "y": event.y_root, "card": card,
                       "mx": None, "my": None}
        return "break"

    def _drag_motion(self, event):
        press = self._press
        if not press:
            return "break"
        if "ghost" not in press:
            if (abs(event.x_root - press["x"]) < DRAG_THRESHOLD
                    and abs(event.y_root - press["y"]) < DRAG_THRESHOLD):
                return "break"
            task = self._task_by_id(press["card"].task_id)
            if task is None:
                self._press = None
                return "break"
            press["ghost"] = self._make_ghost(task["title"])
            self._ghost_fade_in(press["ghost"])
            # призрак появляется под курсором, а не в углу экрана
            press["ghost"].geometry(
                f"+{event.x_root + 8}+{event.y_root + 8}")
            # выделение запоминаем БЕЗ перерисовки: render() здесь уничтожил бы
            # карточки посреди перетаскивания и сорвал бы захват мыши
            self.selected_id = task["id"]
        press["mx"], press["my"] = event.x_root, event.y_root
        self._ghost_kick()
        target = self._column_at(event.x_root, event.y_root)
        if target != self._hover:
            self._set_hover(target)
        return "break"

    def _drag_release(self, event):
        press = self._press
        self._press = None
        if self._ghost_job:
            try:
                self.after_cancel(self._ghost_job)
            except Exception:
                pass
            self._ghost_job = None
        if not press:
            return "break"
        ghost = press.get("ghost")
        if ghost is None:
            # одинарный клик без перетаскивания — выделить карточку;
            # открытие — по двойному клику (_open_from_event)
            self.select_card(press["card"].task_id)
        else:
            self._ghost_fade_out(ghost)
            target = self._column_at(event.x_root, event.y_root)
            self._set_hover(None)
            if target and target != press["card"].status:
                self.move_task(press["card"].task_id, target)
        return "break"


# ----------------------------------------------------------------------------
# Демо-данные и самопроверка
# ----------------------------------------------------------------------------

def demo_tasks() -> list:
    today = dt.date.today()

    def mk(title, desc, status, importance, offset, seq):
        t = new_task(title, desc, status, importance,
                     "" if offset is None
                     else (today + dt.timedelta(days=offset)).isoformat())
        created = dt.datetime.now() - dt.timedelta(minutes=seq * 7)
        t["created"] = created.isoformat(timespec="seconds")
        return t

    return [
        mk("Подготовить квартальный отчёт",
           "Собрать цифры по отделу, свести в таблицу и отправить руководителю до конца недели.",
           "new", "high", -2, 1),
        mk("Позвонить в поддержку банка",
           "Уточнить лимиты по корпоративной карте и заказать выписку за месяц.",
           "new", "medium", 1, 2),
        mk("Выбрать день командного созвона",
           "Опросить коллег в чате, удобное время до обеда.",
           "new", "low", None, 3),
        mk("Дописать ТЗ на новую форму",
           "Раздел «Права доступа» остался с прошлого раза, согласовать с безопасниками.",
           "progress", "high", 0, 4),
        mk("Заказать картриджи для принтера",
           "2 чёрных, 1 цветной. Кабинет 305.",
           "progress", "low", 5, 5),
        mk("Оплатить хостинг",
           "Продлить тариф на год, чек — в бухгалтерию.",
           "done", "medium", -1, 6),
        mk("Разобрать входящие письма",
           "Почистить папку «Входящие», перенести задачи в трекер.",
           "done", "low", None, 7),
    ]


def run_selftest() -> bool:
    """Проверка логики без GUI."""
    path = temp_data_path("daytasks_selftest.json")
    if os.path.exists(path):
        os.remove(path)
    store = Store(path)
    assert store.load() == []

    today = dt.date.today()
    t1 = new_task("A", "desc", "new", "high", "")
    t2 = new_task("B", "desc", "new", "low",
                  (today - dt.timedelta(days=1)).isoformat())
    t3 = new_task("C", "desc", "done", "medium",
                  (today - dt.timedelta(days=5)).isoformat())
    store.save([t1, t2, t3])
    loaded = store.load()
    assert [t["title"] for t in loaded] == ["A", "B", "C"]

    # сортировка: просроченная активная — первая, выполненная просрочка — нет
    ordered = sorted(loaded, key=lambda t: sort_key(t, today))
    assert ordered[0]["title"] == "B"
    assert is_overdue(ordered[0], today)
    assert not is_overdue(ordered[2], today)

    # парсер дат
    assert parse_date("") is None
    assert parse_date("2026-09-25") == dt.date(2026, 9, 25)
    assert parse_date("мусор") is None

    if os.path.exists(path):
        os.remove(path)
    return True


# ----------------------------------------------------------------------------
# Точка входа
# ----------------------------------------------------------------------------

def main():
    ctk.set_default_color_theme("blue")

    flags = set(sys.argv[1:])
    if "--selftest" in flags:
        marker = os.path.join(os.getcwd(), "selftest_ok.txt")
        try:
            ok = run_selftest()
            content = "OK" if ok else "FAIL"
        except Exception:
            import traceback
            content = "ERROR:\n" + traceback.format_exc()
            ok = False
        with open(marker, "w", encoding="utf-8") as f:
            f.write(content)
        sys.exit(0 if ok else 1)

    if "--demo" in flags:
        store = Store(temp_data_path("daytasks_demo.json"))
    else:
        store = Store(default_data_path())

    app = App(store, demo="--demo" in flags)
    app.mainloop()


if __name__ == "__main__":
    main()
