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


def hide_console():
    """Hide the inherited batch console under Windows/Proton."""
    if sys.platform != "win32":
        return
    kernel = ctypes.windll.kernel32
    kernel.GetConsoleWindow.restype = ctypes.c_void_p
    window = kernel.GetConsoleWindow()
    if window:
        show = ctypes.windll.user32.ShowWindow
        show.argtypes = [ctypes.c_void_p, ctypes.c_int]
        show.restype = ctypes.c_bool
        show(window, 0)


def foreground_window(root):
    """Request activation of Tk's outer Wine window after it has been mapped."""
    if sys.platform != "win32":
        return
    user32 = ctypes.windll.user32
    user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    user32.GetAncestor.restype = ctypes.c_void_p
    user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
    user32.SetForegroundWindow.restype = ctypes.c_bool
    window = user32.GetAncestor(root.winfo_id(), 2) or root.winfo_id()
    if not user32.SetForegroundWindow(window):
        LOG.info("Desktop deferred foreground activation")


class Music:
    """Async PCM playback with no external player or codec dependency.

    The bundled WAV contains the two-second fade, so restarting it on return
    from a game fades in again without blocking the Tk event loop.
    """
    def __init__(self):
        self.backend = None
        try:
            import winsound
            self.backend = winsound
        except ImportError:
            LOG.warning("Windows audio backend unavailable")

    def start(self):
        path = ROOT / "controller-assets" / "theme.wav"
        if self.backend and path.is_file():
            try:
                self.backend.PlaySound(str(path), self.backend.SND_FILENAME |
                                       self.backend.SND_ASYNC | self.backend.SND_LOOP |
                                       self.backend.SND_NODEFAULT)
            except RuntimeError:
                LOG.exception("Menu music could not start")

    def stop(self):
        if self.backend:
            try:
                self.backend.PlaySound(None, 0)
            except RuntimeError:
                LOG.exception("Menu music could not stop")


def load_cover(key, mode="RGB"):
    for extension in ("jpg", "png", "jpeg", "webp", "JPG", "PNG", "JPEG"):
        path = ROOT / "controller-assets" / (key + "." + extension)
        if not path.is_file():
            continue
        try:
            with Image.open(path) as image:
                return image.convert(mode)
        except (OSError, ValueError):
            LOG.exception("Could not read cover %s", path.name)
    return None


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
        self.music = Music()
        self.focus_generation = 0
        self.closing = False
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
        self.covers = [load_cover(key) for key, _ in GAMES]
        self.logo = load_cover("logo", "RGBA")
        if self.logo:
            # Fit the artwork itself, even if the exported PNG has transparent margins.
            bounds = self.logo.getbbox()
            if bounds:
                self.logo = self.logo.crop(bounds)
        self.logo_image = None
        self.logo_size = None
        self.adventure = load_cover("adventure", "RGBA")
        if self.adventure and self.adventure.getbbox():
            self.adventure = self.adventure.crop(self.adventure.getbbox())
        self.adventure_image = None
        self.adventure_size = None
        self.draw()
        self.present()
        root.after(250, lambda: self.process is None and self.music.start())
        root.after(30, self.poll)

    def present(self):
        """Activate at startup/return; never keep stealing focus afterward."""
        self.focus_generation += 1
        generation = self.focus_generation
        self.root.deiconify()
        self.root.attributes("-fullscreen", True)

        def activate():
            if self.closing or self.process or generation != self.focus_generation:
                return
            self.root.attributes("-topmost", True)
            self.root.lift()
            self.root.focus_force()
            try:
                foreground_window(self.root)
            except (AttributeError, OSError):
                LOG.exception("Native foreground request failed")

        def release():
            if not self.closing and generation == self.focus_generation:
                self.root.attributes("-topmost", False)

        # Steam/CMD may briefly reactivate as the hidden console disappears.
        # All retries end after 1.2 seconds, and are canceled by game launch.
        for delay in (50, 350, 900):
            self.root.after(delay, activate)
        self.root.after(1200, release)

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
        if self.logo:
            ratio = min(w * .65 / self.logo.width, h * .16 / self.logo.height)
            size = (max(1, int(self.logo.width * ratio)), max(1, int(self.logo.height * ratio)))
            if self.logo_size != size:
                self.logo_image = ImageTk.PhotoImage(self.logo.resize(size, Image.Resampling.LANCZOS))
                self.logo_size = size
            c.create_image(w / 2, h * .115, image=self.logo_image)
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
        if self.status == "Choose your adventure" and self.adventure:
            ratio = 3 * min(w * .65 / self.adventure.width, h * .08 / self.adventure.height)
            size = (max(1, int(self.adventure.width * ratio)), max(1, int(self.adventure.height * ratio)))
            if self.adventure_size != size:
                self.adventure_image = ImageTk.PhotoImage(self.adventure.resize(size, Image.Resampling.LANCZOS))
                self.adventure_size = size
            c.create_image(w / 2, h * .85, image=self.adventure_image)
        else:
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
            self.music.stop()
            self.focus_generation += 1
            self.root.attributes("-topmost", False)
            self.process = subprocess.Popen(command, cwd=str(ROOT), stdout=self.child_log,
                                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except OSError as error:
            LOG.exception("Game launch failed")
            if self.child_log:
                self.child_log.close()
                self.child_log = None
            self.pads = Gamepads()
            self.music.start()
            self.status = "Could not start game: " + str(error)
            self.present()
            self.draw()
            return
        self.keys.clear()
        self.root.withdraw()

    def close(self):
        # Never terminate the game or its launcher when closing this menu.
        self.closing = True
        self.music.stop()
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
            self.present()
            self.music.start()
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
    hide_console()
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass
    logging.basicConfig(filename=str(ROOT / "controller-menu.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    LOG.info("Controller companion v0.4 starting (%s)", sys.platform)
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
