# HEIC Dönüştürücü

[![Sürüm](https://img.shields.io/github/v/release/akifgk/heic_donustur?label=s%C3%BCr%C3%BCm)](https://github.com/akifgk/heic_donustur/releases/latest)
[![Lisans: MIT](https://img.shields.io/badge/lisans-MIT-green.svg)](LICENSE)
![Platform: Windows](https://img.shields.io/badge/platform-Windows-0078D6)

iPhone'dan bilgisayara aktardığın HEIC/HEIF fotoğraflarını tek seferde JPEG ya da PNG'ye çevirir.
Çekim tarihi, konum, kamera bilgisi, fotoğrafın yönü ve dosya tarihi korunur. Kurulum gerekmez,
tek dosyalık bir Windows programıdır.

> *English:* a small Windows tool that batch-converts iPhone HEIC/HEIF photos to JPEG or PNG,
> keeping EXIF data, orientation and file dates. Download the `.exe` from
> [Releases](https://github.com/akifgk/heic_donustur/releases/latest); no install needed.

## İndir

[**HEIC-Donustur.exe dosyasını indir**](https://github.com/akifgk/heic_donustur/releases/latest)
(Windows, yaklaşık 35 MB)

1. İndirdiğin dosyaya çift tıkla. Kurulum ya da Python gerekmez.
2. Fotoğrafları ya da bir klasörü pencereye sürükleyip bırak.
3. **Dönüştür**'e bas.

> **Windows uyarı verirse:** program dijital olarak imzalı olmadığı için "Bilinmeyen yayıncı"
> (SmartScreen) uyarısı çıkabilir. **Ek bilgi → Yine de çalıştır** ile açılır. Bazı antivirüsler
> paketlenmiş Python programlarına yanlış alarm verebilir. Kaynak kodun tamamı bu depoda açık;
> istersen [kendin derleyebilirsin](#kaynaktan-çalıştırma-ve-derleme).

## Ne yapar

- **Toplu dönüştürme:** dosya ya da klasör ekle, alt klasörler taranır.
- **JPEG veya PNG:** JPEG'de kalite 50–100 arası seçilir (varsayılan 92); PNG kayıpsızdır ama her
  fotoğraf 15–25 MB olur.
- **Bilgiler korunur:** EXIF (çekim tarihi, konum, telefon modeli), fotoğrafın yönü, dosyanın
  değiştirilme zamanı. Yön piksellere işlenir, yani fotoğraf her programda doğru dik görünür.
- **Önizleme:** listeden bir satır seçince yönü düzeltilmiş resim, piksel boyutu, çekim tarihi ve
  telefon modeli görünür.
- **Güvenli:** "Yazmadan dene" hiçbir dosya yazmadan nereye ne yazılacağını gösterir. Aynı adlı
  çıktı varsa varsayılan olarak üstüne yazılmaz ("Aynı adlı çıktı varsa üstüne yaz" ile açılır).
- **Kayıt yeri:** orijinalin yanına ya da kaynak klasörde yeni bir klasöre; alt klasör yapısı korunur.
- **Orijinali temizleme (isteğe bağlı):** "Çevrilen HEIC dosyalarını Geri Dönüşüm Kutusu'na taşı"
  seçeneği orijinali kalıcı silmez. Bu seçenek bilerek hatırlanmaz, her seferinde sen işaretlersin.

Ayarların (biçim, kalite, kayıt yeri) `%APPDATA%\HEIC-Donustur\ayarlar.json` içinde hatırlanır.

## Kısayollar

| İşlem | Nasıl |
| --- | --- |
| Dosya ya da klasör ekle | Pencereye sürükle-bırak ya da "Dosya ekle" / "Klasör ekle" |
| Dosyayı aç, klasörde göster, listeden çıkar | Satıra sağ tık |
| Seçili satırları listeden çıkar | `Delete` |

## Komut satırı

Arayüz olmadan da kullanılır. Python ve `requirements.txt` gerekir.

```bash
python heic_donustur.py KLASOR                    # alt klasörler dahil, yanına .jpg yazar
python heic_donustur.py KLASOR --format png       # PNG olarak
python heic_donustur.py KLASOR --kalite 85        # JPEG kalitesi
python heic_donustur.py KLASOR --cikti D:/Cikti   # klasör yapısını koruyarak başka yere
python heic_donustur.py KLASOR --dene             # hiçbir şey yazmadan ne yapacağını listeler
python heic_donustur.py KLASOR --sil              # başarılı çevirimden sonra orijinali siler
python heic_donustur.py KLASOR --zorla            # hedef varsa üstüne yazar
```

## Sık sorulanlar

**Fotoğraflarım bir yere gönderiliyor mu?** Hayır. Her şey bilgisayarında çalışır, program internet
bağlantısı kullanmaz.

**Konum bilgisi korunuyor, paylaşmadan önce silmem gerekir mi?** Konum EXIF içinde kalır. Fotoğrafı
paylaşmadan önce istersen konumu başka bir araçla sil.

**Mac ya da Linux'ta çalışır mı?** Hazır program yalnızca Windows içindir. Komut satırı sürümü Python'un
çalıştığı yerlerde çalışmalı, ama Windows dışında denenmedi.

## Kaynaktan çalıştırma ve derleme

Gereksinim: Python 3.12.

```bash
pip install -r requirements.txt
python arayuz.py            # arayüz
python heic_donustur.py     # komut satırı
```

Tek dosyalık exe üretmek için `derle.bat` çalıştırılır; çıktı `dist\HEIC-Donustur.exe` olur
(PyInstaller kullanır).

| Dosya | Görevi |
| --- | --- |
| `heic_donustur.py` | Çekirdek dönüştürme ve komut satırı |
| `arayuz.py` | Tkinter arayüzü |
| `derle.bat` | PyInstaller ile exe üretir |

## Lisans

[MIT](LICENSE)
