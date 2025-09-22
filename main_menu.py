import pygame
import os
import json
import re
import config
import utils
from song_parser import parse_song
from tile import TileType
from enum import Enum
from arduino_handler import ArduinoHandler


class MenuState(Enum):
    TITLE = 0
    SONG_SELECTION = 1
    SETTINGS = 2


class InputField:
    def __init__(self, rect, text=""):
        self.rect = rect
        self.text = text


class MainMenuScreen:
    def __init__(self, surface):
        pygame.mixer.init()
        self.original_surface = surface
        self.font_path = config.FONT_PATH
        self.symbol_font_path = config.SYMBOL_FONT_PATH
        self.songs_dir = config.SONGS_DIR
        self.sounds_dir = config.SOUNDS_DIR
        self.background = pygame.transform.scale(
            utils.load_image(config.BACKGROUND_IMG),
            (config.SCREEN_WIDTH, config.SCREEN_HEIGHT)
        )
        self.songs = []
        self.filtered_songs = []
        self.search_text = ""
        self.scroll_offset = 0
        self.max_scroll = 0
        self.selected_song = None
        self.preview_channel = None
        self.preview_notes = []
        self.preview_index = 0
        self.preview_start_time = 0
        self.state = MenuState.TITLE
        self.buttons = []
        self.active_text_input = None
        self.preview_playing = False
        self.keybinds = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3}
        self.waiting_for_key = None
        self.com_port = config.SERIAL_PORT
        self.com_port_text = self.com_port
        self.arduino = ArduinoHandler(self.com_port)
        self.is_fullscreen = False
        self.scaled_surface = surface
        self.blit_offset = (0, 0)
        self.update_display_mode()
        self.create_title_buttons()
        self.load_songs()

    def load_songs(self):
        """Load all JSON song files from the songs directory and calculate difficulties."""
        self.songs = []
        for filename in os.listdir(self.songs_dir):
            if filename.endswith('.json'):
                display_name = filename[:-5].replace('_', ' ')
                difficulty = self.calculate_song_difficulty(os.path.join(self.songs_dir, filename))
                self.songs.append({
                    'filename': filename,
                    'display_name': display_name,
                    'difficulty': difficulty['value'],
                    'difficulty_class': difficulty['class'],
                    'difficulty_color': difficulty['color']
                })
        self.songs.sort(key=lambda x: x['display_name'])
        self.filtered_songs = self.songs.copy()
        self.update_max_scroll()

    def calculate_song_difficulty(self, song_path):
        """Calculate song difficulty based on tile values and sequences."""
        with open(song_path, 'r', encoding='utf-8') as f:
            song_data = json.load(f)

        difficulty_values = []
        for part in song_data.get('musics', []):
            bpm = float(part.get('bpm', song_data.get('baseBpm', 120)))
            base_beats = float(part.get('baseBeats', 0.25))
            tps = (bpm / base_beats) / 60.0
            scores = part.get('scores', [])
            if not scores:
                continue

            tile_values = []
            prev_tile_value = 0
            prev_was_double = False
            prev_was_sliding = False

            for score in scores:
                events = score.split(',')
                for event in events:
                    event = event.strip()
                    if not event:
                        continue

                    if event.startswith(('2<', '3<', '5<', '6<', '7<', '8<', '9<', '10<')):
                        tile_kind = int(event[0])
                        inner_content = event[2:-1].split(',')
                        if tile_kind == 5:
                            value = 4 if not prev_was_double else prev_tile_value + 0.2
                            if prev_tile_value > 4 and not prev_was_double:
                                value = prev_tile_value + 0.2
                            tile_values.append(min(value, 8))
                            prev_was_double = True
                            prev_was_sliding = False
                        elif tile_kind == 6:
                            for sub_event in inner_content:
                                note_match = re.match(r'([a-zA-Z#\-1-5\.]+)\[([A-P]+)\]', sub_event.strip())
                                if note_match:
                                    duration_str = note_match.group(2)
                                    beat_value = sum(config.BEAT_MAP.get(char, 0) for char in duration_str)
                                    value = 1 if beat_value <= base_beats else 1 / (
                                                (beat_value - 1) ** 2) if beat_value > 1 else 1
                                    if prev_was_double:
                                        value *= 3
                                    if prev_was_sliding:
                                        value *= 2
                                    tile_values.append(min(value, 8))
                            prev_was_double = False
                            prev_was_sliding = False
                        elif tile_kind == 7 or tile_kind == 8:
                            tile_values.append(2.5)
                            for _ in inner_content[1:]:
                                tile_values.append(0)
                            prev_was_sliding = True
                            prev_was_double = False
                        elif tile_kind == 10:
                            sub_events = inner_content
                            for i, sub_event in enumerate(sub_events):
                                if i == len(sub_events) - 1:
                                    tile_values.append(4)
                                else:
                                    tile_values.append(0.5)
                            prev_was_double = False
                            prev_was_sliding = False
                        continue

                    note_match = re.match(r'(\([^)]+\)|\S+)\[([A-P]+)\]', event)
                    space_match = re.match(r'([Q-Y]+)', event)
                    if note_match:
                        duration_str = note_match.group(2)
                        beat_value = sum(config.BEAT_MAP.get(char, 0) for char in duration_str)
                        value = 1 if beat_value < base_beats else 1 / ((beat_value - 1) ** 2) if beat_value > 1 else 1
                        if prev_was_double:
                            value = prev_tile_value + 0.2
                        if prev_was_sliding:
                            value *= 2
                        tile_values.append(min(value, 8))
                        prev_was_double = False
                        prev_was_sliding = False
                    elif space_match:
                        space_str = space_match.group(1)
                        beat_value = sum(config.SPACE_MAP.get(char, 0) for char in space_str)
                        if beat_value == 1:
                            tile_values.append(0.5)
                        elif beat_value == 2:
                            tile_values.append(0.125)
                        elif beat_value == 3:
                            tile_values.append(0.055555)
                        else:
                            tile_values.append(0.03125)
                        prev_was_double = False
                        prev_was_sliding = False
                    prev_tile_value = tile_values[-1] if tile_values else 0

            sequence_values = []
            for i in range(len(tile_values)):
                sequence_sum = sum(tile_values[i:i + 10])
                sequence_values.append(sequence_sum * (tps ** 4))

            A = sum(value * (tps ** 4) for value in tile_values)
            B = max(sequence_values) if sequence_values else 0
            difficulty = (A / 20) + B
            difficulty_values.append(difficulty)

        total_difficulty = max(difficulty_values) if difficulty_values else 0
        return {
            'value': total_difficulty,
            'class': self.get_difficulty_class(total_difficulty),
            'color': self.get_difficulty_color(total_difficulty)
        }

    def get_difficulty_class(self, difficulty):
        if difficulty < 4000:
            return "Baby Level"
        elif difficulty < 8000:
            return "Extremely Simple"
        elif difficulty < 12000:
            return "Very Simple"
        elif difficulty < 18000:
            return "Simple"
        elif difficulty < 25000:
            return "Moderately Simple"
        elif difficulty < 35000:
            return "Moderate"
        elif difficulty < 50000:
            return "Moderately Difficult"
        elif difficulty < 75000:
            return "Considerably Difficult"
        elif difficulty < 100000:
            return "Difficult"
        elif difficulty < 150000:
            return "Very Difficult"
        elif difficulty < 200000:
            return "Extremely Difficult"
        elif difficulty < 300000:
            return "Insanely Difficult"
        elif difficulty < 500000:
            return "Alien Level"
        else:
            return "Quite Impossible"

    def get_difficulty_color(self, difficulty):
        if difficulty < 4000:
            return (0, 255, 0)
        elif difficulty < 12000:
            return (0, 200, 200)
        elif difficulty < 25000:
            return (0, 0, 255)
        elif difficulty < 50000:
            return (255, 255, 0)
        elif difficulty < 100000:
            return (255, 165, 0)
        elif difficulty < 200000:
            return (255, 0, 0)
        else:
            return (128, 0, 128)

    def create_title_buttons(self):
        self.buttons = [
            utils.Button((config.SCREEN_WIDTH // 2 - 100, 300, 200, 60), "Play",
                         lambda: self.switch_state(MenuState.SONG_SELECTION)),
            utils.Button((config.SCREEN_WIDTH // 2 - 100, 380, 200, 60), "Settings",
                         lambda: self.switch_state(MenuState.SETTINGS)),
            utils.Button((config.SCREEN_WIDTH // 2 - 100, 460, 200, 60), "Quit", lambda: None)
        ]

    def create_song_selection_buttons(self):
        def play_song():
            if self.selected_song:
                self.stop_preview()
                return self.selected_song['filename']

        self.buttons = [
            utils.Button((config.SCREEN_WIDTH - 120, config.SCREEN_HEIGHT - 80, 100, 50), "Play", play_song),
            utils.Button((50, config.SCREEN_HEIGHT - 80, 100, 50), "Back", lambda: self.switch_state(MenuState.TITLE))
        ]
        self.search_field = InputField(pygame.Rect(50, 50, config.SCREEN_WIDTH - 100, 40), self.search_text)

    def create_settings_buttons(self):
        def toggle_fullscreen():
            self.is_fullscreen = not self.is_fullscreen
            self.update_display_mode()

        def rescan_arduino():
            self.arduino.close()
            self.arduino = ArduinoHandler(self.com_port)

        self.buttons = [
            utils.Button((50, config.SCREEN_HEIGHT - 80, 100, 50), "Back", lambda: self.switch_state(MenuState.TITLE)),
            utils.Button((config.SCREEN_WIDTH - 150, config.SCREEN_HEIGHT - 80, 100, 50), "Fullscreen",
                         toggle_fullscreen),
            utils.Button((config.SCREEN_WIDTH - 150, 400, 100, 50), "Rescan Arduino", rescan_arduino)
        ]
        self.keybind_buttons = [
            utils.Button((200, 200 + i * 60, 100, 40), pygame.key.name(list(self.keybinds.keys())[i]),
                         lambda i=i: self.start_keybind(i))
            for i in range(4)
        ]
        self.com_port_field = InputField(pygame.Rect(200, 450, 150, 40), self.com_port)

    def start_keybind(self, lane):
        self.waiting_for_key = lane
        self.active_text_input = None

    def update_display_mode(self):
        if self.is_fullscreen:
            info = pygame.display.Info()
            screen_w, screen_h = info.current_w, info.current_h
            aspect_ratio = config.SCREEN_WIDTH / config.SCREEN_HEIGHT
            if screen_w / screen_h > aspect_ratio:
                new_w = int(screen_h * aspect_ratio)
                new_h = screen_h
                offset_x = (screen_w - new_w) // 2
                offset_y = 0
            else:
                new_w = screen_w
                new_h = int(screen_w / aspect_ratio)
                offset_x = 0
                offset_y = (screen_h - new_h) // 2
            self.surface = pygame.display.set_mode((new_w, new_h), pygame.FULLSCREEN)
            self.scaled_surface = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
            self.blit_offset = (offset_x, offset_y)
        else:
            self.surface = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
            self.scaled_surface = self.surface
            self.blit_offset = (0, 0)

    def switch_state(self, new_state):
        self.state = new_state
        self.active_text_input = None
        self.search_text = ""
        self.scroll_offset = 0
        self.selected_song = None
        self.stop_preview()
        if new_state == MenuState.TITLE:
            self.create_title_buttons()
        elif new_state == MenuState.SONG_SELECTION:
            self.create_song_selection_buttons()
            self.filter_songs()
        elif new_state == MenuState.SETTINGS:
            self.create_settings_buttons()

    def update_max_scroll(self):
        item_height = 60
        total_height = len(self.filtered_songs) * item_height
        self.max_scroll = max(0, total_height - (config.SCREEN_HEIGHT - 200))

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return None
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    for button in self.buttons:
                        button.handle_event(event)
                    if self.state == MenuState.SONG_SELECTION:
                        self.handle_song_selection(event.pos)
                    elif self.state == MenuState.SETTINGS:
                        self.handle_settings_interaction(event.pos)
                elif event.button == 4 and self.state == MenuState.SONG_SELECTION:
                    self.scroll_offset = max(0, self.scroll_offset - 20)
                elif event.button == 5 and self.state == MenuState.SONG_SELECTION:
                    self.scroll_offset = min(self.max_scroll, self.scroll_offset + 20)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == MenuState.TITLE:
                        return None
                    else:
                        self.switch_state(MenuState.TITLE)
                elif self.waiting_for_key is not None:
                    if event.key not in self.keybinds and event.key not in self.keybinds.values():
                        old_key = list(self.keybinds.keys())[self.waiting_for_key]
                        self.keybinds[event.key] = self.keybinds.pop(old_key)
                        self.keybind_buttons[self.waiting_for_key].text = pygame.key.name(event.key)
                        self.waiting_for_key = None
                elif self.active_text_input:
                    if event.key == pygame.K_BACKSPACE:
                        self.active_text_input.text = self.active_text_input.text[:-1]
                    elif event.key == pygame.K_RETURN:
                        if self.active_text_input == self.com_port_field:
                            self.com_port = self.active_text_input.text
                            self.com_port_text = self.com_port
                            self.arduino.close()
                            self.arduino = ArduinoHandler(self.com_port)
                        elif self.active_text_input == self.search_field:
                            self.search_text = self.active_text_input.text
                            self.filter_songs()
                        self.active_text_input = None
                    else:
                        char = event.unicode
                        if char.isprintable():
                            self.active_text_input.text += char
                    if self.active_text_input == self.search_field:
                        self.search_text = self.active_text_input.text
                        self.filter_songs()
        return self.check_button_actions()

    def handle_song_selection(self, pos):
        item_height = 60
        list_y = 150
        for i, song in enumerate(self.filtered_songs):
            y = list_y + i * item_height - self.scroll_offset
            if list_y <= y <= config.SCREEN_HEIGHT - 100:
                song_rect = pygame.Rect(50, y, config.SCREEN_WIDTH - 100, item_height)
                play_button_rect = pygame.Rect(song_rect.right - 50, y + 15, 40, 40)
                if play_button_rect.collidepoint(pos):
                    self.selected_song = song
                    self.play_song_preview(song)
                    return
                if song_rect.collidepoint(pos):
                    self.selected_song = song
                    self.stop_preview()
                    return
        if self.search_field.rect.collidepoint(pos):
            self.active_text_input = self.search_field
            self.search_field.text = self.search_text

    def handle_settings_interaction(self, pos):
        for button in self.keybind_buttons:
            if button.rect.collidepoint(pos):
                button.on_click()
        if self.com_port_field.rect.collidepoint(pos):
            self.active_text_input = self.com_port_field
            self.com_port_field.text = self.com_port_text

    def filter_songs(self):
        self.filtered_songs = [
            song for song in self.songs
            if self.search_text.lower() in song['display_name'].lower()
        ]
        self.update_max_scroll()
        self.scroll_offset = 0
        self.selected_song = None
        self.stop_preview()

    def play_song_preview(self, song):
        self.stop_preview()
        song_path = os.path.join(self.songs_dir, song['filename'])
        parsed_data = parse_song(song_path)
        audition = json.load(open(song_path, 'r', encoding='utf-8')).get('audition', {'start': [0, 0], 'end': [1, 0]})
        start_id, start_idx = audition['start']
        end_id, end_idx = audition['end']

        self.preview_notes = []
        cumulative_time = 0
        for part_id in sorted(parsed_data.keys()):
            part = parsed_data[part_id]
            if part_id < start_id or part_id > end_id:
                continue
            for track in part['accompaniment_tracks']:
                for note in track:
                    note_time = note['time'] + cumulative_time
                    if (part_id == start_id and note_time < start_idx) or (part_id == end_id and note_time > end_idx):
                        continue
                    self.preview_notes.append({'time': note_time, 'note': note['note']})
            part_duration = max((t.time + t.duration for t in part['playable_tiles']), default=0)
            cumulative_time += part_duration
        self.preview_notes.sort(key=lambda x: x['time'])

        if self.preview_notes:
            self.preview_channel = pygame.mixer.find_channel(True)
            self.preview_index = 0
            self.preview_start_time = pygame.time.get_ticks() / 1000.0
            self.preview_playing = True

    def stop_preview(self):
        if self.preview_channel:
            self.preview_channel.stop()
        self.preview_playing = False
        self.preview_notes = []
        self.preview_index = 0

    def update(self):
        for button in self.buttons:
            button.update()
        if self.state == MenuState.SETTINGS:
            for button in self.keybind_buttons:
                button.update()
        if self.preview_playing and self.preview_channel:
            current_time = pygame.time.get_ticks() / 1000.0 - self.preview_start_time
            while self.preview_index < len(self.preview_notes) and \
                    self.preview_notes[self.preview_index]['time'] <= current_time:
                note_name = self.preview_notes[self.preview_index]['note']
                sound_path = os.path.join(self.sounds_dir, f"{note_name}.mp3")
                if os.path.exists(sound_path):
                    sound = pygame.mixer.Sound(sound_path)
                    self.preview_channel.play(sound)
                self.preview_index += 1
            if self.preview_index >= len(self.preview_notes):
                self.stop_preview()

    def check_button_actions(self):
        for button in self.buttons:
            if button.on_click and button.is_hovered and pygame.mouse.get_pressed()[0]:
                result = button.on_click()
                if result:
                    return result
        return None

    def draw(self):
        self.scaled_surface.fill((0, 0, 0))
        self.scaled_surface.blit(self.background, (0, 0))

        if self.state == MenuState.TITLE:
            utils.draw_text(
                self.scaled_surface, "Piano Tiles 2", 80,
                config.SCREEN_WIDTH // 2, 100, config.WHITE, self.font_path, "center", shadow=True
            )
            for button in self.buttons:
                button.draw(self.scaled_surface)

        elif self.state == MenuState.SONG_SELECTION:
            utils.draw_rounded_rect(self.scaled_surface, self.search_field.rect,
                                    config.LIGHT_BLUE if self.active_text_input == self.search_field else config.GRAY,
                                    10)
            display_text = self.search_field.text if self.search_field.text else "Search songs..." if self.active_text_input != self.search_field else ""
            utils.draw_text(
                self.scaled_surface, display_text, 24,
                self.search_field.rect.left + 10, self.search_field.rect.centery,
                config.WHITE, self.font_path, "midleft"
            )

            item_height = 60
            list_y = 150
            for i, song in enumerate(self.filtered_songs):
                y = list_y + i * item_height - self.scroll_offset
                if y < 100 or y > config.SCREEN_HEIGHT - 100:
                    continue
                song_rect = pygame.Rect(50, y, config.SCREEN_WIDTH - 100, item_height)
                is_selected = song == self.selected_song
                bg_color = (80, 80, 80) if is_selected else (50, 50, 50)
                utils.draw_rounded_rect(self.scaled_surface, song_rect, bg_color, 10)

                diff_rect = pygame.Rect(song_rect.left + 10, y + 10, 40, 40)
                utils.draw_rounded_rect(self.scaled_surface, diff_rect, song['difficulty_color'], 10)

                utils.draw_text(
                    self.scaled_surface, song['display_name'], 24,
                    song_rect.left + 60, song_rect.centery,
                    config.WHITE, self.font_path, "midleft"
                )
                utils.draw_text(
                    self.scaled_surface, song['difficulty_class'], 16,
                    song_rect.left + 60, song_rect.centery + 20,
                    config.WHITE, self.font_path, "midleft"
                )

                play_button_rect = pygame.Rect(song_rect.right - 50, y + 15, 40, 40)
                utils.draw_rounded_rect(self.scaled_surface, play_button_rect,
                                        config.CYAN if self.preview_playing and song == self.selected_song else config.GRAY,
                                        5)
                utils.draw_text(
                    self.scaled_surface, "▶", 20, play_button_rect.centerx, play_button_rect.centery,
                    config.WHITE, self.symbol_font_path, "center"
                )

            for button in self.buttons:
                button.draw(self.scaled_surface)

        elif self.state == MenuState.SETTINGS:
            utils.draw_text(
                self.scaled_surface, "Settings", 60,
                config.SCREEN_WIDTH // 2, 50, config.WHITE, self.font_path, "center", shadow=True
            )
            for i, button in enumerate(self.keybind_buttons):
                utils.draw_text(
                    self.scaled_surface, f"Lane {i + 1}:", 24, 100, 200 + i * 60,
                    config.WHITE, self.font_path, "midleft"
                )
                button.draw(self.scaled_surface)
            utils.draw_text(
                self.scaled_surface, "COM Port:", 24, 100, 450,
                config.WHITE, self.font_path, "midleft"
            )
            utils.draw_rounded_rect(self.scaled_surface, self.com_port_field.rect,
                                    config.LIGHT_BLUE if self.active_text_input == self.com_port_field else config.GRAY,
                                    10)
            utils.draw_text(
                self.scaled_surface, self.com_port_field.text, 24,
                self.com_port_field.rect.left + 10, self.com_port_field.rect.centery,
                config.WHITE, self.font_path, "midleft"
            )
            utils.draw_text(
                self.scaled_surface, f"Arduino: {'Connected' if self.arduino.connected else 'Not Connected'}", 24,
                100, 500, config.GREEN if self.arduino.connected else config.RED, self.font_path, "midleft"
            )
            for button in self.buttons:
                button.draw(self.scaled_surface)

        if self.is_fullscreen:
            scaled = pygame.transform.scale(self.scaled_surface, self.surface.get_size())
            self.surface.fill((0, 0, 0))
            self.surface.blit(scaled, self.blit_offset)
        else:
            self.surface.blit(self.scaled_surface, (0, 0))
        pygame.display.flip()

    def run(self, clock):
        running = True
        while running:
            result = self.handle_events()
            if result:
                return result
            self.update()
            self.draw()
            clock.tick(config.FPS)
        return None


if __name__ == '__main__':
    import platform
    import asyncio

    pygame.init()
    screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
    pygame.display.set_caption("Piano Tiles 2")
    clock = pygame.time.Clock()
    menu = MainMenuScreen(screen)


    async def main():
        result = menu.run(clock)
        print(f"Selected song: {result}")
        pygame.quit()


    if platform.system() == "Emscripten":
        asyncio.ensure_future(main())
    else:
        asyncio.run(main())