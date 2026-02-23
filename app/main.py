from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
import math
import os
import tkinter as tk
from tkinter import ttk
import sys
from tkinter.font import Font
from typing import Any, Callable, Literal, Type

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
BACKGROUND_COLOR = "#7BA24E"  # "#999999"
DEFAULT_BASE_COLOR = "#FFFFCF"
DEFAULT_PATH_COLOR = "#FFE580"

HALF_TILE = TILE_SIZE / 2

class ArrowPosition(str, Enum):
    START = "first"
    END = "last"
    BOTH = "both"

class CanvasTag(str, Enum):
    TEXT_BACKGROUND = "text_background"
    TEXT = "text"
    BASE = "base"
    PATH = "path"


@dataclass
class CanvasObjectInfo:
    creation_function: Callable
    coords: list[float]
    params: dict[str, Any]
    caption: map.CaptionInfo | None


class CanvasObject:
    DEFAULT_WIDTH = 2
    BOLD_WIDTH = 3
    canvas_tag = CanvasTag.BASE

    def _put_on_canvas(self, canvas: tk.Canvas, objects: list[CanvasObjectInfo]):
        for item in objects:
            if "tags" in item.params:
                tags = item.params["tags"]
                if not isinstance(tags, str):
                    tags_set = set(tags)
                    tags_set.add(self.canvas_tag)
                    tags = tuple(tags_set)
                del item.params["tags"]
            else:
                tags = self.canvas_tag
            item_id = item.creation_function(
                *item.coords,
                **item.params,
                tags=tags,
            )
            if item.caption is not None:
                tmp = canvas.bbox(item_id)
                top_left_x, top_left_y, bottom_right_x, bottom_right_y = tmp
                direction: Literal[1, -1] = 1
                match item.caption.relative_pos:
                    case "right":
                        start_x = bottom_right_x
                        start_y = (top_left_y + bottom_right_y) / 2
                        anchor = tk.W
                    case "left":
                        start_x = top_left_x
                        start_y = (top_left_y + bottom_right_y) / 2
                        anchor = tk.E
                        direction = -1
                    case "up":
                        start_x = (top_left_x + bottom_right_x) / 2
                        start_y = top_left_y
                        anchor = tk.S
                    case "down":
                        start_x = (top_left_x + bottom_right_x) / 2
                        start_y = bottom_right_y
                        anchor = tk.N
                    case "center":
                        start_x = (top_left_x + bottom_right_x) / 2
                        start_y = (top_left_y + bottom_right_y) / 2
                        anchor = tk.CENTER
                for part in item.caption.contents[::direction]:
                    if "tags" in part.extra_params:
                        tags = part.extra_params["tags"]
                        if not isinstance(tags, str):
                            tags_set = set(tags)
                            tags_set.add(self.canvas_tag)
                            tags = tuple(tags_set)
                        del part.extra_params["tags"]
                    else:
                        tags = CanvasTag.TEXT
                    text_id = canvas.create_text(
                        start_x,
                        start_y,
                        anchor=anchor,
                        text=part.text,
                        justify="center",
                        tags=tags,
                        **part.extra_params,
                    )
                    cur_bbox = canvas.bbox(text_id)
                    if part.boxed:
                        canvas.create_rectangle(*cur_bbox, tags=CanvasTag.TEXT_BACKGROUND)
                    if part.arrowed:
                        canvas.create_line(
                            cur_bbox[0],
                            cur_bbox[1],
                            cur_bbox[2],
                            cur_bbox[1],
                            arrow="first" if part.arrowed == "l" else "last",
                            arrowshape=(3, 3 * math.sqrt(2), 3),
                            tags=CanvasTag.TEXT,
                        )
                    if direction < 0:
                        start_x = cur_bbox[0]
                        if tk.E not in anchor:
                            anchor += tk.E
                    else:
                        start_x = cur_bbox[2]
                        if tk.W not in anchor:
                            anchor += tk.W

    @abstractmethod
    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[int, int],
        extra_params: dict[str, Any],
        caption: list[map.TextParams] | None,
    ):
        pass


