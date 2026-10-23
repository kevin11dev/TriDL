import customtkinter as ctk
import yt_dlp
import threading
import os
import re

# ── Theme ────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

PLATFORMS = {
    "tiktok":    {"label": "🎵  TikTok  •  No Watermark", "color": "#ff0050"},
    "youtube":   {"label": "▶️  YouTube",                  "color": "#ff0000"},
    "instagram": {"label": "📸  Instagram",                "color": "#c13584"},
}

DOWNLOAD_FOLDER = os.path.join(os.path.expanduser("~"), "Downloads", "VideoDownloader")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


def detect_platform(url: str) -> str:
    if "tiktok.com"   in url: return "tiktok"
    if "youtube.com"  in url or "youtu.be" in url: return "youtube"
    if "instagram.com" in url: return "instagram"
    return "unknown"


def get_ydl_opts(platform: str, output_path: str) -> dict:
    base = {"outtmpl": output_path, "quiet": True, "no_warnings": True}
    if platform == "tiktok":
        base["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]"
        base["extractor_args"] = {"tiktok": {"webpage_download": True}}
    elif platform == "youtube":
        base["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]"
        base["merge_output_format"] = "mp4"
    elif platform == "instagram":
        base["format"] = "best[ext=mp4]/best"
    return base


# ── Main Window ──────────────────────────────────────────
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("TriDL")
        self.geometry("540x420")
        self.resizable(False, False)

        # ── Title ──
        ctk.CTkLabel(self, text="⬇  TriDL",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(30, 4))
        ctk.CTkLabel(self, text="Paste a YouTube, TikTok, or Instagram link",
                     font=ctk.CTkFont(size=13), text_color="gray").pack()

        # ── Platform badge ──
        self.badge = ctk.CTkLabel(self, text="Paste a link below",
                                  font=ctk.CTkFont(size=12),
                                  fg_color="#2b2b2b", corner_radius=12,
                                  padx=12, pady=4)
        self.badge.pack(pady=(16, 0))

        # ── URL entry ──
        self.url_var = ctk.StringVar()
        self.url_var.trace_add("write", self._on_url_change)
        self.entry = ctk.CTkEntry(self, textvariable=self.url_var,
                                  placeholder_text="https://...",
                                  width=440, height=44,
                                  font=ctk.CTkFont(size=13))
        self.entry.pack(pady=(14, 0))

        # ── Folder row ──
        folder_frame = ctk.CTkFrame(self, fg_color="transparent")
        folder_frame.pack(pady=(10, 0))
        self.folder_label = ctk.CTkLabel(folder_frame,
                                         text=f"📁  {DOWNLOAD_FOLDER}",
                                         font=ctk.CTkFont(size=11),
                                         text_color="gray", wraplength=340)
        self.folder_label.pack(side="left", padx=(0, 8))
        ctk.CTkButton(folder_frame, text="Change", width=70, height=26,
                      command=self._pick_folder).pack(side="left")

        # ── Download button ──
        self.btn = ctk.CTkButton(self, text="Download", width=440, height=46,
                                 font=ctk.CTkFont(size=15, weight="bold"),
                                 command=self._start_download)
        self.btn.pack(pady=(18, 0))

        # ── Progress bar ──
        self.progress = ctk.CTkProgressBar(self, width=440)
        self.progress.set(0)
        self.progress.pack(pady=(14, 0))

        # ── Status label ──
        self.status = ctk.CTkLabel(self, text="",
                                   font=ctk.CTkFont(size=12),
                                   wraplength=440)
        self.status.pack(pady=(10, 0))

        self._save_folder = DOWNLOAD_FOLDER

    # ── Helpers ──────────────────────────────────────────
    def _on_url_change(self, *_):
        url = self.url_var.get()
        platform = detect_platform(url)
        if platform in PLATFORMS:
            info = PLATFORMS[platform]
            self.badge.configure(text=info["label"],
                                 fg_color=info["color"],
                                 text_color="white")
        else:
            self.badge.configure(text="Paste a link below",
                                 fg_color="#2b2b2b",
                                 text_color="gray")

    def _pick_folder(self):
        from tkinter import filedialog
        folder = filedialog.askdirectory(initialdir=self._save_folder)
        if folder:
            self._save_folder = folder
            self.folder_label.configure(text=f"📁  {folder}")

    def _set_status(self, msg: str, color: str = "white"):
        self.status.configure(text=msg, text_color=color)

    def _start_download(self):
        url = self.url_var.get().strip()
        if not url:
            self._set_status("⚠  Please enter a URL.", "orange"); return

        platform = detect_platform(url)
        if platform == "unknown":
            self._set_status("❌  Unsupported platform. Use YouTube, TikTok, or Instagram.", "#ff6b6b")
            return

        self.btn.configure(state="disabled", text="Downloading…")
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self._set_status("⏳  Downloading, please wait…", "#88aaff")

        threading.Thread(target=self._download_worker,
                         args=(url, platform), daemon=True).start()

    def _download_worker(self, url: str, platform: str):
        # Sanitise filename — use video title if possible
        safe = re.sub(r'[\\/*?:"<>|]', "_", url.split("?")[0].split("/")[-1]) or "video"
        output_path = os.path.join(self._save_folder, f"{safe}.%(ext)s")
        opts = get_ydl_opts(platform, output_path)

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            self.after(0, self._on_success)
        except Exception as e:
            self.after(0, self._on_error, str(e))

    def _on_success(self):
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(1)
        self._set_status(f"✅  Saved to {self._save_folder}", "#4cff91")
        self.btn.configure(state="normal", text="Download")
        self.url_var.set("")
        self.badge.configure(text="Paste a link below",
                             fg_color="#2b2b2b", text_color="gray")

    def _on_error(self, msg: str):
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress.set(0)
        self._set_status(f"❌  {msg}", "#ff6b6b")
        self.btn.configure(state="normal", text="Download")


if __name__ == "__main__":
    app = App()
    app.mainloop()