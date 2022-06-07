import enum
import functools
from glob import glob
from msilib.schema import Font
import pygame
import sys
from pygame.locals import *
from typing import Set, List, Tuple
import random

__frame_coroutines = []


def game_frame_coroutine(func):
    global __frame_coroutines

    def wrapper(*args, **kwargs):
        cr = func(*args, **kwargs)
        __frame_coroutines.append(cr)
    return wrapper


def on_frame_routines():
    global __frame_coroutines
    crs = __frame_coroutines
    cp = []
    for cr in crs:
        try:
            ret = next(cr)
            if ret:
                cr.send(0)
                cp.append(cr)
        except:
            pass
    __frame_coroutines = cp


'''
Game Configuration
'''


class GameConst:
    OUTER_SHELL_LEN: int = 18
    ROOM_LEN: int = 40
    FPS: int = 60
    SCREEN_X = 1024
    SCREEN_Y = 768
    GAME_TITLE = 'Cube 2D'

    GAME_BG_COLOR = (255, 255, 255)

    ROOM_COLOR = (230, 50, 100)
    STATIONARY_ROOM_COLOR = (50, 255, 20)
    ROOM_SELECTED_STYLE = (255, 255, 0)

    # derived constants
    INNER_SHELL_LEN: int = OUTER_SHELL_LEN - 2
    MAX_ROOM_NUM: int = INNER_SHELL_LEN * INNER_SHELL_LEN


'''
Game Class
'''


class TextRender:
    def __init__(self, surface: pygame.Surface):
        self.surface: pygame.Surface = surface

    def draw_multi_line_text(self, text: str, topleft, color: Tuple[int, int, int], font: pygame.font.Font, aa=False):
        lines = text.split('\n')
        fontHeight = font.size("Tg")[1]

        for idx, line in enumerate(lines):
            font_img = font.render(line, aa, color)
            rect = font_img.get_rect()
            rect.topleft = (topleft[0], topleft[1] + idx * fontHeight)
            self.surface.blit(font_img, rect)

    def draw_wrap_text(self, text: str, color: Tuple[int, int, int], rect: Rect, font: Font, aa=False, bkg=None):
        rect = Rect(rect)
        y = rect.top
        lineSpacing = -2
        # get the height of the font
        fontHeight = font.size("Tg")[1]
        while text:
            i = 1
            # determine if the row of text will be outside our area
            if y + fontHeight > rect.bottom:
                break
            # determine maximum width of line
            while font.size(text[:i])[0] < rect.width and i < len(text):
                i += 1
            # if we've wrapped the text, then adjust the wrap to the last word
            if i < len(text):
                i = text.rfind(" ", 0, i) + 1
            # render the line and blit it to the surface
            if bkg:
                image = font.render(text[:i], 1, color, bkg)
                image.set_colorkey(bkg)
            else:
                image = font.render(text[:i], aa, color)
            self.surface.blit(image, (rect.left, y))
            y += fontHeight + lineSpacing
            # remove the text we just blitted
            text = text[i:]
        return text


class Vec2:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y

    def add(self, other):
        return Vec2(self.x + other.x, self.y + other.y)

    def sub(self, other):
        return Vec2(self.x - other.x, self.y - other.y)

    def __add__(self, other):
        return self.add(other)

    def __sub__(self, other):
        return self.sub(other)

    def __str__(self):
        return "[{}, {}]".format(self.x, self.y)


