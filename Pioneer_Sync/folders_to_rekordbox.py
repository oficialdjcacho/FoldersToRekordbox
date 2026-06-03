import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from tinytag import TinyTag
except ImportError:  # pragma: no cover
    TinyTag = None


AUDIO_EXTENSIONS = (".mp3", ".flac", ".wav", ".aiff", ".m4a", ".aif")


@dataclass
class TrackMeta:
    path: str
    title: str
    artist: str
    album: str
    genre: str
    year: int
    bpm: float
    duration: int


def is_audio_file(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTENSIONS


def scan_tracks(root_folder: Path, progress_callback=None) -> list[Path]:
    tracks: list[Path] = []
    scanned_files = 0
    for current_root, _, files in os.walk(root_folder):
        for filename in files:
            scanned_files += 1
            candidate = Path(current_root) / filename
            if is_audio_file(candidate):
                tracks.append(candidate)
            if progress_callback and scanned_files % 500 == 0:
                progress_callback("Escaneando archivos...", 0.15)
    return tracks


def read_metadata(audio_path: Path) -> TrackMeta:
    title = audio_path.stem
    artist = ""
    album = ""
    genre = ""
    year = 0
    bpm = 0.0
    duration = 0

    if TinyTag is not None:
        try:
            tag = TinyTag.get(str(audio_path))
            title = getattr(tag, "title", None) or title
            artist = getattr(tag, "artist", None) or ""
            album = getattr(tag, "album", None) or ""
            genre = getattr(tag, "genre", None) or ""
            year_value = getattr(tag, "year", None)
            if year_value:
                try:
                    year = int(str(year_value)[:4])
                except ValueError:
                    year = 0
            bpm_value = getattr(tag, "bpm", None)
            if bpm_value:
                try:
                    bpm = float(bpm_value)
                except ValueError:
                    bpm = 0.0
            duration_value = getattr(tag, "duration", None)
            if duration_value:
                duration = int(duration_value)
        except Exception:
            pass

    return TrackMeta(
        path=str(audio_path),
        title=title,
        artist=artist,
        album=album,
        genre=genre,
        year=year,
        bpm=bpm,
        duration=duration,
    )


def windows_to_rekordbox_location(file_path: Path, music_root: Path) -> str:
    absolute_path = file_path.resolve().as_posix()
    if absolute_path.startswith("/"):
        absolute_path = absolute_path[1:]
    return f"file://localhost/{quote(absolute_path, safe='/:')}"


def build_playlist_tree(tracks_root: Path, collection_name: str, progress_callback=None):
    track_paths = scan_tracks(tracks_root, progress_callback=progress_callback)
    tracks_by_folder: dict[Path, list[Path]] = {}
    for track_path in track_paths:
        folder = track_path.parent
        tracks_by_folder.setdefault(folder, []).append(track_path)

    return {
        "collection_name": collection_name,
        "root": tracks_root,
        "folders": tracks_by_folder,
        "tracks": track_paths,
    }


def create_rekordbox_xml(tracks_root: Path, output_file: Path, collection_name: str = "Pioneer Sync", progress_callback=None):
    if progress_callback:
        progress_callback("Escaneando carpeta...", 0.03)
    data = build_playlist_tree(tracks_root, collection_name, progress_callback=progress_callback)
    if progress_callback:
        progress_callback(f"Procesando {len(data['tracks'])} pistas...", 0.2)

    root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")
    product = ET.SubElement(root, "PRODUCT", Name="rekordbox", Version="7")
    collection = ET.SubElement(root, "COLLECTION", Entries=str(len(data["tracks"])))

    track_id_map: dict[Path, int] = {}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sorted_tracks = sorted(data["tracks"])
    max_workers = min(32, max(4, (os.cpu_count() or 4) * 2))
    metadata_results: list[tuple[int, Path, TrackMeta]] = []
    if progress_callback:
        progress_callback(f"Leyendo metadatos con {max_workers} hilos...", 0.22)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(read_metadata, track_path): (index, track_path) for index, track_path in enumerate(sorted_tracks, start=1)}
        completed = 0
        total = len(futures)
        for future in as_completed(futures):
            index, track_path = futures[future]
            try:
                metadata_results.append((index, track_path, future.result()))
            except Exception:
                metadata_results.append((index, track_path, TrackMeta(str(track_path), track_path.stem, "", "", "", 0, 0.0, 0)))
            completed += 1
            if progress_callback and completed % 250 == 0:
                progress_callback(f"Leyendo metadatos... {completed}/{total}", 0.22 + (completed / total) * 0.48)

    metadata_results.sort(key=lambda item: item[0])
    for index, track_path, meta in metadata_results:
        track_id_map[track_path] = index
        location = windows_to_rekordbox_location(track_path, tracks_root)
        ET.SubElement(
            collection,
            "TRACK",
            TrackID=str(index),
            Name=meta.title,
            Artist=meta.artist,
            Album=meta.album,
            Genre=meta.genre,
            AverageBpm=f"{meta.bpm:.2f}" if meta.bpm else "",
            Year=str(meta.year) if meta.year else "",
            Kind=track_path.suffix.lstrip(".").upper(),
            Size=str(track_path.stat().st_size),
            TotalTime=str(meta.duration),
            Location=location,
            DateAdded=now,
        )
    if progress_callback:
        progress_callback("Construyendo playlists...", 0.72)

    playlists = ET.SubElement(root, "PLAYLISTS")
    root_node = ET.SubElement(playlists, "NODE", Type="0", Name="ROOT")

    folders_sorted = sorted(data["folders"].keys(), key=lambda p: (len(p.relative_to(tracks_root).parts), str(p).lower()))
    nodes_by_folder: dict[Path, ET.Element] = {}
    nodes_by_folder[tracks_root] = root_node

    def add_folder_chain(folder_path: Path) -> ET.Element:
        current_path = tracks_root
        current_node = root_node
        for part in folder_path.relative_to(tracks_root).parts:
            current_path = current_path / part
            if current_path not in nodes_by_folder:
                nodes_by_folder[current_path] = ET.SubElement(current_node, "NODE", Type="0", Name=part)
            current_node = nodes_by_folder[current_path]
        return current_node

    playlist_nodes: list[ET.Element] = []

    for folder in folders_sorted:
        parent_node = add_folder_chain(folder.parent if folder != tracks_root else tracks_root)
        playlist_node = ET.SubElement(parent_node, "NODE", Type="1", Name=folder.name, Entries=str(len(data["folders"][folder])), KeyType="0")
        for track_path in sorted(data["folders"][folder]):
            ET.SubElement(playlist_node, "TRACK", Key=str(track_id_map[track_path]))
        playlist_nodes.append(playlist_node)

    def count_nodes(node: ET.Element) -> int:
        return sum(1 for child in node if child.tag == "NODE")

    def set_counts(node: ET.Element) -> None:
        if node.get("Type") == "0":
            node.set("Count", str(count_nodes(node)))
        for child in node:
            if child.tag == "NODE":
                set_counts(child)

    set_counts(root_node)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ", level=0)
    if progress_callback:
        progress_callback("Escribiendo XML...", 0.9)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    tree.write(output_file, encoding="UTF-8", xml_declaration=True)
    if progress_callback:
        progress_callback("XML generado correctamente.", 1.0)


def load_config(config_file: Path) -> dict:
    if config_file.exists():
        return json.loads(config_file.read_text(encoding="utf-8"))
    return {}


def save_config(config_file: Path, data: dict) -> None:
    config_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate a rekordbox XML library from a music folder.")
    parser.add_argument("music_folder", help="Root folder containing audio files")
    parser.add_argument("-o", "--output", default="rekordbox_library.xml", help="Output XML file")
    parser.add_argument("-n", "--name", default="Pioneer Sync", help="Top-level playlist name")
    args = parser.parse_args()

    create_rekordbox_xml(Path(args.music_folder), Path(args.output), args.name)
