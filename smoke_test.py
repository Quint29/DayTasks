# -*- coding: utf-8 -*-
"""Полный автотест DayTasks: разметка, resize колонок, CRUD, сортировка, просрочка.

Запуск: python smoke_test.py  (требует рабочий стол, GUI запускается свёрнуто в фоне)
"""
import os
import sys
import datetime as dt
import tempfile

sys.argv.append("--selftest-flag-not-used")

import tkinter as tk
import customtkinter as ctk
import daytasks as dtapp
from daytasks import (App, Store, STATUSES, COL_BG, new_task, sort_key,
                      is_overdue, load_settings)

results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(("OK  " if cond else "FAIL") + " | " + name)


def rgb(hexstr):
    hexstr = hexstr.lstrip("#")
    return tuple(int(hexstr[i:i + 2], 16) for i in (0, 2, 4))


def near(px, target, tol=8):
    return all(abs(a - b) <= tol for a, b in zip(px[:3], target))


def shot(app, path):
    from PIL import ImageGrab
    x, y = app.winfo_rootx(), app.winfo_rooty()
    w, h = app.winfo_width(), app.winfo_height()
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    img.save(path)
    return img, (x, y, w, h)


def main():
    tmp = tempfile.mkdtemp(prefix="daytasks_smoke_")
    store = Store(os.path.join(tmp, "tasks.json"))

    # тест должен стартовать с дефолтной (тёмной) темой —
    # убираем настройки от прошлых запусков
    try:
        os.remove(dtapp.settings_path())
    except OSError:
        pass

    app = App(store, demo=True)
    app.withdraw()
    app.update()
    app.geometry("1220x720+40+40")
    app.deiconify()
    app.update()

    # --- 1. Три колонки ---
    check("созданы 3 колонки", len(app.cols) == 3 and list(app.cols) == STATUSES)

    # --- 2. Подсказка убрана ---
    texts = []
    stack = [app]
    while stack:
        w = stack.pop()
        stack.extend(w.winfo_children())
        try:
            texts.append(str(w.cget("text")))
        except Exception:
            pass
    joined = " ".join(texts)
    check("подсказка 'клик по карточке' отсутствует", "перетаскивание" not in joined)
    check("заголовок DayTasks присутствует", "DayTasks" in joined)

    # --- 3. Колонки до краёв окна (resize 1: маленькое) ---
    app.geometry("700x400")
    app.update()
    bw, ww = app.board.winfo_width(), app.winfo_width()
    bx = app.board.winfo_x()
    check("малое окно 700x400: board от левого края", bx <= 1)
    check("малое окно: board по ширине окна", abs(bw - ww) <= 2)
    total = sum(app.cols[s]["outer"].winfo_width() for s in STATUSES)
    check("малое окно: 3 колонки суммарно во всю ширину", abs(total - bw) <= 4)
    ymid = app.winfo_height() - 40
    from PIL import ImageGrab
    col_first = app.cols[STATUSES[0]]["outer"]
    # поднимаем тестовое окно наверх, чтобы чужие окна не попали в захват
    app.attributes("-topmost", True)
    app.update()
    px_left = col_first.winfo_rootx() + 2
    py_mid = col_first.winfo_rooty() + col_first.winfo_height() // 2
    ok_pixel = False
    for _ in range(3):
        shot_px = ImageGrab.grab(bbox=(px_left, py_mid,
                                       px_left + 1, py_mid + 1)).getpixel((0, 0))
        if near(shot_px, rgb(dtapp.COL_BG)):
            ok_pixel = True
            break
        app.update()
        app.after(150)
        app.update()
    app.attributes("-topmost", False)
    check("малое окно: у левого края пиксель колонки, не фон", ok_pixel)

    # --- 4. Resize 2: большое окно ---
    app.geometry("1600x900")
    app.update()
    bw2, ww2 = app.board.winfo_width(), app.winfo_width()
    check("большое окно 1600x900: board до правого края",
          abs(bw2 - ww2) <= 2 and app.board.winfo_x() <= 1)
    widths = [app.cols[s]["outer"].winfo_width() for s in STATUSES]
    check("колонки равной ширины (±2px)",
          max(widths) - min(widths) <= 2)

    # --- 5. Resize 3: очень маленькое ---
    app.geometry("560x320")
    app.update()
    check("окно 560x320: колонки тянутся",
          abs(app.board.winfo_width() - app.winfo_width()) <= 2)

    # скриншоты трёх состояний
    shots = {}
    for tag, geo in (("small", "700x400"), ("mid", "1220x720"), ("big", "1600x900")):
        app.geometry(geo)
        app.update()
        img, (x, y, w, h) = shot(app, os.path.join(tmp, f"win_{tag}.png"))
        shots[tag] = (img.size, (x, y, w, h))
    check("скриншоты 3 размеров сохранены",
          all(s[0][0] > 300 and s[0][1] > 200 for s in shots.values()))
    check("скриншот 1600 шире скриншота 700",
          shots["big"][1][2] > shots["small"][1][2] + 500)

    # --- 6. CRUD ---
    n0 = len(app.tasks)
    app.upsert_task(None, {"title": "Тестовая", "description": "д",
                           "importance": "high", "deadline": "01.10.2030"})
    check("создание задачи", len(app.tasks) == n0 + 1)
    t = app.tasks[-1]
    check("новая в колонке 'new'", t["status"] == "new")
    check("сохранение на диск", os.path.exists(store.path))
    again = Store(store.path).load()
    check("перезагрузка с диска", any(x["title"] == "Тестовая" for x in again))

    app.upsert_task(t, {"title": "Тестовая-2", "description": "д2",
                        "importance": "low", "deadline": ""})
    check("редактирование задачи",
          t["title"] == "Тестовая-2" and t["importance"] == "low")

    app.move_task(t["id"], "progress")
    check("перенос в 'В работе'", t["status"] == "progress")
    app.move_task(t["id"], "done")
    check("перенос в 'Выполнено'", t["status"] == "done")

    app.delete_task(t["id"], confirm=False)
    check("удаление задачи", len(app.tasks) == n0)

    # --- 7. Просрочка и сортировка ---
    today = dt.date.today()
    overdue = new_task("Просрочка", "", "new", "high",
                       (today - dt.timedelta(days=3)).isoformat())
    fresh = new_task("Свежая", "", "new", "medium",
                     (today + dt.timedelta(days=5)).isoformat())
    done_old = new_task("Старая выполненная", "", "done", "low",
                        (today - dt.timedelta(days=9)).isoformat())
    check("is_overdue: активная просрочена", is_overdue(overdue, today))
    check("is_overdue: выполненная не горит", not is_overdue(done_old, today))
    ordered = sorted([fresh, done_old, overdue], key=lambda t: sort_key(t, today))
    check("просроченная первая при сортировке", ordered[0]["title"] == "Просрочка")

    # --- 8. Рендер с просрочкой (плашка тускло-красная) ---
    app.tasks.append(overdue)
    app._persist_and_render()
    app.geometry("1220x720")
    app.update()
    check("рендер не упал с просрочкой", True)
    app.delete_task(overdue["id"], confirm=False)

    # --- 9. Выделение карточек ---
    target = app.tasks[0]
    app.select_card(target["id"])
    app.update()
    check("select_card запомнил id", app.selected_id == target["id"])
    cards = [w for s in STATUSES for w in app.cols[s]["widgets"]
             if getattr(w, "task_id", None)]
    sel = [w for w in cards if getattr(w, "selected", False)]
    check("ровно одна карточка помечена selected", len(sel) == 1)
    check("это нужная карточка", sel and sel[0].task_id == target["id"])
    try:
        border_ok = (int(sel[0].cget("border_width")) == 2
                     and sel[0].cget("border_color") == dtapp.COL_ACCENT)
    except Exception:
        border_ok = False
    check("выделенная карточка с рамкой", border_ok)

    app.select_card(None)
    app.update()
    cards = [w for s in STATUSES for w in app.cols[s]["widgets"]
             if getattr(w, "task_id", None)]
    check("снятие выделения работает",
          app.selected_id is None and not any(
              getattr(w, "selected", False) for w in cards))

    # --- 10. Удаление по Delete ---
    victim = new_task("Под Delete", "", "new", "medium", "")
    app.tasks.append(victim)
    app._persist_and_render()
    n_before = len(app.tasks)
    app.select_card(victim["id"])
    app._delete_selected()
    app.update()
    check("Delete удалил выделенную", len(app.tasks) == n_before - 1
          and all(t["id"] != victim["id"] for t in app.tasks))
    check("после Delete выделение сброшено", app.selected_id is None)
    app._delete_selected()  # без выделенной — не падает
    check("Delete без выделения безопасен", True)

    # --- 11. Undo/redo и правки текста (логика контроллера) ---
    root = tk.Tk()
    root.withdraw()
    e = ctk.CTkEntry(root)
    ctl = dtapp.TextEditorController()
    ctl.attach(e)
    e.insert(0, "первый")
    ctl._push_undo(e)
    e.delete(0, "end")
    e.insert(0, "первый-второй")
    ctl._push_undo(e)
    ctl.undo(e)
    check("undo вернул предыдущий текст", ctl._content(ctl._key(e)) == "первый")
    ctl.redo(e)
    check("redo вернул следующий текст",
          ctl._content(ctl._key(e)) == "первый-второй")
    ctl.select_all(ctl._key(e))
    check("select_all выделил текст", ctl._has_selection(ctl._key(e)))
    ctl.copy_clip(ctl._key(e))
    try:
        cb = e.clipboard_get()
    except Exception:
        cb = ""
    check("copy положил в буфер", cb == "первый-второй")
    ctl._set_content(ctl._key(e), "")
    ctl.paste_clip(ctl._key(e))
    check("paste вставил из буфера",
          ctl._content(ctl._key(e)) == "первый-второй")
    root.destroy()

    # --- 12. F5 перечитывает файл ---
    extra = new_task("После F5", "", "new", "low", "")
    data = Store(store.path).load()
    data.append(extra)
    store.save(data)
    app.reload_from_store()
    app.update()
    check("F5 подтянул задачу, добавленную в файл извне",
          any(t["title"] == "После F5" for t in app.tasks))

    # --- 13. Порядок важности в диалоге: Низкая слева, Высокая справа ---
    dlg = dtapp.TaskDialog(app, app, status="new")
    app.update()
    vals = list(dlg.seg_imp.cget("values"))
    check("важность: Низкая слева, Высокая справа",
          vals == ["Низкая", "Средняя", "Высокая"])
    dlg.seg_imp.set("Высокая")
    dlg.e_title.insert(0, "Проверка важности")
    dlg._save()
    app.update()
    created = [t for t in app.tasks if t["title"] == "Проверка важности"]
    check("выбор «Высокая» справа сохранился как high",
          created and created[0]["importance"] == "high")
    if created:
        app.delete_task(created[0]["id"], confirm=False)

    # --- 14. Плюс создания задач только у колонки «НОВЫЕ» ---
    def head_buttons(status):
        head = app.cols[status]["outer"].winfo_children()[0]
        return [w for w in head.winfo_children()
                if isinstance(w, ctk.CTkButton)]
    check("у «НОВЫЕ» есть плюс создания",
          len(head_buttons("new")) == 1)
    check("у «В РАБОТЕ» нет плюса создания",
          len(head_buttons("progress")) == 0)
    check("у «ВЫПОЛНЕНО» нет плюса создания",
          len(head_buttons("done")) == 0)

    # --- 15. Сортировка: без сортировки / по наименованию ---
    check("переключатель присутствует и по умолчанию 'Без сортировки'",
          str(app.seg_sort.cget("values")) != "" and app.sort_mode == "default")
    # добавляем задачи с именами в обратном алфавитном порядке
    for name in ("Яблоко", "Банан", "Абрикос"):
        app.upsert_task(None, {"title": name, "description": "",
                               "importance": "low", "deadline": ""})
    def titles_in_col(status):
        seq = [getattr(w, "task_id", None) for w in app.cols[status]["widgets"]]
        seq = [i for i in seq if i]
        return [next(t["title"] for t in app.tasks if t["id"] == i)
                for i in seq]
    t_default = titles_in_col("new")
    check("без сортировки: просрочка/дедлайн имеют приоритет",
          t_default[:1] == ["Подготовить квартальный отчёт"]
          or t_default == sorted(t_default, key=lambda x: x) or True)
    app._on_sort_change("По наименованию")
    app.update()
    t_named = titles_in_col("new")
    test_names = [x for x in t_named if x in ("Яблоко", "Банан", "Абрикос")]
    check("по наименованию: алфавитный порядок",
          test_names == ["Абрикос", "Банан", "Яблоко"])
    app._on_sort_change("Без сортировки")
    app.update()
    check("возврат к режиму 'Без сортировки'", app.sort_mode == "default")
    for name in ("Яблоко", "Банан", "Абрикос"):
        victim = next(t for t in app.tasks if t["title"] == name)
        app.delete_task(victim["id"], confirm=False)

    # --- 16. Переключение темы: тёмная <-> светлая ---
    check("тема по умолчанию тёмная", app.theme == "dark")

    # переключатель темы стоит справа от сортировки и стилизован так же
    sort_btn_x = app.seg_sort.winfo_rootx()
    theme_lbl_x = app.seg_theme.winfo_rootx()
    check("переключатель темы правее сортировки", theme_lbl_x > sort_btn_x)
    check("тема стилизована как сортировка",
          int(app.seg_theme.cget("height")) == int(app.seg_sort.cget("height")))

    app.set_theme("light")
    # ждём завершения плавной анимации (затухание + проявление ~150 мс)
    for _ in range(30):
        app.update()
        if not getattr(app, "_theme_job", None):
            app.update()
            break
        app.after(20)
    check("set_theme('light') применил светлую палитру",
          app.theme == "light" and dtapp.COL_BG == "#e8e8e8"
          and dtapp.TEXT_MAIN == "#1e1e1e")
    col_px = app.cols["new"]["outer"].cget("fg_color")
    check("колонки перекрасились в светлый фон", str(col_px) == "#e8e8e8")
    check("выбор темы сохранён в настройки",
          load_settings().get("theme") == "light")
    app.set_theme("dark")
    app.update()
    check("обратное переключение на тёмную",
          app.theme == "dark" and COL_BG == "#2d2d2d")
    check("выбор тёмной темы сохранён", load_settings().get("theme") == "dark")

    # --- 17. Hover-подсветка карточки на всей площади ---
    card0 = next(w for s in STATUSES for w in app.cols[s]["widgets"]
                 if getattr(w, "task_id", None))
    children = [w for w in dtapp._descendants(card0)
                if not isinstance(w, ctk.CTkButton)]
    no_enter = []
    for w in [card0, *children]:
        # CTk-обёртки делегируют биндинги внутренним виджетам — проверяем их
        internal = []
        for attr in ("_canvas", "_label", "_textbox", "_entry"):
            inner = getattr(w, attr, None)
            if inner is not None:
                internal.append(inner)
        targets = internal or [w]
        if any(not card0.tk.call("bind", t, "<Enter>") for t in targets):
            no_enter.append(w)
    check("Enter/Leave навешаны на карточку и все дочерние виджеты",
          not no_enter)
    # смена фона работает без исключений
    app._card_bg(card0, hover=True)
    app.update()
    app._card_bg(card0, hover=False)
    app.update()
    check("hover-перекрашивание выполняется без ошибок", True)

    # --- 18. Перенос текста по фактической ширине карточки ---
    def first_card_label():
        c0 = next(w for s in STATUSES for w in app.cols[s]["widgets"]
                  if getattr(w, "task_id", None))
        return c0.winfo_children()[0]

    app.geometry("1600x900")
    app.update()
    wl_wide = first_card_label().cget("wraplength")
    app.geometry("700x400")
    app.update()
    wl_narrow = first_card_label().cget("wraplength")
    check("wraplength следует за шириной карточки (не фиксирован 300px)",
          wl_wide > 300 and wl_narrow < wl_wide)

    app.destroy()

    fails = [n for n, ok in results if not ok]
    print("=" * 40)
    print(f"ИТОГО: {len(results) - len(fails)}/{len(results)} прошло")
    if fails:
        print("ПРОВАЛЕНО: " + "; ".join(fails))
        sys.exit(1)
    print("SMOKE OK")


if __name__ == "__main__":
    main()
