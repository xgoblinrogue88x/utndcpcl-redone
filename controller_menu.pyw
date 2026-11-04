"""Companion menu. Install in the original launcher's root directory."""
import ctypes
import os
from pathlib import Path
import logging
import subprocess
import sys
import time
import tkinter as tk
from PIL import Image, ImageTk

ROOT = Path(__file__).resolve().parent
GAMES = (("u1", "Drake’s Fortune"), ("u2", "Among Thieves"),
         ("u3", "Drake’s Deception"))
BG, GOLD, TEXT = "#10181c", "#dfbd76", "#f6f0e3"
LOG = logging.getLogger("controller-menu")


def launch_command(root, game):
    if game not in {key for key, _ in GAMES}:
        raise ValueError("Unknown game")
    script = root / "launcher" / "uncharted_launcher.pyw"
    if not script.is_file():
        raise FileNotFoundError("Install beside the original launcher folder")
    # Stay inside Steam's existing Proton session and bundled Python. Bypass the
    # EXE bootstrapper, whose lifetime need not match the game process.
    return [sys.executable, str(root / "controller_menu.pyw"), "--launch-game", game]


def run_original(game):
    """Embedded Python may not put the script folder on sys.path."""
    import runpy
    if game not in {key for key, _ in GAMES}:
        raise ValueError("Unknown game")
    script = ROOT / "launcher" / "uncharted_launcher.pyw"
    sys.path.insert(0, str(script.parent))
    sys.argv = [str(script), "--play", game]
    runpy.run_path(str(script), run_name="__main__")


class Gamepads:
    """Small SDL3 adapter; discover devices once a second, not every frame."""
    def __init__(self):
        self.sdl = None
        self.pads = {}
        self.next_scan = 0
        path = ROOT / "gow3_pc" / "out" / "SDL3.dll"
        if not path.is_file():
            LOG.warning("SDL3.dll missing; use Steam Input keyboard bindings")
            return
        try:
            sdl = ctypes.CDLL(str(path))
            signatures = {
                "SDL_Init": ([ctypes.c_uint32], ctypes.c_bool),
                "SDL_QuitSubSystem": ([ctypes.c_uint32], None),
                "SDL_GetGamepads": ([ctypes.POINTER(ctypes.c_int)], ctypes.POINTER(ctypes.c_uint32)),
                "SDL_OpenGamepad": ([ctypes.c_uint32], ctypes.c_void_p),
                "SDL_CloseGamepad": ([ctypes.c_void_p], None),
                "SDL_GetGamepadButton": ([ctypes.c_void_p, ctypes.c_int], ctypes.c_bool),
                "SDL_GetGamepadAxis": ([ctypes.c_void_p, ctypes.c_int], ctypes.c_int16),
                "SDL_SetHint": ([ctypes.c_char_p, ctypes.c_char_p], ctypes.c_bool),
                "SDL_free": ([ctypes.c_void_p], None),
                "SDL_PumpEvents": ([], None),
                "SDL_UpdateGamepads": ([], None),
            }
            for name, (args, result) in signatures.items():
                function = getattr(sdl, name)
                function.argtypes, function.restype = args, result
            sdl.SDL_SetHint(b"SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", b"1")
            if sdl.SDL_Init(0x2000):
                self.sdl = sdl
            else:
                LOG.warning("SDL gamepad initialization failed")
        except (OSError, AttributeError):
            LOG.exception("Could not load SDL controller support")

    def held(self):
        if not self.sdl:
            return set()
        sdl = self.sdl
        sdl.SDL_PumpEvents()
        now = time.monotonic()
        if now >= self.next_scan:
            self.next_scan = now + 1
            count = ctypes.c_int()
            ids = sdl.SDL_GetGamepads(ctypes.byref(count))
            try:
                current = set(ids[i] for i in range(count.value)) if ids else set()
            finally:
                if ids:
                    sdl.SDL_free(ctypes.cast(ids, ctypes.c_void_p))
            for jid in set(self.pads) - current:
                sdl.SDL_CloseGamepad(self.pads.pop(jid))
            for jid in current - set(self.pads):
                pad = sdl.SDL_OpenGamepad(jid)
                if pad:
                    self.pads[jid] = pad
        sdl.SDL_UpdateGamepads()
        held = set()
        for pad in self.pads.values():
            for index, name in ((0, "a"), (1, "b"), (13, "left"), (14, "right")):
                if sdl.SDL_GetGamepadButton(pad, index):
                    held.add(name)
            axis = sdl.SDL_GetGamepadAxis(pad, 0)
            if abs(axis) > 20000:
                held.add("left" if axis < 0 else "right")
        return held

    def close(self):
        if self.sdl:
            for pad in self.pads.values():
                self.sdl.SDL_CloseGamepad(pad)
            self.pads.clear()
            self.sdl.SDL_QuitSubSystem(0x2000)
            self.sdl = None


