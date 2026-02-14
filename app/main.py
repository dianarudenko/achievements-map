from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
import math
import os
import re
import tkinter as tk
from tkinter import ttk
import sys
from tkinter.font import Font
from typing import Any, Callable, Type

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)

from app import map  # noqa: E402
MAP = map.map

SPRITES_DIR = "sprites"
SPRITES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    SPRITES_DIR,
)

TILE_SIZE = 32
BACKGROUND_COLOR = "#999999" # "#7BA24E"
DEFAULT_BASE_COLOR = "#FFFFCF"

HALF_TILE = TILE_SIZE / 2

class ArrowPosition(str, Enum):
    START = "first"
    END = "last"
    BOTH = "both"


@dataclass
class CanvasObjectInfo:
    creation_function: Callable
    coords: list[float]
    params: dict[str, Any]


class CanvasObject:
    DEFAULT_WIDTH = 2
    BOLD_WIDTH = 3

    def __init__(
        self,
        default_params: dict[str, Any] | None = None,
        default_caption_params: dict[str, Any] | None = None,
    ):
        self.default_params = default_params or {}
        self.default_caption_params = default_caption_params or {}

    def _put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[int, int],
        objects: list[CanvasObjectInfo],
        text: str | None = None,
        text_params: dict | None = None,
        size: tuple[int, int] = (1, 1),
    ):
        # if color is not None:
        #     create_params: dict[str, Any] = {
        #         "fill": self.color,
        #         "width": self.BOLD_WIDTH,
        #         "outline": color,
        #     }
        #     text_params: dict[str, Any] = {
        #         "fill": color,
        #         "font": Font(weight="bold"),
        #     }
        # elif bold:
        #     create_params = {
        #         "fill": self.color,
        #         "width": self.BOLD_WIDTH,
        #     }
        #     text_params = {"font": Font(weight="bold")}
        # else:
        #     create_params = {
        #         "fill": self.color,
        #         "width": self.DEFAULT_WIDTH,
        #     }
        #     text_params = {}
        for item in objects:
            params = self.default_params.copy()
            params.update(item.params)
            item.creation_function(
                *item.coords,
                **params,
            )
        if text is not None:
            center_x = coords[0] + HALF_TILE * size[0]
            center_y = coords[1] + HALF_TILE * size[1]
            params = self.default_caption_params.copy()
            if text_params:
                params.update(text_params)
            canvas.create_text(
                center_x,
                center_y,
                text=text,
                justify="center",
                **params,
            )

    @abstractmethod
    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[int, int],
        text: str | None = None,
        params: dict[str, Any] | None = None,
        text_params: dict[str, Any] | None = None,
    ):
        pass


class TagsRegistry:
    @dataclass
    class ObjectInfo:
        cls: Type[CanvasObject]
        init_params: dict[str, Any]
        object: CanvasObject | None = None
    
    default_tag = map.BASE
    tag_to_object: dict[str, ObjectInfo] = {}

    @classmethod
    def connect_to(
        cls,
        tag: str,
        init_params: dict[str, Any] = {},
        default: bool = False,
    ):
        def decorator(obj_cls: Type[CanvasObject]):
            TagsRegistry.tag_to_object[tag] = TagsRegistry.ObjectInfo(
                cls=obj_cls,
                init_params=init_params,
            )
            if default:
                TagsRegistry.default_tag = tag
            return obj_cls
        return decorator
    
    @classmethod
    def _get_object(cls, tag: str) -> CanvasObject | None:
        object_info = cls.tag_to_object.get(tag)
        if object_info is None:
            object_info = cls.tag_to_object.get(cls.default_tag)
            if object_info is None:
                return None
        if object_info.object is None:
            object_info.object = object_info.cls(**object_info.init_params)
        return object_info.object
    
    @classmethod
    def parse_cell_and_put_on_canvas(cls, cell: str | None):
        if cell:
            topleft_x = TILE_SIZE * j
            topleft_y = TILE_SIZE * i
            object_params = {}
            caption_params = {}
            text = cell
            bold = False
            if cell.startswith(map.BOLD):
                text = text.lstrip(map.BOLD)
                bold = True
            else:
                object_params["width"] = CanvasObject.DEFAULT_WIDTH
            color_match = re.match(r"(.+?)#(#?\w+)", text, flags=re.I)
            if color_match is not None:
                color = color_match.group(2)
                object_params["outline"] = color
                caption_params["fill"] = color
                text = color_match.group(1)
                bold = True
            parts = text.split("_")
            if len(parts) > 2:
                tag = parts[1]
                value = parts[2]
            else:
                tag = text
                value = text
            item = cls._get_object(tag)
            if item is not None:
                if bold:
                    object_params["width"] = item.BOLD_WIDTH
                    caption_params["font"] = Font(weight="bold")
                else:
                    object_params["width"] = item.DEFAULT_WIDTH
                item.put_on_canvas(
                    canvas=canvas.widget,
                    coords=(topleft_x, topleft_y),
                    text=value,
                    params=object_params,
                    text_params=caption_params,
                )


