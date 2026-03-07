import tkinter as tk
from typing import Type

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
            parent.rowconfigure(position[1], weight=1)
        if resize_vertically:
            parent.columnconfigure(position[0], weight=1)


class ScrollableCanvas(ResizableWidget):
    widget: tk.Canvas

    def __init__(
        self,
        parent: tk.Widget,
        scrollregion: tuple[int, int, int, int],
        **kwargs,
    ):
        self.scrollregion = scrollregion
        super().__init__(
            widget_class=tk.Canvas,
            parent=parent,
            scrollregion=scrollregion,
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
        self.widget.bind("<Configure>", self.on_canvas_configure)


    def on_canvas_configure(self, event: tk.Event):
        """Called when the canvas widget itself is resized (e.g., by parent grid)."""
        new_width = max(self.scrollregion[2], event.width)
        new_height = max(self.scrollregion[3], event.height)
    
        self.widget["scrollregion"] = (0, 0, new_width, new_height)

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