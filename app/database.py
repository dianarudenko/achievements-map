from dataclasses import asdict, dataclass
import json
from typing import Literal

# import mysql.connector
# from mysql.connector.pooling import PooledMySQLConnection
# from mysql.connector.abstracts import MySQLConnectionAbstract
# from mysql.connector.cursor import MySQLCursorDict
import sqlite3

from app.constants import INITIAL_MAP_NAME

from .map import MapObjectInfo, MapState, MapTag, TextParams, initial_map

DB_NAME = "achievements_map_db"
DB_HOST="localhost"
DB_USER="user"
DB_PASSWORD="password"

MAP_TABLE_NAME = "map"
MAP_ITEM_TABLE_NAME = "map_item"


@dataclass
class DataBase:
    connection: sqlite3.Connection
    cursor: sqlite3.Cursor


class InitialMapError(Exception):
    def __init__(self):
        super().__init__("Bad initial map!")

class MapNotFoundError(Exception):
    def __init__(self, map_id: int):
        super().__init__(f"Map {map_id} doesn't exist!")


def create_map_table(db: DataBase):
    db.cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MAP_TABLE_NAME} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            width INTEGER CHECK(width > 0) NOT NULL,
            height INTEGER CHECK(height > 0) NOT NULL,
            initialized INTEGER CHECK(initialized IN (0, 1)) NOT NULL DEFAULT 0
        )
        """
    )

def add_map(db: DataBase, name: str, width: int, height: int) -> int:
    db.cursor.execute(
        f"INSERT INTO {MAP_TABLE_NAME} (name, width, height) VALUES (?, ?, ?)",
        (name, width, height),
    )
    db.connection.commit()
    map_id: int = db.cursor.lastrowid  # type: ignore
    db.cursor.close()
    return map_id

def create_map_item_table(db: DataBase):
    db.cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MAP_ITEM_TABLE_NAME} (
            row INTEGER CHECK(row >= 0) NOT NULL,
            column INTEGER CHECK(column >= 0) NOT NULL,
            map INTEGER REFERENCES {MAP_TABLE_NAME} ON DELETE CASCADE NOT NULL,
            tag TEXT CHECK(tag IN ({",".join('"' + v.value + '"' for v in MapTag)})) NOT NULL,
            state TEXT CHECK(state IN ({",".join('"' + v.value + '"' for v in MapState)})) NOT NULL,
            bold INTEGER CHECK(bold IN (0, 1)) NOT NULL DEFAULT 0,
            color TEXT NULL,
            extra_params TEXT NULL,
            caption TEXT NULL,
            PRIMARY KEY (row, column)
        )
        """
    )

def drop_map_item_table(db: DataBase):
    db.cursor.execute(f"DROP TABLE IF EXISTS {MAP_ITEM_TABLE_NAME}")

def recreate_map_item_table(db: DataBase):
    drop_map_item_table(db)
    create_map_item_table(db)

def fill_map_item_table(db: DataBase, map_id: int):
    sql = f"""
        INSERT INTO {MAP_ITEM_TABLE_NAME}
        (row, column, map, tag, state, bold, color, extra_params, caption) VALUES
        (?  , ?     , ?  , ?  , ?    , ?   , ?    , ?           , ?      )
    """
    values: list[
        tuple[int, int, int, MapTag, MapState, Literal[0, 1], str | None, str | None, str | None]
    ] = []
    for i, row in enumerate(initial_map):
        for j, cell in enumerate(row):
            if cell:
                values.append((
                    i,
                    j,
                    map_id,
                    cell.tag,
                    cell.state,
                    1 if cell.bold else 0,
                    cell.color,
                    json.dumps(cell.extra_params) if cell.extra_params else None,
                    json.dumps([asdict(t) for t in cell.caption]) if cell.caption else None,
                ))

    db.cursor.executemany(sql, values)
    db.cursor.execute(f"UPDATE {MAP_TABLE_NAME} SET initialized = 0 WHERE id = {map_id}")
    db.connection.commit()

def get_map(db: DataBase, map_id: int) -> list[tuple[int, int, MapObjectInfo]]:
    result: list[tuple[int, int, MapObjectInfo]] = []
    db.cursor.execute(f"SELECT * FROM {MAP_TABLE_NAME} WHERE id = {map_id}")
    if db.cursor.rowcount == 0:
        raise MapNotFoundError(map_id=map_id)
    db.cursor.execute(f"SELECT * FROM {MAP_ITEM_TABLE_NAME} WHERE map = {map_id}")
    row_dict: dict
    for row_dict in db.cursor.fetchall():
        row = row_dict["row"]
        column = row_dict["column"]
        extra_params = row_dict["extra_params"]
        caption = row_dict["caption"]
        obj_info = MapObjectInfo(
            tag=MapTag(row_dict["tag"]),
            state=MapState(row_dict["state"]),
            bold=bool(row_dict["bold"]),
            color=row_dict["color"],
            extra_params=json.loads(extra_params) if extra_params is not None else {},
            caption=[TextParams(**t) for t in json.loads(caption)] if caption is not None else None,
        )
        result.append((row, column, obj_info))
    return result

def db_connect() -> DataBase:
    db_connection = sqlite3.connect(DB_NAME)
    db_cursor = db_connection.cursor()
    db_cursor.row_factory = sqlite3.Row
    return DataBase(
        connection=db_connection,
        cursor=db_cursor,
    )

def init_db(db: DataBase) -> int:
    create_map_table(db)
    # create_map_item_table(db)
    recreate_map_item_table(db)
    map_id: int
    db.cursor.execute(f"SELECT id, initialized from {MAP_TABLE_NAME} WHERE name = '{INITIAL_MAP_NAME}'")
    result = db.cursor.fetchone()
    if result is None:
        height = len(initial_map)
        if height > 0:
            width = len(initial_map[1])
            if width > 0:
                map_id = add_map(db, name=INITIAL_MAP_NAME, width=width, height=height)
                fill_map_item_table(db, map_id)
            else:
                raise InitialMapError
        else:
            raise InitialMapError
    else:
        map_id, initialized = result
        if not initialized:
            fill_map_item_table(db, map_id)
    return map_id

def db_disconnect(db: DataBase):
    db.cursor.close()
    db.connection.close()