class Connection(CanvasObject):
    DEFAULT_WIDTH = 8
    PATH_COLOR = "#FFE580"
    BOLD_WIDTH = 16

    def __init__(
        self,
        points: list[tuple[float, float]],
        arrow: ArrowPosition | None = None,
        color: str = PATH_COLOR,
        wide: bool = False,
    ):
        super().__init__(
            default_params={
                "arrow": arrow,
                "fill": color,
                "width": self.BOLD_WIDTH if wide else self.DEFAULT_WIDTH,
            }
        )
        self.points = points

    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[int, int],
        text: str | None = None,
        params: dict[str, Any] | None = None,
        text_params: dict[str, Any] | None = None,
    ):
        self._put_on_canvas(
            canvas=canvas,
            coords=coords,
            objects=[
                CanvasObjectInfo(
                    creation_function=canvas.create_line,
                    coords=self._get_coords(coords),
                    params=params or {}
                ),
            ],
        )

    def _get_coords(self, _coords: tuple[float, float]):
        coords: list[float] = []
        for point in self.points:
            coords.append(point[0] + _coords[0])
            coords.append(point[1] + _coords[1])
        return coords
    
@TagsRegistry.connect_to(map.H_PATH)
class HorizontalPath(Connection):
    def __init__(self, arrow: ArrowPosition | None = None):
        center_y = HALF_TILE
        super().__init__(
            points=([
                (0, center_y),
                (0 + TILE_SIZE, center_y),
            ]),
            arrow=arrow,
        )
    

@TagsRegistry.connect_to(map.V_PATH)
class VerticalPath(Connection):
    def __init__(self, arrow: ArrowPosition | None = None):
        center_x = HALF_TILE
        super().__init__(
            points=([
                (center_x, 0),
                (center_x, TILE_SIZE),
            ]),
            arrow=arrow,
        )
    

@TagsRegistry.connect_to(map.DOWN_RIGHT)
class DownRightPath(Connection):
    def __init__(self):
        center_x = HALF_TILE
        center_y = HALF_TILE
        super().__init__(
            points=([
                (TILE_SIZE, center_y),
                (center_x, center_y),
                (center_x, TILE_SIZE),
            ])
        )
    

@TagsRegistry.connect_to(map.DOWN_LEFT)
class DownLeftPath(Connection):
    def __init__(self):
        center_x = HALF_TILE
        center_y = HALF_TILE
        super().__init__(
            points=([
                (0, center_y),
                (center_x, center_y),
                (center_x, TILE_SIZE),
            ])
        )
    

@TagsRegistry.connect_to(map.UP_RIGHT)
class UpRightPath(Connection):
    def __init__(self):
        center_x = HALF_TILE
        center_y = HALF_TILE
        super().__init__(
            points=([
                (center_x, 0),
                (center_x, center_y),
                (TILE_SIZE, center_y),
            ])
        )
    

@TagsRegistry.connect_to(map.UP_LEFT)
class UpLeftPath(Connection):
    def __init__(self):
        center_x = HALF_TILE
        center_y = HALF_TILE
        super().__init__(
            points=([
                (0, center_y),
                (center_x, center_y),
                (center_x, 0),
            ])
        )
    

@TagsRegistry.connect_to(map.V_LEFT)
class VerticalLeftPath(Connection):
    def __init__(self):
        center_x = HALF_TILE
        center_y = HALF_TILE
        super().__init__(
            points=([
                (center_x, 0),
                (center_x, center_y),
                (0, center_y),
                (center_x, center_y),
                (center_x, TILE_SIZE),
            ])
        )
    

