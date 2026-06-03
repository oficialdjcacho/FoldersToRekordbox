import json
import os
import locale
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from folders_to_rekordbox import create_rekordbox_xml


APP_NAME = "Folders to Rekordbox"
CONFIG_FILE = "pioneer_sync_config.json"
BG = "#1E1E1E"
PANEL = "#2A2A2A"
PANEL_2 = "#333333"
TEXT = "#F0F0F0"
TEXT_DIM = "#A8A8A8"
ACCENT = "#2D7DFF"
ACCENT_HOVER = "#1F6FFF"
ACCENT_TEXT = "#FFFFFF"


STRINGS = {
    "en": {
        "title": APP_NAME,
        "music_folder": "Music folder:",
        "output_file": "XML output file:",
        "collection_name": "Collection name:",
        "browse": "Browse",
        "save_as": "Save as",
        "generate": "Generate XML",
        "ready": "Ready to export.",
        "select_music": "Select a music folder.",
        "music_missing": "The music folder does not exist.",
        "generating": "Generating XML...",
        "done": "XML generated successfully.",
        "ok_title": "OK",
        "ok_msg": "File generated:\n{}",
        "error_title": "Error",
    },
    "es": {
        "title": APP_NAME,
        "music_folder": "Carpeta de música:",
        "output_file": "Archivo XML de salida:",
        "collection_name": "Nombre de la colección:",
        "browse": "Buscar",
        "save_as": "Guardar como",
        "generate": "Generar XML",
        "ready": "Listo para exportar.",
        "select_music": "Selecciona una carpeta de música.",
        "music_missing": "La carpeta de música no existe.",
        "generating": "Generando XML...",
        "done": "XML generado correctamente.",
        "ok_title": "OK",
        "ok_msg": "Archivo generado:\n{}",
        "error_title": "Error",
    },
}


def detect_language() -> str:
    try:
        if os.name == "nt":
            import ctypes

            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            lang = locale.windows_locale.get(lang_id, "en_US")
        else:
            lang, _ = locale.getdefaultlocale()
        if lang:
            code = lang.split("_")[0].lower()
            if code in STRINGS:
                return code
    except Exception:
        pass
    return "en"


class PioneerSyncApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        ctk.set_appearance_mode("Dark")
        self.title(APP_NAME)
        self.geometry("720x500")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        self.lang = detect_language()
        self.txt = STRINGS[self.lang]

        icon_path = Path(__file__).with_name("rekordbox.ico")
        if os.name == "nt" and icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

        self.music_folder = ctk.StringVar()
        self.output_file = ctk.StringVar(value=str(Path("Pioneer_Sync") / "rekordbox_library.xml"))
        self.collection_name = ctk.StringVar(value=APP_NAME)
        self.status_var = ctk.StringVar(value=self.txt["ready"])

        self._load_config()
        self._build_ui()

    def _build_ui(self):
        logo_path = Path(__file__).with_name("rekordbox.webp")
        ctk.CTkLabel(self, text=APP_NAME, font=ctk.CTkFont(size=24, weight="bold"), text_color=ACCENT).pack(pady=(20, 10))

        frame = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=14)
        frame.pack(padx=25, pady=10, fill="x")

        ctk.CTkLabel(frame, text=self.txt["music_folder"], font=ctk.CTkFont(weight="bold"), text_color=TEXT).grid(row=0, column=0, padx=15, pady=(15, 2), sticky="w")
        ctk.CTkEntry(frame, textvariable=self.music_folder, width=470, fg_color=PANEL_2, border_color="#4A4A4A", text_color=TEXT).grid(row=1, column=0, padx=15, pady=(0, 12), sticky="w")
        ctk.CTkButton(frame, text=self.txt["browse"], width=100, fg_color=ACCENT, text_color=ACCENT_TEXT, hover_color=ACCENT_HOVER, command=self._browse_music).grid(row=1, column=1, padx=(0, 15), pady=(0, 12))

        ctk.CTkLabel(frame, text=self.txt["output_file"], font=ctk.CTkFont(weight="bold"), text_color=TEXT).grid(row=2, column=0, padx=15, pady=(0, 2), sticky="w")
        ctk.CTkEntry(frame, textvariable=self.output_file, width=470, fg_color=PANEL_2, border_color="#4A4A4A", text_color=TEXT).grid(row=3, column=0, padx=15, pady=(0, 12), sticky="w")
        ctk.CTkButton(frame, text=self.txt["save_as"], width=100, fg_color=ACCENT, text_color=ACCENT_TEXT, hover_color=ACCENT_HOVER, command=self._browse_output).grid(row=3, column=1, padx=(0, 15), pady=(0, 12))

        ctk.CTkLabel(frame, text=self.txt["collection_name"], font=ctk.CTkFont(weight="bold"), text_color=TEXT).grid(row=4, column=0, padx=15, pady=(0, 2), sticky="w")
        ctk.CTkEntry(frame, textvariable=self.collection_name, width=470, fg_color=PANEL_2, border_color="#4A4A4A", text_color=TEXT).grid(row=5, column=0, padx=15, pady=(0, 18), sticky="w")

        self.status_label = ctk.CTkLabel(self, textvariable=self.status_var, font=ctk.CTkFont(size=14), text_color=TEXT)
        self.status_label.pack(pady=(10, 4))

        self.progress = ctk.CTkProgressBar(self, width=620, height=12, progress_color=ACCENT)
        self.progress.pack(pady=(2, 3))
        self.progress.set(0)
        self.progress_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=12), text_color=TEXT_DIM)
        self.progress_label.pack(pady=(2, 0))

        self.export_button = ctk.CTkButton(
            self,
            text=self.txt["generate"],
            font=ctk.CTkFont(size=16, weight="bold"),
            height=45,
            fg_color=ACCENT,
            text_color=ACCENT_TEXT,
            hover_color=ACCENT_HOVER,
            command=self._start_export,
        )
        self.export_button.pack(pady=(15, 10), fill="x", padx=60)

    def _browse_music(self):
        folder = filedialog.askdirectory()
        if folder:
            self.music_folder.set(folder)
            self._save_config()

    def _browse_output(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xml",
            filetypes=[("XML", "*.xml")],
            initialfile="rekordbox_library.xml",
        )
        if file_path:
            self.output_file.set(file_path)
            self._save_config()

    def _set_status(self, text: str, progress: float | None = None):
        def apply():
            self.status_var.set(text)
            self.progress_label.configure(text=text)
            if progress is not None:
                self.progress.set(progress)

        self.after(0, apply)

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                data = json.loads(Path(CONFIG_FILE).read_text(encoding="utf-8"))
                self.music_folder.set(data.get("music_folder", ""))
                self.output_file.set(data.get("output_file", self.output_file.get()))
                self.collection_name.set(data.get("collection_name", self.collection_name.get()))
            except Exception:
                pass

    def _save_config(self):
        data = {
            "music_folder": self.music_folder.get(),
            "output_file": self.output_file.get(),
            "collection_name": self.collection_name.get(),
        }
        try:
            Path(CONFIG_FILE).write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _start_export(self):
        if not self.music_folder.get():
            messagebox.showerror(self.txt["error_title"], self.txt["select_music"])
            return
        if not Path(self.music_folder.get()).exists():
            messagebox.showerror(self.txt["error_title"], self.txt["music_missing"])
            return

        self.export_button.configure(state="disabled")
        self.progress.set(0)
        self.progress.configure(mode="determinate")
        self._set_status(self.txt["generating"])
        self._save_config()
        threading.Thread(target=self._export_worker, daemon=True).start()

    def _export_worker(self):
        try:
            create_rekordbox_xml(
                Path(self.music_folder.get()),
                Path(self.output_file.get()),
                self.collection_name.get().strip() or "Rekordbox Folder to Playlist",
                progress_callback=lambda text, value: self._set_status(text, value),
            )
            self.after(0, self._export_done)
        except Exception as exc:
            self.after(0, lambda: self._export_failed(str(exc)))

    def _export_done(self):
        self.progress.set(1)
        self._set_status(self.txt["done"], 1)
        self.progress.configure(mode="determinate")
        self.export_button.configure(state="normal")
        messagebox.showinfo(self.txt["ok_title"], self.txt["ok_msg"].format(self.output_file.get()))

    def _export_failed(self, error_text: str):
        self.export_button.configure(state="normal")
        self._set_status(error_text)
        messagebox.showerror("Error", error_text)


if __name__ == "__main__":
    app = PioneerSyncApp()
    app.mainloop()
