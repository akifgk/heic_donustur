# HEIC Dönüştürücü

iPhone'dan PC'ye aktarılan HEIC/HEIF fotoğrafları toplu olarak JPEG veya PNG'ye çevirir.
EXIF (çekim tarihi, konum), yön bilgisi ve dosya tarihi korunur.

- `heic_donustur.py` — çekirdek + komut satırı (`python heic_donustur.py KLASOR --dene`)
- `arayuz.py` — Tkinter arayüzü (`python arayuz.py`)
- `derle.bat` — PyInstaller ile `dist\HEIC-Donustur.exe` üretir

Gereksinim: Python 3.12, `pip install pillow pillow-heif`.
