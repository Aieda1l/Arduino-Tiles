import sys
import os
import json
import re
import time
import glob
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QComboBox, QProgressBar, QGridLayout
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
import pygame

# --- Constants ---
BEAT_MAP = {
    'H': 8, 'I': 4, 'J': 2, 'K': 1, 'L': 0.5, 'M': 0.25,
    'N': 0.125, 'O': 0.0625, 'P': 0.03125
}
SPACE_MAP = {
    'Q': 8, 'R': 4, 'S': 2, 'T': 1, 'U': 0.5, 'V': 0.25,
    'W': 0.125, 'X': 0.0625, 'Y': 0.03125
}
SOUNDS_DIR = os.path.join("assets", "snd")


# --- Audio Playback Thread ---
class PlaybackThread(QThread):
    update_time_signal = pyqtSignal(float, float)
    finished_signal = pyqtSignal()

    def __init__(self, scheduled_notes, sounds):
        super().__init__()
        self.scheduled_notes = sorted(scheduled_notes, key=lambda x: x[0])
        self.sounds = sounds
        self._is_running = True
        self.total_duration = 0
        if self.scheduled_notes:
            self.total_duration = self.scheduled_notes[-1][0]

    def run(self):
        if not self.scheduled_notes:
            self.finished_signal.emit()
            return

        start_time = time.time()
        note_index = 0

        while note_index < len(self.scheduled_notes) and self._is_running:
            current_time = time.time() - start_time

            while note_index < len(self.scheduled_notes) and self.scheduled_notes[note_index][0] <= current_time:
                _, note_name = self.scheduled_notes[note_index]
                if note_name in self.sounds:
                    self.sounds[note_name].play()
                note_index += 1

            self.update_time_signal.emit(current_time, self.total_duration)
            self.msleep(1)

        while pygame.mixer.get_busy() and self._is_running:
            current_time = time.time() - start_time
            self.update_time_signal.emit(current_time, self.total_duration)
            self.msleep(10)

        if self._is_running:
            self.finished_signal.emit()

    def stop(self):
        self._is_running = False
        pygame.mixer.stop()