@TagsRegistry.connect_to(map.V_RIGHT)
class VerticalRightPath(Connection):
    def __init__(self):
        center_x = HALF_TILE
        center_y = HALF_TILE
        super().__init__(
            points=([
                (center_x, 0),
                (center_x, center_y),
                (TILE_SIZE, center_y),
                (center_x, center_y),
                (center_x, TILE_SIZE),
            ])
        )
    

@TagsRegistry.connect_to(map.H_UP)
class HorizontalUpPath(Connection):
    def __init__(self):
        center_x = HALF_TILE
        center_y = HALF_TILE
        super().__init__(
            points=([
                (0, center_y),
                (center_x, center_y),
                (center_x, 0),
                (center_x, center_y),
                (TILE_SIZE, center_y),
            ])
        )
    

@TagsRegistry.connect_to(map.H_DOWN)
class HorizontalDownPath(Connection):
    def __init__(self):
        center_x = HALF_TILE
        center_y = HALF_TILE
        super().__init__(
            points=([
                (0, center_y),
                (center_x, center_y),
                (center_x, TILE_SIZE),
                (center_x, center_y),
                (TILE_SIZE, center_y),
            ])
        )


@TagsRegistry.connect_to(map.CROSS)
class Cross(Connection):
    def __init__(self):
        center_x = HALF_TILE
        center_y = HALF_TILE
        super().__init__(
            points=([
                (0, center_y),
                (center_x, center_y),
                (center_x, 0),
                (center_x, center_y),
                (TILE_SIZE, center_y),
                (center_x, center_y),
                (center_x, TILE_SIZE),
            ])
        )


@TagsRegistry.connect_to(map.GO_RIGHT, init_params={"arrow": ArrowPosition.END})
class RightArrow(HorizontalPath):
    pass
    

@TagsRegistry.connect_to(map.GO_LEFT, init_params={"arrow": ArrowPosition.START})
class LeftArrow(HorizontalPath):
    pass


@TagsRegistry.connect_to(map.GO_UP, init_params={"arrow": ArrowPosition.START})
class UpArrow(VerticalPath):
    pass


@TagsRegistry.connect_to(map.GO_DOWN, init_params={"arrow": ArrowPosition.END})
class DownArrow(VerticalPath):
    pass


@TagsRegistry.connect_to(map.BASE, init_params={"color": DEFAULT_BASE_COLOR})
class CircleBase(CanvasObject):
    def __init__(self, color: str):
        super().__init__(
            default_params={
                "fill": color
            }
        )

    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[int, int],
        text: str | None = None,
        params: dict[str, Any] | None = None,
        text_params: dict[str, Any] | None = None,
    ):
        topleft_x = coords[0]
        topleft_y = coords[1]
        bottomright_x = topleft_x + TILE_SIZE
        bottomright_y = topleft_y + TILE_SIZE
        self._put_on_canvas(
            canvas=canvas,
            coords=coords,
            objects=[
                CanvasObjectInfo(
                    creation_function=canvas.create_oval,
                    coords=[
                        topleft_x,
                        topleft_y,
                        bottomright_x,
                        bottomright_y,
                    ],
                    params=params or {},
                ),
            ],
            text=text,
            text_params=text_params,
        )


@TagsRegistry.connect_to(map.RHOMB, init_params={"color": "#AA9853"})
class RhombBase(CanvasObject):
    SIZE = (1, 1)

    def __init__(self, color: str):
        super().__init__(
            default_params={
                "fill": color,
            }
        )

    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[int, int],
        text: str | None = None,
        params: dict[str, Any] | None = None,
        text_params: dict[str, Any] | None = None,
    ):
        self._put_on_canvas(
            canvas=canvas,
            coords=coords,
            objects=[
                CanvasObjectInfo(
                    creation_function=canvas.create_polygon,
                    coords=[
                        coords[0],
                        coords[1] + HALF_TILE * self.SIZE[1],
                        coords[0] + HALF_TILE * self.SIZE[0],
                        coords[1],
                        coords[0] + TILE_SIZE * self.SIZE[0],
                        coords[1] + HALF_TILE * self.SIZE[1],
                        coords[0] + HALF_TILE * self.SIZE[0],
                        coords[1] + TILE_SIZE * self.SIZE[1],
                    ],
                    params=params or {}
                ),
            ],
            text=text,
            text_params=text_params,
            size=self.SIZE,
        )


@TagsRegistry.connect_to(map.BIG_RHOMB, init_params={"color": "#AA9853"})
class BigRhombBase(RhombBase):
    SIZE = (2, 3)


