import pygame
from enum import Enum, auto
import random
import config
import utils


class TileType(Enum):
    Normal = auto()
    LongNote = auto()
    Dual = auto()
    SpecialHold = auto()


class TileState(Enum):
    ACTIVE = auto()
    HIT = auto()
    MISSED = auto()
    HELD = auto()
    PASSED = auto()


class Particle:
    def __init__(self, x, y, image, scale=0.4):
        self.original_image = image
        self.scale = scale
        self.image = pygame.transform.smoothscale(self.original_image,
                                                  (int(self.original_image.get_width() * self.scale),
                                                   int(self.original_image.get_height() * self.scale)))
        self.x = x
        self.y = y
        self.vx = random.uniform(-2, 2)
        self.vy = random.uniform(-4, -1)
        self.lifetime = random.randint(20, 40)
        self.alpha = 255

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.lifetime -= 1
        if self.lifetime > 0:
            self.alpha = max(0, self.alpha - (255 / self.lifetime))

    def draw(self, surface):
        if self.lifetime > 0:
            temp_img = self.image.copy()
            temp_img.set_alpha(self.alpha)
            surface.blit(temp_img, temp_img.get_rect(center=(self.x, self.y)))


class Tile:
    def __init__(self, lane, time, duration, notes, tile_type, sub_type, sub_notes=None):
        self.lane = lane
        self.time = time
        self.duration = duration
        self.notes = notes
        self.type = tile_type
        self.sub_type = sub_type
        self.sub_notes = sub_notes if sub_notes else []

        self.state = TileState.ACTIVE
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.hit_quality_color = None
        self.fade_alpha = 255

        self.hold_progress = 0.0
        self.is_being_held = False
        self.initial_hit_scored = False
        self.sub_notes_hit = [False] * len(self.sub_notes)

        self.crazy_circle_scale = 0.0
        self.crazy_circle_anim_start_time = -1
        self.CRAZY_ANIM_DURATION = 0.15

        # Flash properties for missed tiles
        self.flash_start_time = -1
        self.FLASH_DURATION = 0.3  # Duration of red flash in seconds

        if not hasattr(Tile, 'assets_loaded'):
            Tile.circle_light_img = utils.load_image(config.CIRCLE_LIGHT_IMG)
            Tile.crazy_circle_img = utils.load_image(config.CRAZY_CIRCLE_IMG)
            Tile.dot_light_img = utils.load_image(config.DOT_LIGHT_IMG)
            Tile.assets_loaded = True

    def update(self, current_time, tps):
        if self.state in [TileState.ACTIVE, TileState.HELD, TileState.PASSED]:
            scroll_speed = tps * config.TILE_WIDTH * 1.5
            time_diff = self.time - current_time

            pos_y = config.STRIKE_LINE_Y - (time_diff * scroll_speed) - (config.TILE_WIDTH / 2)

            base_height = self.duration * scroll_speed
            height = max(base_height, config.TILE_WIDTH / 2)

            lanes = [self.lane] if isinstance(self.lane, int) else self.lane
            self.rect = pygame.Rect(lanes[0] * config.TILE_WIDTH, pos_y - height + (config.TILE_WIDTH / 2),
                                    config.TILE_WIDTH * (2 if self.sub_type == TileType.Dual else 1), height)

        elif self.state == TileState.HIT:
            self.fade_alpha = max(0, self.fade_alpha - 15)

        # Update flash for missed state
        if self.state == TileState.MISSED:
            if self.flash_start_time > 0:
                flash_elapsed = current_time - self.flash_start_time
                if flash_elapsed >= self.FLASH_DURATION:
                    self.state = TileState.ACTIVE  # Revert to active after flash
                    self.flash_start_time = -1
                    self.hit_quality_color = None

        if self.crazy_circle_anim_start_time > 0:
            anim_elapsed = current_time - self.crazy_circle_anim_start_time
            self.crazy_circle_scale = min(1.0, anim_elapsed / self.CRAZY_ANIM_DURATION)
            if self.crazy_circle_scale >= 1.0:
                self.crazy_circle_anim_start_time = -1

    def draw(self, surface):
        if self.state == TileState.HIT and self.fade_alpha == 0:
            return
        lanes = [self.lane] if isinstance(self.lane, int) else self.lane

        for lane in lanes:
            draw_rect = self.rect.copy()
            draw_rect.x = lane * config.TILE_WIDTH
            color = config.BLACK
            if self.state in [TileState.HIT, TileState.MISSED] and self.hit_quality_color:
                color = self.hit_quality_color

            temp_surface = pygame.Surface(draw_rect.size, pygame.SRCALPHA)

            if self.type == TileType.LongNote and self.state not in [TileState.HIT, TileState.MISSED]:
                self.draw_long_note_gradient(temp_surface, draw_rect.size)
                line_end_y = draw_rect.height - (Tile.circle_light_img.get_height() / 2)
                pygame.draw.line(temp_surface, config.GRAY, (draw_rect.width / 2, 0), (draw_rect.width / 2, line_end_y),
                                 2)
            else:
                pygame.draw.rect(temp_surface, color, (0, 0, draw_rect.width, draw_rect.height))

            if self.state == TileState.HELD:
                self.draw_curved_fill(temp_surface, draw_rect.size)

            temp_surface.set_alpha(self.fade_alpha)
            surface.blit(temp_surface, draw_rect.topleft)

            if self.type == TileType.LongNote and self.state not in [TileState.HIT, TileState.MISSED]:
                circle_pos = (draw_rect.centerx, draw_rect.bottom - Tile.circle_light_img.get_height() / 2)
                surface.blit(Tile.circle_light_img, Tile.circle_light_img.get_rect(center=circle_pos))

                if self.state == TileState.HELD and self.crazy_circle_scale > 0:
                    scaled_size = (int(Tile.crazy_circle_img.get_width() * self.crazy_circle_scale),
                                   int(Tile.crazy_circle_img.get_height() * self.crazy_circle_scale))
                    scaled_crazy = pygame.transform.smoothscale(Tile.crazy_circle_img, scaled_size)
                    surface.blit(scaled_crazy, scaled_crazy.get_rect(center=circle_pos))

                if self.sub_type == TileType.SpecialHold:
                    self.draw_sub_note_dots(surface, draw_rect)

    def draw_curved_fill(self, surface, size):
        width, height = size
        held_height = height * self.hold_progress
        if held_height <= 0: return

        fill_surface = pygame.Surface(size, pygame.SRCALPHA)
        curve_height = 30

        top_y = height - held_height

        rect_height = max(0, held_height - curve_height)
        rect_part = pygame.Rect(0, top_y + curve_height, width, rect_height)

        if rect_part.height > 0:
            pygame.draw.rect(fill_surface, config.CYAN, rect_part)

        if held_height > 0:
            ellipse_rect = pygame.Rect(0, top_y, width, curve_height * 2)
            pygame.draw.ellipse(fill_surface, config.CYAN, ellipse_rect)

        surface.blit(fill_surface, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

    def draw_sub_note_dots(self, surface, draw_rect):
        total_duration = sum(sn['duration'] for sn in self.sub_notes)
        if total_duration > 0:
            current_duration_sum = 0
            for i, note_info in enumerate(self.sub_notes):
                current_duration_sum += note_info['duration']
                progress = current_duration_sum / total_duration
                dot_y = draw_rect.bottom - (draw_rect.height * progress)
                dot_rect = Tile.dot_light_img.get_rect(center=(draw_rect.centerx, dot_y))

                dot_img = Tile.dot_light_img.copy()
                if self.sub_notes_hit[i]:
                    dot_img.fill((150, 255, 255, 150), special_flags=pygame.BLEND_RGBA_ADD)
                surface.blit(dot_img, dot_rect)

    def draw_long_note_gradient(self, surface, size):
        width, height = size
        if height <= 0: return
        top_color, bottom_color = config.BLACK, (0, 0, 80)
        gradient = pygame.Surface((1, int(height)))
        for y in range(int(height)):
            ratio = y / height
            color = [int(bottom_color[i] * (1 - ratio) + top_color[i] * ratio) for i in range(3)]
            gradient.set_at((0, y), color)
        surface.blit(pygame.transform.scale(gradient, (int(width), int(height))), (0, 0))

    def check_hit(self, hit_time):
        time_diff = abs(hit_time - self.time)
        if time_diff <= config.PERFECT_TIMING: return "perfect", config.PERFECT_COLOR
        if time_diff <= config.GREAT_TIMING: return "great", config.GREAT_COLOR
        if time_diff <= config.GOOD_TIMING: return "good", config.GOOD_COLOR
        return "miss", config.MISS_COLOR

    def on_hit(self, quality, color, hit_time):
        self.hit_quality_color = color
        if quality in ['perfect', 'great']:
            if self.type == TileType.LongNote:
                self.state = TileState.HELD
                self.is_being_held = True
                self.initial_hit_scored = True
                self.crazy_circle_anim_start_time = hit_time
            else:
                self.state = TileState.HIT
        else:
            self.miss(hit_time)

    def miss(self, hit_time):
        self.state = TileState.MISSED
        self.hit_quality_color = config.MISS_COLOR
        self.flash_start_time = hit_time

    def pass_by(self):
        self.state = TileState.PASSED

    def update_hold(self, current_time):
        if self.state != TileState.HELD: return 0, []

        elapsed_time = current_time - self.time
        self.hold_progress = min(1.0, elapsed_time / self.duration)

        newly_hit_info = []
        if self.sub_type == TileType.SpecialHold:
            time_into_hold = 0
            total_duration = sum(sn['duration'] for sn in self.sub_notes)
            if total_duration > 0:
                for i, note_info in enumerate(self.sub_notes):
                    time_into_hold += note_info['duration']
                    if not self.sub_notes_hit[i] and elapsed_time >= time_into_hold:
                        self.sub_notes_hit[i] = True
                        progress = time_into_hold / total_duration
                        hit_y = self.rect.bottom - (self.rect.height * progress)
                        newly_hit_info.append({'notes': note_info['notes'], 'y': hit_y})

        if self.hold_progress >= 1.0:
            self.state = TileState.HIT
            self.hit_quality_color = config.PERFECT_COLOR
            return 1, newly_hit_info
        return 0, newly_hit_info

    def release_hold(self):
        if self.state == TileState.HELD:
            self.state = TileState.HIT
            self.is_being_held = False


if __name__ == '__main__':
    pygame.init()
    screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    pygame.display.set_caption("Tile Test")
    clock = pygame.time.Clock()

    tiles = [
        Tile(0, 2.0, 0.1, ['c1'], TileType.Normal, TileType.Normal),
        Tile(1, 2.5, 1.5, ['d1'], TileType.LongNote, TileType.Normal),
        Tile(2, 3.0, 0.1, ['e1'], TileType.Normal, TileType.Normal),
        Tile(3, 4.0, 2.0, ['f1'], TileType.LongNote, TileType.SpecialHold,
             sub_notes=[{'notes': ['g1'], 'duration': 1.0}, {'notes': ['a1'], 'duration': 1.0}]),
        Tile(0, 4.5, 0.1, ['b1'], TileType.Normal, TileType.Normal),
        Tile((1, 2), 5.0, 0.1, ['c2', 'e2'], TileType.Normal, TileType.Dual),
    ]

    game_time, tps = 0.0, 4.0
    particles = []

    running = True
    while running:
        dt = clock.tick(config.FPS) / 1000.0
        game_time += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.KEYDOWN and event.key in config.KEYBINDS:
                lane = config.KEYBINDS[event.key]
                active_tiles = [t for t in tiles if t.state in [TileState.ACTIVE, TileState.MISSED] and (
                            t.lane == lane or (isinstance(t.lane, tuple) and lane in t.lane))]
                if active_tiles:
                    best_tile = min(active_tiles, key=lambda t: abs(t.rect.bottom - config.STRIKE_LINE_Y))
                    quality, color = best_tile.check_hit(game_time)
                    best_tile.on_hit(quality, color, game_time)
                    print(f"Lane {lane + 1} Hit: {best_tile.notes} -> {quality.upper()}")
                    if quality in ['perfect', 'great']:
                        lanes_to_spawn = [best_tile.lane] if isinstance(best_tile.lane, int) else best_tile.lane
                        for lane_index in lanes_to_spawn:
                            for _ in range(10):
                                particles.append(Particle(lane_index * config.TILE_WIDTH + config.TILE_WIDTH / 2,
                                                          config.STRIKE_LINE_Y, Tile.dot_light_img))

        keys = pygame.key.get_pressed()
        for tile in tiles:
            tile.update(game_time, tps)
            if tile.state == TileState.ACTIVE and tile.time < game_time - config.GOOD_TIMING:
                tile.pass_by()
            if tile.state == TileState.HELD:
                is_held = isinstance(tile.lane, int) and any(
                    keys[key] and lane == tile.lane
                    for key, lane in config.KEYBINDS.items()
                )
                if not is_held:
                    tile.release_hold()
                else:
                    _, new_hits = tile.update_hold(game_time)
                    for hit in new_hits:
                        print(f"Played sub-note: {hit['notes']}")
                        for _ in range(5):
                            particles.append(Particle(tile.rect.centerx, hit['y'], Tile.dot_light_img))

        screen.fill(config.LIGHT_BLUE)
        for i in range(1, 4): pygame.draw.line(screen, config.WHITE, (i * config.TILE_WIDTH, 0),
                                               (i * config.TILE_WIDTH, config.SCREEN_HEIGHT), 1)
        pygame.draw.line(screen, config.GRAY, (0, config.STRIKE_LINE_Y), (config.SCREEN_WIDTH, config.STRIKE_LINE_Y), 3)

        for tile in tiles: tile.draw(screen)
        for p in particles: p.update(); p.draw(screen)
        particles = [p for p in particles if p.lifetime > 0]

        if game_time > 10:
            print("\n--- RESETTING DEMO ---\n")
            game_time = 0;
            particles.clear()
            for t in tiles: t.__init__(t.lane, t.time, t.duration, t.notes, t.type, t.sub_type, t.sub_notes)

        pygame.display.flip()

    pygame.quit()
    print("Tile test finished.")