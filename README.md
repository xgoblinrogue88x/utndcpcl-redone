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

## Bazzite update (v0.2)

Replace the old `controller_menu.pyw` with the updated file. Keep the Steam
shortcut that already opened the menu; no extra Bazzite packages or system
changes are needed. Continue using Proton Experimental. Do not create another
Steam shortcut or prefix, or run a second Proton command inside Launch Options.

The menu now starts `launcher/uncharted_launcher.pyw --play u1` (or u2/u3)
with the same bundled Python and inherited Steam environment, bypassing the
EXE bootstrapper. It releases its controller handles before launching and waits
for the original Python launcher to finish before restoring the menu.

Startup no longer imports the entire original launcher. SDL device discovery
runs once per second rather than every frame. Cover images are cached at their
displayed size (capped at 540 pixels tall), and window resize redraws are delayed
until resizing settles. These reduce work; no Bazzite timing measurements have
been made in the cloud environment.

If the session closes again, send `controller-menu.log` and
`controller-game.log` from the main Uncharted folder, plus the original
launcher's `analysis/uncharted-user/launcher-error.log` if present. Check logs for
personal paths before sharing. A game crash can still appear only in the
original launcher's analysis logs. No crash cause is confirmed yet.

## Cover art and music

The download now includes your three original 600×900 PNG covers:

| File | Game |
| --- | --- |
| `controller-assets/u1.png` | Drake's Fortune |
| `controller-assets/u2.png` | Among Thieves |
| `controller-assets/u3.png` | Drake's Deception |

Extract the entire ZIP into the main Uncharted folder and allow the existing
`controller-assets` folder to merge. No manual cover setup is needed. Restart
the menu after updating. JPEG and WebP replacements are also supported; missing
or unreadable files use a labeled placeholder.

## Fullscreen activation (v0.4)

The menu requests focus after its window maps, with brief retries while Steam
and the hidden batch console settle. The temporary topmost setting clears after
1.2 seconds; launching a game cancels retries and clears topmost immediately.
The same activation runs when returning from a game. This does not change KDE's
global focus settings. Actual desktop activation still needs testing on Bazzite.

Your exact covers are bundled in `controller-assets`; see the table above.

## Music and hidden console (v0.3)

Extract the **whole update ZIP**, including `controller-assets/theme.wav`, into
the main Uncharted folder and replace the older companion files. Keep your
existing game folders, settings, and cover files.

The supplied Nate's Theme 3.0 recording is bundled as a 16-bit stereo WAV for
Windows/Proton's built-in audio playback. It has a two-second fade-in and plays
at 55% source level, looping while the menu is open. It stops before launching
a game or exiting the menu, and restarts with a fade when returning from a game.
No FLAC codec, music player, or Python package installation is needed. Removing
or renaming `theme.wav` disables music.

The updated CMD starter uses console Python so the menu can hide its inherited
command window at startup; the fallback uses pythonw and exits the CMD starter.
A brief startup flash is still possible when Steam starts CMD. To avoid CMD
entirely, use `python/pythonw.exe` directly as the Steam Target with the quoted
full path to `controller_menu.pyw` as Launch Options (see installation above).
Child game launches use Windows' no-console flag.

Console visibility and audible playback still need verification on Bazzite;
cloud tests cover lifecycle calls and validate the WAV fade, format and duration.

## Validation and limits

`python -m unittest -v test_controller_menu.py` checks all three launch commands,
missing-install handling, controller confirm debouncing and navigation repeat.
The original uploaded source confirms support for `--play u1`, `u2`, and `u3`.
The companion uses a standalone SDL adapter and starts the original launcher only
when a game is selected.

Actual Proton startup, controller input, focus restoration, and game lifetime
tracking must still be tested on the Bazzite PC with the complete installation.
The cloud checkout does not contain the game runtime, Windows Python, or SDL3 DLL.

## Image header update

The download includes `controller-assets/logo.png`, exported from the supplied
logo reference with the image tool. It replaces the text header automatically.
The menu preserves its transparency and proportions and fits the visible logo
above the covers. Captions beneath the covers have been removed.

Extract the entire ZIP into the main Uncharted folder, merge `controller-assets`,
and replace the older companion files. No separate logo download or manual
image setup is needed. Covers, music, and the fullscreen-focus changes are included.

The normal “Choose your adventure” prompt is now `controller-assets/adventure.png`,
exported from the supplied wordmark reference. It scales proportionally beneath
the covers. Exit confirmation and error messages remain readable text.

The adventure wordmark now renders at three times its previous size.

## Background artwork

`controller-assets/background.png` contains the parchment/Drake background
exported from the supplied reference with the image tool. It fills the viewport
without stretching, center-cropping where screen proportions differ. The fitted
image is cached until the viewport size changes. Footer controls and status text
use a dark ink color on the parchment for readability.
