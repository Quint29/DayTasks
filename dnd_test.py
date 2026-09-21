# -*- coding: utf-8 -*-
"""Имитация перетаскивания карточки мышью через event_generate.

Полный цикл: Button-1 на карточке -> B1-Motion до другой колонки ->
ButtonRelease. Проверяем, что задача сменила колонку.
"""
import os
import sys
import tempfile

sys.argv.append("--flag")

import daytasks as dtapp
from daytasks import App, Store, STATUSES

results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(("OK  " if cond else "FAIL") + " | " + name)


def find_card(app, task_id):
    for s in STATUSES:
        for w in app.cols[s]["widgets"]:
            if getattr(w, "task_id", None) == task_id:
                return w
    return None


def first_label(card):
    for w in dtapp._descendants(card):
        if isinstance(w, dtapp.ctk.CTkLabel):
            return w
    return card


def drag(app, card, target_status):
    """press на карточке -> 5 шагов motion -> release над целевой колонкой."""
    widget = first_label(card)
    inner = getattr(widget, "_label", None) or widget
    x0 = widget.winfo_rootx() + widget.winfo_width() // 2
    y0 = widget.winfo_rooty() + widget.winfo_height() // 2

    inner.event_generate("<Button-1>", x=5, y=5, rootx=x0, rooty=y0)
    app.update()

    tgt = app.cols[target_status]["outer"]
    tx = tgt.winfo_rootx() + tgt.winfo_width() // 2
    ty = tgt.winfo_rooty() + tgt.winfo_height() // 2
    for i in range(1, 6):
        ix = x0 + (tx - x0) * i // 5
        iy = y0 + (ty - y0) * i // 5
        inner.event_generate("<B1-Motion>", x=5, y=5, rootx=ix, rooty=iy)
        app.update()

    inner.event_generate("<ButtonRelease-1>", x=5, y=5, rootx=tx, rooty=ty)
    app.update()


def main():
    tmp = tempfile.mkdtemp(prefix="daytasks_dnd_")
    store = Store(os.path.join(tmp, "tasks.json"))
    app = App(store, demo=True)
    app.geometry("1220x720+60+60")
    app.update()

    # --- сценарий 1: из «Новые» в «В работе» ---
    t = app.tasks[0]
    assert t["status"] == "new", "первая демо-задача должна быть в 'new'"
    card = find_card(app, t["id"])
    check("карточка найдена в 'Новые'", card is not None)

    drag(app, card, "progress")
    check("drag&drop: задача перелетела в 'В работе'", t["status"] == "progress")
    check("после dnd выделение на перетащенной", app.selected_id == t["id"])
    # призрак после броска тает, а не разрушается мгновенно
    app.update()
    ghost_alive = bool(press_ghost := getattr(app, "_press", None))
    check("ghost-состояние сброшено после броска",
          app._press is None and not ghost_alive)

    # --- сценарий 2: обратно, из «В работе» в «Новые» ---
    card = find_card(app, t["id"])
    drag(app, card, "new")
    check("drag&drop обратно в 'Новые'", t["status"] == "new")

    # --- сценарий 3: одинарный клик = выделение, двойной клик = открытие ---
    card = find_card(app, t["id"])
    widget = first_label(card)
    inner = getattr(widget, "_label", None) or widget
    wx = widget.winfo_rootx() + 5
    wy = widget.winfo_rooty() + 5

    # одинарный клик: press + release без движения
    inner.event_generate("<Button-1>", x=2, y=2, rootx=wx, rooty=wy)
    app.update()
    inner.event_generate("<ButtonRelease-1>", x=2, y=2, rootx=wx, rooty=wy)
    app.update()
    check("одинарный клик выделил карточку",
          app.selected_id == t["id"]
          and not getattr(app, "_dialogs", {}).get(t["id"]))

    # двойной клик: два быстрых нажатия — Tk сам сгенерирует Double-Button-1
    for n in range(2):
        inner.event_generate("<Button-1>", x=2, y=2, rootx=wx, rooty=wy,
                             when="tail")
        inner.event_generate("<ButtonRelease-1>", x=2, y=2,
                             rootx=wx, rooty=wy, when="tail")
        app.update()
    app.update()
    dlg = getattr(app, "_dialogs", {}).get(t["id"])
    check("двойной клик открыл диалог", dlg is not None
          and dlg.winfo_exists())
    if dlg is not None and dlg.winfo_exists():
        # ждём завершения плавного появления (до ~300 мс)
        for _ in range(20):
            app.update()
            app.after(20)
            if not dlg._fade_job:
                break
        alpha = float(dlg.attributes("-alpha"))
        check("диалог проявился до полной прозрачности (alpha=1.0)",
              abs(alpha - 1.0) < 0.05)
        title_in_dialog = dlg.e_title.get()
        check("в диалоге видны название и описание задачи",
              title_in_dialog == t["title"]
              and "цифры" in dlg.tb_desc.get("1.0", "end-1c"))
        check("статус при просмотре не изменился", t["status"] == "new")
        dlg.destroy()
        app.update()

    # --- сценарий 4: drag в «Выполнено» ---
    card = find_card(app, t["id"])
    drag(app, card, "done")
    check("drag&drop в 'Выполнено'", t["status"] == "done")
    check("сохранение после dnd",
          any(x["id"] == t["id"] and x["status"] == "done"
              for x in Store(store.path).load()))

    app.destroy()
    fails = [n for n, ok in results if not ok]
    print("=" * 40)
    print(f"ИТОГО: {len(results) - len(fails)}/{len(results)} прошло")
    if fails:
        print("ПРОВАЛЕНО: " + "; ".join(fails))
        sys.exit(1)
    print("DND OK")


if __name__ == "__main__":
    main()
