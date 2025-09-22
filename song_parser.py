import json
import re
import os
from tile import Tile, TileType
import config


def _parse_duration(duration_str, bpm):
    """Calculates duration in absolute seconds based on beat value and BPM."""
    total_beats = sum(config.BEAT_MAP.get(char, 0) for char in duration_str)
    if bpm > 0:
        return total_beats * (60.0 / bpm)
    return 0


def _parse_space(space_str, bpm):
    """Calculates space duration in absolute seconds based on beat value and BPM."""
    total_beats = sum(config.SPACE_MAP.get(char, 0) for char in space_str)
    if bpm > 0:
        return total_beats * (60.0 / bpm)
    return 0


def parse_song(file_path):
    """
    Loads and parses a song's JSON file. It finds the first track with actual notes
    to use for playable tiles and keeps all other non-empty tracks for accompaniment.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        song_data = json.load(f)

    parsed_data = {}
    base_bpm = float(song_data.get('baseBpm', 120))

    event_pattern = re.compile(
        r"^\s*(\d<[^>]+>)|"
        r"^\s*(\(([^)]+)\)\[([A-P]+)\])|"
        r"^\s*([a-zA-Z#\-1-5\.]+\s*\[[A-P]+\])|"
        r"^\s*([Q-Y]+)"
    )
    note_pattern = re.compile(r"([a-zA-Z#\-1-5\.]+)\s*\[([A-P]+)\]")
    space_pattern = re.compile(r"([Q-Y]+)")

    for part in song_data.get('musics', []):
        part_id = part.get('id')
        bpm = float(part.get('bpm', base_bpm))
        base_beats = float(part.get('baseBeats', 0.25))

        playable_tiles = []
        accompaniment_tracks = []
        playable_track_found = False

        for track_index, score_string in enumerate(part.get('scores', [])):
            current_track_notes = []  # For accompaniment
            temp_playable_tiles = []  # Temporary list for this track's tiles

            is_potentially_playable = not playable_track_found

            current_time = 0.0
            current_lane = 0
            remaining_str = score_string.strip()

            track_has_notes = False  # Flag to see if we find any real notes

            while remaining_str:
                match = event_pattern.match(remaining_str)
                if not match:
                    next_sep = re.search(r'[,;]', remaining_str)
                    remaining_str = remaining_str[next_sep.end():].lstrip() if next_sep else ""
                    continue

                full_event_str = match.group(0)

                if match.group(1):  # Special Tile
                    # ... (Parsing logic for special tiles)
                    content, tile_kind = match.group(1), int(match.group(1)[0])
                    inner_content = content[2:-1]
                    sub_events, sub_note_time, total_duration = inner_content.split(','), 0, 0
                    all_notes_in_tile, sub_notes_data = [], []

                    has_notes_in_special = False

                    for sub_event_str in sub_events:
                        sub_event = sub_event_str.strip()
                        note_match = note_pattern.match(sub_event)
                        space_match = space_pattern.match(sub_event)
                        duration = 0
                        if note_match:
                            notes, duration_str = note_match.group(1).split('.'), note_match.group(2)
                            beat_value = sum(config.BEAT_MAP.get(char, 0) for char in duration_str)
                            duration = _parse_duration(duration_str, bpm)
                            for note in notes:
                                if note.lower() not in ['mute', 'empty']:
                                    has_notes_in_special = True
                                    track_has_notes = True
                                current_track_notes.append({'time': current_time + sub_note_time, 'note': note})
                            all_notes_in_tile.extend(notes)
                            sub_notes_data.append({'notes': notes, 'duration': duration, 'beat_value': beat_value})
                        elif space_match:
                            duration = _parse_space(space_match.group(1), bpm)
                        sub_note_time += duration
                    total_duration = sub_note_time

                    if is_potentially_playable and has_notes_in_special:
                        lane = (current_lane, (current_lane + 1) % 4) if tile_kind == 5 else current_lane
                        # A special tile is a long note if ANY of its sub-notes are long
                        is_long = any(sn['beat_value'] > base_beats for sn in sub_notes_data)
                        tile_type = TileType.LongNote if tile_kind == 6 or is_long else TileType.Normal
                        sub_type = TileType.SpecialHold if tile_kind == 6 else (
                            TileType.Dual if tile_kind == 5 else TileType.Normal)
                        temp_playable_tiles.append(
                            Tile(lane, current_time, total_duration, all_notes_in_tile, tile_type, sub_type,
                                 sub_notes=sub_notes_data if tile_kind == 6 else []))
                        current_lane = (current_lane + (2 if tile_kind == 5 else 1)) % 4
                    current_time += total_duration
                else:  # Normal Notes, Chords, Spaces
                    duration = 0
                    if match.group(2):  # Chord
                        notes, duration_str = match.group(3).split('.'), match.group(4)
                        beat_value = sum(config.BEAT_MAP.get(char, 0) for char in duration_str)
                        duration = _parse_duration(duration_str, bpm)
                        for note in notes:
                            if note.lower() not in ['mute', 'empty']: track_has_notes = True
                            current_track_notes.append({'time': current_time, 'note': note})
                        if is_potentially_playable:
                            tile_type = TileType.LongNote if beat_value > base_beats else TileType.Normal
                            temp_playable_tiles.append(
                                Tile(current_lane, current_time, duration, notes, tile_type, TileType.Normal))
                            current_lane = (current_lane + 1) % 4
                    elif match.group(5):  # Note
                        note_match = note_pattern.match(match.group(5).strip())
                        notes, duration_str = [note_match.group(1)], note_match.group(2)
                        beat_value = sum(config.BEAT_MAP.get(char, 0) for char in duration_str)
                        duration = _parse_duration(duration_str, bpm)
                        for note in notes:
                            if note.lower() not in ['mute', 'empty']: track_has_notes = True
                            current_track_notes.append({'time': current_time, 'note': note})
                        if is_potentially_playable:
                            tile_type = TileType.LongNote if beat_value > base_beats else TileType.Normal
                            temp_playable_tiles.append(
                                Tile(current_lane, current_time, duration, notes, tile_type, TileType.Normal))
                            current_lane = (current_lane + 1) % 4
                    elif match.group(6):  # Space
                        duration = _parse_space(match.group(6), bpm)
                    current_time += duration
                remaining_str = remaining_str[len(full_event_str):].lstrip(' ,;')

            if is_potentially_playable and track_has_notes:
                playable_tiles = temp_playable_tiles
                playable_track_found = True
            elif current_track_notes:
                accompaniment_tracks.append(sorted(current_track_notes, key=lambda x: x['time']))

        parsed_data[part_id] = {
            'metadata': {'id': part_id, 'bpm': bpm, 'baseBeats': base_beats},
            'playable_tiles': playable_tiles,
            'accompaniment_tracks': accompaniment_tracks
        }
    return parsed_data