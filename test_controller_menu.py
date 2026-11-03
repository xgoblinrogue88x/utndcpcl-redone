import importlib.machinery
from pathlib import Path
import tempfile
import types
import unittest

module = types.ModuleType("controller_menu")
module.__file__ = str(Path(__file__).with_name("controller_menu.pyw"))
importlib.machinery.SourceFileLoader(module.__name__, module.__file__).exec_module(module)


class ControllerTests(unittest.TestCase):
    def test_original_launcher_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Uncharted Launcher.exe").touch()
            for key in ("u1", "u2", "u3"):
                self.assertEqual(module.launch_command(root, key),
                                 [str(root / "Uncharted Launcher.exe"), "--play", key])
            with self.assertRaises(ValueError):
                module.launch_command(root, "invalid")

    def test_missing_installation(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                module.launch_command(Path(directory), "u1")

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
