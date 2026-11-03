"""Companion menu. Install in the original launcher's root directory."""
import ctypes
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time
import tkinter as tk
from PIL import Image, ImageTk

ROOT = Path(__file__).resolve().parent
GAMES = (("u1", "Drake’s Fortune"), ("u2", "Among Thieves"),
         ("u3", "Drake’s Deception"))
BG, GOLD, TEXT = "#10181c", "#dfbd76", "#f6f0e3"


def launch_command(root, game):
    if game not in {key for key, _ in GAMES}:
        raise ValueError("Unknown game")
    starter = root / "Uncharted Launcher.exe"
    if not starter.is_file():
        raise FileNotFoundError("Install beside Uncharted Launcher.exe")
    return [str(starter), "--play", game]


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
        self.images = []
        self.exit_until = 0
        self.status = "Choose your adventure"
        self.canvas = tk.Canvas(root, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        root.title("Uncharted · The Nathan Drake Collection")
        root.attributes("-fullscreen", True)
        root.configure(bg=BG)
        root.bind("<Configure>", lambda _: self.draw())
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

    def draw(self):
        c = self.canvas
        c.delete("all")
        self.images.clear()
        w, h = max(c.winfo_width(), 640), max(c.winfo_height(), 480)
        scale = min(w / 1280, h / 720)
        def text(x, y, value, size, color=TEXT):
            c.create_text(x, y, text=value, fill=color,
                          font=("Segoe UI", max(10, int(size * scale))))
        text(w / 2, h * .09, "UNCHARTED", 34, GOLD)
        text(w / 2, h * .155, "THE NATHAN DRAKE COLLECTION", 14)
        ch = int(h * .49)
        cw = int(ch * 2 / 3)
        for i, (key, name) in enumerate(GAMES):
            x, y = w / 2 + (i - 1) * (cw + 48 * scale), h * .23
            selected = i == self.index
            c.create_rectangle(x - cw / 2 - 7, y - 7, x + cw / 2 + 7, y + ch + 7,
                               fill=GOLD if selected else "#35434a", outline="")
            if self.covers[i]:
                image = ImageTk.PhotoImage(self.covers[i].resize((cw, ch), Image.Resampling.LANCZOS))
                self.images.append(image)
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
            self.process = subprocess.Popen(launch_command(ROOT, GAMES[self.index][0]), cwd=str(ROOT))
        except OSError as error:
            self.status = "Could not start game: " + str(error)
            self.draw()
            return
        self.keys.clear()
        self.root.withdraw()

    def close(self):
        # Never terminate the game or its launcher when closing this menu.
        self.root.destroy()

    def poll(self):
        held = set(self.keys)
        if self.process:
            if self.process.poll() is None:
                self.root.after(250, self.poll)
                return
            code = self.process.returncode
            self.process = None
            self.status = "Choose your adventure" if code == 0 else "Launcher exited with code " + str(code)
            self.root.deiconify()
            self.root.focus_force()
            # Absorb held buttons when control returns from a game.
            self.navigation.previous = {"a", "b", "left", "right"}
            self.draw()
        if self.pads:
            try:
                buttons = self.pads.held()
                held.update(buttons & {"a", "b"})
                if "dpleft" in buttons:
                    held.add("left")
                if "dpright" in buttons:
                    held.add("right")
                for pad in self.pads.pads.values():
                    axis = self.pads.sdl.SDL_GetGamepadAxis(pad, 0)
                    if abs(axis) > 20000:
                        held.add("left" if axis < 0 else "right")
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
    # Reuse the installed launcher's SDL3 adapter without starting its UI.
    sys.path.insert(0, str(ROOT / "launcher"))
    adapter = runpy.run_path(str(ROOT / "launcher" / "uncharted_launcher.pyw"),
                             run_name="controller_adapter")
    root = tk.Tk()
    Menu(root, adapter["Gamepads"]())
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        from tkinter import messagebox
        error = traceback.format_exc()
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("Uncharted controller menu", error[-1800:])
        root.destroy()
