import os

os.environ.setdefault("ALSA_CONF_PATH", "/dev/null")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("JACK_NO_START_SERVER", "1")
os.environ.setdefault("PA_ALSA_PLUGINS_SO", "")

import json
import queue
import re
import subprocess
import threading
import time

import speech_recognition as sr
import tkinter as tk
from tkinter import BOTH, LEFT, RIGHT, X, StringVar
import tkinter.font as tkfont
from pynput import keyboard as pynput_keyboard


HOME_DIR = "/home/kitretsu"
OPENCLAW_BIN = f"{HOME_DIR}/.nvm/versions/node/v24.14.0/bin/openclaw"
OPENCLAW_PATH = f"{HOME_DIR}/.nvm/versions/node/v24.14.0/bin"

WAKE_RE = re.compile(r"\b(?:chhotu|chotu|chodu)\b", re.IGNORECASE)
WAKE_ONLY_RE = re.compile(r"^\s*(?:chhotu|chotu|chodu)\s*$", re.IGNORECASE)


class PopupWin:
    def __init__(self):
        self.ui_queue = queue.Queue()
        self.thread = None
        self.running = False
        self.root = None
        self.entry_var = None
        self.entry_widget = None
        self.hide_job = None
        self.hovering = False
        self.visible_kind = "idle"

        self.action_event = threading.Event()
        self.action_type = None
        self.action_text = ""
        self.input_mode = "voice"

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        while self.root is None and self.running:
            time.sleep(0.05)

    def _run(self):
        self.root = tk.Tk()
        self.root.title("CHHOTU ASSISTANT")
        self.root.withdraw()
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.96)
        self.root.configure(bg="#111318")
        self.root.after(40, self._pump)
        self.root.mainloop()

    def _pump(self):
        if not self.running:
            return

        try:
            while True:
                action, payload = self.ui_queue.get_nowait()
                if action == "render":
                    self._render(payload)
                elif action == "hide":
                    self._hide_now()
                elif action == "quit":
                    self.running = False
                    if self.root is not None:
                        self.root.quit()
                    return
        except queue.Empty:
            pass

        if self.running and self.root is not None:
            self.root.after(40, self._pump)

    def _cancel_hide_job(self):
        if self.hide_job is not None and self.root is not None:
            try:
                self.root.after_cancel(self.hide_job)
            except Exception:
                pass
        self.hide_job = None

    def _release_grab(self):
        if self.root is not None:
            try:
                if self.root.grab_current() is not None:
                    self.root.grab_release()
            except Exception:
                pass

    def _bind_hover(self, widget):
        if widget is None:
            return
        try:
            widget.bind("<Enter>", self._on_hover_enter)
            widget.bind("<Leave>", self._on_hover_leave)
        except Exception:
            pass

    def _text_size(self, text, font_obj, max_width):
        lines = text.splitlines() or [text]
        measured_width = 0
        wrapped_lines = 0
        for line in lines:
            if not line.strip():
                wrapped_lines += 1
                continue
            current = ""
            segments = []
            for word in line.split():
                trial = f"{current} {word}".strip()
                if current and font_obj.measure(trial) > max_width:
                    segments.append(current)
                    current = word
                else:
                    current = trial
            if current:
                segments.append(current)
            wrapped_lines += len(segments)
            for segment in segments:
                measured_width = max(measured_width, font_obj.measure(segment))
        return measured_width, max(1, wrapped_lines)

    def _compute_geometry(self, payload):
        title = payload.get("title", "CHOTU")
        body = payload.get("body", "")
        footer = payload.get("footer", "")
        show_entry = payload.get("show_entry", False)

        title_font = tkfont.Font(family="Arial", size=12, weight="bold")
        body_font = tkfont.Font(family="Arial", size=10)
        footer_font = tkfont.Font(family="Arial", size=9)

        width_candidates = [
            title_font.measure(title) + 140,
            body_font.measure(body.replace("\n", " ")) + 60,
            footer_font.measure(footer.replace("\n", " ")) + 60,
        ]

        measured_body_width, body_lines = self._text_size(body, body_font, 420)
        measured_footer_width, footer_lines = self._text_size(footer, footer_font, 420)

        width = max(320, min(560, max(width_candidates + [measured_body_width + 70, measured_footer_width + 70])))

        base_height = 108 if not show_entry else 156
        height = base_height + (body_lines * 18) + (footer_lines * 14)
        if show_entry:
            height += 42
        return width, min(360, height)

    def _place_window(self, width, height):
        if self.root is None:
            return
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(0, sw - width - 24)
        y = max(0, sh - height - 56)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _render(self, payload):
        if self.root is None:
            return

        self._cancel_hide_job()
        self._release_grab()
        self.hovering = False
        self.visible_kind = payload.get("mode", "idle")
        for child in self.root.winfo_children():
            child.destroy()

        mode = payload.get("mode", "listening")
        title = payload.get("title", "CHOTU")
        body = payload.get("body", "CHHOTU")
        accent = payload.get("accent", "#89b4fa")
        show_entry = payload.get("show_entry", False)
        allow_voice = payload.get("allow_voice", True)
        auto_hide_ms = payload.get("auto_hide_ms")
        status_text = payload.get("status_text", mode.upper())

        width, height = self._compute_geometry(payload)
        self._place_window(width, height)

        self.root.overrideredirect(False)

        shell = tk.Frame(self.root, bg=accent, bd=0, highlightthickness=0)
        shell.pack(fill=BOTH, expand=True, padx=2, pady=2)

        card = tk.Frame(shell, bg="#111318", padx=16, pady=14)
        card.pack(fill=BOTH, expand=True)

        top = tk.Frame(card, bg="#111318")
        top.pack(fill=X)

        tk.Label(
            top,
            text=title,
            font=("Arial", 12, "bold"),
            bg="#111318",
            fg=accent,
        ).pack(side=LEFT)
        tk.Label(
            top,
            text=status_text,
            font=("Arial", 9, "bold"),
            bg="#111318",
            fg=accent,
        ).pack(side=RIGHT)

        tk.Label(
            card,
            text=body,
            font=("Arial", 10),
            bg="#111318",
            fg="#dbe1f2",
            wraplength=max(260, width - 70),
            justify=LEFT,
        ).pack(anchor="w", pady=(10, 8))

        if show_entry:
            self.input_mode = "voice"
            self.entry_var = StringVar(value=payload.get("preset", ""))
            self.entry_widget = tk.Entry(
                card,
                textvariable=self.entry_var,
                font=("Arial", 11),
                bg="#232634",
                fg="#ffffff",
                insertbackground="#ffffff",
                relief="flat",
                highlightthickness=1,
                highlightbackground="#3a3f55",
                highlightcolor=accent,
                takefocus=1,
            )
            self.entry_widget.pack(fill=X, pady=(0, 8))

            button_row = tk.Frame(card, bg="#111318")
            button_row.pack(fill=X)

            def submit(_event=None):
                text = self.entry_var.get().strip()
                if not text:
                    return
                self.action_text = text
                self.action_type = "submit"
                self.input_mode = "typed"
                self.action_event.set()

            def use_voice():
                if allow_voice:
                    self.action_text = ""
                    self.action_type = "voice"
                    self.input_mode = "voice"
                    self.action_event.set()

            def cancel():
                self.action_text = ""
                self.action_type = "cancel"
                self.input_mode = "cancel"
                self.action_event.set()

            def mark_typed(_event=None):
                if self.input_mode != "cancel":
                    self.input_mode = "typed"

            def activate_typing(_event=None):
                mark_typed()
                if self.root is not None:
                    self.root.after_idle(self.root.focus_force)
                    self.root.after_idle(self.entry_widget.focus_set)
                    self.root.after_idle(self.entry_widget.focus_force)
                    self.root.after_idle(self.entry_widget.icursor, tk.END)
                return None

            self.entry_widget.bind("<Return>", submit)
            self.entry_widget.bind("<Escape>", lambda _e: cancel())
            self.entry_widget.bind("<FocusIn>", mark_typed)
            self.entry_widget.bind("<Button-1>", activate_typing)
            self.entry_widget.bind("<ButtonRelease-1>", activate_typing)
            self.entry_widget.bind("<Key>", mark_typed)
            self._bind_hover(self.entry_widget)

            tk.Button(
                button_row,
                text="Use Voice",
                command=use_voice,
                bg="#394057",
                fg="#ffffff",
                activebackground="#4b5470",
                activeforeground="#ffffff",
                relief="flat",
                padx=10,
                pady=3,
            ).pack(side=LEFT)
            tk.Button(
                button_row,
                text="Cancel",
                command=cancel,
                bg="#394057",
                fg="#ffffff",
                activebackground="#4b5470",
                activeforeground="#ffffff",
                relief="flat",
                padx=10,
                pady=3,
            ).pack(side=RIGHT)
            self._bind_hover(button_row)
        else:
            tk.Label(
                card,
                text=payload.get("footer", ""),
                font=("Arial", 9),
                bg="#111318",
                fg="#9aa4bf",
                wraplength=max(260, width - 70),
                justify=LEFT,
            ).pack(anchor="w", pady=(2, 0))

        self._bind_hover(shell)
        self._bind_hover(card)
        self._bind_hover(top)

        self.root.deiconify()
        self.root.update_idletasks()
        self.root.lift()
        self.root.attributes("-topmost", True)
        try:
            self.root.focus_force()
        except Exception:
            pass
        if show_entry and self.entry_widget is not None:
            try:
                self.entry_widget.focus_set()
            except Exception:
                pass

        self.root.bind("<Enter>", self._on_hover_enter)
        self.root.bind("<Leave>", self._on_hover_leave)
        if show_entry and self.entry_widget is not None:
            self.entry_widget.bind("<Enter>", self._on_hover_enter)
            self.entry_widget.bind("<Leave>", self._on_hover_leave)
        if auto_hide_ms:
            self._schedule_hide(auto_hide_ms)
        self.root.update()

    def _schedule_hide(self, delay_ms):
        self._cancel_hide_job()
        if self.root is not None and not self.hovering:
            self.hide_job = self.root.after(delay_ms, self._hide_now)

    def _on_hover_enter(self, _event=None):
        self.hovering = True
        self._cancel_hide_job()

    def _on_hover_leave(self, _event=None):
        self.hovering = False
        if self.visible_kind in ("done", "error") and self.root is not None:
            self._schedule_hide(2000)

    def _hide_now(self):
        self._cancel_hide_job()
        self._release_grab()
        if self.root is not None:
            self.root.withdraw()

    def show_command(self, mode, body, allow_voice=True, preset=""):
        self.action_event.clear()
        self.action_type = None
        self.action_text = ""
        status_text = "VOICE LISTENING NOW"
        self.ui_queue.put(
            (
                "render",
                {
                    "mode": mode,
                    "title": "CHOTU",
                    "status_text": status_text,
                    "body": body,
                    "show_entry": True,
                    "allow_voice": allow_voice,
                    "preset": preset,
                    "accent": "#a6e3a1" if mode == "listening" else "#cba6f7",
                    "footer": "Speak now. Click the box only if you want to type.",
                },
            )
        )

    def show_processing(self, body):
        self.ui_queue.put(
            (
                "render",
                {
                    "mode": "processing",
                    "title": "CHOTU",
                    "status_text": "RUNNING",
                    "body": body,
                    "show_entry": False,
                    "allow_voice": False,
                    "accent": "#fab387",
                    "footer": "",
                },
            )
        )

    def show_result(self, body, error=False):
        self.ui_queue.put(
            (
                "render",
                {
                    "mode": "error" if error else "done",
                    "title": "CHOTU",
                    "status_text": "ERROR" if error else "DONE",
                    "body": body,
                    "show_entry": False,
                    "allow_voice": False,
                    "accent": "#f38ba8" if error else "#89b4fa",
                    "footer": "",
                    "auto_hide_ms": 2000,
                },
            )
        )

    def hide(self):
        self.ui_queue.put(("hide", None))

    def signal_cancel(self):
        self.action_text = ""
        self.action_type = "cancel"
        self.input_mode = "cancel"
        self.action_event.set()

    def wait_for_action(self, timeout=None):
        if not self.action_event.wait(timeout):
            return None, ""
        return self.action_type, self.action_text

    def get_input_mode(self):
        return self.input_mode


