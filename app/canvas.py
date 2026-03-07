from abc import abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import math
import os
from typing import Any, Callable, Literal, Type
import tkinter as tk
from tkinter.font import Font

from app.constants import (
    DEFAULT_BASE_COLOR,
    DEFAULT_PATH_COLOR,
    HALF_TILE,
    SPRITES_PATH,
    TILE_SIZE,
    CHARACTER_SPRITE_PATH
)
from app import database
from app.widget import ScrollableCanvas

from .map import CaptionInfo, MapObjectInfo, MapState, MapTag, TextParams


class ArrowPosition(str, Enum):
    START = "first"
    END = "last"
    BOTH = "both"

class CanvasTag(str, Enum):
    BACKGROUND = "background"
    TEXT_BACKGROUND = "text_background"
    TEXT = "text"
    BASE = "base"
    PATH = "path"
    CHARACTER = "character"
    BASE_HITBOX = "base_hitbox"
    POPUP = "popup"


@dataclass
class CanvasObjectInfo:
    creation_function: Callable
    coords: list[float]
    params: dict[str, Any]
    caption: CaptionInfo | None


@dataclass
class CanvasMeta:
    canvas: tk.Canvas
    width: float
    height: float
    background_hitbox_id: int
    background_hitbox_width: float
    background_hitbox_height: float
    map_id: int
    db: database.DataBase
    clickable_bases: dict[int, tuple[float, float, float, float]] = field(default_factory=dict)
    chosen_base: int | None = None
    character_id: int | None = None

current_canvas: CanvasMeta


def get_base_actions_frame(canvas: tk.Canvas) -> tk.Frame:
    frame = tk.Frame(canvas)
    description_area = tk.Text(frame, width=25, height=10)
    description_area.grid(row=0, column=0, columnspan=2)
    description_button = tk.Button(frame, text="Редактировать")
    description_button.grid(row=1, column=0)
    go_button = tk.Button(frame, text="Перейти")
    go_button.grid(row=1, column=1)
    go_button.bind("<Button-1>", CanvasObject.move_character)
    return frame