class Room(pygame.sprite.Sprite):
    def __init__(self, original_location: Vec2):
        super(Room, self).__init__()
        self._original_position = original_location
        self._pos = original_location
        self._ident: Tuple[int, int] = (0, 0)
        self._action = []
        self._seq = 0
        self._init_room_meta()
        self._statinary = False
        self._fmt = 'Original Location: {}\nCurrent Location: {}\nIdentifier: {}\nCycle Seq: {}'

        self.rect = Rect(0, 0, 0, 0)
        self.color = (230, 50, 100)
        self.selected = False

        self._update_rect()

    def _update_rect(self):
        pos = self.pos
        len = GameConst.ROOM_LEN
        x, y = pos.x * len, pos.y * len
        self.rect = Rect(x, y, len, len)

    def _init_room_meta(self):
        x, y = self._original_position.x, self._original_position.y
        cx = random.randrange(0, x) if x > 0 else 0
        cy = random.randrange(0, y) if y > 0 else 0
        self._ident = ((cx, x - cx), (cy, y - cy))
        self._action = [Vec2(0, 0), Vec2(2*cx - x, 0),
                        Vec2(2*cx - x, 2 * cy - y), Vec2(0, 2*cy-y)]

    def __hash__(self):
        return self._original_position.y * GameConst.INNER_SHELL_LEN + self._original_position.x

    def __str__(self):
        return self._fmt.format(str(self._original_position), str(self.pos), self._ident, self.seq)

    def _is_out_of_bound(self, pos: Vec2):

        def in_bound(pos):
            if pos.x >= 1 and pos.y >= 1 \
                    and pos.x < GameConst.INNER_SHELL_LEN \
                    and pos.y < GameConst.INNER_SHELL_LEN:
                return True
            return False
        for i in range(4):
            if not in_bound(self._original_position + self._action[i]):
                return True
        return False

    @game_frame_coroutine
    def advance(self):
        cur_pos = self.pos
        LEN = GameConst.ROOM_LEN
        cx, cy = cur_pos.x * LEN, cur_pos.y * LEN
        next_seq = (self.seq + 1) % 4
        self.seq = next_seq    # advanced here

        next_pos = self.pos
        nx, ny = next_pos.x * LEN, next_pos.y * LEN

        def lerp(a: float, b: float, f: float):
            return a * (1.0 - f) + b * f

        c = 0
        frames = 120
        while True:
            if c == frames:
                self.rect = Rect(nx, ny, LEN, LEN)
                break
            f = c / float(frames)
            f = f * f
            x, y = lerp(float(cx), float(nx), f), lerp(float(cy), float(ny), f)
            self.rect = Rect(x, y, LEN, LEN)
            c += 1
            yield True

    @property
    def statinary(self):
        return self._statinary

    @statinary.setter
    def statinary(self, val):
        self._statinary = val
        if not val:
            self.color = GameConst.ROOM_COLOR
        else:
            self.color = GameConst.STATIONARY_ROOM_COLOR

    @property
    def ident(self):
        return self._ident

    @property
    def seq(self):
        return self._seq

    @seq.setter
    def seq(self, val):
        self._seq = val

    @property
    def pos(self):
        return self._pos + self._action[self.seq]


'''
Game Routine
'''


def draw_text(surface):
    text = font18.render(GameConst.GAME_TITLE, True, (0, 0, 0))
    rect = text.get_rect()
    rect.center = (GameConst.OUTER_SHELL_LEN * GameConst.ROOM_LEN + 150, 40)
    surface.blit(text, rect)

    text = font12.render(global_info, True, (0, 0, 0))
    rect = text.get_rect()
    rect.center = (GameConst.OUTER_SHELL_LEN * GameConst.ROOM_LEN + 150, 60)
    surface.blit(text, rect)

    text = font12.render("Press 'N' to apply a movement", True, (255, 100, 0))
    rect = text.get_rect()
    rect.center = (GameConst.OUTER_SHELL_LEN * GameConst.ROOM_LEN + 150, 80)
    surface.blit(text, rect)

    text = font12.render("Click on a cube to select and inspect", True, (255, 100, 0))
    rect = text.get_rect()
    rect.center = (GameConst.OUTER_SHELL_LEN * GameConst.ROOM_LEN + 150, 100)
    surface.blit(text, rect)

    rect = Rect((GameConst.OUTER_SHELL_LEN *
                GameConst.ROOM_LEN + 50, 80, 250, 400))
    TextRenderer.draw_multi_line_text(
        str(selected_room), (GameConst.OUTER_SHELL_LEN * GameConst.ROOM_LEN + 50, 120), (0, 0, 0), font12, True)