class TagsRegistry:
    @dataclass
    class ObjectInfo:
        cls: Type[CanvasObject]
        init_params: dict[str, Any]
        object: CanvasObject | None = None
    
    default_tag = map.MapTag.BASE
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
    def parse_cell_and_put_on_canvas(cls, cell: Literal[""] | None | map.MapObjectInfo):
        if cell:
            topleft_x = TILE_SIZE * j
            topleft_y = TILE_SIZE * i
            object_params = {}
            caption_params = {}
            bold = False
            if cell.bold:
                bold = True
            else:
                object_params["width"] = CanvasObject.DEFAULT_WIDTH
            if cell.color is not None:
                object_params["outline"] = cell.color
                caption_params["fill"] = cell.color
                bold = True
            item = cls._get_object(cell.tag)
            if item is not None:
                if bold:
                    object_params["width"] = item.BOLD_WIDTH
                    caption_params["font"] = Font(weight="bold")
                else:
                    object_params["width"] = item.DEFAULT_WIDTH
                object_params.update(cell.extra_params)
                if cell.caption is not None:
                    for part in cell.caption:
                        part.extra_params.update(caption_params)
                item.put_on_canvas(
                    canvas=canvas.widget,
                    coords=(topleft_x, topleft_y),
                    extra_params=object_params,
                    caption=cell.caption,
                )


class Connection(CanvasObject):
    DEFAULT_WIDTH = 8
    BOLD_WIDTH = 16
    canvas_tag = CanvasTag.PATH

    def __init__(
        self,
        points: list[tuple[float, float]],
        caption_pos: Literal["left", "right", "up", "down", "center"] = "center",
        color: str = DEFAULT_PATH_COLOR,
        arrow: ArrowPosition | None = None,
    ):
        self.arrow = arrow
        self.points = points
        self.color = color
        self.caption_pos: Literal["left", "right", "up", "down", "center"] = caption_pos

    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[int, int],
        extra_params: dict[str, Any],
        caption: list[map.TextParams] | None,
    ):
        params = {
            "fill": self.color,
            "arrow": self.arrow,
        }
        params.update(extra_params)
        self._put_on_canvas(
            canvas=canvas,
            objects=[
                CanvasObjectInfo(
                    creation_function=canvas.create_line,
                    coords=self._get_coords(coords),
                    params=params,
                    caption=map.CaptionInfo(
                        contents=caption,
                        relative_pos=self.caption_pos,
                    ) if caption is not None else None,
                ),
            ],
        )

    def _get_coords(self, _coords: tuple[float, float]):
        coords: list[float] = []
        for point in self.points:
            coords.append(point[0] + _coords[0])
            coords.append(point[1] + _coords[1])
        return coords
    
@TagsRegistry.connect_to(map.MapTag.H_PATH)
class HorizontalPath(Connection):
    def __init__(self, arrow: ArrowPosition | None = None):
        center_y = HALF_TILE
        super().__init__(
            points=([
                (0, center_y),
                (TILE_SIZE, center_y),
            ]),
            arrow=arrow,
            caption_pos="up",
        )
    

@TagsRegistry.connect_to(map.MapTag.V_PATH)
class VerticalPath(Connection):
    def __init__(self, arrow: ArrowPosition | None = None):
        center_x = HALF_TILE
        super().__init__(
            points=([
                (center_x, 0),
                (center_x, TILE_SIZE),
            ]),
            arrow=arrow,
            caption_pos="right",
        )


