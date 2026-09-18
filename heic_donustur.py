#!/usr/bin/env python3
"""iPhone'dan gelen HEIC/HEIF fotoğrafları toplu olarak JPEG veya PNG'ye çevirir.

Kullanım:
    python heic_donustur.py KLASOR                  # alt klasörler dahil, yanına .jpg yazar
    python heic_donustur.py KLASOR --format png     # PNG ister
    python heic_donustur.py KLASOR --cikti D:/Cikti  # ağaç yapısını koruyarak başka klasöre
    python heic_donustur.py KLASOR --sil            # başarılı çevirimden sonra orijinali siler
    python heic_donustur.py KLASOR --dene           # ne yapacağını söyler, dokunmaz

EXIF (çekim tarihi, konum, kamera) korunur; yön bilgisi piksellere işlenir; dosyanın
değiştirilme zamanı orijinalinkiyle eşitlenir ki Windows'ta sıralama bozulmasın.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from PIL import Image, ImageOps
import pillow_heif

pillow_heif.register_heif_opener()

# Windows konsolu cp1254 olabilir; Türkçe çıktı kırılmasın
for _akis in (sys.stdout, sys.stderr):
    _akis.reconfigure(errors="replace")

UZANTILAR = {".heic", ".heif", ".hif"}


def hedef_yol(kaynak: Path, kok: Path, cikti: Path | None, uzanti: str) -> Path:
    if cikti is None:
        return kaynak.with_suffix(uzanti)
    return (cikti / kaynak.relative_to(kok)).with_suffix(uzanti)


def cevir(kaynak: Path, hedef: Path, fmt: str, kalite: int) -> None:
    with Image.open(kaynak) as img:
        img = ImageOps.exif_transpose(img)  # yönü piksellere işle, Orientation etiketini sıfırla
        exif = img.info.get("exif")
        kayit = {}
        if exif:
            kayit["exif"] = exif
        if fmt == "jpeg":
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            kayit.update(quality=kalite, optimize=True)
        else:  # png
            kayit.update(compress_level=6)
        hedef.parent.mkdir(parents=True, exist_ok=True)
        gecici = hedef.with_name(hedef.name + ".part")
        img.save(gecici, format=fmt.upper(), **kayit)
    os.replace(gecici, hedef)
    st = kaynak.stat()
    os.utime(hedef, (st.st_atime, st.st_mtime))


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("klasor", type=Path, help="taranacak klasör (alt klasörler dahil)")
    p.add_argument("--format", choices=["jpeg", "png"], default="jpeg")
    p.add_argument("--kalite", type=int, default=92, help="JPEG kalitesi (varsayılan 92)")
    p.add_argument("--cikti", type=Path, help="çıktı klasörü; verilmezse orijinalin yanına yazar")
    p.add_argument("--sil", action="store_true", help="başarılı çevirimden sonra orijinali sil")
    p.add_argument("--zorla", action="store_true", help="hedef varsa üstüne yaz")
    p.add_argument("--dene", action="store_true", help="hiçbir şey yazma, sadece listele")
    a = p.parse_args()

    kok: Path = a.klasor.resolve()
    if not kok.is_dir():
        print(f"klasör yok: {kok}", file=sys.stderr)
        return 2
    uzanti = ".jpg" if a.format == "jpeg" else ".png"

    dosyalar = sorted(f for f in kok.rglob("*") if f.is_file() and f.suffix.lower() in UZANTILAR)
    if not dosyalar:
        print("HEIC/HEIF dosyası bulunamadı.")
        return 0

    ok = atlandi = hata = 0
    for i, kaynak in enumerate(dosyalar, 1):
        hedef = hedef_yol(kaynak, kok, a.cikti, uzanti)
        etiket = f"[{i}/{len(dosyalar)}] {kaynak.relative_to(kok)}"
        if hedef.exists() and not a.zorla:
            atlandi += 1
            print(f"{etiket}  -> atlandı (var: {hedef.name})")
            continue
        if a.dene:
            print(f"{etiket}  -> {hedef}")
            continue
        try:
            cevir(kaynak, hedef, a.format, a.kalite)
        except Exception as e:  # noqa: BLE001
            hata += 1
            print(f"{etiket}  -> HATA: {e}", file=sys.stderr)
            continue
        ok += 1
        if a.sil:
            kaynak.unlink()
        print(f"{etiket}  -> {hedef.name}")

    print(f"\nbitti: {ok} çevrildi, {atlandi} atlandı, {hata} hata"
          + (" (deneme modu)" if a.dene else ""))
    return 1 if hata else 0


if __name__ == "__main__":
    sys.exit(main())
