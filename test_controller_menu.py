import importlib.machinery
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

module = types.ModuleType("controller_menu")
module.__file__ = str(Path(__file__).with_name("controller_menu.pyw"))
importlib.machinery.SourceFileLoader(module.__name__, module.__file__).exec_module(module)


class ControllerTests(unittest.TestCase):
    def test_original_launcher_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "launcher").mkdir()
            (root / "launcher" / "uncharted_launcher.pyw").touch()
            for key in ("u1", "u2", "u3"):
                self.assertEqual(module.launch_command(root, key),
                                 [module.sys.executable, str(root / "controller_menu.pyw"), "--launch-game", key])
            with self.assertRaises(ValueError):
                module.launch_command(root, "invalid")

    def test_embedded_python_bridge_sets_import_path_and_arguments(self):
        import sys
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(module, "ROOT", root), patch("runpy.run_path") as run:
                old_path, old_argv = sys.path[:], sys.argv[:]
                try:
                    module.run_original("u3")
                    script = root / "launcher" / "uncharted_launcher.pyw"
                    self.assertEqual(sys.path[0], str(script.parent))
                    self.assertEqual(sys.argv, [str(script), "--play", "u3"])
                    run.assert_called_once_with(str(script), run_name="__main__")
                finally:
                    sys.path[:], sys.argv = old_path, old_argv

    def test_missing_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                module.launch_command(Path(directory), "u1")

    def test_handoff_preserves_environment_and_releases_controller(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "launcher").mkdir()
            (root / "launcher" / "uncharted_launcher.pyw").touch()
            menu = module.Menu.__new__(module.Menu)
            menu.process, menu.child_log, menu.index = None, None, 1
            menu.pads, menu.root, menu.music = Mock(), Mock(), Mock()
            menu.keys = {"a"}
            menu.focus_generation = 0
            with patch.object(module, "ROOT", root), patch.object(module.subprocess, "Popen") as popen:
                menu.play()
                args, kwargs = popen.call_args
                self.assertEqual(args[0][-2:], ["--launch-game", "u2"])
                self.assertNotIn("env", kwargs)  # inherits Steam's Proton environment
                menu.pads.close.assert_called_once()
                menu.music.stop.assert_called_once()
                self.assertEqual(kwargs["creationflags"], getattr(module.subprocess, "CREATE_NO_WINDOW", 0))
                menu.root.withdraw.assert_called_once()
                menu.child_log.close()

    def test_failed_handoff_keeps_menu_visible(self):
        menu = module.Menu.__new__(module.Menu)
        menu.process, menu.child_log, menu.index = None, None, 0
        menu.root, menu.draw, menu.music, menu.present = Mock(), Mock(), Mock(), Mock()
        with tempfile.TemporaryDirectory() as directory, patch.object(module, "ROOT", Path(directory)), patch.object(module, "Gamepads"), self.assertLogs(module.LOG, level="ERROR"):
            menu.play()
            menu.root.withdraw.assert_not_called()
            menu.draw.assert_called_once()
            self.assertIn("Could not start game", menu.status)

    def test_music_is_async_looping_and_stops(self):
        music = module.Music.__new__(module.Music)
        backend = Mock(SND_FILENAME=1, SND_ASYNC=2, SND_LOOP=4, SND_NODEFAULT=8)
        music.backend = backend
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "controller-assets").mkdir()
            (root / "controller-assets" / "theme.wav").touch()
            with patch.object(module, "ROOT", root):
                music.start()
                backend.PlaySound.assert_called_once_with(str(root / "controller-assets" / "theme.wav"), 15)
                music.stop()
                backend.PlaySound.assert_called_with(None, 0)

    def test_png_covers_load_without_renaming_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "controller-assets").mkdir()
            module.Image.new("RGB", (60, 90), "red").save(root / "controller-assets" / "u2.png")
            with patch.object(module, "ROOT", root):
                self.assertEqual(module.load_cover("u2").size, (60, 90))
                self.assertIsNone(module.load_cover("u1"))

    def test_focus_is_bounded_and_released(self):
        menu = module.Menu.__new__(module.Menu)
        menu.root = Mock()
        menu.focus_generation, menu.closing, menu.process = 0, False, None
        callbacks = {}
        menu.root.after.side_effect = lambda delay, callback: callbacks.update({delay: callback})
        with patch.object(module, "foreground_window") as foreground:
            menu.present()
            self.assertEqual(set(callbacks), {50, 350, 900, 1200})
            menu.root.attributes.assert_called_with("-fullscreen", True)
            callbacks[50]()
            foreground.assert_called_once_with(menu.root)
            menu.root.focus_force.assert_called_once()
            callbacks[1200]()
            menu.root.attributes.assert_called_with("-topmost", False)
            menu.process = Mock()
            callbacks[900]()
            foreground.assert_called_once()

    def test_pending_activation_cannot_steal_game_focus(self):
        menu = module.Menu.__new__(module.Menu)
        menu.root = Mock()
        menu.focus_generation, menu.closing, menu.process = 0, False, None
        callbacks = {}
        menu.root.after.side_effect = lambda delay, callback: callbacks.update({delay: callback})
        with patch.object(module, "foreground_window") as foreground:
            menu.present()
            menu.focus_generation += 1  # launching a game invalidates pending timers
            callbacks[350]()
            foreground.assert_not_called()

    def test_confirm_requires_release(self):
        nav = module.Navigation()
        self.assertIn("a", nav.update({"a"}, 0)[1])
        self.assertNotIn("a", nav.update({"a"}, 1)[1])
        nav.update(set(), 2)
        self.assertIn("a", nav.update({"a"}, 3)[1])

    def test_stick_repeat_and_reversal(self):
        nav = module.Navigation()
        self.assertEqual(nav.update({"right"}, 0)[0], 1)
        self.assertEqual(nav.update({"right"}, .2)[0], 0)
        self.assertEqual(nav.update({"right"}, .41)[0], 1)
        self.assertEqual(nav.update({"left"}, .42)[0], -1)
        self.assertEqual(nav.update({"left", "right"}, .5)[0], 0)


if __name__ == "__main__":
    unittest.main()
