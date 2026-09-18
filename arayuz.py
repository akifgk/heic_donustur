#!/usr/bin/env python3
"""HEIC Dönüştürücü: heic_donustur.py çekirdeğinin küçük Tkinter arayüzü.

Klasör ya da tek tek dosya seç, biçimi belirle, Başlat'a bas. Dönüştürme arka
iş parçacığında koşar; pencere donmaz, ilerleme ve günlük anlık gelir.
"""
from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import heic_donustur as cekirdek

BASLIK = "HEIC Dönüştürücü"


class Uygulama(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(BASLIK)
        self.minsize(640, 480)

        self.kaynaklar: list[Path] = []   # seçilen HEIC dosyaları
        self.kok: Path | None = None       # çıktı klasörü için göreli yolun kökü
        self.kuyruk: queue.Queue = queue.Queue()
        self.calisiyor = False
        self.iptal = threading.Event()

        self.fmt = tk.StringVar(value="jpeg")
        self.kalite = tk.IntVar(value=92)
        self.cikti = tk.StringVar(value="")
        self.sil = tk.BooleanVar(value=False)
        self.zorla = tk.BooleanVar(value=False)
        self.kaynak_metin = tk.StringVar(value="Henüz seçim yok")

        self._kur()
        self.after(100, self._kuyrugu_bosalt)

    # ----- arayüz kurulumu -----------------------------------------------
    def _kur(self) -> None:
        pad = {"padx": 8, "pady": 4}
        ana = ttk.Frame(self, padding=10)
        ana.pack(fill="both", expand=True)

        # Kaynak
        kutu = ttk.LabelFrame(ana, text="Kaynak", padding=8)
        kutu.pack(fill="x", **pad)
        ttk.Button(kutu, text="Klasör seç...", command=self._klasor_sec).pack(side="left")
        ttk.Button(kutu, text="Dosya seç...", command=self._dosya_sec).pack(side="left", padx=(6, 0))
        ttk.Button(kutu, text="Temizle", command=self._temizle).pack(side="left", padx=(6, 0))
        ttk.Label(kutu, textvariable=self.kaynak_metin, foreground="#555").pack(side="left", padx=12)

        # Ayarlar
        kutu = ttk.LabelFrame(ana, text="Ayarlar", padding=8)
        kutu.pack(fill="x", **pad)
        satir = ttk.Frame(kutu)
        satir.pack(fill="x")
        ttk.Label(satir, text="Biçim:").pack(side="left")
        ttk.Radiobutton(satir, text="JPEG (küçük, önerilen)", variable=self.fmt, value="jpeg",
                        command=self._fmt_degisti).pack(side="left", padx=(6, 0))
        ttk.Radiobutton(satir, text="PNG (kayıpsız, büyük)", variable=self.fmt, value="png",
                        command=self._fmt_degisti).pack(side="left", padx=(6, 0))
        ttk.Label(satir, text="   Kalite:").pack(side="left")
        self.kalite_kutu = ttk.Spinbox(satir, from_=50, to=100, width=5, textvariable=self.kalite)
        self.kalite_kutu.pack(side="left", padx=(4, 0))

        satir = ttk.Frame(kutu)
        satir.pack(fill="x", pady=(6, 0))
        ttk.Label(satir, text="Çıktı klasörü:").pack(side="left")
        ttk.Entry(satir, textvariable=self.cikti).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(satir, text="Seç...", command=self._cikti_sec).pack(side="left")
        ttk.Button(satir, text="Yanına yaz", command=lambda: self.cikti.set("")).pack(side="left", padx=(4, 0))
        ttk.Label(kutu, text="Boş bırakılırsa her dosya orijinalinin yanına yazılır.",
                  foreground="#777").pack(anchor="w", pady=(2, 0))

        satir = ttk.Frame(kutu)
        satir.pack(fill="x", pady=(6, 0))
        ttk.Checkbutton(satir, text="Var olan hedefin üstüne yaz", variable=self.zorla).pack(side="left")
        ttk.Checkbutton(satir, text="Başarılı çevirimden sonra orijinal HEIC dosyasını sil",
                        variable=self.sil).pack(side="left", padx=(16, 0))

        # Düğmeler
        satir = ttk.Frame(ana)
        satir.pack(fill="x", **pad)
        self.dene_dugme = ttk.Button(satir, text="Dene (yazmadan listele)",
                                     command=lambda: self._baslat(dene=True))
        self.dene_dugme.pack(side="left")
        self.baslat_dugme = ttk.Button(satir, text="Başlat", command=self._baslat)
        self.baslat_dugme.pack(side="left", padx=(6, 0))
        self.iptal_dugme = ttk.Button(satir, text="Durdur", command=self.iptal.set, state="disabled")
        self.iptal_dugme.pack(side="left", padx=(6, 0))
        self.durum = ttk.Label(satir, text="")
        self.durum.pack(side="right")

        self.ilerleme = ttk.Progressbar(ana, mode="determinate")
        self.ilerleme.pack(fill="x", **pad)

        # Günlük
        kutu = ttk.LabelFrame(ana, text="Günlük", padding=4)
        kutu.pack(fill="both", expand=True, **pad)
        self.gunluk = tk.Text(kutu, height=12, wrap="none", state="disabled", font=("Consolas", 9))
        kaydirma = ttk.Scrollbar(kutu, command=self.gunluk.yview)
        self.gunluk.configure(yscrollcommand=kaydirma.set)
        self.gunluk.pack(side="left", fill="both", expand=True)
        kaydirma.pack(side="right", fill="y")
        self.gunluk.tag_configure("hata", foreground="#b00020")
        self.gunluk.tag_configure("soluk", foreground="#777")

    # ----- seçimler --------------------------------------------------------
    def _klasor_sec(self) -> None:
        yol = filedialog.askdirectory(title="HEIC dosyalarının olduğu klasör")
        if not yol:
            return
        self.kok = Path(yol)
        self.kaynaklar = cekirdek.tara(self.kok)
        self._kaynak_guncelle(str(self.kok))

    def _dosya_sec(self) -> None:
        yollar = filedialog.askopenfilenames(
            title="HEIC dosyaları seç",
            filetypes=[("HEIC/HEIF", "*.heic *.heif *.hif *.HEIC *.HEIF"), ("Tümü", "*.*")])
        if not yollar:
            return
        yeni = [Path(y) for y in yollar]
        self.kaynaklar = sorted(set(self.kaynaklar) | set(yeni))
        self.kok = Path(os.path.commonpath([str(p.parent) for p in self.kaynaklar]))
        self._kaynak_guncelle("seçili dosyalar")

    def _temizle(self) -> None:
        self.kaynaklar, self.kok = [], None
        self.kaynak_metin.set("Henüz seçim yok")

    def _kaynak_guncelle(self, etiket: str) -> None:
        n = len(self.kaynaklar)
        self.kaynak_metin.set(f"{n} dosya - {etiket}" if n else f"HEIC bulunamadı - {etiket}")
        self._yaz(f"{n} HEIC/HEIF dosyası seçildi ({etiket})", "soluk")

    def _cikti_sec(self) -> None:
        yol = filedialog.askdirectory(title="Çıktı klasörü")
        if yol:
            self.cikti.set(yol)

    def _fmt_degisti(self) -> None:
        self.kalite_kutu.configure(state="normal" if self.fmt.get() == "jpeg" else "disabled")

    # ----- çalıştırma ------------------------------------------------------
    def _baslat(self, dene: bool = False) -> None:
        if self.calisiyor:
            return
        if not self.kaynaklar:
            messagebox.showinfo(BASLIK, "Önce bir klasör ya da dosya seç.")
            return
        if self.sil.get() and not dene:
            if not messagebox.askyesno(BASLIK, "Orijinal HEIC dosyaları çevrildikten sonra SİLİNECEK.\nEmin misin?"):
                return
        ayar = dict(
            fmt=self.fmt.get(), kalite=int(self.kalite.get()),
            cikti=Path(self.cikti.get()) if self.cikti.get().strip() else None,
            sil=self.sil.get(), zorla=self.zorla.get(), dene=dene,
        )
        self.calisiyor = True
        self.iptal.clear()
        for d in (self.dene_dugme, self.baslat_dugme):
            d.configure(state="disabled")
        self.iptal_dugme.configure(state="normal")
        self.ilerleme.configure(maximum=len(self.kaynaklar), value=0)
        self._yaz(("-- DENEME -- " if dene else "-- BAŞLADI -- ") + f"{len(self.kaynaklar)} dosya", "soluk")
        threading.Thread(target=self._isci, args=(list(self.kaynaklar), self.kok, ayar), daemon=True).start()

    def _isci(self, dosyalar: list[Path], kok: Path, a: dict) -> None:
        uzanti = ".jpg" if a["fmt"] == "jpeg" else ".png"
        ok = atlandi = hata = 0
        for i, kaynak in enumerate(dosyalar, 1):
            if self.iptal.is_set():
                self.kuyruk.put(("yaz", "Durduruldu.", "hata"))
                break
            hedef = cekirdek.hedef_yol(kaynak, kok, a["cikti"], uzanti)
            etiket = f"[{i}/{len(dosyalar)}] {kaynak.name}"
            if hedef.exists() and not a["zorla"]:
                atlandi += 1
                self.kuyruk.put(("yaz", f"{etiket}  -> atlandı (zaten var)", "soluk"))
            elif a["dene"]:
                self.kuyruk.put(("yaz", f"{etiket}  -> {hedef}", None))
            else:
                try:
                    cekirdek.cevir(kaynak, hedef, a["fmt"], a["kalite"])
                except Exception as e:  # noqa: BLE001
                    hata += 1
                    self.kuyruk.put(("yaz", f"{etiket}  -> HATA: {e}", "hata"))
                else:
                    ok += 1
                    if a["sil"]:
                        kaynak.unlink()
                    self.kuyruk.put(("yaz", f"{etiket}  -> {hedef.name}", None))
            self.kuyruk.put(("ilerleme", i))
        self.kuyruk.put(("bitti", ok, atlandi, hata, a["dene"]))

    def _kuyrugu_bosalt(self) -> None:
        try:
            while True:
                m = self.kuyruk.get_nowait()
                if m[0] == "yaz":
                    self._yaz(m[1], m[2])
                elif m[0] == "ilerleme":
                    self.ilerleme.configure(value=m[1])
                    self.durum.configure(text=f"{m[1]}/{len(self.kaynaklar)}")
                elif m[0] == "bitti":
                    _, ok, atlandi, hata, dene = m
                    self._yaz(f"bitti: {ok} çevrildi, {atlandi} atlandı, {hata} hata"
                              + (" (deneme)" if dene else ""), "hata" if hata else "soluk")
                    self.calisiyor = False
                    for d in (self.dene_dugme, self.baslat_dugme):
                        d.configure(state="normal")
                    self.iptal_dugme.configure(state="disabled")
                    self.durum.configure(text="")
        except queue.Empty:
            pass
        self.after(100, self._kuyrugu_bosalt)

    def _yaz(self, metin: str, etiket: str | None = None) -> None:
        self.gunluk.configure(state="normal")
        self.gunluk.insert("end", metin + "\n", etiket or ())
        self.gunluk.see("end")
        self.gunluk.configure(state="disabled")


if __name__ == "__main__":
    Uygulama().mainloop()