# --- Main Application Window ---
class JsonPlayer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Piano Tiles 2 JSON Player")
        self.setGeometry(100, 100, 500, 280)

        self.sounds = {}
        self.parsed_song_data = {}
        self.playback_thread = None

        self.init_pygame()
        self.load_sounds()
        self.init_ui()

    def init_pygame(self):
        pygame.init()
        pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.mixer.set_num_channels(128)
        print("Pygame Mixer Initialized.")

    def load_sounds(self):
        print(f"Loading sounds from: {os.path.abspath(SOUNDS_DIR)}")
        if not os.path.isdir(SOUNDS_DIR):
            print("Error: Sound directory not found!")
            return

        sound_files = glob.glob(os.path.join(SOUNDS_DIR, "*.mp3"))
        for f in sound_files:
            note_name = os.path.splitext(os.path.basename(f))[0]
            try:
                self.sounds[note_name] = pygame.mixer.Sound(f)
            except pygame.error as e:
                print(f"Could not load sound {note_name}: {e}")
        print(f"Loaded {len(self.sounds)} sounds.")

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        file_layout = QHBoxLayout()
        self.file_label = QLabel("No file loaded.")
        self.file_label.setStyleSheet("font-style: italic;")
        open_button = QPushButton("Open JSON File")
        open_button.clicked.connect(self.open_file)
        file_layout.addWidget(self.file_label, 1)
        file_layout.addWidget(open_button)
        main_layout.addLayout(file_layout)

        selectors_layout = QGridLayout()
        selectors_layout.addWidget(QLabel("Select ID / Part:"), 0, 0)
        self.id_combo = QComboBox()
        self.id_combo.setEnabled(False)
        self.id_combo.currentIndexChanged.connect(self.update_track_selector)
        selectors_layout.addWidget(self.id_combo, 0, 1)

        selectors_layout.addWidget(QLabel("Select Track:"), 1, 0)
        self.track_combo = QComboBox()
        self.track_combo.setEnabled(False)
        selectors_layout.addWidget(self.track_combo, 1, 1)
        main_layout.addLayout(selectors_layout)

        controls_layout = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self.play_music)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_music)
        controls_layout.addWidget(self.play_button)
        controls_layout.addWidget(self.stop_button)
        main_layout.addLayout(controls_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("0.00s / 0.00s")
        main_layout.addWidget(self.progress_bar)

    def open_file(self):
        self.stop_music()
        songs_dir = os.path.abspath("assets/songs")
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Song JSON", songs_dir, "JSON Files (*.json)")

        if file_path:
            self.file_label.setText(os.path.basename(file_path))
            self.parse_file(file_path)

    def parse_duration(self, duration_str, bpm):
        total_beats = sum(BEAT_MAP.get(char, 0) for char in duration_str)
        return total_beats * (60.0 / bpm) if bpm > 0 else 0

    def parse_space(self, space_str, bpm):
        total_beats = sum(SPACE_MAP.get(char, 0) for char in space_str)
        return total_beats * (60.0 / bpm) if bpm > 0 else 0

    def parse_file(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.parsed_song_data = self.parse_json_data(data)
            self.id_combo.clear()
            self.track_combo.clear()

            if not self.parsed_song_data:
                self.id_combo.setEnabled(False)
                self.play_button.setEnabled(False)
                return

            for part_id in sorted(self.parsed_song_data.keys()):
                bpm = self.parsed_song_data[part_id]['bpm']
                self.id_combo.addItem(f"ID {part_id} ({bpm} BPM)", userData=part_id)

            self.id_combo.setEnabled(True)
            self.update_track_selector()

        except Exception as e:
            self.file_label.setText(f"Error parsing file: {e}")
            self.id_combo.clear()
            self.track_combo.clear()
            self.id_combo.setEnabled(False)
            self.track_combo.setEnabled(False)
            self.play_button.setEnabled(False)

    def update_track_selector(self):
        self.track_combo.clear()
        selected_id = self.id_combo.currentData()
        if selected_id is None:
            self.track_combo.setEnabled(False)
            self.play_button.setEnabled(False)
            return

        part_data = self.parsed_song_data[selected_id]
        tracks = part_data['tracks']

        for track_idx in sorted(tracks.keys()):
            self.track_combo.addItem(f"Track {track_idx + 1} ({len(tracks[track_idx])} notes)", userData=track_idx)

        if len(tracks) > 1:
            self.track_combo.addItem("Play All Tracks", userData=-1)  # -1 for "All"

        self.track_combo.setEnabled(True)
        self.play_button.setEnabled(True)

    def parse_json_data(self, song_data):
        event_pattern = re.compile(
            r"^\s*(\d<[^>]+>)|^\s*(\(([^)]+)\)\[([A-P]+)\])|^\s*([a-zA-Z#\-1-5\.]+\s*\[[A-P]+\])|^\s*([Q-Y]+)")
        note_pattern = re.compile(r"([a-zA-Z#\-1-5\.]+)\s*\[([A-P]+)\]")

        parsed_song = {}

        for part in song_data.get('musics', []):
            part_id = part.get('id')
            bpm = float(part.get('bpm', song_data.get('baseBpm')))

            part_data = {'bpm': bpm, 'tracks': {}}

            for track_idx, scores_str in enumerate(part.get('scores', [])):
                if not scores_str: continue

                track_notes = []
                current_time = 0.0
                remaining_str = scores_str.strip()

                while remaining_str:
                    match = event_pattern.match(remaining_str)
                    if not match:
                        next_sep = re.search(r'[,;]', remaining_str);
                        remaining_str = remaining_str[next_sep.end():].lstrip() if next_sep else ""
                        continue

                    full_event_str, notes_to_add, duration = match.group(0), [], 0

                    if match.group(1):  # Special
                        inner, sub_time = match.group(1)[2:-1], 0
                        for sub_event in inner.split(','):
                            if sub_match := note_pattern.match(sub_event.strip()):
                                sub_dur = self.parse_duration(sub_match.group(2), bpm)
                                for note in sub_match.group(1).split('.'): track_notes.append(
                                    (current_time + sub_time, note))
                                sub_time += sub_dur
                        duration = sub_time
                    elif match.group(2):  # Chord
                        duration = self.parse_duration(match.group(4), bpm)
                        for note in match.group(3).split('.'): track_notes.append((current_time, note))
                    elif match.group(5):  # Note
                        if note_match := note_pattern.match(match.group(5).strip()):
                            duration = self.parse_duration(note_match.group(2), bpm)
                            for note in note_match.group(1).split('.'): track_notes.append((current_time, note))
                    elif match.group(6):  # Space
                        duration = self.parse_space(match.group(6), bpm)

                    current_time += duration
                    remaining_str = remaining_str[len(full_event_str):].lstrip(' ,;')

                if track_notes:
                    part_data['tracks'][track_idx] = track_notes

            if part_data['tracks']:
                parsed_song[part_id] = part_data

        return parsed_song

    def play_music(self):
        selected_id = self.id_combo.currentData()
        selected_track = self.track_combo.currentData()
        if selected_id is None or selected_track is None: return

        self.stop_music()
        notes_to_play = []
        tracks = self.parsed_song_data[selected_id]['tracks']

        if selected_track == -1:  # Play All
            for track_notes in tracks.values():
                notes_to_play.extend(track_notes)
        elif selected_track in tracks:
            notes_to_play = tracks[selected_track]

        if not notes_to_play: return

        self.playback_thread = PlaybackThread(notes_to_play, self.sounds)
        self.playback_thread.update_time_signal.connect(self.update_progress)
        self.playback_thread.finished_signal.connect(self.on_playback_finished)

        self.play_button.setEnabled(False);
        self.stop_button.setEnabled(True)
        self.id_combo.setEnabled(False);
        self.track_combo.setEnabled(False)
        self.playback_thread.start()

    def stop_music(self):
        if self.playback_thread and self.playback_thread.isRunning():
            self.playback_thread.stop();
            self.playback_thread.wait()
        self.on_playback_finished()

    def update_progress(self, current_time, total_duration):
        self.progress_bar.setFormat(f"{current_time:.2f}s / {total_duration:.2f}s")
        if total_duration > 0: self.progress_bar.setValue(int((current_time / total_duration) * 100))

    def on_playback_finished(self):
        self.progress_bar.setValue(0);
        self.progress_bar.setFormat("0.00s / 0.00s")
        self.play_button.setEnabled(bool(self.parsed_song_data));
        self.stop_button.setEnabled(False)
        self.id_combo.setEnabled(bool(self.parsed_song_data));
        self.track_combo.setEnabled(bool(self.parsed_song_data))
        self.playback_thread = None

    def closeEvent(self, event):
        self.stop_music();
        pygame.quit();
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    player = JsonPlayer()
    player.show()
    sys.exit(app.exec())