class Navigation:
    """One press per confirm; delayed repeat for held navigation."""
    def __init__(self):
        self.previous = set()
        self.direction = 0
        self.next_repeat = 0

    def update(self, held, now):
        fresh = held - self.previous
        direction = int("right" in held) - int("left" in held)
        step = 0
        if direction and (direction != self.direction or now >= self.next_repeat):
            step = direction
            self.next_repeat = now + (0.4 if direction != self.direction else 0.18)
        self.direction = direction
        self.previous = set(held)
        return step, fresh


class Menu:
    def __init__(self, root, gamepads):
        self.root, self.pads = root, gamepads
        self.index = 0
        self.process = None
        self.keys = set()
        self.navigation = Navigation()
        self.images = {}
        self.image_size = None
        self.redraw_job = None
        self.child_log = None
        self.exit_until = 0
        self.status = "Choose your adventure"
        self.canvas = tk.Canvas(root, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        root.title("Uncharted · The Nathan Drake Collection")
        root.attributes("-fullscreen", True)
        root.configure(bg=BG)
        self.canvas.bind("<Configure>", self.schedule_draw)
        root.bind("<KeyPress>", lambda e: self.key(e.keysym, True))
        root.bind("<KeyRelease>", lambda e: self.key(e.keysym, False))
        root.bind("<FocusOut>", lambda _: self.keys.clear())
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.covers = []
        for key, _ in GAMES:
            path = ROOT / "controller-assets" / (key + ".jpg")
            try:
                with Image.open(path) as image:
                    self.covers.append(image.convert("RGB"))
            except (OSError, ValueError):
                self.covers.append(None)
        self.draw()
        root.after(30, self.poll)

    def key(self, name, down):
        action = {"Left": "left", "Right": "right", "Return": "a",
                  "Escape": "b"}.get(name)
        if action:
            if down:
                self.keys.add(action)
            else:
                self.keys.discard(action)

    def schedule_draw(self, event=None):
        if self.redraw_job is not None:
            self.root.after_cancel(self.redraw_job)
        self.redraw_job = self.root.after(100, self.draw)

    def draw(self):
        self.redraw_job = None
        c = self.canvas
        c.delete("all")
        w, h = max(c.winfo_width(), 640), max(c.winfo_height(), 480)
        scale = min(w / 1280, h / 720)
        def text(x, y, value, size, color=TEXT):
            c.create_text(x, y, text=value, fill=color,
                          font=("Segoe UI", max(10, int(size * scale))))
        text(w / 2, h * .09, "UNCHARTED", 34, GOLD)
        text(w / 2, h * .155, "THE NATHAN DRAKE COLLECTION", 14)
        ch = min(540, int(h * .49))
        cw = int(ch * 2 / 3)
        if self.image_size != (cw, ch):
            self.images.clear()
            self.image_size = (cw, ch)
        for i, (key, name) in enumerate(GAMES):
            x, y = w / 2 + (i - 1) * (cw + 48 * scale), h * .23
            selected = i == self.index
            c.create_rectangle(x - cw / 2 - 7, y - 7, x + cw / 2 + 7, y + ch + 7,
                               fill=GOLD if selected else "#35434a", outline="")
            if self.covers[i]:
                if i not in self.images:
                    self.images[i] = ImageTk.PhotoImage(self.covers[i].resize((cw, ch), Image.Resampling.LANCZOS))
                image = self.images[i]
                c.create_image(x, y, image=image, anchor="n")
            else:
                c.create_rectangle(x - cw / 2, y, x + cw / 2, y + ch, fill="#21343a", outline="")
                text(x, y + ch * .40, "UNCHARTED " + str(i + 1), 20, GOLD)
                text(x, y + ch * .56, "Cover art pending", 12)
            text(x, y + ch + 30 * scale, name, 17, GOLD if selected else TEXT)
        text(w / 2, h * .85, self.status, 16)
        text(w / 2, h * .94, "D-pad / Left stick: Select     A / Cross: Play     B / Circle: Exit", 14, GOLD)

    def play(self):
        if self.process:
            return
        try:
            command = launch_command(ROOT, GAMES[self.index][0])
            self.child_log = (ROOT / "controller-game.log").open("a", encoding="utf-8")
            LOG.info("Launching %s through bundled Python", GAMES[self.index][0])
            self.child_log.write("\n--- " + time.strftime("%Y-%m-%d %H:%M:%S") + " " + GAMES[self.index][0] + " ---\n")
            self.child_log.flush()
            if self.pads:
                self.pads.close()
            self.process = subprocess.Popen(command, cwd=str(ROOT), stdout=self.child_log,
                                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        except OSError as error:
            LOG.exception("Game launch failed")
            if self.child_log:
                self.child_log.close()
                self.child_log = None
            self.pads = Gamepads()
            self.status = "Could not start game: " + str(error)
            self.draw()
            return
        self.keys.clear()
        self.root.withdraw()

    def close(self):
        # Never terminate the game or its launcher when closing this menu.
        if self.pads:
            self.pads.close()
        if self.child_log:
            self.child_log.close()
        self.root.destroy()

    def poll(self):
        held = set(self.keys)
        if self.process:
            if self.process.poll() is None:
                self.root.after(250, self.poll)
                return
            code = self.process.returncode
            self.process = None
            LOG.info("Launcher process exited: %s", code)
            self.child_log.close()
            self.child_log = None
            self.pads = Gamepads()
            self.status = "Choose your adventure" if code == 0 else "Launcher exited with code " + str(code)
            self.root.deiconify()
            self.root.focus_force()
            # Absorb held buttons when control returns from a game.
            self.navigation.previous = {"a", "b", "left", "right"}
            self.draw()
        if self.pads:
            try:
                held.update(self.pads.held())
            except (OSError, AttributeError):
                self.status = "Controller unavailable. Steam Input can map arrows / Enter / Escape."
        # Ignore background controller input while another window has focus.
        if self.root.focus_displayof() is None:
            held.clear()
        step, fresh = self.navigation.update(held, time.monotonic())
        if step:
            self.index = (self.index + step) % len(GAMES)
            self.exit_until = 0
            self.status = "Choose your adventure"
            self.draw()
        if "b" in fresh:
            if time.monotonic() < self.exit_until:
                self.close()
                return
            self.exit_until = time.monotonic() + 3
            self.status = "Press B / Circle again to exit"
            self.draw()
        elif "a" in fresh:
            self.exit_until = 0
            self.play()
        self.root.after(30, self.poll)


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    logging.basicConfig(filename=str(ROOT / "controller-menu.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    LOG.info("Controller companion v0.2 starting (%s)", sys.platform)
    root = tk.Tk()
    root.report_callback_exception = lambda kind, value, trace: LOG.error(
        "Menu callback failed", exc_info=(kind, value, trace))
    Menu(root, Gamepads())
    root.mainloop()


if __name__ == "__main__":
    try:
        if len(sys.argv) == 3 and sys.argv[1] == "--launch-game":
            run_original(sys.argv[2])
        else:
            main()
    except Exception:
        import traceback
        from tkinter import messagebox
        LOG.exception("Menu startup failed")
        error = traceback.format_exc()
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Uncharted controller menu", error[-1800:])
        root.destroy()
