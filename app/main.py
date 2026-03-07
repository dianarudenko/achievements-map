import os
import tkinter as tk
from tkinter import ttk
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app import map  # noqa: E402
from app.canvas import draw_map  # noqa: E402
from app.constants import BACKGROUND_COLOR, TILE_SIZE  # noqa: E402
from app.database import db_connect, db_disconnect, init_db  # noqa: E402
from app.widget import ResizableWidget, ScrollableCanvas  # noqa: E402


MAP = map.initial_map

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

    draw_map(db, initial_map_id, canvas)

    root.mainloop()

    db_disconnect(db)