class CanvasObject:
    DEFAULT_WIDTH = 2
    BOLD_WIDTH = 3
    canvas_tag = CanvasTag.BASE
    character_obj: tk.PhotoImage | None = None

    def _put_on_canvas(
        self,
        canvas: tk.Canvas,
        objects: list[CanvasObjectInfo],
        add_hitbox: bool = True,
    ):
        created_objects: list[int] = []
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
            created_objects.append(item_id)
            if item.caption is not None:
                top_left_x, top_left_y, bottom_right_x, bottom_right_y = canvas.bbox(item_id)
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
        if add_hitbox:
            hitbox = canvas.bbox(*created_objects)
            hitbox_id = canvas.create_rectangle(
                hitbox,
                outline="",
                tags=CanvasTag.BASE_HITBOX,
            )
            current_canvas.clickable_bases[hitbox_id] = hitbox
    
    @classmethod
    def put_character(
        cls,
        canvas: tk.Canvas,
        coords: tuple[float, float, float, float],
    ):
        if cls.character_obj is None:
            cls.character_obj = tk.PhotoImage(file=CHARACTER_SPRITE_PATH)
        center_x = (coords[0] + coords[2]) / 2
        center_y = (coords[1] + coords[3]) / 2
        current_canvas.character_id = canvas.create_image(
            center_x,
            center_y,
            image=cls.character_obj,
            anchor=tk.CENTER,
            tags=CanvasTag.CHARACTER,
        )

    @abstractmethod
    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[int, int],
        extra_params: dict[str, Any],
        caption: list[TextParams] | None,
        state: MapState,
    ):
        pass

    @classmethod
    def handle_base_click(cls, event: tk.Event):
        canvas: tk.Canvas = event.widget  # type: ignore
        canvas.delete(CanvasTag.POPUP)
        canvas_x = canvas.canvasx(event.x)
        canvas_y = canvas.canvasy(event.y)
        base_hitbox_id: int = canvas.find_closest(canvas_x, canvas_y)[0]
        current_canvas.chosen_base = base_hitbox_id
        canvas.create_window(
            canvas_x,
            canvas_y,
            anchor=tk.N,
            window=get_base_actions_frame(canvas),
            tags=CanvasTag.POPUP,
        )

    @classmethod
    def handle_outside_click(cls, event: tk.Event):
        canvas: tk.Canvas = event.widget  # type: ignore
        canvas.delete(CanvasTag.POPUP)
        current_canvas.chosen_base = None

    @classmethod
    def handle_resizing(cls, event: tk.Event):
        canvas: tk.Canvas = event.widget  # type: ignore
        new_width = max(event.width, current_canvas.width)
        new_height = max(event.height, current_canvas.height)
        x_scale = new_width / current_canvas.background_hitbox_width
        y_scale = new_height / current_canvas.background_hitbox_height
        current_canvas.background_hitbox_width = new_width
        current_canvas.background_hitbox_height = new_height
        canvas.scale(current_canvas.background_hitbox_id, 0, 0, x_scale, y_scale)

    @classmethod
    def move_character(
        cls,
        event: tk.Event,
    ):
        canvas: tk.Canvas = current_canvas.canvas
        if current_canvas.chosen_base is not None:
            canvas.delete(CanvasTag.CHARACTER)
            base_coords = current_canvas.clickable_bases[current_canvas.chosen_base]
            cls.put_character(canvas, base_coords)
            column = int((base_coords[0] + HALF_TILE) // TILE_SIZE)
            row = int((base_coords[1] + HALF_TILE) // TILE_SIZE)
            database.move_character(
                db=current_canvas.db,
                map_id=current_canvas.map_id,
                row=row,
                column=column,
            )
            canvas.delete(CanvasTag.POPUP)


class TagsRegistry:
    @dataclass
    class ObjectInfo:
        cls: Type[CanvasObject]
        init_params: dict[str, Any]
        object: CanvasObject | None = None
    
    default_tag = MapTag.BASE
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
    def parse_cell_and_put_on_canvas(
        cls,
        canvas: tk.Canvas,
        row: int,
        column: int, 
        cell: Literal[""] | None | MapObjectInfo,
    ):
        if cell:
            topleft_x = TILE_SIZE * column
            topleft_y = TILE_SIZE * row
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
                    canvas=canvas,
                    coords=(topleft_x, topleft_y),
                    extra_params=object_params,
                    caption=cell.caption,
                    state=cell.state,
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
        caption: list[TextParams] | None,
        state: MapState,
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
                    caption=CaptionInfo(
                        contents=caption,
                        relative_pos=self.caption_pos,
                    ) if caption is not None else None,
                ),
            ],
            add_hitbox=False,
        )

    def _get_coords(self, _coords: tuple[float, float]):
        coords: list[float] = []
        for point in self.points:
            coords.append(point[0] + _coords[0])
            coords.append(point[1] + _coords[1])
        return coords
    
@TagsRegistry.connect_to(MapTag.H_PATH)
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
    

@TagsRegistry.connect_to(MapTag.V_PATH)
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
        caption: list[TextParams] | None,
        state: MapState,
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
            add_hitbox=False,
        )

    def _get_cross_coords(self, _coords: tuple[float, float]):
        coords: list[float] = []
        for point in self.cross_points:
            coords.append(point[0] + _coords[0])
            coords.append(point[1] + _coords[1])
        return coords


@TagsRegistry.connect_to(MapTag.CROSSED_H_PATH)
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


@TagsRegistry.connect_to(MapTag.CROSSED_V_PATH)
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
    

@TagsRegistry.connect_to(MapTag.DOWN_RIGHT)
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
    

@TagsRegistry.connect_to(MapTag.DOWN_LEFT)
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
    

@TagsRegistry.connect_to(MapTag.UP_RIGHT)
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
    

@TagsRegistry.connect_to(MapTag.UP_LEFT)
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
    

