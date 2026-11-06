@echo off
rem Сборка портативной программы: dist\FuzzyStudent.exe (Python на целевом компьютере не нужен)
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --disable-pip-version-check -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean --onefile --windowed --name FuzzyStudent ^
    --exclude-module tkinter --exclude-module PyQt5 --exclude-module PySide6 ^
    --add-data "gui\check.svg;gui" ^
    main.py
echo.
echo Готово: dist\FuzzyStudent.exe
pause
