# Uncharted controller companion

A fullscreen, three-game controller menu for an **existing working installation**
of Uncharted Launcher. This is a companion, not a replacement game runtime.
The original launcher remains responsible for game paths, saves, graphics,
controller configuration and launching games. No settings are copied or edited
by this menu. The original launcher may update its own settings as usual.

## Install on Bazzite / Proton Experimental

1. Extract `controller_menu.pyw`, `Start Controller Menu.cmd`, and the
   `controller-assets` folder into the same folder as `Uncharted Launcher.exe`.
   Leave the existing `launcher`, `python`, `tools`, and game folders intact.
2. Configure and verify each game in the original launcher first.
3. In Steam, edit your **existing working shortcut**, keeping Proton Experimental
   and its current compatibility data. Set its Target to the bundled
   `python/pythonw.exe` (or `python/python.exe` if pythonw is absent).
   Set Start In to the folder containing `Uncharted Launcher.exe`.
4. Set Launch Options to the full, quoted path to `controller_menu.pyw`.
   For example: `"/home/yourname/Games/Uncharted/controller_menu.pyw"`.
   If you already have environment variables or wrappers in Launch Options,
   preserve them and put the script argument after `%command%`.
5. Launch the existing Steam shortcut. Keep the original EXE available to open
   the settings UI from Desktop Mode. Restore the old Target and Launch Options
   to switch back.

The script needs the original installation's Python, Tkinter, Pillow, and SDL3;
it does not install a second Python or run a separate Proton instance.
`Start Controller Menu.cmd` is a Windows/Wine convenience entry point; the
direct Python target above is the recommended Steam setup.

## Controls

- D-pad left/right or left stick: select a game (hold to repeat).
- A / Cross: launch the selected game.
- B / Circle, then B / Circle again within three seconds: exit.
- Keyboard fallback: arrows, Enter, Escape. Steam Input may map those keys if
  the controller is not exposed as an SDL gamepad.

The menu hides while the original launcher process runs and returns when that
process exits. It never kills the game. This relies on the installed EXE staying
alive for its game session; if your packaged EXE detaches immediately, report
that behavior so process tracking can be adapted to the actual starter.

## Cover art and music

Copy the provided covers into `controller-assets` with these exact filenames:

| File | Game |
| --- | --- |
| `u1.jpg` | Drake's Fortune |
| `u2.jpg` | Among Thieves |
| `u3.jpg` | Drake's Deception |

The menu fits 2:3 covers. Missing/unreadable covers get a labeled placeholder.
The images shown in chat are not bundled in this repository yet; send them as
downloadable image files or a ZIP to include them in a release.

Optional FLAC theme playback is planned after the audio file arrives; this
version does not play music.

## Validation and limits

`python -m unittest -v test_controller_menu.py` checks all three launch commands,
missing-install handling, controller confirm debouncing and navigation repeat.
The original uploaded source confirms support for `--play u1`, `u2`, and `u3`.
The companion loads only its SDL gamepad adapter; it does not execute its main UI.

Actual Proton startup, controller input, focus restoration, and game lifetime
tracking must still be tested on the Bazzite PC with the complete installation.
The cloud checkout does not contain the game runtime, Windows Python, or SDL3 DLL.
