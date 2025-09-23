import pygame
import os
import random
from enum import Enum, auto
import song_parser
import config
from tile import Tile, Particle, TileState, TileType
from arduino_handler import ArduinoHandler
import utils
from collections import deque


class FloatingText:
    def __init__(self, text, x, y, font, color=config.WHITE):
        self.x, self.y = x, y
        self.text = text
        self.font = font
        self.color = color
        self.alpha = 255
        self.vy = -1

    def update(self):
        self.y += self.vy
        self.alpha = max(0, self.alpha - 5)

    def draw(self, surface):
        utils.draw_text(surface, self.text, 24, self.x, self.y, (*self.color, self.alpha), self.font, shadow=False)


class GameState(Enum):
    COUNTDOWN = auto()
    PLAYING = auto()
    FINISHED = auto()


class GameScreen:
    def __init__(self, surface):
        self.surface = surface
        self.assets = self.load_assets()
        self.sounds = self.load_sounds()
        self.pitch_map = self._create_pitch_map()

        self.arduino = ArduinoHandler()

        self.reset_game_state()

    def reset_game_state(self):
        self.game_state = GameState.COUNTDOWN
        self.parsed_song = None
        self.active_tiles = []
        self.upcoming_tiles = deque()
        self.particles = []
        self.floating_texts = []
        self.tps = 4.0

        self.score = 0
        self.combo = 0
        self.stars_earned = 0

        self.game_time = 0.0
        self.time_offset = 0.0
        self.countdown_timer = 3.99

        self.last_hit_musical_time = 0.0

        self.last_pitch = 60
        self.last_lane = -1

        self.autoplay = False

        self.star_end_times = []
        self.num_stars = 0

    def load_assets(self):
        assets = {'background': pygame.transform.scale(utils.load_image(config.BACKGROUND_IMG),
                                                       (config.SCREEN_WIDTH, config.SCREEN_HEIGHT))}
        return assets

    def load_sounds(self):
        sounds = {}
        print(f"Loading sounds from: {os.path.abspath(config.SOUNDS_DIR)}")
        for filename in os.listdir(config.SOUNDS_DIR):
            if filename.endswith(".mp3"):
                note_name = os.path.splitext(filename)[0]
                try:
                    sounds[note_name] = pygame.mixer.Sound(os.path.join(config.SOUNDS_DIR, filename))
                except pygame.error as e:
                    print(f"Could not load sound {note_name}: {e}")
        pygame.mixer.set_num_channels(128)
        print(f"Loaded {len(sounds)} sounds.")
        return sounds

    def _play_sound(self, note_name):
        if note_name in self.sounds:
            channel = pygame.mixer.find_channel(True)
            if channel: channel.play(self.sounds[note_name])

    def load_song(self, song_file_name):
        self.reset_game_state()
        song_path = os.path.join(config.SONGS_DIR, song_file_name)
        self.parsed_song = song_parser.parse_song(song_path)

        cumulative_time = 0.0
        self.star_end_times = []
        self.accompaniment_tracks = []
        temp_active_tiles = []
        first = True
        star_ids = sorted(self.parsed_song.keys())
        self.num_stars = len(star_ids)

        for star_id in star_ids:
            part_data = self.parsed_song[star_id]
            metadata = part_data['metadata']

            if first:
                self.tps = (metadata['bpm'] / metadata['baseBeats']) / 60.0

            tiles_to_add = part_data['playable_tiles']

            self._assign_lanes(tiles_to_add, is_first_part=first)
            first = False

            for tile in tiles_to_add:
                tile.time += cumulative_time

            temp_active_tiles.extend(tiles_to_add)

            for track in part_data['accompaniment_tracks']:
                offset_track = [{'time': n['time'] + cumulative_time, 'note': n['note']} for n in track]
                self.accompaniment_tracks.append(offset_track)

            part_duration = 0.0
            if tiles_to_add:
                part_duration = max(part_duration, max(t.time - cumulative_time + t.duration for t in tiles_to_add))
            if part_data['accompaniment_tracks']:
                for track in part_data['accompaniment_tracks']:
                    if track:
                        part_duration = max(part_duration, max(n['time'] for n in track))

            cumulative_time += part_duration
            self.star_end_times.append(cumulative_time)

        self.upcoming_tiles = deque(sorted(temp_active_tiles, key=lambda t: t.time))
        self.active_tiles = []

        self.accompaniment_indices = [0] * len(self.accompaniment_tracks)
        self.game_state = GameState.COUNTDOWN

    def _get_pitch_value(self, note_name):
        return self.pitch_map.get(note_name.replace('.', ''), self.pitch_map['c1'])

    def _assign_lanes(self, tiles, is_first_part=False):
        if not tiles: return

        note_name_map = {}
        for tile in tiles:
            if tile.notes: note_name_map[tile] = tile.notes[0]

        tiles.sort(key=lambda t: t.time)

        for i, tile in enumerate(tiles):
            current_pitch = self._get_pitch_value(note_name_map.get(tile, 'c1'))
            potential_lane = self.last_lane

            if is_first_part and i == 0:
                potential_lane = random.randint(0, 3)
            elif self.last_lane != -1:
                if current_pitch > self.last_pitch:
                    potential_lane = min(self.last_lane + 1, 3)
                elif current_pitch < self.last_pitch:
                    potential_lane = max(self.last_lane - 1, 0)

                if potential_lane == self.last_lane:
                    potential_lane = (self.last_lane + 1) % 4

            num_lanes = 2 if tile.sub_type == TileType.Dual else 1
            if potential_lane + num_lanes > 4:
                potential_lane = 4 - num_lanes

            if tile.sub_type == TileType.Dual:
                tile.lane = (potential_lane, potential_lane + 1)
            else:
                tile.lane = potential_lane

            self.last_lane = potential_lane
            self.last_pitch = current_pitch

    def run(self, clock):
        self.game_loop = True
        while self.game_loop:
            self.real_time_clock = clock.tick(config.FPS) / 1000.0
            self.handle_events()
            self.update(self.real_time_clock)
            self.draw()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT: self.game_loop = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: self.game_loop = False
                if event.key == pygame.K_a: self.autoplay = not self.autoplay; print(
                    f"Autoplay {'ON' if self.autoplay else 'OFF'}")
                if self.game_state == GameState.PLAYING: self._handle_input(event)

    def _handle_input(self, event, arduino_taps=None):
        if self.autoplay: return
        taps = []
        if arduino_taps:
            taps.extend(arduino_taps)
        if event is not None and event.type == pygame.KEYDOWN and event.key in config.KEYBINDS:
            taps.append(config.KEYBINDS[event.key])

        for lane_idx in set(taps):
            self._process_tap(lane_idx, self.game_time)

    def update(self, dt):
        lookahead_time = config.BEATS_AHEAD / self.tps
        while self.upcoming_tiles and self.upcoming_tiles[0].time <= self.game_time + lookahead_time:
            self.active_tiles.append(self.upcoming_tiles.popleft())

        if self.game_state == GameState.COUNTDOWN:
            self.countdown_timer -= dt

            if self.countdown_timer <= 0:
                self.game_state = GameState.PLAYING
                self.game_time = -2.0

        elif self.game_state == GameState.PLAYING:
            self.game_time += dt

            arduino_taps = self.arduino.read_input()
            if arduino_taps:
                self._handle_input(None, arduino_taps=arduino_taps)

            if self.autoplay:
                self._handle_autoplay()

            self._update_tiles()

            while self.stars_earned < self.num_stars and self.game_time >= self.star_end_times[self.stars_earned]:
                self.stars_earned += 1

            if self.stars_earned == self.num_stars and self.is_level_finished():
                self.game_state = GameState.FINISHED

        elif self.game_state == GameState.FINISHED:
            pass

        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.lifetime > 0]

    def _handle_autoplay(self):
        for tile in self.active_tiles:
            if tile.state in [TileState.ACTIVE, TileState.MISSED] and tile.time <= self.game_time:
                lane_to_tap = tile.lane if isinstance(tile.lane, int) else tile.lane[0]
                self._process_tap(lane_to_tap, tile.time)

            if tile.state == TileState.HELD and tile.time + tile.duration <= self.game_time:
                tile.release_hold()
                self.score += int(config.HOLD_POINTS_PER_BEAT * self.combo * tile.duration * self.tps / 2)

    def _process_tap(self, lane_idx, hit_time):
        hittable_tiles = [
            t for t in self.active_tiles if t.state in [TileState.ACTIVE, TileState.MISSED] and
                                            abs(t.time - hit_time) < config.GOOD_TIMING and
                                            (t.lane == lane_idx or (isinstance(t.lane, tuple) and lane_idx in t.lane))
        ]
        if not hittable_tiles: return
        best_tile = min(hittable_tiles, key=lambda t: abs(t.time - hit_time))
        quality, color = best_tile.check_hit(hit_time)

        if quality in ['perfect', 'great']:
            best_tile.on_hit(quality, color, hit_time)

            for i, track in enumerate(self.accompaniment_tracks):
                while self.accompaniment_indices[i] < len(track) and \
                        track[self.accompaniment_indices[i]]['time'] + self.time_offset <= best_tile.time:
                    note_time = track[self.accompaniment_indices[i]]['time'] + self.time_offset
                    if note_time > self.last_hit_musical_time:
                        self._play_sound(track[self.accompaniment_indices[i]]['note'])
                    self.accompaniment_indices[i] += 1

            self.last_hit_musical_time = best_tile.time

            for note in best_tile.notes: self._play_sound(note)
            if quality == 'perfect':
                self.score += int(10 * self.combo)
            elif quality == 'great':
                self.score += int(5 * self.combo)
            self.combo = min(self.combo + 1, 999)
            lanes = [best_tile.lane] if isinstance(best_tile.lane, int) else best_tile.lane
            for ln in lanes: self._create_particles(ln)
        else:
            best_tile.miss(hit_time)
            self.combo = 0

    def _update_tiles(self):
        arduino_held_lanes = self.arduino.get_held_lanes()
        keys_held = pygame.key.get_pressed()
        remaining_tiles = []
        is_level_done = True

        for tile in self.active_tiles:
            tile.update(self.game_time, self.tps)

            if tile.state == TileState.HELD:
                is_held = self.autoplay
                lanes = [tile.lane] if isinstance(tile.lane, int) else tile.lane
                for l in lanes:
                    if l in arduino_held_lanes or any(keys_held[key] and lane == l for key, lane in config.KEYBINDS.items()):
                        is_held = True

                if is_held:
                    score_multiplier, new_notes_info = tile.update_hold(self.game_time)
                    if score_multiplier > 0:
                        bonus = int(score_multiplier * config.HOLD_POINTS_PER_BEAT * self.combo)
                        self.score += bonus
                        self.floating_texts.append(
                            FloatingText(f"+{bonus}", tile.rect.centerx, tile.rect.top, config.FONT_PATH))
                    for note_info in new_notes_info:
                        for note in note_info['notes']: self._play_sound(note)
                        self._create_particles(tile.rect.centerx / config.TILE_WIDTH, hit_y=note_info['y'], count=3)
                else:
                    tile.release_hold()

            if tile.state == TileState.ACTIVE and tile.time < self.game_time - config.GOOD_TIMING:
                self.combo = 0
                tile.pass_by()

            if tile.state == TileState.HIT and tile.fade_alpha <= 0:
                continue

            if tile.rect.top < self.surface.get_height() + 100:
                remaining_tiles.append(tile)
                if tile.state in [TileState.ACTIVE, TileState.HELD, TileState.MISSED]:
                    is_level_done = False

        self.active_tiles = remaining_tiles
        self.level_is_finished = is_level_done

    def is_level_finished(self):
        return self.level_is_finished

    def _create_particles(self, lane, count=8, hit_y=config.STRIKE_LINE_Y):
        x = (lane * config.TILE_WIDTH) + (config.TILE_WIDTH / 2)
        for _ in range(count): self.particles.append(Particle(x, hit_y, Tile.dot_light_img))

    def draw(self):
        self.surface.blit(self.assets['background'], (0, 0))
        for i in range(1, 4): pygame.draw.line(self.surface, config.WHITE, (i * config.TILE_WIDTH, 0),
                                               (i * config.TILE_WIDTH, config.SCREEN_HEIGHT), 1)
        pygame.draw.line(self.surface, config.GRAY, (0, config.STRIKE_LINE_Y),
                         (config.SCREEN_WIDTH, config.STRIKE_LINE_Y), 3)

        for p in self.particles: p.draw(self.surface)
        if self.game_state != GameState.COUNTDOWN:
            for t in self.active_tiles: t.draw(self.surface)
        for ft in self.floating_texts:
            ft.update()
            ft.draw(self.surface)
        self.floating_texts = [ft for ft in self.floating_texts if ft.alpha > 0]

        utils.draw_text(self.surface, f"Score: {self.score}", 30, config.SCREEN_WIDTH - 10, 25, config.WHITE,
                        config.FONT_PATH, "topright", shadow=True)
        utils.draw_text(self.surface, f"Combo: {self.combo}", 40, 10, 25, config.WHITE, config.FONT_PATH, "topleft",
                        shadow=True)
        utils.draw_text(self.surface, "".join(["★" * self.stars_earned]), 40, config.SCREEN_WIDTH / 2, 25, "yellow",
                        config.SYMBOL_FONT_PATH, "center", shadow=True)

        if self.game_state == GameState.COUNTDOWN and self.countdown_timer < 3:
            utils.draw_text(self.surface, str(int(self.countdown_timer) + 1), 100, config.SCREEN_WIDTH // 2,
                            config.SCREEN_HEIGHT // 2, config.WHITE, config.FONT_PATH, 'center', True)
        elif self.game_state == GameState.FINISHED:
            utils.draw_text(self.surface, "Song Clear!", 80, config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2 - 50,
                            "cyan", config.FONT_PATH, "center", True)
            utils.draw_text(self.surface, f"Final Score: {self.score}", 40, config.SCREEN_WIDTH // 2,
                            config.SCREEN_HEIGHT // 2 + 50, config.WHITE, config.FONT_PATH, "center", True)

        pygame.display.flip()

    def _create_pitch_map(self):
        notes, note_map, val = "a,#a,b,c,#c,d,#d,e,f,#f,g,#g".split(','), {}, 21
        for oct in range(-3, 6):
            for note in notes:
                if oct < 0 and note in "c,#c,d,#d,e,f,#f,g,#g": continue
                if oct == 5 and note not in "c": continue
                name = note[0].upper() + note[1:] if oct < 0 else note
                oct_str = str(abs(oct)) if oct != 0 else ""
                if oct < 0:
                    name += "-" + oct_str
                elif oct > 0:
                    name += oct_str
                note_map[name] = val
                val += 1
        return note_map


if __name__ == '__main__':
    pygame.init()
    screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    pygame.display.set_caption("Game Screen Test")
    clock = pygame.time.Clock()
    game = GameScreen(screen)
    game.load_song("Bad Apple.json")
    game.run(clock)
    pygame.quit()