class CrossedConnection(Connection):
    def __init__(
        self,
        points: list[tuple[float, float]],
        cross_points: list[tuple[float, float]],
        color: str = DEFAULT_PATH_COLOR,
        cross_color: str = "red",
        cross_width: float = 6,
        dash_style: tuple[int, ...] = (8, 4)
    ):
        super().__init__(points=points, color=color)
        self.cross_points = cross_points
        self.cross_color = cross_color
        self.cross_width = cross_width
        self.dash_style = dash_style

    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[int, int],
        extra_params: dict[str, Any],
        caption: list[map.TextParams] | None,
    ):
        if "fill" not in extra_params:
            extra_params["fill"] = self.color
        cross_params = {
            "fill": self.cross_color,
            "width": self.cross_width,
            "dash": self.dash_style,
        }
        self._put_on_canvas(
            canvas=canvas,
            objects=[
                CanvasObjectInfo(
                    creation_function=canvas.create_line,
                    coords=self._get_coords(coords),
                    params=extra_params,
                    caption=None,
                ),
                CanvasObjectInfo(
                    creation_function=canvas.create_line,
                    coords=self._get_cross_coords(coords),
                    params=cross_params,
                    caption=None,
                ),
            ],
        )

    def _get_cross_coords(self, _coords: tuple[float, float]):
        coords: list[float] = []
        for point in self.cross_points:
            coords.append(point[0] + _coords[0])
            coords.append(point[1] + _coords[1])
        return coords


@TagsRegistry.connect_to(map.MapTag.CROSSED_H_PATH)
class CrossedHorizontalPath(CrossedConnection):
    def __init__(self, cross_color: str = "red", cross_width: float = 6, dash_style: tuple[int, ...] = (8, 4)):
        center_y = HALF_TILE
        center_x = HALF_TILE
        super().__init__(
            points=([
                (0, center_y),
                (TILE_SIZE, center_y),
            ]),
            cross_points=([
                (center_x, 0),
                (center_x, TILE_SIZE),
            ]),
            cross_color=cross_color,
            cross_width=cross_width,
            dash_style=dash_style,
        )


@TagsRegistry.connect_to(map.MapTag.CROSSED_V_PATH)
class CrossedVerticalPath(CrossedConnection):
    def __init__(self, cross_color: str = "red", cross_width: float = 6, dash_style: tuple[int, ...] = (8, 4)):
        center_y = HALF_TILE
        center_x = HALF_TILE
        super().__init__(
            points=([
                (center_x, 0),
                (center_x, TILE_SIZE),
            ]),
            cross_points=([
                (0, center_y),
                (TILE_SIZE, center_y),
            ]),
            cross_color=cross_color,
            cross_width=cross_width,
            dash_style=dash_style,
        )
    

@TagsRegistry.connect_to(map.MapTag.DOWN_RIGHT)
class DownRightPath(Connection):
    def __init__(self):
        center_x = HALF_TILE
        center_y = HALF_TILE
        super().__init__(
            points=([
                (TILE_SIZE, center_y),
                (center_x, center_y),
                (center_x, TILE_SIZE),
            ]),
            caption_pos="up",
        )
    

@TagsRegistry.connect_to(map.MapTag.DOWN_LEFT)
class DownLeftPath(Connection):
    def __init__(self):
        center_x = HALF_TILE
        center_y = HALF_TILE
        super().__init__(
            points=([
                (0, center_y),
                (center_x, center_y),
                (center_x, TILE_SIZE),
            ]),
            caption_pos="right",
        )
    

@TagsRegistry.connect_to(map.MapTag.UP_RIGHT)
class UpRightPath(Connection):
    def __init__(self):
        center_x = HALF_TILE
        center_y = HALF_TILE
        super().__init__(
            points=([
                (center_x, 0),
                (center_x, center_y),
                (TILE_SIZE, center_y),
            ]),
            caption_pos="down",
        )
    

@TagsRegistry.connect_to(map.MapTag.UP_LEFT)
class UpLeftPath(Connection):
    def __init__(self):
        center_x = HALF_TILE
        center_y = HALF_TILE
        super().__init__(
            points=([
                (0, center_y),
                (center_x, center_y),
                (center_x, 0),
            ]),
            caption_pos="right",
        )
    