def on_mouse_button_down(mouse_pos):
    for room in room_list:
        if room.rect.collidepoint(mouse_pos[0], mouse_pos[1]):
            on_room_click(room)


def on_mouse_move(mouse_pos):
    pass


def on_room_click(room):
    global room_info
    global selected_room
    room_info = str(room)
    if selected_room:
        selected_room.selected = False
    selected_room = room
    room.selected = True


def init_room_list(count) -> List[Room]:
    room_list: Set[Room] = set()
    len = GameConst.INNER_SHELL_LEN
    shuffle = [x for x in range(len * len)]
    random.shuffle(shuffle)
    for idx in shuffle[:count]:
        x, y = idx % len + 1, int(idx / len) + 1
        pos = Vec2(x, y)
        room = Room(pos)
        retry_count = 0
        while room._is_out_of_bound(room.pos) and retry_count < 1000:
            retry_count += 1
            room = Room(pos)
        if retry_count >= 1000 and room._is_out_of_bound(room.pos):
            room.statinary = True
        room_list.add(room)
    return room_list


def draw_room(surface):
    room_len = GameConst.ROOM_LEN
    for room in room_list:
        x, y = room.pos.x, room.pos.y
        pygame.draw.rect(surface, room.color, room.rect, border_radius=4)
        if room.selected:
            pygame.draw.rect(surface, GameConst.ROOM_SELECTED_STYLE,
                             room.rect, width=2, border_radius=4)


def draw_shell(surface):
    len = GameConst.OUTER_SHELL_LEN + 1
    shell_len = GameConst.ROOM_LEN * GameConst.OUTER_SHELL_LEN
    for i in range(len):
        r = i * GameConst.ROOM_LEN
        pygame.draw.line(surface, (50, 100, 230), (0, r), (shell_len, r), 3)
        pygame.draw.line(surface, (50, 100, 230), (r, 0), (r, shell_len), 3)


def random_movement(count=0):
    rooms = list(filter(lambda r: not r.statinary, room_list))
    count = min(len(rooms), count)
    if count > 0:
        random.shuffle(rooms)
        for room in rooms[:count]:
            room.advance()
    else:
        for room in rooms:
            room.advance()


'''
Game State Objects
'''


pygame.init()
pygame.display.set_caption("Cube 2D")

font18 = pygame.font.Font('Dinosaur.ttf', 18)
font12 = pygame.font.Font('Dinosaur.ttf', 12)
FramePerSec = pygame.time.Clock()

# game event
ROOM_MOVE_EVENT = pygame.USEREVENT + 0
pygame.time.set_timer(ROOM_MOVE_EVENT, 1000)


DISPLAYSURF = pygame.display.set_mode((GameConst.SCREEN_X, GameConst.SCREEN_Y))
DISPLAYSURF.fill(GameConst.GAME_BG_COLOR)

TextRenderer = TextRender(DISPLAYSURF)

room_list = init_room_list(16*16)
grid_dfs = []
global_info = '{} x {} Rooms'.format(
    GameConst.INNER_SHELL_LEN, GameConst.INNER_SHELL_LEN)
room_info = ''
selected_room = None

'''
Game Loop
'''
while True:
    for event in pygame.event.get():
        if event.type == QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == ROOM_MOVE_EVENT:
            pass
            # random_movement()
        elif event.type == pygame.MOUSEBUTTONDOWN:
            pos = pygame.mouse.get_pos()
            on_mouse_button_down(pos)
        elif event.type == pygame.MOUSEMOTION:
            pos = pygame.mouse.get_pos()
            on_mouse_move(pos)
        elif event.type == pygame.KEYDOWN:
            if pygame.key.get_pressed()[pygame.K_n]:
	            random_movement()

    on_frame_routines()
    DISPLAYSURF.fill(GameConst.GAME_BG_COLOR)
    draw_shell(DISPLAYSURF)
    draw_room(DISPLAYSURF)
    draw_text(DISPLAYSURF)
    pygame.display.update()
    FramePerSec.tick(GameConst.FPS)
