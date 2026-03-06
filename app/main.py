import os
import tkinter as tk
from tkinter import ttk
import sys
from typing import Type

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app import map  # noqa: E402
from app.canvas import TagsRegistry, sort_canvas_objects  # noqa: E402
from app.constants import BACKGROUND_COLOR, TILE_SIZE  # noqa: E402
from app.database import db_connect, db_disconnect, get_map, init_db  # noqa: E402


MAP = map.initial_map


class ResizableWidget:
    def __init__(
        self,
        widget_class: Type[tk.Widget],
        parent: tk.Widget | tk.Tk,
        position: tuple[int, int] = (0, 0),
        sticky: str = tk.N+tk.W+tk.E+tk.S,
        resize_vertically: bool = True,
        resize_horizontally: bool = True,
        **kwargs,
    ):
        self.widget = widget_class(parent, **kwargs)
        self.widget.grid(row=position[0], column=position[1], sticky=sticky)

        if resize_horizontally:
            parent.rowconfigure(position[0], weight=1)
        if resize_vertically:
            parent.columnconfigure(position[1], weight=1)


class ScrollableCanvas(ResizableWidget):
    widget: tk.Canvas

    def __init__(
        self,
        parent: tk.Widget,
        **kwargs,
    ):
        super().__init__(
            widget_class=tk.Canvas,
            parent=parent,
            **kwargs,
        )
        self.x_scroll: tk.Scrollbar = tk.Scrollbar(
            parent,
            orient=tk.HORIZONTAL,
            command=self.widget.xview,
        )
        self.x_scroll.grid(row=1, column=0, sticky=tk.W+tk.E)
        self.widget['xscrollcommand'] = self.x_scroll.set
        self.y_scroll: tk.Scrollbar = tk.Scrollbar(
            parent,
            orient=tk.VERTICAL,
            command=self.widget.yview,
        )
        self.y_scroll.grid(row=0, column=1, sticky=tk.S+tk.N)
        self.widget['yscrollcommand'] = self.y_scroll.set

        self.widget.bind_all("<Button-4>", self.linux_scroll_hadler)
        self.widget.bind_all("<Button-5>", self.linux_scroll_hadler)
        self.widget.bind_all("<MouseWheel>", self.windows_scroll_hadler)
        self.widget.bind_all("<Shift-Button-4>", self.linux_horizontal_scroll_hadler)
        self.widget.bind_all("<Shift-Button-5>", self.linux_horizontal_scroll_hadler)
        self.widget.bind_all("<Shift-MouseWheel>", self.windows_horizontal_scroll_hadler)

    def windows_scroll_hadler(self, event: tk.Event):
        one_step_size = 120
        delta = event.delta // one_step_size
        self.widget.yview_scroll(-delta, "units")

    def linux_scroll_hadler(self, event: tk.Event):
        if event.num == 4:
            self.widget.yview_scroll(-1, "units")
        else:
            self.widget.yview_scroll(1, "units")

    def windows_horizontal_scroll_hadler(self, event: tk.Event):
        one_step_size = 120
        delta = event.delta // one_step_size
        self.widget.xview_scroll(-delta, "units")

    def linux_horizontal_scroll_hadler(self, event: tk.Event):
        if event.num == 4:
            self.widget.xview_scroll(-1, "units")
        else:
            self.widget.xview_scroll(1, "units")

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Карта достижений")

    # get map size
    map_size_x = 0
    for row in MAP:
        if len(row) > map_size_x:
            map_size_x = len(row)
    map_size_x *= TILE_SIZE
    map_size_y = len(MAP) * TILE_SIZE
    window_width = min(map_size_x, root.winfo_screenwidth())
    window_height = min(map_size_y, root.winfo_screenheight())

    mainframe = ResizableWidget(ttk.Frame, root, width=window_width, height=window_height)
    canvas = ScrollableCanvas(
        parent=mainframe.widget,
        width=window_width,
        height=window_height,
        scrollregion=(0, 0, map_size_x, map_size_y),
        background=BACKGROUND_COLOR,
    )

    db = db_connect()
    initial_map_id = init_db(db)

    for row, column, cell in get_map(db, initial_map_id):
        TagsRegistry.parse_cell_and_put_on_canvas(canvas.widget, row, column, cell)
    sort_canvas_objects(canvas.widget)

    root.mainloop()

    db_disconnect(db)