@TagsRegistry.connect_to(map.MapTag.V_LEFT)
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
            ]),
            caption_pos="right",
        )
    

@TagsRegistry.connect_to(map.MapTag.V_RIGHT)
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
            ]),
            caption_pos="left",
        )
    

@TagsRegistry.connect_to(map.MapTag.H_UP)
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
            ]),
            caption_pos="down",
        )
    

@TagsRegistry.connect_to(map.MapTag.H_DOWN)
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
            ]),
            caption_pos="up",
        )


@TagsRegistry.connect_to(map.MapTag.CROSS)
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


@TagsRegistry.connect_to(map.MapTag.GO_RIGHT, init_params={"arrow": ArrowPosition.END})
class RightArrow(HorizontalPath):
    pass
    

@TagsRegistry.connect_to(map.MapTag.GO_LEFT, init_params={"arrow": ArrowPosition.START})
class LeftArrow(HorizontalPath):
    pass


@TagsRegistry.connect_to(map.MapTag.GO_UP, init_params={"arrow": ArrowPosition.START})
class UpArrow(VerticalPath):
    pass


@TagsRegistry.connect_to(map.MapTag.GO_DOWN, init_params={"arrow": ArrowPosition.END})
class DownArrow(VerticalPath):
    pass


@TagsRegistry.connect_to(map.MapTag.BASE, init_params={"color": DEFAULT_BASE_COLOR})
class CircleBase(CanvasObject):
    def __init__(self, color: str):
        self.color = color

    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[int, int],
        extra_params: dict[str, Any],
        caption: list[map.TextParams] | None,
    ):
        topleft_x = coords[0]
        topleft_y = coords[1]
        bottomright_x = topleft_x + TILE_SIZE
        bottomright_y = topleft_y + TILE_SIZE
        if "fill" not in extra_params:
            extra_params["fill"] = self.color
        self._put_on_canvas(
            canvas=canvas,
            objects=[
                CanvasObjectInfo(
                    creation_function=canvas.create_oval,
                    coords=[
                        topleft_x,
                        topleft_y,
                        bottomright_x,
                        bottomright_y,
                    ],
                    params=extra_params,
                    caption=map.CaptionInfo(
                        contents=caption,
                        relative_pos="center",
                    ) if caption is not None else None,
                ),
            ],
        )


@TagsRegistry.connect_to(map.MapTag.RHOMB, init_params={"color": "#AA9853"})
class RhombBase(CanvasObject):
    SIZE = (1, 1)

    def __init__(self, color: str):
        self.color = color

    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[int, int],
        extra_params: dict[str, Any],
        caption: list[map.TextParams] | None,
    ):
        if "fill" not in extra_params:
            extra_params["fill"] = self.color
        self._put_on_canvas(
            canvas=canvas,
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
                    params=extra_params,
                    caption=map.CaptionInfo(
                        contents=caption,
                        relative_pos="center",
                    ) if caption is not None else None,
                ),
            ],
        )


@TagsRegistry.connect_to(map.MapTag.BIG_RHOMB, init_params={"color": "#AA9853"})
class BigRhombBase(RhombBase):
    SIZE = (2, 3)


@TagsRegistry.connect_to(map.MapTag.SQUARE, init_params={"color": DEFAULT_BASE_COLOR})
class SquareBase(CanvasObject):
    def __init__(self, color: str, prefix: str = "K"):
        self.prefix = prefix
        self.color = color

    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[int, int],
        extra_params: dict[str, Any],
        caption: list[map.TextParams] | None,
    ):
        if "fill" not in extra_params:
            extra_params["fill"] = self.color
        self._put_on_canvas(
            canvas=canvas,
            objects=[
                CanvasObjectInfo(
                    creation_function=canvas.create_rectangle,
                    coords=[
                        coords[0],
                        coords[1],
                        coords[0] + TILE_SIZE,
                        coords[1] + TILE_SIZE,
                    ],
                    params=extra_params,
                    caption=map.CaptionInfo(
                        contents=caption,
                        relative_pos="center",
                    ) if caption is not None else None,
                ),
            ],
        )