@TagsRegistry.connect_to(MapTag.V_LEFT)
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
    

@TagsRegistry.connect_to(MapTag.V_RIGHT)
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
    

@TagsRegistry.connect_to(MapTag.H_UP)
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
    

@TagsRegistry.connect_to(MapTag.H_DOWN)
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


@TagsRegistry.connect_to(MapTag.CROSS)
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


@TagsRegistry.connect_to(MapTag.GO_RIGHT, init_params={"arrow": ArrowPosition.END})
class RightArrow(HorizontalPath):
    pass
    

@TagsRegistry.connect_to(MapTag.GO_LEFT, init_params={"arrow": ArrowPosition.START})
class LeftArrow(HorizontalPath):
    pass


@TagsRegistry.connect_to(MapTag.GO_UP, init_params={"arrow": ArrowPosition.START})
class UpArrow(VerticalPath):
    pass


@TagsRegistry.connect_to(MapTag.GO_DOWN, init_params={"arrow": ArrowPosition.END})
class DownArrow(VerticalPath):
    pass


@TagsRegistry.connect_to(MapTag.BASE, init_params={"color": DEFAULT_BASE_COLOR})
class CircleBase(CanvasObject):
    def __init__(self, color: str):
        self.color = color

    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[float, float],
        extra_params: dict[str, Any],
        caption: list[TextParams] | None,
        state: MapState,
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
                    caption=CaptionInfo(
                        contents=caption,
                        relative_pos="center",
                    ) if caption is not None else None,
                ),
            ],
        )
        if state == MapState.CURRENT:
            self.put_character(
                canvas=canvas,
                coords=(topleft_x, topleft_y, bottomright_x, bottomright_y),
            )


@TagsRegistry.connect_to(MapTag.RHOMB, init_params={"color": "#AA9853"})
class RhombBase(CanvasObject):
    SIZE = (1, 1)

    def __init__(self, color: str):
        self.color = color

    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[float, float],
        extra_params: dict[str, Any],
        caption: list[TextParams] | None,
        state: MapState,
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
                    caption=CaptionInfo(
                        contents=caption,
                        relative_pos="center",
                    ) if caption is not None else None,
                ),
            ],
        )
        if state == MapState.CURRENT:
            self.put_character(
                canvas=canvas,
                coords=(
                    coords[0],
                    coords[1],
                    coords[0] + self.SIZE[0] * TILE_SIZE,
                    coords[1] + self.SIZE[1] * TILE_SIZE,
                ),
            )


@TagsRegistry.connect_to(MapTag.BIG_RHOMB, init_params={"color": "#AA9853"})
class BigRhombBase(RhombBase):
    SIZE = (2, 3)


@TagsRegistry.connect_to(MapTag.SQUARE, init_params={"color": DEFAULT_BASE_COLOR})
class SquareBase(CanvasObject):
    def __init__(self, color: str, prefix: str = "K"):
        self.prefix = prefix
        self.color = color

    def put_on_canvas(
        self,
        canvas: tk.Canvas,
        coords: tuple[int, int],
        extra_params: dict[str, Any],
        caption: list[TextParams] | None,
        state: MapState,
    ):
        if "fill" not in extra_params:
            extra_params["fill"] = self.color
        if caption is not None:
            if len(caption) > 0:
                caption[0].text = self.prefix + caption[0].text
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
                    caption=CaptionInfo(
                        contents=caption,
                        relative_pos="center",
                    ) if caption is not None else None,
                ),
            ],
        )
        if state == MapState.CURRENT:
            self.put_character(
                canvas=canvas,
                coords=(
                    coords[0],
                    coords[1],
                    coords[0] + TILE_SIZE,
                    coords[1] + TILE_SIZE,
                ),
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
        caption: list[TextParams] | None,
        state: MapState,
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
                    caption=CaptionInfo(
                        contents=caption,
                        relative_pos="center",
                    ) if caption is not None else None,
                ),
            ],
        )
        if state == MapState.CURRENT:
            self.put_character(
                canvas=canvas,
                coords=(
                    coords[0],
                    coords[1],
                    coords[0] + self.TILE_SIZE,
                    coords[1] + self.TILE_SIZE,
                ),
            )


