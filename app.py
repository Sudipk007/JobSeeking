import asyncio
import json
import os
import queue
import sys
import threading

import customtkinter as ctk
from dotenv import load_dotenv
from PIL import Image

# Resolve paths when running as a PyInstaller bundle or plain script
def _base_path() -> str:
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))


def _res(filename: str) -> str:
    """Return absolute path to a bundled resource file."""
    return os.path.join(_base_path(), filename)


# Load .env from bundle root or script directory
load_dotenv(_res(".env"))

# Import pipeline after env is loaded
from main import run, load_config, build_url  # noqa: E402

# ── Theme ─────────────────────────────────────────────────────────────────────
NAVY  = "#1B2A4A"
GOLD  = "#F5A623"
LIGHT = "#F7F8FA"
GREEN = "#16A34A"
RED   = "#DC2626"

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")


# ── Stdout redirector ─────────────────────────────────────────────────────────
class _QueueWriter:
    def __init__(self, q: queue.Queue):
        self.q = q

    def write(self, text: str):
        if text:
            self.q.put(text)

    def flush(self):
        pass


# ── Main app window ───────────────────────────────────────────────────────────
class JobScraperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Netnova Job Scraper")
        self.geometry("580x720")
        self.resizable(False, False)
        self.configure(fg_color=LIGHT)

        self._config = load_config(_res("config.json"))
        self._log_queue: queue.Queue = queue.Queue()
        self._old_stdout = None

        self._build_header()
        self._build_form()
        self._build_log_panel()
        self._build_status_bar()

        self.after(100, self._poll_log)

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=NAVY, corner_radius=0, height=76)
        header.pack(fill="x")
        header.pack_propagate(False)

        inner = ctk.CTkFrame(header, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=20)

        # Logo
        logo_path = _res(os.getenv("COMPANY_LOGO", "log.png"))
        if os.path.exists(logo_path):
            try:
                img = Image.open(logo_path)
                logo_ctk = ctk.CTkImage(light_image=img, size=(52, 52))
                ctk.CTkLabel(inner, image=logo_ctk, text="").pack(side="left", pady=12)
            except Exception:
                pass

        # Company name + tagline
        text_col = ctk.CTkFrame(inner, fg_color="transparent")
        text_col.pack(side="left", padx=14)
        company = os.getenv("COMPANY_NAME", "Netnova Tech Company")
        ctk.CTkLabel(text_col, text=company,
                     font=ctk.CTkFont(size=17, weight="bold"),
                     text_color="white").pack(anchor="w")
        ctk.CTkLabel(text_col, text="Job Intelligence Scraper",
                     font=ctk.CTkFont(size=11),
                     text_color="#8CA3C8").pack(anchor="w")

        # Gold accent bar under header
        ctk.CTkFrame(self, height=4, fg_color=GOLD, corner_radius=0).pack(fill="x")

    # ── Form ──────────────────────────────────────────────────────────────────
    def _build_form(self):
        card = ctk.CTkFrame(self, fg_color="white", corner_radius=12)
        card.pack(fill="x", padx=20, pady=16)

        pad = {"padx": 20}

        # City
        ctk.CTkLabel(card, text="City", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#555").pack(anchor="w", pady=(16, 2), **pad)
        self._city = ctk.CTkEntry(card, placeholder_text="e.g. New York, Chicago, Austin",
                                   height=40, font=ctk.CTkFont(size=13),
                                   border_color=NAVY, border_width=1)
        self._city.pack(fill="x", pady=(0, 12), **pad)

        # Source
        ctk.CTkLabel(card, text="Source", font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#555").pack(anchor="w", pady=(0, 4), **pad)
        src_row = ctk.CTkFrame(card, fg_color="transparent")
        src_row.pack(fill="x", pady=(0, 12), **pad)
        self._source = ctk.StringVar(value=self._config.get("scraper", "both"))
        for val, label in [("indeed", "Indeed"), ("linkedin", "LinkedIn"), ("both", "Both")]:
            ctk.CTkRadioButton(src_row, text=label, value=val, variable=self._source,
                               font=ctk.CTkFont(size=13),
                               fg_color=NAVY, hover_color=GOLD,
                               border_color=NAVY).pack(side="left", padx=(0, 20))

        # Job Title / Keywords
        ctk.CTkLabel(card, text="Job Title / Keywords",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#555").pack(anchor="w", pady=(0, 2), **pad)
        default_kw = self._config.get("sites", {}).get("indeed", {}).get("keywords", "")
        self._keywords = ctk.CTkEntry(card, height=40, font=ctk.CTkFont(size=13),
                                       border_color=NAVY, border_width=1,
                                       placeholder_text="e.g. Software Engineer, CCNA, Data Analyst")
        self._keywords.insert(0, default_kw)
        self._keywords.pack(fill="x", pady=(0, 12), **pad)

        # Max results
        ctk.CTkLabel(card, text="Max Results per Source",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#555").pack(anchor="w", pady=(0, 2), **pad)
        self._max_items = ctk.CTkEntry(card, height=40, width=90,
                                        font=ctk.CTkFont(size=13),
                                        border_color=NAVY, border_width=1)
        default_max = str(self._config.get("sites", {}).get("indeed", {}).get("max_items", 30))
        self._max_items.insert(0, default_max)
        self._max_items.pack(anchor="w", pady=(0, 16), **pad)

        # Run button
        self._run_btn = ctk.CTkButton(card, text="▶   Run Scraper", height=50,
                                       font=ctk.CTkFont(size=15, weight="bold"),
                                       fg_color=NAVY, hover_color=GOLD,
                                       text_color="white", corner_radius=8,
                                       command=self._on_run)
        self._run_btn.pack(fill="x", padx=20, pady=(0, 20))

    # ── Log panel ─────────────────────────────────────────────────────────────
    def _build_log_panel(self):
        ctk.CTkLabel(self, text="Progress Log",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color="#555").pack(anchor="w", padx=20, pady=(0, 4))

        self._log = ctk.CTkTextbox(self, height=200,
                                    font=ctk.CTkFont(family="Courier", size=11),
                                    fg_color="white", text_color="#222",
                                    border_color="#E8EBF0", border_width=1,
                                    state="disabled", wrap="word", corner_radius=8)
        self._log.pack(fill="both", expand=True, padx=20, pady=(0, 8))

    # ── Status bar ────────────────────────────────────────────────────────────
    def _build_status_bar(self):
        bar = ctk.CTkFrame(self, fg_color="white", corner_radius=8, height=36)
        bar.pack(fill="x", padx=20, pady=(0, 16))
        bar.pack_propagate(False)
        self._status = ctk.CTkLabel(bar, text="● Ready",
                                     font=ctk.CTkFont(size=12),
                                     text_color=GREEN)
        self._status.pack(side="left", padx=16)

    # ── Run handler ───────────────────────────────────────────────────────────
    def _on_run(self):
        try:
            self._do_run()
        except Exception as exc:
            # Catch any exception in the UI thread and show it in the log
            self._restore_stdout()
            self._run_btn.configure(state="normal", text="▶   Run Scraper")
            self._status.configure(text="✗  Error", text_color=RED)
            self._append_log(f"\n✗  Unexpected error: {exc}\n")

    def _do_run(self):
        city = self._city.get().strip()
        if not city:
            self._append_log("⚠  Please enter a city before running.\n")
            return

        try:
            max_items = int(self._max_items.get() or 30)
        except ValueError:
            self._append_log("⚠  Max results must be a whole number.\n")
            return

        import copy
        cfg = copy.deepcopy(self._config)
        cfg["scraper"] = self._source.get()
        keywords = self._keywords.get().strip()
        for site in ("indeed", "linkedin"):
            cfg["sites"][site]["keywords"] = keywords
            cfg["sites"][site]["max_items"] = max_items

        # Lock UI and show immediate feedback
        self._run_btn.configure(state="disabled", text="⟳  Running…")
        self._status.configure(text="⟳  Running…", text_color=GOLD)
        self._clear_log()
        self._append_log(f"Starting scraper: {cfg['scraper'].upper()}  |  City: {city}\n")
        self._append_log(f"Job Title / Keywords: {keywords}\n")
        self._append_log("─" * 55 + "\n")

        # Redirect stdout → queue so print() from scrapers appears in the log
        self._old_stdout = sys.stdout
        sys.stdout = _QueueWriter(self._log_queue)

        def worker():
            try:
                # Use explicit event loop — more reliable than asyncio.run() in threads
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(run(cfg, city=city))
                finally:
                    loop.close()
                self._log_queue.put("__DONE__")
            except SystemExit:
                self._log_queue.put("__ERROR__Scraper stopped early — see log above.")
            except Exception as exc:
                import traceback
                self._log_queue.put(f"__ERROR__{type(exc).__name__}: {exc}\n{traceback.format_exc()}")

        threading.Thread(target=worker, daemon=True).start()

    # ── Queue polling ─────────────────────────────────────────────────────────
    def _poll_log(self):
        try:
            while True:
                msg = self._log_queue.get_nowait()
                if msg == "__DONE__":
                    self._restore_stdout()
                    self._append_log("\n✓  Done! Check your email for the report.\n")
                    self._run_btn.configure(state="normal", text="▶   Run Scraper")
                    self._status.configure(text="✓  Done", text_color=GREEN)
                elif msg.startswith("__ERROR__"):
                    self._restore_stdout()
                    err = msg[len("__ERROR__"):]
                    self._append_log(f"\n✗  {err}\n")
                    self._run_btn.configure(state="normal", text="▶   Run Scraper")
                    self._status.configure(text="✗  Error — see log", text_color=RED)
                else:
                    self._append_log(msg)
        except queue.Empty:
            pass
        except Exception:
            pass  # Never let a display error stop the polling loop
        finally:
            self.after(100, self._poll_log)  # Always reschedule, no matter what

    def _restore_stdout(self):
        if self._old_stdout is not None:
            sys.stdout = self._old_stdout
            self._old_stdout = None

    def _append_log(self, text: str):
        self._log.configure(state="normal")
        self._log.insert("end", text)
        self._log.see("end")
        self._log.configure(state="disabled")

    def _clear_log(self):
        self._log.configure(state="normal")
        self._log.delete("1.0", "end")
        self._log.configure(state="disabled")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = JobScraperApp()
    app.mainloop()