class BigSquaredCircleBase(CanvasObject):
    TILE_SIZE = 3 * TILE_SIZE
    CIRCLE_OFFSET = 4
    CORNER_SIZE = 2

    def __init__(self, square_color: str, circle_color: str):
        self.square_color = square_color
        self.circle_color = circle_color
    
    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[int, int],
        extra_params: dict[str, Any],
        caption: list[map.TextParams] | None,
    ):
        square_params = {
            "fill": self.square_color,
            "outline": "black",
            "smooth": True,
            "splinesteps": 24,
        }
        circle_params = {"fill": self.circle_color}
        square_params.update(extra_params)
        circle_params.update(extra_params)
        if caption is not None:
            for part in caption:
                if "font" not in part.extra_params:
                    part.extra_params["font"] = Font(weight="bold")
        self._put_on_canvas(
            canvas=canvas,
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
                    caption=None,
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
                    caption=map.CaptionInfo(
                        contents=caption,
                        relative_pos="center",
                    ) if caption is not None else None,
                ),
            ],
        )


@TagsRegistry.connect_to(map.MapTag.START, init_params={"square_color": "#BEBE4C", "circle_color": "#FFFF66"})
class StartBase(BigSquaredCircleBase):
    pass


@TagsRegistry.connect_to(map.MapTag.FINISH, init_params={"square_color": "#B62323", "circle_color": "#FF3333"})
class FinishBase(BigSquaredCircleBase):
    pass


@TagsRegistry.connect_to(map.MapTag.STAR)
class StarBase(CanvasObject):
    def __init__(
        self,
        p: int = 5,
        q: int = 2,
        color: str = "#FFF134",
        size: int = 3,
    ):
        self.color = color
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
        extra_params: dict[str, Any],
        caption: list[map.TextParams] | None,
    ):
        params = {
            "fill": self.color,
            "outline": "black",
            "smooth": True,
            "splinesteps": 24,
        }
        params.update(extra_params)
        if caption is not None:
            for part in caption:
                if "font" not in part.extra_params:
                    part.extra_params["font"] = Font(weight="bold")
        self._put_on_canvas(
            canvas=canvas,
            objects=[
                CanvasObjectInfo(
                    creation_function=canvas.create_polygon,
                    coords=self._get_coords(coords),
                    params=params,
                    caption=map.CaptionInfo(
                        contents=caption,
                        relative_pos="center",
                    ) if caption is not None else None,
                ),
            ],
        )


class Image(CanvasObject):
    def __init__(self, path: str, mirror_x=False, mirror_y=False, rotate=False):
        self.image_path = os.path.join(SPRITES_PATH, path)
        self.mirror_x=mirror_x
        self.mirror_y=mirror_y
        self.rotate=rotate
        self._set_image()

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
        extra_params: dict[str, Any],
        caption: list[map.TextParams] | None,
    ):
        params = {
            "image": self.image,
            "anchor": "nw",
        }
        params.update(extra_params)
        self._put_on_canvas(
            canvas=canvas,
            objects=[
                CanvasObjectInfo(
                    creation_function=canvas.create_image,
                    coords=coords,  # type: ignore
                    params=extra_params,
                    caption=map.CaptionInfo(
                        contents=caption,
                        relative_pos="center",
                    ) if caption is not None else None,
                )
            ],
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

def sort_canvas_objects(canvas: tk.Canvas):
    canvas.tag_raise(CanvasTag.PATH)
    canvas.tag_raise(CanvasTag.BASE)
    canvas.tag_raise(CanvasTag.TEXT_BACKGROUND)
    canvas.tag_raise(CanvasTag.TEXT)

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

    sort_canvas_objects(canvas.widget)

    root.mainloop()