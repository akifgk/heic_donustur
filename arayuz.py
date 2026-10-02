#!/usr/bin/env python3
"""HEIC Dönüştürücü: heic_donustur.py çekirdeğinin Tkinter arayüzü.

Fotoğrafları ya da klasörü pencereye bırak (veya seç), biçimi ve kayıt yerini belirle,
Dönüştür'e bas. Dönüştürme arka iş parçacığında koşar; her dosyanın durumu listede anlık
güncellenir. Listeden bir satır seçilince önizleme yönü düzeltilmiş hâliyle gösterilir.
Ayarlar %APPDATA%\\HEIC-Donustur\\ayarlar.json içinde hatırlanır.
"""
from __future__ import annotations

import ctypes
import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox, ttk

from PIL import Image, ImageOps, ImageTk

import heic_donustur as cekirdek

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _Pencere = TkinterDnD.Tk
    DND_VAR = True
except ImportError:  # paket yoksa arayüz yine açılır, sadece sürükle-bırak olmaz
    _Pencere = tk.Tk
    DND_VAR = False

# Yüksek DPI ekranda Tk bulanık çizilmesin; pencere oluşmadan önce çağrılmalı.
if sys.platform == "win32":
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass

BASLIK = "HEIC Dönüştürücü"
AYAR_DOSYASI = Path(os.environ.get("APPDATA") or Path.home()) / "HEIC-Donustur" / "ayarlar.json"
MODLAR = ("yanina", "yeni", "secili")

RENK = dict(
    zemin="#ffffff", yuzey="#f3f3f3", cizgi="#d4d4d4", metin="#1b1b1b", soluk="#616161",
    vurgu="#0067c0", vurgu_koyu="#00539c", vurgu_acik="#e3eefa", pasif="#a6a6a6",
    basari="#0f7b0f", hata="#c42b1c",
)


# ----- yardımcılar ---------------------------------------------------------
def ayar_oku() -> dict:
    """Kayıtlı ayarları okur; bozuk ya da eksik dosyada varsayılanlara döner."""
    a = {"fmt": "jpeg", "kalite": 92, "cikti_modu": "yanina",
         "yeni_klasor_adi": "Donusturulmus", "cikti": "", "zorla": False}
    try:
        kayit = json.loads(AYAR_DOSYASI.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return a
    if kayit.get("fmt") in ("jpeg", "png"):
        a["fmt"] = kayit["fmt"]
    if isinstance(kayit.get("kalite"), int) and 50 <= kayit["kalite"] <= 100:
        a["kalite"] = kayit["kalite"]
    if kayit.get("cikti_modu") in MODLAR:
        a["cikti_modu"] = kayit["cikti_modu"]
    for anahtar in ("yeni_klasor_adi", "cikti"):
        if isinstance(kayit.get(anahtar), str):
            a[anahtar] = kayit[anahtar]
    a["zorla"] = bool(kayit.get("zorla", False))
    return a


def ayar_yaz(a: dict) -> None:
    try:
        AYAR_DOSYASI.parent.mkdir(parents=True, exist_ok=True)
        AYAR_DOSYASI.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass  # ayar kaydedilemedi diye dönüştürme durmasın


def boyut_yaz(b: float) -> str:
    for birim in ("B", "KB", "MB", "GB"):
        if b < 1024 or birim == "GB":
            return f"{b:.0f} {birim}" if birim == "B" else f"{b:.1f} {birim}".replace(".", ",")
        b /= 1024
    return ""


def hedef_bul(kaynak: Path, kok: Path | None, cikti: Path | None, uzanti: str,
              yeni_ad: str | None) -> Path:
    """Çıktı yolu. cikti None ve yeni_ad yoksa orijinalin yanı; yeni_ad varsa kaynak kökünün
    içindeki yeni klasör (kök bulunamazsa dosyanın kendi klasöründe). Alt klasör yapısı korunur."""
    ad = kaynak.with_suffix(uzanti).name
    if yeni_ad:
        if kok is None:
            return kaynak.parent / yeni_ad / ad
        cikti = kok / yeni_ad
    if cikti is None:
        return kaynak.with_suffix(uzanti)
    if kok is not None and kaynak.is_relative_to(kok):
        return cekirdek.hedef_yol(kaynak, kok, cikti, uzanti)
    return cikti / ad


def geri_donusume_tasi(yol: Path) -> None:
    """Dosyayı Geri Dönüşüm Kutusu'na taşır; Windows dışında kalıcı siler."""
    if sys.platform != "win32":
        yol.unlink()
        return
    from ctypes import wintypes

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
                    ("fFlags", ctypes.c_uint16), ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", wintypes.LPCWSTR)]

    fo_delete, fof_silent, fof_noconfirmation, fof_allowundo, fof_noerrorui = 3, 0x4, 0x10, 0x40, 0x400
    # pFrom çift NUL ile biter: biri burada, biri ctypes'ın eklediği
    islem = SHFILEOPSTRUCTW(None, fo_delete, str(yol.resolve()) + "\0", None,
                            fof_allowundo | fof_noconfirmation | fof_silent | fof_noerrorui,
                            False, None, None)
    sonuc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(islem))
    if sonuc or islem.fAnyOperationsAborted or yol.exists():
        raise OSError(f"Geri Dönüşüm Kutusu'na taşınamadı (kod {sonuc})")