@TagsRegistry.connect_to(map.SQUARE, init_params={"color": DEFAULT_BASE_COLOR})
class SquareBase(CanvasObject):
    DEFAULT_WIDTH = 3

    def __init__(self, color: str, prefix: str = "K"):
        super().__init__(
            default_params={
                "fill": color,
            },
            default_caption_params={
                "font": Font(weight="bold"),
            }
        )
        self.prefix = prefix

    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[int, int],
        text: str | None = None,
        params: dict[str, Any] | None = None,
        text_params: dict[str, Any] | None = None,
    ):
        self._put_on_canvas(
            canvas=canvas,
            coords=coords,
            objects=[
                CanvasObjectInfo(
                    creation_function=canvas.create_rectangle,
                    coords=[
                        coords[0],
                        coords[1],
                        coords[0] + TILE_SIZE,
                        coords[1] + TILE_SIZE,
                    ],
                    params=params or {}
                ),
            ],
            text=(self.prefix + text) if text else None,
            text_params=text_params,
        )


class BigSquaredCircleBase(CanvasObject):
    TILE_SIZE = 3 * TILE_SIZE
    SIZE = (3, 3)
    CIRCLE_OFFSET = 4
    CORNER_SIZE = 2

    def __init__(self, square_color: str, circle_color: str):
        super().__init__(
            default_caption_params={
                "font": Font(weight="bold")
            }
        )
        self.square_color = square_color
        self.circle_color = circle_color
    
    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[int, int],
        text: str | None = None,
        params: dict[str, Any] | None = None,
        text_params: dict[str, Any] | None = None,
    ):
        square_params = {
            "fill": self.square_color,
            "outline": "black",
            "smooth": True,
            "splinesteps": 24,
        }
        circle_params = {"fill": self.circle_color}
        if params is not None:
            square_params.update(params)
            circle_params.update(params)
        self._put_on_canvas(
            canvas=canvas,
            coords=coords,
            objects=[
                CanvasObjectInfo(
                    creation_function=canvas.create_polygon,
                    coords=[
                        coords[0] + self.CORNER_SIZE,
                        coords[1],
                        coords[0] + self.TILE_SIZE - self.CORNER_SIZE,
                        coords[1],
                        coords[0] + self.TILE_SIZE,
                        coords[1] + self.CORNER_SIZE,
                        coords[0] + self.TILE_SIZE,
                        coords[1] + self.TILE_SIZE - self.CORNER_SIZE,
                        coords[0] + self.TILE_SIZE - self.CORNER_SIZE,
                        coords[1] + self.TILE_SIZE,
                        coords[0] + self.CORNER_SIZE,
                        coords[1] + self.TILE_SIZE,
                        coords[0],
                        coords[1] + self.TILE_SIZE - self.CORNER_SIZE,
                        coords[0],
                        coords[1] + self.CORNER_SIZE,
                    ],
                    params=square_params,
                ),
                CanvasObjectInfo(
                    creation_function=canvas.create_oval,
                    coords=[
                        coords[0] + self.CIRCLE_OFFSET,
                        coords[1] + self.CIRCLE_OFFSET,
                        coords[0] + self.TILE_SIZE - self.CIRCLE_OFFSET,
                        coords[1] + self.TILE_SIZE - self.CIRCLE_OFFSET,
                    ],
                    params=circle_params,
                ),
            ],
            text=text,
            text_params=text_params,
            size=self.SIZE,
        )


@TagsRegistry.connect_to(map.START, init_params={"square_color": "#BEBE4C", "circle_color": "#FFFF66"})
class StartBase(BigSquaredCircleBase):
    pass


@TagsRegistry.connect_to(map.FINISH, init_params={"square_color": "#B62323", "circle_color": "#FF3333"})
class FinishBase(BigSquaredCircleBase):
    pass


