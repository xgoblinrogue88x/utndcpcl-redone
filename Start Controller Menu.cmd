@echo off
cd /d "%~dp0"
if exist "python\pythonw.exe" (
  "python\pythonw.exe" "%~dp0controller_menu.pyw"
  exit /b
)
if exist "python\python.exe" (
  "python\python.exe" "%~dp0controller_menu.pyw"
  exit /b
)
echo Could not find the launcher's bundled Python in the python folder.
echo Run controller_menu.pyw with the same Python used by the original launcher.
pause