@TagsRegistry.connect_to(MapTag.START, init_params={"square_color": "#BEBE4C", "circle_color": "#FFFF66"})
class StartBase(BigSquaredCircleBase):
    pass


@TagsRegistry.connect_to(MapTag.FINISH, init_params={"square_color": "#B62323", "circle_color": "#FF3333"})
class FinishBase(BigSquaredCircleBase):
    pass


@TagsRegistry.connect_to(MapTag.STAR)
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
        caption: list[TextParams] | None,
        state: MapState,
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
                    caption=CaptionInfo(
                        contents=caption,
                        relative_pos="center",
                    ) if caption is not None else None,
                ),
            ],
        )
        if state == MapState.CURRENT:
            self.put_character(
                canvas=canvas,
                coords=(
                    coords[0],
                    coords[1],
                    coords[0] + self.star_size,
                    coords[1] + self.star_size,
                ),
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
        caption: list[TextParams] | None,
        state: MapState,
    ):
        params = {
            "image": self.image,
            "anchor": "nw",
        }
        # params.update(extra_params)
        self._put_on_canvas(
            canvas=canvas,
            objects=[
                CanvasObjectInfo(
                    creation_function=canvas.create_image,
                    coords=coords,  # type: ignore
                    params=params,
                    caption=CaptionInfo(
                        contents=caption,
                        relative_pos="center",
                    ) if caption is not None else None,
                )
            ],
        )
        if state == MapState.CURRENT:
            self.put_character(
                canvas=canvas,
                coords=(
                    coords[0],
                    coords[1],
                    coords[0] + TILE_SIZE,
                    coords[1] + TILE_SIZE,
                ),
            )


def setup_canvas(db: database.DataBase, map_id: int, canvas: ScrollableCanvas):
    # add canvas background hitbox
    global current_canvas
    canvas_width = canvas.scrollregion[2]
    canvas_height = canvas.scrollregion[3]
    canvas_background_id = canvas.widget.create_rectangle(
        canvas.scrollregion,
        outline="",
        tags=CanvasTag.BACKGROUND,
    )
    current_canvas = CanvasMeta(
        canvas=canvas.widget,
        width=canvas_width,
        height=canvas_height,
        background_hitbox_id=canvas_background_id,
        background_hitbox_width=canvas_width,
        background_hitbox_height=canvas_height,
        db=db,
        map_id=map_id,
    )


def configure_canvas(canvas: tk.Canvas):
    # order canvas objects
    canvas.tag_raise(CanvasTag.PATH)
    canvas.tag_raise(CanvasTag.BASE)
    canvas.tag_raise(CanvasTag.TEXT_BACKGROUND)
    canvas.tag_raise(CanvasTag.TEXT)
    canvas.tag_raise(CanvasTag.CHARACTER)
    canvas.tag_raise(CanvasTag.BACKGROUND)
    canvas.tag_raise(CanvasTag.BASE_HITBOX)

    # add events associated with clicks on bases
    canvas.tag_bind(CanvasTag.BASE_HITBOX, "<Button-1>", CanvasObject.handle_base_click)
    canvas.tag_bind(CanvasTag.BASE_HITBOX, "<Button-1>", CanvasObject.handle_base_click)
    canvas.tag_bind(CanvasTag.BACKGROUND, "<Button-1>", CanvasObject.handle_outside_click)

    # resize canvas background on windows resizing
    canvas.bind("<Configure>", CanvasObject.handle_resizing, add="+")


def draw_map(db: database.DataBase, map_id: int, canvas: ScrollableCanvas):
    setup_canvas(db, map_id, canvas)
    for row, column, cell in database.get_map(db, map_id):
        TagsRegistry.parse_cell_and_put_on_canvas(canvas.widget, row, column, cell)
    configure_canvas(canvas.widget)