import pygame
import os
import json
import re
import config
import utils
from song_parser import parse_song
from tile import TileType


class MainMenuScreen:
    def __init__(self, surface):
        pygame.mixer.init()
        self.surface = surface
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
        self.sort_key = 'display_name'
        self.sort_reverse = False
        self.scrollbar_rect = pygame.Rect(config.SCREEN_WIDTH - 30, 150, 20, config.SCREEN_HEIGHT - 250)
        self.scrollbar_handle_height = 50
        self.scrollbar_dragging = False
        self.scrollbar_handle_rect = pygame.Rect(0, 0, 0, 0)
        self.load_songs()
        self.buttons = []
        self.create_buttons()
        self.active_text_input = False
        self.preview_playing = False
        self.preview_notes = []
        self.preview_index = 0
        self.preview_start_time = 0

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
        self.sort_songs()
        self.filtered_songs = self.songs.copy()
        self.update_max_scroll()

    def sort_songs(self):
        """Sort songs based on current sort key and direction."""
        self.songs.sort(key=lambda x: x[self.sort_key], reverse=self.sort_reverse)
        self.filter_songs()

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

            # Parse tiles
            tile_values = []
            prev_tile_value = 0
            prev_was_double = False
            prev_was_sliding = False
            rapid_sequence = []

            for score in scores:
                events = score.split(',')
                for event in events:
                    event = event.strip()
                    if not event:
                        continue

                    # Handle special tiles
                    if event.startswith(('2<', '3<', '5<', '6<', '7<', '8<', '9<', '10<')):
                        tile_kind = int(event[0])
                        inner_content = event[2:-1].split(',')
                        if tile_kind == 5:  # Double tile
                            value = 4 if not prev_was_double else prev_tile_value + 0.2
                            if prev_tile_value > 4 and not prev_was_double:
                                value = prev_tile_value + 0.2
                            tile_values.append(min(value, 8))
                            prev_was_double = True
                            prev_was_sliding = False
                        elif tile_kind == 6:  # Long tile
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
                        elif tile_kind == 7 or tile_kind == 8:  # Sliding tiles
                            tile_values.append(2.5)  # First sliding tile
                            for _ in inner_content[1:]:
                                tile_values.append(0)  # Subsequent sliding tiles
                            prev_was_sliding = True
                            prev_was_double = False
                        elif tile_kind == 10:  # Burst tile (rapid)
                            sub_events = inner_content
                            for i, sub_event in enumerate(sub_events):
                                if i == len(sub_events) - 1:
                                    tile_values.append(4)  # Last rapid tile
                                else:
                                    tile_values.append(0.5)  # Precedent rapid tiles
                            prev_was_double = False
                            prev_was_sliding = False
                        continue

                    # Handle normal/long tiles
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
                        else:  # 4 or more
                            tile_values.append(0.03125)
                        prev_was_double = False
                        prev_was_sliding = False
                    prev_tile_value = tile_values[-1] if tile_values else 0

            # Calculate sequences
            sequence_values = []
            for i in range(len(tile_values)):
                sequence_sum = sum(tile_values[i:i + 10])
                sequence_values.append(sequence_sum * (tps ** 4))

            # Calculate difficulty
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
        """Return difficulty class based on value."""
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
        """Return color based on difficulty value."""
        if difficulty < 4000:
            return (0, 255, 0)  # Green
        elif difficulty < 12000:
            return (0, 200, 200)  # Cyan
        elif difficulty < 25000:
            return (0, 0, 255)  # Blue
        elif difficulty < 50000:
            return (255, 255, 0)  # Yellow
        elif difficulty < 100000:
            return (255, 165, 0)  # Orange
        elif difficulty < 200000:
            return (255, 0, 0)  # Red
        else:
            return (128, 0, 128)  # Purple

    def create_buttons(self):
        """Create buttons for the menu."""
        self.buttons = []

        # Play button for selected song
        def play_song():
            if self.selected_song:
                self.stop_preview()
                return {'action': 'play_song', 'filename': self.selected_song['filename']}

        self.buttons.append(utils.Button(
            (config.SCREEN_WIDTH - 120, config.SCREEN_HEIGHT - 80, 100, 50),
            "Play", play_song
        ))
        # Back button
        self.buttons.append(utils.Button(
            (20, config.SCREEN_HEIGHT - 80, 100, 50),
            "Back", lambda: {'action': 'back'}
        ))
        # Sort by name button
        self.buttons.append(utils.Button(
            (50, 100, 100, 40),
            "Sort: Name", lambda: self.toggle_sort('display_name')
        ))
        # Sort by difficulty button
        self.buttons.append(utils.Button(
            (160, 100, 120, 40),
            "Sort: Difficulty", lambda: self.toggle_sort('difficulty')
        ))

    def toggle_sort(self, key):
        """Toggle sorting by the specified key."""
        if self.sort_key == key:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_key = key
            self.sort_reverse = False
        self.sort_songs()

    def update_max_scroll(self):
        """Calculate maximum scroll offset based on number of songs."""
        item_height = 60
        total_height = len(self.filtered_songs) * item_height
        self.max_scroll = max(0, total_height - (config.SCREEN_HEIGHT - 250))
        # Update scrollbar handle size
        visible_height = config.SCREEN_HEIGHT - 250
        if total_height > visible_height:
            self.scrollbar_handle_height = max(30, (visible_height / total_height) * visible_height)
        else:
            self.scrollbar_handle_height = visible_height
        self.update_scrollbar_handle()

    def update_scrollbar_handle(self):
        """Update the position and size of the scrollbar handle."""
        if self.max_scroll > 0:
            handle_y = self.scrollbar_rect.top + (self.scroll_offset / self.max_scroll) * (
                self.scrollbar_rect.height - self.scrollbar_handle_height)
        else:
            handle_y = self.scrollbar_rect.top
        self.scrollbar_handle_rect = pygame.Rect(
            self.scrollbar_rect.left, handle_y,
            self.scrollbar_rect.width, self.scrollbar_handle_height
        )

    def handle_events(self):
        """Handle user input events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return {'action': 'quit'}
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    for button in self.buttons:
                        button.handle_event(event)
                    self.handle_song_selection(event.pos)
                    # Check if scrollbar handle is clicked
                    if self.scrollbar_handle_rect.collidepoint(event.pos):
                        self.scrollbar_dragging = True
                elif event.button == 4:  # Scroll up
                    self.scroll_offset = max(0, self.scroll_offset - 20)
                    self.update_scrollbar_handle()
                elif event.button == 5:  # Scroll down
                    self.scroll_offset = min(self.max_scroll, self.scroll_offset + 20)
                    self.update_scrollbar_handle()
            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:  # Left click
                    self.scrollbar_dragging = False
            if event.type == pygame.MOUSEMOTION:
                if self.scrollbar_dragging:
                    mouse_y = event.pos[1]
                    relative_y = mouse_y - self.scrollbar_rect.top
                    scroll_ratio = relative_y / (self.scrollbar_rect.height - self.scrollbar_handle_height)
                    self.scroll_offset = scroll_ratio * self.max_scroll
                    self.scroll_offset = max(0, min(self.scroll_offset, self.max_scroll))
                    self.update_scrollbar_handle()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return {'action': 'back'}
                if self.active_text_input:
                    if event.key == pygame.K_BACKSPACE:
                        self.search_text = self.search_text[:-1]
                    elif event.key == pygame.K_RETURN:
                        self.active_text_input = False
                    else:
                        char = event.unicode
                        if char.isprintable():
                            self.search_text += char
                    self.filter_songs()

        return self.check_button_actions()

    def handle_song_selection(self, pos):
        """Handle clicking on a song in the list."""
        item_height = 60
        list_y = 150
        for i, song in enumerate(self.filtered_songs):
            y = list_y + i * item_height - self.scroll_offset
            if list_y <= y <= config.SCREEN_HEIGHT - 100:
                song_rect = pygame.Rect(50, y, config.SCREEN_WIDTH - 100, item_height)
                play_button_rect = pygame.Rect(song_rect.right - 40, y + 10, 30, 30)
                if play_button_rect.collidepoint(pos):
                    self.play_song_preview(song)
                    return
                if song_rect.collidepoint(pos):
                    self.selected_song = song
                    self.stop_preview()
                    return
        # Click on search bar
        search_rect = pygame.Rect(50, 50, config.SCREEN_WIDTH - 100, 40)
        if search_rect.collidepoint(pos):
            self.active_text_input = True

    def filter_songs(self):
        """Filter song list based on search text."""
        self.filtered_songs = [
            song for song in self.songs
            if self.search_text.lower() in song['display_name'].lower()
        ]
        self.update_max_scroll()
        self.scroll_offset = 0
        self.selected_song = None
        self.stop_preview()

    def play_song_preview(self, song):
        """Play a preview of the selected song."""
        self.stop_preview()
        song_path = os.path.join(self.songs_dir, song['filename'])
        parsed_data = parse_song(song_path)
        audition = json.load(open(song_path, 'r', encoding='utf-8')).get('audition', {'start': [0, 0], 'end': [1, 0]})
        start_id, start_idx = audition['start']
        end_id, end_idx = audition['end']

        # Collect accompaniment notes within the audition range
        self.preview_notes = []
        start_time = 0
        for part_id in sorted(parsed_data.keys()):
            part = parsed_data[part_id]
            if part_id < start_id:
                continue
            if part_id > end_id:
                break
            for track in part['accompaniment_tracks']:
                for note in track:
                    if part_id == start_id and note['time'] < start_idx:
                        continue
                    if part_id == end_id and note['time'] > end_idx:
                        continue
                    self.preview_notes.append(note)
        self.preview_notes.sort(key=lambda x: x['time'])

        if self.preview_notes:
            self.preview_channel = pygame.mixer.find_channel(True)
            self.preview_index = 0
            self.preview_start_time = pygame.time.get_ticks() / 1000.0
            self.preview_playing = True

    def stop_preview(self):
        """Stop any playing preview."""
        if self.preview_channel:
            self.preview_channel.stop()
        self.preview_playing = False
        self.preview_notes = []
        self.preview_index = 0

    def update(self):
        """Update button states and preview playback."""
        for button in self.buttons:
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
        """Check if any button was clicked and return the result."""
        for button in self.buttons:
            if button.on_click and button.is_hovered and pygame.mouse.get_pressed()[0]:
                result = button.on_click()
                if result:
                    return result
        return None

    def draw(self):
        """Draw the main menu screen."""
        self.surface.blit(self.background, (0, 0))

        # Draw title
        utils.draw_text(
            self.surface, config.GAME_NAME, 60,
            config.SCREEN_WIDTH // 2, 30,
            config.WHITE, self.font_path, "center", shadow=True
        )

        # Draw search bar
        search_rect = pygame.Rect(50, 50, config.SCREEN_WIDTH - 100, 40)
        utils.draw_rounded_rect(self.surface, search_rect,
                                config.GRAY if not self.active_text_input else config.LIGHT_BLUE, 10)
        search_text = self.search_text if self.search_text else (
            "Search songs..." if not self.active_text_input else "")
        utils.draw_text(
            self.surface, search_text, 24,
            search_rect.left + 10, search_rect.centery,
            config.WHITE if self.search_text else (180, 180, 180) if not self.active_text_input else config.WHITE,
            self.font_path, "midleft"
        )

        # Draw song list
        item_height = 60
        list_y = 150
        for i, song in enumerate(self.filtered_songs):
            y = list_y + i * item_height - self.scroll_offset
            if y < 100 or y > config.SCREEN_HEIGHT - 100:
                continue
            song_rect = pygame.Rect(50, y, config.SCREEN_WIDTH - 100, item_height)
            is_selected = song == self.selected_song
            bg_color = (80, 80, 80) if is_selected else (50, 50, 50)
            utils.draw_rounded_rect(self.surface, song_rect, bg_color, 10)

            # Draw difficulty indicator
            diff_rect = pygame.Rect(song_rect.left + 10, y + 10, 40, 40)
            utils.draw_rounded_rect(self.surface, diff_rect, song['difficulty_color'], 10)

            # Draw song name
            utils.draw_text(
                self.surface, song['display_name'], 24,
                song_rect.left + 60, song_rect.centery,
                config.WHITE, self.font_path, "midleft"
            )

            # Draw difficulty text
            utils.draw_text(
                self.surface, song['difficulty_class'], 16,
                song_rect.left + 60, song_rect.centery + 20,
                config.WHITE, self.font_path, "midleft"
            )

            # Draw play preview button
            play_button_rect = pygame.Rect(song_rect.right - 40, y + 10, 30, 30)
            utils.draw_rounded_rect(self.surface, play_button_rect,
                                    config.CYAN if self.preview_playing and song == self.selected_song else config.GRAY,
                                    5)
            utils.draw_text(
                self.surface, "▶", 20, play_button_rect.centerx, play_button_rect.centery,
                config.WHITE, self.symbol_font_path, "center"
            )

        # Draw scrollbar
        if self.max_scroll > 0:
            utils.draw_rounded_rect(self.surface, self.scrollbar_rect, (100, 100, 100), 5)
            utils.draw_rounded_rect(self.surface, self.scrollbar_handle_rect, (150, 150, 150), 5)

        # Draw buttons
        for button in self.buttons:
            button.draw(self.surface)

        pygame.display.flip()

    def run(self, clock):
        """Main loop for the menu screen."""
        running = True
        while running:
            result = self.handle_events()
            if result:
                return result
            self.update()
            self.draw()
            clock.tick(config.FPS)
        return {'action': 'quit'}