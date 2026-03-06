import os


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
INITIAL_MAP_NAME = "Initial map"

CHARACTER_SPRITE_PATH = os.path.join(SPRITES_PATH, "character.png")
print(CHARACTER_SPRITE_PATH)