class Chotu:
    def __init__(self):
        self.state_lock = threading.Lock()
        self.state = "idle"
        self.session_id = 0
        self.command_cancel = threading.Event()

        self.popup = PopupWin()
        self.popup.start()

        self.wake_recognizer = sr.Recognizer()
        self.command_recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()

        self.wake_recognizer.energy_threshold = 400
        self.wake_recognizer.pause_threshold = 0.8
        self.wake_recognizer.dynamic_energy_threshold = True

        self.command_recognizer.energy_threshold = 400
        self.command_recognizer.pause_threshold = 0.8
        self.command_recognizer.dynamic_energy_threshold = True

        with self.microphone as source:
            self.wake_recognizer.adjust_for_ambient_noise(source, duration=1.2)

        self.keyboard_listener = pynput_keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self.keyboard_listener.start()

        self.alt_down_at = None

        self._main_loop()

    def _get_state(self):
        with self.state_lock:
            return self.state

    def _set_state(self, new_state):
        with self.state_lock:
            self.state = new_state

    def _bump_session(self):
        with self.state_lock:
            self.session_id += 1
            return self.session_id

    def _session_matches(self, session_id):
        with self.state_lock:
            return self.session_id == session_id

    def _current_state_and_session(self):
        with self.state_lock:
            return self.state, self.session_id

    def _on_key_press(self, key):
        try:
            if key in (pynput_keyboard.Key.alt_l, pynput_keyboard.Key.alt_r):
                if self.alt_down_at is None:
                    self.alt_down_at = time.time()
        except Exception:
            pass

    def _on_key_release(self, key):
        try:
            if key in (pynput_keyboard.Key.alt_l, pynput_keyboard.Key.alt_r):
                if self.alt_down_at is None:
                    return
                held_for = time.time() - self.alt_down_at
                self.alt_down_at = None
                threading.Thread(
                    target=self._handle_alt_hold,
                    args=(held_for,),
                    daemon=True,
                ).start()
        except Exception:
            pass

    def _handle_alt_hold(self, held_for):
        state = self._get_state()
        if state == "processing":
            return

        if held_for < 1.0:
            return

        if state in ("listening", "typing"):
            self._cancel_session()
            return

        if state == "idle":
            self._start_command_session(
                mode="voice",
                allow_voice=True,
                prompt="Say or type a command.",
                replace=True,
            )

    def _normalize_text(self, text):
        return " ".join(text.lower().split())

    def _extract_command(self, text):
        text = self._normalize_text(text)
        match = WAKE_RE.search(text)
        if not match:
            return None

        tail = text[match.end():].strip(" ,.!?;:-")
        return tail or None

    def _contains_wake(self, text):
        return WAKE_RE.search(text) is not None

    def _start_command_session(self, mode, allow_voice, prompt, replace=False):
        state = self._get_state()
        if state == "processing":
            return

        if state in ("listening", "typing"):
            if not replace and mode == state:
                return
            self._cancel_session(silent=True)

        session_id = self._bump_session()
        self.command_cancel = threading.Event()
        self._set_state("typing" if mode == "typing" else "listening")
        self.popup.show_command(mode, prompt, allow_voice=allow_voice)

        worker = threading.Thread(
            target=self._command_session_worker,
            args=(session_id, mode, allow_voice),
            daemon=True,
        )
        worker.start()

    def _start_typing_mode(self):
        self._start_command_session(
            mode="typing",
            allow_voice=True,
            prompt="Type a command and press Enter.",
            replace=True,
        )

    def _cancel_session(self, silent=False):
        state = self._get_state()
        if state not in ("listening", "typing"):
            return

        self.command_cancel.set()
        self._bump_session()
        self._set_state("idle")
        self.popup.signal_cancel()
        self.popup.hide()
        if not silent:
            pass

    def _capture_command_voice(self, session_id):
        while self._session_matches(session_id) and not self.command_cancel.is_set():
            try:
                with self.microphone as source:
                    audio = self.command_recognizer.listen(
                        source,
                        timeout=0.35,
                        phrase_time_limit=7,
                    )
                if not self._session_matches(session_id) or self.command_cancel.is_set():
                    return None
                text = self.command_recognizer.recognize_google(
                    audio,
                    language="en-IN",
                )
                cleaned = self._extract_command(text)
                if cleaned:
                    return cleaned

                normalized = self._normalize_text(text)
                if WAKE_ONLY_RE.match(normalized):
                    continue

                return normalized
            except sr.WaitTimeoutError:
                continue
            except Exception:
                return None
        return None

    def _command_session_worker(self, session_id, mode, allow_voice):
        if mode == "voice":
            while self._session_matches(session_id) and not self.command_cancel.is_set():
                input_mode = self.popup.get_input_mode()
                if input_mode == "cancel":
                    self._cancel_session(silent=True)
                    return

                if input_mode == "typed":
                    action, text = self.popup.wait_for_action(timeout=0.1)
                    if action == "submit":
                        cmd = self._normalize_text(text)
                        if cmd:
                            self.run_cmd(cmd)
                        else:
                            self._cancel_session(silent=True)
                        return
                    if action == "cancel":
                        self._cancel_session(silent=True)
                        return
                    time.sleep(0.05)
                    continue

                if input_mode == "voice":
                    cmd = self._capture_command_voice(session_id)
                    if not self._session_matches(session_id) or self.command_cancel.is_set():
                        return
                    if cmd:
                        self.run_cmd(cmd)
                        return
                    time.sleep(0.05)
                    continue

                time.sleep(0.05)
            return

        if mode == "typing":
            while self._session_matches(session_id) and not self.command_cancel.is_set():
                input_mode = self.popup.get_input_mode()
                if input_mode == "cancel":
                    self._cancel_session(silent=True)
                    return

                if input_mode == "typed":
                    action, text = self.popup.wait_for_action(timeout=0.1)
                    if action == "submit":
                        cmd = self._normalize_text(text)
                        if cmd:
                            self.run_cmd(cmd)
                        else:
                            self._cancel_session(silent=True)
                        return
                    if action == "cancel":
                        self._cancel_session(silent=True)
                        return
                elif input_mode == "voice":
                    cmd = self._capture_command_voice(session_id)
                    if not self._session_matches(session_id) or self.command_cancel.is_set():
                        return
                    if cmd:
                        self.run_cmd(cmd)
                        return
                time.sleep(0.05)

    def run_cmd(self, cmd):
        cmd = self._normalize_text(cmd)
        if not cmd:
            return

        state = self._get_state()
        if state == "processing":
            return

        self._bump_session()
        self.command_cancel.set()
        self._set_state("processing")

        short = cmd[:42] + ("..." if len(cmd) > 42 else "")
        self.popup.show_processing(f"Running: {short}")

        worker = threading.Thread(target=self._run_openclaw, args=(cmd,), daemon=True)
        worker.start()

    def _run_openclaw(self, cmd):
        try:
            env = os.environ.copy()
            env["PATH"] = f"{OPENCLAW_PATH}:{env.get('PATH', '')}"
            env["HOME"] = HOME_DIR
            env["ALSA_CONF_PATH"] = "/dev/null"

            result = subprocess.run(
                [
                    OPENCLAW_BIN,
                    "--log-level",
                    "silent",
                    "agent",
                    "--agent",
                    "main",
                    "--message",
                    cmd,
                    "--json",
                ],
                capture_output=True,
                text=True,
                timeout=180,
                env=env,
            )

            if result.returncode == 0:
                output = self._extract_openclaw_output(result.stdout)
                self.popup.show_result(output[:700] or "Done.")
            else:
                message = (result.stderr or result.stdout or "Command failed").strip()
                self.popup.show_result(message[:700], error=True)
        except Exception as exc:
            self.popup.show_result(str(exc)[:700], error=True)
        finally:
            time.sleep(3.5)
            self._set_state("idle")
            self.command_cancel = threading.Event()

    def _extract_openclaw_output(self, stdout):
        text = (stdout or "").strip()
        if not text:
            return "No output."

        try:
            data = json.loads(text)
        except Exception:
            return text

        result = data.get("result", {})
        payloads = result.get("payloads", [])
        if payloads:
            first = payloads[0] or {}
            if isinstance(first, dict):
                message = first.get("text")
                if message:
                    return str(message).strip()

        for key in ("text", "message", "output"):
            value = data.get(key)
            if value:
                return str(value).strip()

        return text

    def _main_loop(self):
        while True:
            if self._get_state() != "idle":
                time.sleep(0.15)
                continue

            try:
                with self.microphone as source:
                    audio = self.wake_recognizer.listen(
                        source,
                        timeout=1.0,
                        phrase_time_limit=7,
                    )
                if self._get_state() != "idle":
                    continue
                text = self.wake_recognizer.recognize_google(
                    audio,
                    language="en-IN",
                )
                command = self._extract_command(text)
                if command:
                    self.run_cmd(command)
                    continue

                if self._contains_wake(text):
                    self._start_command_session(
                        mode="voice",
                        allow_voice=True,
                        prompt="Say or type a command.",
                        replace=True,
                    )
            except sr.WaitTimeoutError:
                pass
            except Exception:
                pass

            time.sleep(0.05)


if __name__ == "__main__":
    Chotu()