def exif_tarih(exif) -> str:
    """'2026:09:18 13:09:00' -> '18.09.2026 13:09'; yoksa boş."""
    ham = exif.get_ifd(0x8769).get(36867) or exif.get(306) or ""
    try:
        tarih, saat = str(ham).split(" ")
        y, a, g = tarih.split(":")
        return f"{g}.{a}.{y} {saat[:5]}"
    except ValueError:
        return ""


class Uygulama(_Pencere):
    def __init__(self) -> None:
        super().__init__()
        self.title(BASLIK)
        self._stil()
        self._yerlestir(int(920 * self.olcek), int(740 * self.olcek))

        self.kaynaklar: list[Path] = []      # listedeki HEIC dosyaları, sıralı
        self.kokler: set[Path] = set()       # eklenen klasörler ve tek dosyaların klasörleri
        self.hedefler: dict[str, Path] = {}  # satır -> yazılan çıktı (önizleme ve açma için)
        self.kuyruk: queue.Queue = queue.Queue()
        self.calisiyor = False
        self.kapanacak = False
        self.iptal = threading.Event()
        self.son_cikti: Path | None = None
        self._onizleme_no = 0
        self._onizleme_foto = None  # PhotoImage'ı tut, yoksa çöpe gider ve resim kaybolur

        a = ayar_oku()
        self.fmt = tk.StringVar(value=a["fmt"])
        self.kalite = tk.IntVar(value=a["kalite"])
        self.cikti_modu = tk.StringVar(value=a["cikti_modu"])
        self.yeni_klasor_adi = tk.StringVar(value=a["yeni_klasor_adi"])
        self.cikti = tk.StringVar(value=a["cikti"])
        self.zorla = tk.BooleanVar(value=a["zorla"])
        self.sil = tk.BooleanVar(value=False)  # bilerek hatırlanmaz

        self._kur()
        self._fmt_degisti()
        self._mod_degisti(sor=False)
        self._liste_yenile()
        if DND_VAR:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._birakildi)
        self.protocol("WM_DELETE_WINDOW", self._kapat)
        self.bind("<Control-o>", lambda _e: self._dosya_sec())
        self.after(60, self._kuyrugu_bosalt)

    # ----- görünüm ---------------------------------------------------------
    def _stil(self) -> None:
        r = RENK
        self.olcek = float(self.tk.call("tk", "scaling")) / (96 / 72)  # 96 DPI'da 1.0
        o = self.olcek
        govde = ("Segoe UI", 10)
        kalin = ("Segoe UI Semibold", 10)
        self.configure(bg=r["zemin"])
        # Varsayılan yazı tipi adlandırılmış fontlardan değişir; option_add("*Font") ttk stillerindeki
        # başlık/kalın yazıları ezdiği için kullanılmıyor.
        for ad in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            tkfont.nametofont(ad).configure(family="Segoe UI", size=10)

        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=r["zemin"], foreground=r["metin"], font=govde,
                    bordercolor=r["cizgi"], lightcolor=r["zemin"], darkcolor=r["zemin"],
                    troughcolor=r["yuzey"], focuscolor=r["vurgu"],
                    selectbackground=r["vurgu_acik"], selectforeground=r["metin"])
        s.map("TLabel", background=[("disabled", r["zemin"])])
        s.configure("Baslik.TLabel", font=("Segoe UI Semibold", 16))
        s.configure("Bolum.TLabel", font=kalin)
        s.configure("Soluk.TLabel", foreground=r["soluk"])
        s.configure("Hata.TLabel", foreground=r["hata"])
        s.configure("Basari.TLabel", foreground=r["basari"])

        s.configure("TButton", background=r["yuzey"], bordercolor=r["cizgi"], lightcolor=r["yuzey"],
                    darkcolor=r["yuzey"], padding=(int(14 * o), int(5 * o)), relief="flat")
        s.map("TButton", background=[("disabled", r["yuzey"]), ("pressed", "#dcdcdc"), ("active", "#e9e9e9")],
              lightcolor=[("pressed", "#dcdcdc"), ("active", "#e9e9e9")],
              darkcolor=[("pressed", "#dcdcdc"), ("active", "#e9e9e9")],
              foreground=[("disabled", r["pasif"])])
        s.configure("Ana.TButton", background=r["vurgu"], foreground="#ffffff", bordercolor=r["vurgu"],
                    lightcolor=r["vurgu"], darkcolor=r["vurgu"], font=kalin,
                    padding=(int(22 * o), int(5 * o)))
        s.map("Ana.TButton",
              background=[("disabled", "#c5d8ec"), ("pressed", r["vurgu_koyu"]), ("active", r["vurgu_koyu"])],
              bordercolor=[("disabled", "#c5d8ec"), ("pressed", r["vurgu_koyu"]), ("active", r["vurgu_koyu"])],
              lightcolor=[("disabled", "#c5d8ec"), ("pressed", r["vurgu_koyu"]), ("active", r["vurgu_koyu"])],
              darkcolor=[("disabled", "#c5d8ec"), ("pressed", r["vurgu_koyu"]), ("active", r["vurgu_koyu"])],
              foreground=[("disabled", "#ffffff")])

        for secici in ("TCheckbutton", "TRadiobutton"):
            s.configure(secici, background=r["zemin"], indicatorbackground="#ffffff",
                        indicatorforeground="#ffffff", upperbordercolor=r["soluk"],
                        lowerbordercolor=r["soluk"], indicatorsize=int(14 * o),
                        indicatormargin=(0, 0, int(8 * o), 0),
                        padding=(0, int(2 * o)))
            s.map(secici, background=[("active", r["zemin"])],
                  indicatorbackground=[("selected", r["vurgu"]), ("pressed", r["vurgu_acik"])],
                  upperbordercolor=[("selected", r["vurgu"]), ("active", r["vurgu"])],
                  lowerbordercolor=[("selected", r["vurgu"]), ("active", r["vurgu"])],
                  foreground=[("disabled", r["pasif"])])

        s.configure("TEntry", fieldbackground="#ffffff", bordercolor=r["cizgi"], lightcolor="#ffffff",
                    darkcolor="#ffffff", padding=int(4 * o))
        s.map("TEntry", bordercolor=[("focus", r["vurgu"])], lightcolor=[("focus", r["vurgu"])],
              fieldbackground=[("disabled", r["yuzey"])], foreground=[("disabled", r["pasif"])])

        s.configure("Horizontal.TScale", background=r["vurgu"], troughcolor="#e4e4e4",
                    bordercolor=r["vurgu"], lightcolor=r["vurgu"], darkcolor=r["vurgu"],
                    sliderlength=int(12 * o))
        s.map("Horizontal.TScale", background=[("disabled", r["pasif"])],
              bordercolor=[("disabled", r["pasif"])], lightcolor=[("disabled", r["pasif"])],
              darkcolor=[("disabled", r["pasif"])])
        s.configure("Horizontal.TProgressbar", background=r["vurgu"], troughcolor=r["yuzey"],
                    bordercolor=r["yuzey"], lightcolor=r["vurgu"], darkcolor=r["vurgu"],
                    thickness=int(6 * o))

        s.configure("Treeview", background="#ffffff", fieldbackground="#ffffff",
                    bordercolor=r["cizgi"], rowheight=int(26 * o))
        s.map("Treeview", background=[("selected", r["vurgu_acik"])],
              foreground=[("selected", r["metin"])])
        s.configure("Treeview.Heading", background=r["yuzey"], foreground=r["soluk"],
                    font=("Segoe UI Semibold", 9), relief="flat", bordercolor=r["cizgi"],
                    lightcolor=r["yuzey"], darkcolor=r["yuzey"], padding=(int(6 * o), int(4 * o)))
        s.map("Treeview.Heading", background=[("active", "#e9e9e9")])
        s.configure("Vertical.TScrollbar", background=r["yuzey"], troughcolor="#ffffff",
                    bordercolor="#ffffff", lightcolor=r["yuzey"], darkcolor=r["yuzey"],
                    arrowcolor=r["soluk"])
        s.configure("TSeparator", background=r["cizgi"])

    def _yerlestir(self, gen: int, yuk: int) -> None:
        """Pencereyi ekranın çalışma alanına (görev çubuğu hariç) sığdırıp ortalar."""
        sol, ust, sag, alt = 0, 0, self.winfo_screenwidth(), self.winfo_screenheight()
        if sys.platform == "win32":
            from ctypes import wintypes
            alan = wintypes.RECT()
            if ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(alan), 0):  # SPI_GETWORKAREA
                sol, ust, sag, alt = alan.left, alan.top, alan.right, alan.bottom
        cerceve = int(40 * self.olcek)  # başlık çubuğu ve kenarlık payı
        gen = min(gen, sag - sol - 20)
        yuk = min(yuk, alt - ust - cerceve - 10)
        self.minsize(min(int(780 * self.olcek), gen), min(int(600 * self.olcek), yuk))
        x = sol + (sag - sol - gen) // 2
        y = ust + max(0, (alt - ust - yuk - cerceve) // 2)
        self.geometry(f"{gen}x{yuk}+{x}+{y}")

    def _kur(self) -> None:
        r, o = RENK, self.olcek
        p = lambda n: int(n * o)  # noqa: E731  (piksel ölçeği)

        ana = ttk.Frame(self, padding=(p(24), p(18), p(24), p(16)))
        ana.pack(fill="both", expand=True)
        ana.columnconfigure(0, weight=1)
        ana.rowconfigure(2, weight=1)

        # Başlık
        ust = ttk.Frame(ana)
        ust.grid(row=0, column=0, sticky="ew")
        ttk.Label(ust, text=BASLIK, style="Baslik.TLabel").pack(anchor="w")
        ttk.Label(ust, style="Soluk.TLabel",
                  text="iPhone fotoğraflarını JPEG ya da PNG'ye çevirir. "
                       "Çekim tarihi, konum ve fotoğrafın yönü korunur.").pack(anchor="w", pady=(p(2), 0))

        # Araç çubuğu
        arac = ttk.Frame(ana)
        arac.grid(row=1, column=0, sticky="ew", pady=(p(16), p(8)))
        self.klasor_dugme = ttk.Button(arac, text="Klasör ekle", command=self._klasor_sec)
        self.klasor_dugme.pack(side="left")
        self.dosya_dugme = ttk.Button(arac, text="Dosya ekle", command=self._dosya_sec)
        self.dosya_dugme.pack(side="left", padx=(p(8), 0))
        self.temizle_dugme = ttk.Button(arac, text="Listeyi temizle", command=self._temizle)
        self.temizle_dugme.pack(side="right")
        self.ozet = ttk.Label(arac, text="", style="Soluk.TLabel")
        self.ozet.pack(side="right", padx=(0, p(12)))

        # Liste (boşken bırakma alanı) + önizleme
        orta = ttk.Frame(ana)
        orta.grid(row=2, column=0, sticky="nsew")
        orta.columnconfigure(0, weight=1)
        orta.rowconfigure(0, weight=1)

        kutu = ttk.Frame(orta)
        kutu.grid(row=0, column=0, sticky="nsew")
        kutu.columnconfigure(0, weight=1)
        kutu.rowconfigure(0, weight=1)
        self.agac = ttk.Treeview(kutu, columns=("ad", "klasor", "boyut", "durum"),
                                 show="headings", selectmode="extended")
        for kol, baslik, gen, hiza, esne in (("ad", "Dosya", 150, "w", False),
                                             ("klasor", "Klasör", 90, "w", True),
                                             ("boyut", "Boyut", 76, "e", False),
                                             ("durum", "Durum", 270, "w", True)):
            self.agac.heading(kol, text=baslik, anchor=hiza)
            self.agac.column(kol, width=p(gen), minwidth=p(60), anchor=hiza, stretch=esne)
        self.agac.tag_configure("ok", foreground=r["basari"])
        self.agac.tag_configure("hata", foreground=r["hata"])
        self.agac.tag_configure("soluk", foreground=r["soluk"])
        self.kaydirma = ttk.Scrollbar(kutu, orient="vertical", command=self.agac.yview)
        self.agac.configure(yscrollcommand=self.kaydirma.set)
        self.agac.grid(row=0, column=0, sticky="nsew")
        self.kaydirma.grid(row=0, column=1, sticky="ns")
        self.agac.bind("<<TreeviewSelect>>", self._secim_degisti)
        self.agac.bind("<Delete>", lambda _e: self._secileni_cikar())
        self.agac.bind("<Double-1>", self._cift_tik)
        self.agac.bind("<Button-3>", self._sag_tik)

        self.menu = tk.Menu(self, tearoff=False)
        self.menu.add_command(label="Aç", command=self._secileni_ac)
        self.menu.add_command(label="Klasörde göster", command=self._klasorde_goster)
        self.menu.add_separator()
        self.menu.add_command(label="Listeden çıkar", command=self._secileni_cikar)

        self.birak = tk.Canvas(kutu, bg=r["zemin"], highlightthickness=0, cursor="hand2")
        self.birak.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self.birak.bind("<Configure>", self._birak_ciz)
        self.birak.bind("<Button-1>", lambda _e: self._dosya_sec())

        on = ttk.Frame(orta, width=p(200))
        on.grid(row=0, column=1, sticky="ns", padx=(p(16), 0))
        on.grid_propagate(False)
        on.columnconfigure(0, weight=1)
        ttk.Label(on, text="Önizleme", style="Bolum.TLabel").grid(row=0, column=0, sticky="w")
        self.on_kutu_boy = p(170)
        cerceve = tk.Frame(on, width=self.on_kutu_boy, height=self.on_kutu_boy, bg=r["yuzey"])
        cerceve.grid(row=1, column=0, sticky="w", pady=(p(6), p(8)))
        cerceve.pack_propagate(False)
        self.on_resim = tk.Label(cerceve, bg=r["yuzey"], fg=r["soluk"], wraplength=p(200),
                                 text="Listeden bir fotoğraf seç")
        self.on_resim.pack(fill="both", expand=True)
        self.on_bilgi = ttk.Label(on, text="", style="Soluk.TLabel", wraplength=p(195), justify="left")
        self.on_bilgi.grid(row=2, column=0, sticky="nw")

        # Ayarlar
        ayar = ttk.Frame(ana)
        ayar.grid(row=3, column=0, sticky="ew", pady=(p(16), 0))
        ayar.columnconfigure(0, minsize=p(110))
        ayar.columnconfigure(1, weight=1)

        ttk.Label(ayar, text="Biçim", style="Bolum.TLabel").grid(row=0, column=0, sticky="w")
        bic = ttk.Frame(ayar)
        bic.grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(bic, text="JPEG", variable=self.fmt, value="jpeg",
                        command=self._fmt_degisti).pack(side="left")
        ttk.Radiobutton(bic, text="PNG", variable=self.fmt, value="png",
                        command=self._fmt_degisti).pack(side="left", padx=(p(18), 0))
        self.kalite_yazi = ttk.Label(bic, text="Kalite")
        self.kalite_yazi.pack(side="left", padx=(p(36), p(10)))
        self.kalite_olcek = ttk.Scale(bic, from_=50, to=100, length=p(170),
                                      command=lambda v: self.kalite.set(round(float(v))))
        self.kalite_olcek.set(self.kalite.get())
        self.kalite_olcek.pack(side="left")
        self.kalite_deger = ttk.Label(bic, textvariable=self.kalite, width=4)
        self.kalite_deger.pack(side="left", padx=(p(8), 0))
        self.bicim_not = ttk.Label(ayar, text="", style="Soluk.TLabel")
        self.bicim_not.grid(row=1, column=1, sticky="w", pady=(p(2), 0))

        ttk.Label(ayar, text="Kayıt yeri", style="Bolum.TLabel").grid(row=2, column=0, sticky="nw",
                                                                     pady=(p(10), 0))
        yer = ttk.Frame(ayar)
        yer.grid(row=2, column=1, sticky="ew", pady=(p(8), 0))
        yer.columnconfigure(1, weight=1)
        ttk.Radiobutton(yer, text="Orijinalin yanına", variable=self.cikti_modu, value="yanina",
                        command=self._mod_degisti).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Radiobutton(yer, text="Kaynak klasörde yeni klasöre", variable=self.cikti_modu, value="yeni",
                        command=self._mod_degisti).grid(row=1, column=0, sticky="w", pady=p(4))
        self.yeni_giris = ttk.Entry(yer, textvariable=self.yeni_klasor_adi, width=24)
        self.yeni_giris.grid(row=1, column=1, sticky="w", padx=p(10))
        ttk.Radiobutton(yer, text="Şu klasöre", variable=self.cikti_modu, value="secili",
                        command=self._mod_degisti).grid(row=2, column=0, sticky="w")
        self.cikti_giris = ttk.Entry(yer, textvariable=self.cikti)
        self.cikti_giris.grid(row=2, column=1, sticky="ew", padx=p(10))
        self.cikti_dugme = ttk.Button(yer, text="Seç…", command=self._cikti_sec)
        self.cikti_dugme.grid(row=2, column=2, sticky="e")

        ttk.Label(ayar, text="Seçenekler", style="Bolum.TLabel").grid(row=3, column=0, sticky="nw",
                                                                     pady=(p(10), 0))
        sec = ttk.Frame(ayar)
        sec.grid(row=3, column=1, sticky="w", pady=(p(8), 0))
        ttk.Checkbutton(sec, text="Aynı adlı çıktı varsa üstüne yaz", variable=self.zorla).pack(anchor="w")
        ttk.Checkbutton(sec, text="Çevrilen HEIC dosyalarını Geri Dönüşüm Kutusu'na taşı",
                        variable=self.sil).pack(anchor="w", pady=(p(2), 0))

        # Alt çubuk
        ttk.Separator(ana).grid(row=4, column=0, sticky="ew", pady=(p(14), p(12)))
        alt = ttk.Frame(ana)
        alt.grid(row=5, column=0, sticky="ew")
        alt.columnconfigure(0, weight=1)
        self.ilerleme = ttk.Progressbar(alt, mode="determinate")
        self.ilerleme.grid(row=0, column=0, columnspan=5, sticky="ew", pady=(0, p(12)))
        self.ilerleme.grid_remove()
        self.durum = ttk.Label(alt, text="", style="Soluk.TLabel")
        self.durum.grid(row=1, column=0, sticky="w")
        self.ac_dugme = ttk.Button(alt, text="Klasörü aç", command=self._klasoru_ac)
        self.ac_dugme.grid(row=1, column=1, padx=(0, p(8)))
        self.ac_dugme.grid_remove()
        self.dene_dugme = ttk.Button(alt, text="Yazmadan dene", command=lambda: self._baslat(dene=True))
        self.dene_dugme.grid(row=1, column=2, padx=(0, p(8)))
        self.iptal_dugme = ttk.Button(alt, text="Durdur", command=self._durdur)
        self.iptal_dugme.grid(row=1, column=3)
        self.iptal_dugme.grid_remove()
        self.baslat_dugme = ttk.Button(alt, text="Dönüştür", style="Ana.TButton", command=self._baslat)
        self.baslat_dugme.grid(row=1, column=4)

    def _birak_ciz(self, _e=None) -> None:
        c, r, o = self.birak, RENK, self.olcek
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        c.create_rectangle(1, 1, w - 2, h - 2, outline="#bdbdbd", dash=(5, 4))
        if DND_VAR:
            ust, alt = ("Fotoğrafları ya da klasörü buraya bırak",
                        "ya da tıklayıp seç; klasörlerin alt klasörleri de taranır")
        else:
            ust, alt = "Fotoğraf seçmek için tıkla", "Sürükle-bırak için: pip install tkinterdnd2"
        c.create_text(w / 2, h / 2 - 13 * o, text=ust, fill=r["metin"], font=("Segoe UI Semibold", 12))
        c.create_text(w / 2, h / 2 + 15 * o, text=alt, fill=r["soluk"], font=("Segoe UI", 10))

    # ----- liste -----------------------------------------------------------
    @property
    def kok(self) -> Path | None:
        """Göreli çıktı yolunun kökü: eklenen klasörlerin ortak atası."""
        if not self.kokler:
            return None
        try:
            return Path(os.path.commonpath([str(k) for k in self.kokler]))
        except ValueError:  # farklı sürücüler
            return None

    def _ekle(self, dosyalar: list[Path], kokler: list[Path]) -> None:
        if self.calisiyor:
            return
        once = len(self.kaynaklar)
        # klasör klasör, her klasörün kendi dosyaları alt klasörlerden önce
        self.kaynaklar = sorted(set(self.kaynaklar) | set(dosyalar),
                                key=lambda d: (str(d.parent).lower(), d.name.lower()))
        if len(self.kaynaklar) > once:
            self.kokler.update(kokler)
        self._liste_yenile()
        eklenen = len(self.kaynaklar) - once
        if dosyalar and not eklenen:
            self._durum_yaz("Bu dosyalar zaten listede.")
        elif not dosyalar:
            self._durum_yaz("Seçilen yerde HEIC/HEIF dosyası bulunamadı.", "Hata.TLabel")
        else:
            self._durum_yaz(f"{eklenen} dosya eklendi.")

    def _klasor_sec(self) -> None:
        yol = filedialog.askdirectory(title="HEIC dosyalarının olduğu klasör")
        if yol:
            kok = Path(yol)
            self._ekle(cekirdek.tara(kok), [kok])

    def _dosya_sec(self) -> None:
        if self.calisiyor:
            return
        yollar = filedialog.askopenfilenames(
            title="HEIC dosyaları seç",
            filetypes=[("HEIC/HEIF", "*.heic *.heif *.hif *.HEIC *.HEIF"), ("Tümü", "*.*")])
        dosyalar = [Path(y) for y in yollar if Path(y).suffix.lower() in cekirdek.UZANTILAR]
        if yollar:
            self._ekle(dosyalar, sorted({d.parent for d in dosyalar}))

    def _birakildi(self, event) -> None:
        """Pencereye bırakılan klasör/dosyaları listeye ekler."""
        yollar = [Path(y) for y in self.tk.splitlist(event.data)]
        dosyalar, kokler = [], []
        for y in yollar:
            if y.is_dir():
                dosyalar.extend(cekirdek.tara(y))
                kokler.append(y)
            elif y.is_file() and y.suffix.lower() in cekirdek.UZANTILAR:
                dosyalar.append(y)
                kokler.append(y.parent)
        self._ekle(dosyalar, kokler)

    def _liste_yenile(self) -> None:
        """Ağacı self.kaynaklar'a göre baştan kurar (dosya ekleme/çıkarma sonrası)."""
        self.agac.delete(*self.agac.get_children())
        kok = self.kok
        toplam = 0
        for d in self.kaynaklar:
            try:
                b = d.stat().st_size
            except OSError:
                b = 0
            toplam += b
            klasor = str(d.parent.relative_to(kok)) if kok and d.is_relative_to(kok) else str(d.parent)
            klasor = "" if klasor == "." else klasor
            hedef = self.hedefler.get(str(d))
            durum, etiket = ("Çevrildi", "ok") if hedef and hedef.exists() else ("", ())
            self.agac.insert("", "end", iid=str(d), values=(d.name, klasor, boyut_yaz(b), durum),
                             tags=etiket)
        n = len(self.kaynaklar)
        self.ozet.configure(text=f"{n} dosya, {boyut_yaz(toplam)}" if n else "")
        if n:
            self.birak.grid_remove()
        else:
            self.birak.grid()
            self._onizleme_temizle()
        self._dugmeleri_ayarla()

    def _temizle(self) -> None:
        if self.calisiyor:
            return
        self.kaynaklar, self.kokler, self.hedefler = [], set(), {}
        self.ac_dugme.grid_remove()
        self.ilerleme.grid_remove()
        self._liste_yenile()
        self._durum_yaz("")

    def _secileni_cikar(self) -> None:
        if self.calisiyor:
            return
        sec = set(self.agac.selection())
        if not sec:
            return
        self.kaynaklar = [d for d in self.kaynaklar if str(d) not in sec]
        if not self.kaynaklar:
            self.kokler = set()
        self._liste_yenile()

    def _secili_yol(self) -> Path | None:
        """Sağ tık / çift tık için: çevrildiyse çıktı, değilse kaynak."""
        sec = self.agac.selection()
        if not sec:
            return None
        hedef = self.hedefler.get(sec[0])
        return hedef if hedef and hedef.exists() else Path(sec[0])

    def _secileni_ac(self) -> None:
        yol = self._secili_yol()
        if yol is None:
            return
        try:
            os.startfile(yol)  # type: ignore[attr-defined]
        except OSError as e:
            self._durum_yaz(f"Açılamadı: {e}", "Hata.TLabel")

    def _klasorde_goster(self) -> None:
        yol = self._secili_yol()
        if yol is not None:
            subprocess.Popen(f'explorer /select,"{yol}"')

    def _cift_tik(self, event) -> None:
        if self.agac.identify_row(event.y):
            self._secileni_ac()

    def _sag_tik(self, event) -> None:
        satir = self.agac.identify_row(event.y)
        if not satir:
            return
        if satir not in self.agac.selection():
            self.agac.selection_set(satir)
        self.menu.entryconfigure("Listeden çıkar", state="disabled" if self.calisiyor else "normal")
        self.menu.tk_popup(event.x_root, event.y_root)

    # ----- önizleme --------------------------------------------------------
    def _onizleme_temizle(self) -> None:
        self._onizleme_no += 1
        self._onizleme_foto = None
        self.on_resim.configure(image="", text="Listeden bir fotoğraf seç")
        self.on_bilgi.configure(text="")

    def _secim_degisti(self, _e=None) -> None:
        yol = self._secili_yol()
        if yol is None:
            return
        self._onizleme_no += 1
        self.on_resim.configure(image="", text="Yükleniyor…")
        self.on_bilgi.configure(text="")
        threading.Thread(target=self._onizleme_hazirla, args=(self._onizleme_no, yol),
                         daemon=True).start()

    def _onizleme_hazirla(self, no: int, yol: Path) -> None:
        kenar = self.on_kutu_boy - 8
        try:
            with Image.open(yol) as img:
                exif = img.getexif()
                duz = ImageOps.exif_transpose(img)  # dosya nasıl görünecekse öyle göster
                genislik, yukseklik = duz.size
                duz.thumbnail((kenar, kenar))
                kucuk = duz.convert("RGB")
            marka, model = str(exif.get(271, "")).strip(), str(exif.get(272, "")).strip()
            kamera = model if model.startswith(marka) else f"{marka} {model}".strip()
            satirlar = [yol.name if yol.suffix.lower() in cekirdek.UZANTILAR else f"Çıktı: {yol.name}",
                        f"{genislik} × {yukseklik} piksel, {boyut_yaz(yol.stat().st_size)}"]
            tarih = exif_tarih(exif)
            if tarih:
                satirlar.append(f"Çekim: {tarih}")
            if kamera:
                satirlar.append(kamera)
            if exif.get_ifd(0x8825):
                satirlar.append("Konum bilgisi var")
            self.kuyruk.put(("onizleme", no, kucuk, "\n".join(satirlar)))
        except Exception as e:  # noqa: BLE001
            self.kuyruk.put(("onizleme", no, None, f"Önizleme açılamadı:\n{e}"))

    # ----- ayarlar ---------------------------------------------------------
    def _fmt_degisti(self) -> None:
        jpeg = self.fmt.get() == "jpeg"
        durum = ["!disabled"] if jpeg else ["disabled"]
        for w in (self.kalite_olcek, self.kalite_yazi, self.kalite_deger):
            w.state(durum)
        self.bicim_not.configure(
            text="JPEG küçük dosya verir; 90 üstü kalitede fark gözle seçilmez." if jpeg
            else "PNG kayıpsızdır ama her fotoğraf 15–25 MB olur.")

    def _mod_degisti(self, sor: bool = True) -> None:
        mod = self.cikti_modu.get()
        self.yeni_giris.state(["!disabled"] if mod == "yeni" else ["disabled"])
        for w in (self.cikti_giris, self.cikti_dugme):
            w.state(["!disabled"] if mod == "secili" else ["disabled"])
        if sor and mod == "secili" and not self.cikti.get().strip():
            self._cikti_sec()

    def _cikti_sec(self) -> None:
        yol = filedialog.askdirectory(title="Çıktı klasörü")
        if yol:
            self.cikti.set(str(Path(yol)))
            self.cikti_modu.set("secili")
            self._mod_degisti(sor=False)

    def _ayarlar(self) -> dict:
        return {"fmt": self.fmt.get(), "kalite": int(self.kalite.get()),
                "cikti_modu": self.cikti_modu.get(), "yeni_klasor_adi": self.yeni_klasor_adi.get(),
                "cikti": self.cikti.get(), "zorla": bool(self.zorla.get())}

    def _dugmeleri_ayarla(self) -> None:
        bos = not self.kaynaklar
        for d in (self.dene_dugme, self.baslat_dugme):
            d.state(["disabled"] if bos or self.calisiyor else ["!disabled"])
        for d in (self.klasor_dugme, self.dosya_dugme):
            d.state(["disabled"] if self.calisiyor else ["!disabled"])
        self.temizle_dugme.state(["disabled"] if bos or self.calisiyor else ["!disabled"])

    def _durum_yaz(self, metin: str, stil: str = "Soluk.TLabel") -> None:
        self.durum.configure(text=metin, style=stil)

    # ----- çalıştırma ------------------------------------------------------
    def _baslat(self, dene: bool = False) -> None:
        if self.calisiyor or not self.kaynaklar:
            return
        mod = self.cikti_modu.get()
        kok = self.kok
        yeni_ad = None
        cikti = None
        if mod == "yeni":
            yeni_ad = self.yeni_klasor_adi.get().strip().strip("\\/") or "Donusturulmus"
            self.yeni_klasor_adi.set(yeni_ad)
        elif mod == "secili":
            metin = self.cikti.get().strip()
            if not metin:
                self._durum_yaz("Çıktı klasörünü seç ya da başka bir kayıt yeri işaretle.", "Hata.TLabel")
                return
            cikti = Path(metin)
        if self.sil.get() and not dene:
            if not messagebox.askyesno(
                    BASLIK, f"{len(self.kaynaklar)} HEIC dosyası çevrildikten sonra Geri Dönüşüm "
                            "Kutusu'na taşınacak.\nDevam edilsin mi?", parent=self):
                return
        ayar_yaz(self._ayarlar())

        if mod == "yanina":
            self.son_cikti = kok or self.kaynaklar[0].parent
        elif mod == "yeni":
            self.son_cikti = (kok / yeni_ad) if kok else self.kaynaklar[0].parent / yeni_ad
        else:
            self.son_cikti = cikti

        a = dict(fmt=self.fmt.get(), kalite=int(self.kalite.get()), cikti=cikti, yeni_ad=yeni_ad,
                 sil=self.sil.get(), zorla=self.zorla.get(), dene=dene)
        self.calisiyor = True
        self.iptal.clear()
        for iid in self.agac.get_children():
            self.agac.set(iid, "durum", "Bekliyor")
            self.agac.item(iid, tags=("soluk",))
        self._dugmeleri_ayarla()
        self.ac_dugme.grid_remove()
        self.baslat_dugme.grid_remove()
        self.iptal_dugme.state(["!disabled"])
        self.iptal_dugme.grid()
        self.ilerleme.configure(maximum=len(self.kaynaklar), value=0)
        self.ilerleme.grid()
        self._durum_yaz("Deneniyor, hiçbir dosya yazılmıyor…" if dene else "Başlıyor…")
        threading.Thread(target=self._isci, args=(list(self.kaynaklar), kok, a), daemon=True).start()

    def _durdur(self) -> None:
        self.iptal.set()
        self.iptal_dugme.state(["disabled"])
        self._durum_yaz("Durduruluyor; elindeki dosyayı bitirince duracak…")

    def _isci(self, dosyalar: list[Path], kok: Path | None, a: dict) -> None:
        uzanti = ".jpg" if a["fmt"] == "jpeg" else ".png"
        ok = atlandi = hata = 0
        durduruldu = False
        for i, kaynak in enumerate(dosyalar, 1):
            if self.iptal.is_set():
                durduruldu = True
                break
            iid = str(kaynak)
            self.kuyruk.put(("ilerleme", i - 1, len(dosyalar), kaynak.name))
            hedef = hedef_bul(kaynak, kok, a["cikti"], uzanti, a["yeni_ad"])
            goster = (str(hedef.relative_to(kok)) if kok and hedef.is_relative_to(kok) else str(hedef))
            if not kaynak.exists():
                hata += 1
                self.kuyruk.put(("durum", iid, "Kaynak dosya bulunamadı", "hata", None))
            elif hedef.exists() and not a["zorla"]:
                atlandi += 1
                self.kuyruk.put(("durum", iid, f"Atlandı, zaten var: {hedef.name}", "soluk", None))
            elif a["dene"]:
                self.kuyruk.put(("durum", iid, f"→ {goster}", (), None))
            else:
                try:
                    cekirdek.cevir(kaynak, hedef, a["fmt"], a["kalite"])
                except Exception as e:  # noqa: BLE001
                    hata += 1
                    self.kuyruk.put(("durum", iid, f"Hata: {e}", "hata", None))
                    continue
                ok += 1
                metin = f"Çevrildi: {hedef.name}"
                if a["sil"]:
                    try:
                        geri_donusume_tasi(kaynak)
                        metin += ", HEIC Geri Dönüşüm'de"
                    except OSError as e:
                        metin += f", HEIC taşınamadı ({e})"
                self.kuyruk.put(("durum", iid, metin, "ok", hedef))
        self.kuyruk.put(("bitti", ok, atlandi, hata, a["dene"], durduruldu))

    def _kuyrugu_bosalt(self) -> None:
        try:
            while True:
                m = self.kuyruk.get_nowait()
                tur = m[0]
                if tur == "durum":
                    _, iid, metin, etiket, hedef = m
                    if hedef is not None:
                        self.hedefler[iid] = hedef
                    if self.agac.exists(iid):
                        self.agac.set(iid, "durum", metin)
                        self.agac.item(iid, tags=etiket)
                elif tur == "ilerleme":
                    _, i, n, ad = m
                    self.ilerleme.configure(value=i)
                    self._durum_yaz(f"{i + 1} / {n}   {ad}")
                elif tur == "onizleme":
                    _, no, kucuk, bilgi = m
                    if no == self._onizleme_no:
                        self._onizleme_foto = ImageTk.PhotoImage(kucuk) if kucuk else None
                        self.on_resim.configure(image=self._onizleme_foto or "",
                                                text="" if kucuk else "Önizleme yok")
                        self.on_bilgi.configure(text=bilgi)
                elif tur == "bitti":
                    self._bitti(*m[1:])
                    if self.kapanacak:
                        self.destroy()
                        return
        except queue.Empty:
            pass
        self.after(60, self._kuyrugu_bosalt)

    def _bitti(self, ok: int, atlandi: int, hata: int, dene: bool, durduruldu: bool) -> None:
        self.calisiyor = False
        self.ilerleme.configure(value=self.ilerleme.cget("maximum") if not durduruldu else self.ilerleme.cget("value"))
        self.iptal_dugme.grid_remove()
        self.baslat_dugme.grid()
        self._dugmeleri_ayarla()
        if dene:
            metin = f"Deneme bitti: {len(self.kaynaklar) - atlandi - hata} dosya çevrilecek, {atlandi} atlanacak."
            if hata:
                metin += f" {hata} dosya bulunamadı."
        else:
            metin = f"{ok} çevrildi, {atlandi} atlandı, {hata} hata."
            if ok and self.son_cikti and self.son_cikti.exists():
                self.ac_dugme.grid()
        if durduruldu:
            metin = "Durduruldu. " + metin
        self._durum_yaz(metin, "Hata.TLabel" if hata else ("Basari.TLabel" if ok and not dene else "Soluk.TLabel"))
        self._secim_degisti()  # seçili satır çevrildiyse önizlemeyi çıktıdan yenile

    def _klasoru_ac(self) -> None:
        if self.son_cikti and self.son_cikti.exists():
            os.startfile(self.son_cikti)  # type: ignore[attr-defined]

    def _kapat(self) -> None:
        ayar_yaz(self._ayarlar())
        if self.calisiyor:
            if not messagebox.askyesno(BASLIK, "Dönüştürme sürüyor. Durdurup kapatılsın mı?", parent=self):
                return
            self.kapanacak = True
            self._durdur()
            return
        self.destroy()


if __name__ == "__main__":
    Uygulama().mainloop()
