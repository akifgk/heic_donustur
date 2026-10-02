# HEIC Dönüştürücü

iPhone'dan PC'ye aktarılan HEIC/HEIF fotoğrafları toplu olarak JPEG veya PNG'ye çevirir.
EXIF (çekim tarihi, konum), yön bilgisi ve dosya tarihi korunur.

- `heic_donustur.py` — çekirdek + komut satırı (`python heic_donustur.py KLASOR --dene`)
- `arayuz.py` — Tkinter arayüzü (`python arayuz.py`)
- `derle.bat` — PyInstaller ile `dist\HEIC-Donustur.exe` üretir

Arayüz:
- Fotoğrafları ya da klasörü pencereye sürükle-bırak, ya da "Klasör ekle" / "Dosya ekle".
- Her dosyanın durumu listede görünür (Bekliyor, Çevrildi, Atlandı, Hata).
- Listeden bir satır seçince önizleme açılır: yönü düzeltilmiş resim, piksel boyutu, çekim
  tarihi, telefon modeli. Dosya çevrildiyse önizleme çıktıdan yapılır; yön orada kontrol edilir.
- Sağ tık: Aç, Klasörde göster, Listeden çıkar. `Delete` seçili satırları çıkarır.
- "Yazmadan dene" hiçbir dosya yazmadan nereye ne yazılacağını gösterir.
- "Çevrilen HEIC dosyalarını Geri Dönüşüm Kutusu'na taşı" orijinali kalıcı silmez.
- Ayarlar (biçim, kalite, kayıt yeri) `%APPDATA%\HEIC-Donustur\ayarlar.json` içinde hatırlanır;
  Geri Dönüşüm seçeneği bilerek hatırlanmaz.

Gereksinim: Python 3.12, `pip install pillow pillow-heif tkinterdnd2`.
