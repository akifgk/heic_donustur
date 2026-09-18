@echo off
rem Tek dosyalik exe uretir: dist\HEIC-Donustur.exe
pip install -q pillow pillow-heif pyinstaller
pyinstaller --noconfirm --onefile --windowed --name HEIC-Donustur --collect-all pillow_heif arayuz.py
echo.
echo Bitti: dist\HEIC-Donustur.exe
pause