@TagsRegistry.connect_to(map.STAR)
class StarBase(CanvasObject):
    def __init__(
        self,
        p: int = 5,
        q: int = 2,
        color: str = "#FFF134",
        size: int = 3,
    ):
        super().__init__(
            default_params={
                "fill": color,
                "outline": "black",
                "smooth": True,
                "splinesteps": 24,
            },
            default_caption_params={
                "font": Font(weight="bold")
            }
        )
        self.size = size
        self.star_size = size * TILE_SIZE
        self._half_star_size = self.star_size / 2
        self.shape = (size, size)
        self.star_r = self._half_star_size + self.star_size / 3
        self.p = p
        self.q = q

    def _get_coords(self, coords: tuple[int, int]) -> list[float]:
        result: list[float] = []
        center_x = coords[0] + self._half_star_size
        center_y = coords[1] + self._half_star_size
        delta_x = 0
        delta_y = self.star_r
        start_x = center_x
        start_y = center_y - delta_y
        initial_angle = math.atan2(delta_y, delta_x)

        step_angle = 2 * math.pi / self.p
        next_vertex_distance = self.star_r * math.sqrt(2 * (1 - math.cos(step_angle)))
        delta = next_vertex_distance / math.sqrt(2 * (1 - math.cos(math.pi - step_angle)))

        vertices: dict[int, tuple[float, float]] = {0: (start_x, start_y)}

        def get_vertex(idx: int) -> tuple[float, float]:
            if idx in vertices:
                return vertices[idx]
            th = initial_angle - idx * step_angle
            x = center_x + self.star_r * math.cos(th)
            y = center_y - self.star_r * math.sin(th)
            vertices[idx] = (x, y)
            return x, y
        
        def get_inner_vertex():
            k = (right_y - start_y) / (right_x - start_x)
            c = start_y - start_x * k
            sign = 1 if right_x - start_x > 0 else -1
            x = start_x + sign * delta / math.sqrt(k * k + 1)
            y = c + k * x
            return x, y

        for i in range(self.p):
            right_x, right_y = get_vertex((i + self.q) % self.p)
            inner_x, inner_y = get_inner_vertex()
            result.extend((start_x, start_y, inner_x, inner_y))
            start_x, start_y = get_vertex((i + 1) % self.p)
        return result
    
    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[int, int],
        text: str | None = None,
        params: dict[str, Any] | None = None,
        text_params: dict[str, Any] | None = None,
    ):
        self._put_on_canvas(
            canvas=canvas,
            coords=coords,
            objects=[
                CanvasObjectInfo(
                    creation_function=canvas.create_polygon,
                    coords=self._get_coords(coords),
                    params=params or {},
                ),
            ],
            text=text,
            text_params=text_params,
            size=self.shape,
        )


class Image(CanvasObject):
    def __init__(self, path: str, mirror_x=False, mirror_y=False, rotate=False):
        self.image_path = os.path.join(SPRITES_PATH, path)
        self.mirror_x=mirror_x
        self.mirror_y=mirror_y
        self.rotate=rotate
        self._set_image()
        super().__init__(
            default_params={
                "image": self.image,
                "anchor": "nw",
            }
        )

    def _set_image(self):
        image = tk.PhotoImage(file=self.image_path)
        width = image.height() if self.rotate else image.width()
        height = image.width() if self.rotate else image.height()
        self.image = tk.PhotoImage(width=width, height=height)
        start_x, end_x, increment_x = (width - 1, -1, -1) if self.mirror_x else (0, width, 1)
        start_y, end_y, increment_y = (height - 1, -1, -1) if self.mirror_y else (0, height, 1)

        data = ""
        for col in range(start_y, end_y, increment_y):
            data = data + "{"
            for row in range(start_x, end_x, increment_x):
                data = data + "#%02x%02x%02x " % image.get(col if self.rotate else row, row if self.rotate else col)
            data = data + "} "
        self.image.put(data, to=(0, 0, width, height))

    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[int, int],
        text: str | None = None,
        params: dict[str, Any] | None = None,
        text_params: dict[str, Any] | None = None,
    ):
        self._put_on_canvas(
            canvas=canvas,
            coords=coords,
            objects=[
                CanvasObjectInfo(
                    creation_function=canvas.create_image,
                    coords=coords,  # type: ignore
                    params=params or {},
                )
            ],
            text=text,
            text_params=text_params,
        )

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
        self.x_scroll.focus()
        self.widget['xscrollcommand'] = self.x_scroll.set
        self.y_scroll: tk.Scrollbar = tk.Scrollbar(
            parent,
            orient=tk.VERTICAL,
            command=self.widget.yview,
        )
        self.y_scroll.grid(row=0, column=1, sticky=tk.S+tk.N)
        self.y_scroll.focus()
        self.widget['yscrollcommand'] = self.y_scroll.set

def parse_and_put_on_canvas(cell: str):
    pass

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

    for i, row in enumerate(MAP):
        for j, cell in enumerate(row):
            TagsRegistry.parse_cell_and_put_on_canvas(cell)

    root.mainloop()