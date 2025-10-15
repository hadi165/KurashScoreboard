#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Kurash Scoreboard – Photo Theme (Responsive + Zoom + Fullscreen, per-row Y/C/D/T)
- Big defaults; scales by window × DPI × zoom.
- Zoom: = / + / KP_Add (in),  - / KP_Subtract (out),  Ctrl+0 (reset)
- Fullscreen: F11 or Alt+Enter; Esc exits
- Y C D T labels are placed UNDER each set of four digits for BOTH competitors.
"""


import os, re, sys, shutil, subprocess, tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import tkinter.font as tkfont

# Backward-compatible resample filter for Pillow
RESAMPLE = getattr(Image, "Resampling", Image).LANCZOS

# --- Windows DPI awareness to avoid blurry UI ---
if sys.platform == "win32":
    try:
        import ctypes
        # Prefer Per-Monitor V2 if available (Windows 10+), else fall back gracefully
        try:
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
            ctypes.windll.user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
        except Exception:
            try:
                # 2 = PROCESS_PER_MONITOR_DPI_AWARE (V1)
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                # Legacy fallback
                ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# --- Robust resource paths (works inside PyInstaller onefile) ---
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    ROOT_DIR = sys._MEIPASS

FLAGS_DIR  = os.path.join(ROOT_DIR, "Flags")
SOUNDS_DIR = os.path.join(ROOT_DIR, "Sounds")
IKA_LOGO_PATH = os.path.join(FLAGS_DIR, "IKA.png")

APP_TITLE = "Kurash Scoreboard (Photo Theme – Responsive)"


DEFAULT_MEN_MMSS   = (5, 0)
DEFAULT_WOMEN_MMSS = (4, 0)

# ---------- Baseline & big font sizes ----------
BASE_W, BASE_H = 1920, 1080
BASE = dict(
    TIME   = 280,  # red timer
    DIGIT  = 230,  # Y/C/D/T digits
    CODE   = 90,   # IOC codes (TKM/UZB)
    NAME   = 48,
    LABEL  = 108,  # Y C D T (3× larger)
    TOPMETA= 70,   # top-left & top-right info
    SUBMETA= 46,   # gender / weight detail
    WINNER = 54    # mid-ribbon winner text
)
FLAG_W, FLAG_H = 288, 192  # baseline flag size
FLAG_BOOST = 1.6 

# Default zoom for initial layout and Ctrl+0 reset (tune to your preference)
# Default zoom tuned so fullscreen layouts fit on common displays without manual adjustment
DEFAULT_ZOOM = 0.54
BASE_NAME_FRAME_WIDTH = 420

# If True, include OS DPI scaling (Per‑Monitor aware) in layout calculations
# We also normalize the initial zoom by the detected DPI so the effective size
# remains consistent across 100%/125%/150% Windows scaling.
RESPECT_DPI = True

COUNTRIES = [
    ("Afghanistan","AFG"),("Bahrain","BRN"),("Chinese Taipei","TPE"),("Hong Kong","HKG"),
    ("India","IND"),("Indonesia","INA"),("Iran","IRI"),("Iraq","IRQ"),
    ("Japan","JPN"),("Kazakhstan","KAZ"),("Malaysia","MAS"),("Philippines","PHI"),
    ("Qatar","QAT"),("Saudi Arabia","KSA"),("Singapore","SGP"),("South Korea","KOR"),
    ("Tajikistan","TJK"),("Thailand","THA"),("Uzbekistan","UZB"),("Vietnam","VIE"),
]
WEIGHTS = ["-48Kg","-52Kg","-57Kg","-60Kg","-63Kg","-65Kg","-66Kg","-70Kg","-73Kg",
           "-78Kg","-81Kg","-83Kg","-87Kg","+87Kg","-90Kg","-100Kg","+100Kg","-120Kg","+120Kg"]

def country_values(): return [f"{n} ({c})" for n,c in COUNTRIES]
def parse_code(s:str)->str:
    m=re.search(r"\(([A-Za-z]{2,3})\)$", s.strip()); return (m.group(1) if m else s.strip())[:3].upper()
def clamp(n, lo=0, hi=99): return max(lo, min(hi, n))

# Order of score buckets as rendered left → right
SCORE_LABELS = ("G", "Y", "C", "D", "T")
LABEL_COLORS = {"D": "#ff5252", "T": "#ff5252"}
LABEL_TO_INDEX = {label: idx for idx, label in enumerate(SCORE_LABELS)}
SCORE_COUNT = len(SCORE_LABELS)
MAX_TIMEOUTS = 2

# ---------------- Config ----------------
class ConfigWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} – Config"); self.geometry("980x720"); self.resizable(True, True)
        self.show_flags = tk.BooleanVar(value=True)
        self.show_names = tk.BooleanVar(value=False)
        self.country1 = tk.StringVar(value="Turkmenistan (TKM)")
        self.country2 = tk.StringVar(value="Uzbekistan (UZB)")
        self.name1 = tk.StringVar(value="")
        self.name2 = tk.StringVar(value="")
        self.event_left = tk.StringVar(value="G-1 / No.48   Final")
        self.gender = tk.StringVar(value="Men")
        self.weight = tk.StringVar(value="-81Kg")
        self.ring = tk.IntVar(value=1)
        self.m_m = tk.IntVar(value=DEFAULT_MEN_MMSS[0]); self.m_s = tk.IntVar(value=DEFAULT_MEN_MMSS[1])
        self.w_m = tk.IntVar(value=DEFAULT_WOMEN_MMSS[0]); self.w_s = tk.IntVar(value=DEFAULT_WOMEN_MMSS[1])
        self._build()

    def _build(self):
        pad={"padx":10,"pady":8}
        lf = ttk.Labelframe(self, text="Event / Meta"); lf.pack(fill="x", padx=12, pady=12)
        ttk.Label(lf,text="Top-left text:").grid(row=0,column=0,sticky="w",**pad)
        ttk.Entry(lf,width=32,textvariable=self.event_left).grid(row=0,column=1,**pad)
        ttk.Label(lf,text="Gender:").grid(row=1,column=0,sticky="w",**pad)
        ttk.Combobox(lf,width=12,textvariable=self.gender,values=["Men","Women","Boys","Girls"]).grid(row=1,column=1,sticky="w",**pad)
        ttk.Label(lf,text="Weight:").grid(row=2,column=0,sticky="w",**pad)
        ttk.Combobox(lf,width=12,textvariable=self.weight,values=WEIGHTS,state="readonly").grid(row=2,column=1,sticky="w",**pad)
        ttk.Checkbutton(lf,text="Show flags",variable=self.show_flags).grid(row=3,column=0,sticky="w",**pad)
        ttk.Checkbutton(lf,text="Show names (under codes)",variable=self.show_names).grid(row=3,column=1,sticky="w",**pad)

        cf = ttk.Labelframe(self, text="Competitors"); cf.pack(fill="x", padx=12, pady=6)
        ttk.Label(cf,text="Blue country:").grid(row=0,column=0,sticky="w",**pad)
        ttk.Combobox(cf,width=28,state="readonly",values=country_values(),textvariable=self.country1).grid(row=0,column=1,sticky="w",**pad)
        ttk.Label(cf,text="Blue name:").grid(row=1,column=0,sticky="w",**pad)
        ttk.Entry(cf,width=28,textvariable=self.name1).grid(row=1,column=1,sticky="w",**pad)
        ttk.Label(cf,text="Green country:").grid(row=2,column=0,sticky="w",**pad)
        ttk.Combobox(cf,width=28,state="readonly",values=country_values(),textvariable=self.country2).grid(row=2,column=1,sticky="w",**pad)
        ttk.Label(cf,text="Green name:").grid(row=3,column=0,sticky="w",**pad)
        ttk.Entry(cf,width=28,textvariable=self.name2).grid(row=3,column=1,sticky="w",**pad)

        bf = ttk.Frame(self); bf.pack(fill="x", padx=12, pady=8)
        tb = ttk.Labelframe(bf, text="Time Preset"); tb.pack(side="left", padx=6)
        ttk.Label(tb,text="Men (MM:SS)").grid(row=0,column=0,sticky="w",**pad)
        ttk.Spinbox(tb,from_=0,to=59,width=3,textvariable=self.m_m).grid(row=0,column=1,**pad)
        ttk.Spinbox(tb,from_=0,to=59,width=3,textvariable=self.m_s).grid(row=0,column=2,**pad)
        ttk.Label(tb,text="Women (MM:SS)").grid(row=1,column=0,sticky="w",**pad)
        ttk.Spinbox(tb,from_=0,to=59,width=3,textvariable=self.w_m).grid(row=1,column=1,**pad)
        ttk.Spinbox(tb,from_=0,to=59,width=3,textvariable=self.w_s).grid(row=1,column=2,**pad)

        rg = ttk.Labelframe(bf, text="Ring / Actions"); rg.pack(side="left", padx=12)
        ttk.Radiobutton(rg,text="Ring 1",variable=self.ring,value=1).grid(row=0,column=0,sticky="w",**pad)
        ttk.Radiobutton(rg,text="Ring 2",variable=self.ring,value=2).grid(row=0,column=1,sticky="w",**pad)
        ttk.Button(rg,text="About",command=lambda:messagebox.showinfo("About","Responsive photo-style score")).grid(row=1,column=0,**pad)
        ttk.Button(rg,text="Start",command=self._start).grid(row=1,column=1,**pad)
        ttk.Button(rg,text="Exit",command=self.destroy).grid(row=1,column=2,**pad)

      
    def _start(self):
        mm, ss = (self.m_m.get(),self.m_s.get()) if self.gender.get().lower()=="men" else (self.w_m.get(),self.w_s.get())
        cfg=dict(
            show_flags=self.show_flags.get(),show_names=self.show_names.get(),
            code1=parse_code(self.country1.get()),code2=parse_code(self.country2.get()),
            name1=self.name1.get().strip(),name2=self.name2.get().strip(),
            event_left=self.event_left.get().strip(),gender=self.gender.get(),weight=self.weight.get(),
            ring=int(self.ring.get()),mm=clamp(mm,0,59),ss=clamp(ss,0,59),
        )
        self.withdraw(); ScoreboardWindow(self,cfg)

# ---------------- Scoreboard ----------------
class ScoreboardWindow(tk.Toplevel):
    def __init__(self, root, cfg):
        super().__init__(root)
        self.root=root; self.cfg=cfg
        self.title(APP_TITLE); self.configure(bg="black")
        self.geometry(f"{BASE_W}x{BASE_H}"); self.minsize(900,600)
        self._fullscreen=False

        self.time_left = cfg["mm"]*60 + cfg["ss"]
        self.running=False; self.after_id=None
        self.auto_winner = tk.BooleanVar(value=True)

        self.blue=[0]*SCORE_COUNT; self.green=[0]*SCORE_COUNT
        self.timeout_counts = {"BLUE": 0, "GREEN": 0}
        self.timeout_widgets = {}
        self.total_match_time = self.time_left
        self.jaza_active = False
        self.jaza_consumed = False
        self.final_reason = ""
        self.scale=1.0
        self.zoom=DEFAULT_ZOOM  # default zoom (you can adjust in-app)
        self.match_over = False  # lock scoring once the match is finished
        self.final_frame = None  # placeholder for full-screen overlay
        self._winner_flag_img = None
        self._event_counter = 0
        self._last_cy_event = None  # (side, label, seq)
        self._last_dt_event = None  # (side, label, seq)
        self._pending_auto_winner = None
        self._auto_winner_after_id = None
        self.auto_deciding = False

        # Named fonts (resize together)
        self.f_time    = tkfont.Font(family="Arial", weight="bold", size=BASE["TIME"])
        self.f_digit   = tkfont.Font(family="Arial", weight="bold", size=BASE["DIGIT"])
        self.f_code    = tkfont.Font(family="Arial", weight="bold", size=BASE["CODE"])
        self.f_topmeta = tkfont.Font(family="Arial", weight="bold", size=BASE["TOPMETA"])
        self.f_label   = tkfont.Font(family="Arial", weight="bold", size=BASE["LABEL"])
        self.f_name    = tkfont.Font(family="Arial", weight="bold", size=BASE["NAME"])
        self.f_winner  = tkfont.Font(family="Arial", weight="bold", size=BASE["WINNER"])
        self.f_submeta = tkfont.Font(family="Arial", weight="normal", size=BASE["SUBMETA"])

        self._blue_flag_img=None; self._green_flag_img=None
        self._ika_logo_img=None
        self._build(); self._bind(); self._update_time()
        # Apply initial scale
        self._apply_scale()
        self.bind("<Configure>", self._on_resize)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.deiconify(); self.focus_force()
        # Start fullscreen by default (F11/Esc still work)
        self.after(0, lambda: self._toggle_fullscreen(True))


    # ---------- scaling ----------
    def _calc_scale(self):
        s_win = min(max(self.winfo_width(),1)/BASE_W, max(self.winfo_height(),1)/BASE_H)
        try:
            dpi = self.winfo_fpixels('1i')
            s_dpi = max(1.0, dpi/96.0)
        except Exception:
            s_dpi = 1.0
        if not RESPECT_DPI:
            s_dpi = 1.0
        return s_win * s_dpi * self.zoom

    def _apply_scale(self):
        # Include DPI in media scale, but exclude it from font/layout scaling to avoid double DPI
        s_media = self._calc_scale()
        try:
            dpi = self.winfo_fpixels('1i')
            s_dpi = max(1.0, dpi/96.0)
        except Exception:
            s_dpi = 1.0
        if not RESPECT_DPI:
            s_dpi = 1.0

        s_ui = max(0.1, s_media / s_dpi)
        self.scale = s_ui

        def setsize(fontobj, base): fontobj.configure(size=max(10, int(base*s_ui)))
        setsize(self.f_time,   BASE["TIME"])
        setsize(self.f_digit,  BASE["DIGIT"])
        setsize(self.f_code,   BASE["CODE"])
        setsize(self.f_topmeta,BASE["TOPMETA"])
        setsize(self.f_label,  BASE["LABEL"])
        setsize(self.f_name,   BASE["NAME"])
        setsize(self.f_winner, BASE["WINNER"])
        setsize(self.f_submeta,BASE["SUBMETA"])

        self._refresh_flags()
        self._refresh_logo()
        self._sync_name_column_width()

        pad = max(12, int(24*s_ui))
        for cell in getattr(self, "b_cells", []): cell.grid_configure(padx=pad)
        for cell in getattr(self, "g_cells", []): cell.grid_configure(padx=pad)
        self._update_timeout_widgets()
        # Relayout control buttons on scale/resize
        if hasattr(self, "_layout_control_buttons"):
            self._layout_control_buttons()

    def _zoom_in(self):  self.zoom = min(3.0, self.zoom*1.08); self._apply_scale()
    def _zoom_out(self): self.zoom = max(0.35, self.zoom/1.08); self._apply_scale()
    def _zoom_reset(self): self.zoom = DEFAULT_ZOOM; self._apply_scale()

    def _sync_name_column_width(self):
        frames = [getattr(self, "blue_id", None), getattr(self, "green_id", None)]
        if not all(frames):
            return
        try:
            self.update_idletasks()
        except Exception:
            pass

        names = [self.blue_name.cget("text"), self.green_name.cget("text")]
        codes = [self.blue_code.cget("text"), self.green_code.cget("text")]
        name_widths = [self.f_name.measure(txt) if txt else 0 for txt in names]
        code_widths = [self.f_code.measure(txt) if txt else 0 for txt in codes]

        pad = max(40, int(48 * self.scale))
        target_width = max(
            int(BASE_NAME_FRAME_WIDTH * self.scale),
            max(name_widths + [0]) + pad,
            max(code_widths + [0]) + pad // 2
        )

        name_heights = [self.blue_name.winfo_reqheight(), self.green_name.winfo_reqheight()]
        code_heights = [self.blue_code.winfo_reqheight(), self.green_code.winfo_reqheight()]
        content_height = max(name_heights + [0]) + max(code_heights + [0])
        if content_height <= 0:
            try:
                name_ls = self.f_name.metrics("linespace")
                code_ls = self.f_code.metrics("linespace")
            except Exception:
                name_ls = code_ls = 40
            content_height = int((name_ls + code_ls) * 1.2)

        for frame in frames:
            frame.config(width=target_width, height=content_height)

    # ---------- assets ----------
    def _load_flag_image(self, code, w, h):
        for ext in (".jpg",".png",".jpeg"):
            p = os.path.join(FLAGS_DIR, f"{code.upper()}{ext}")
            if os.path.exists(p):
                try:
                    with Image.open(p) as im:
                        resized = im.resize((w, h), RESAMPLE)
                        return ImageTk.PhotoImage(resized)
                except Exception:
                    return None
        return None

    def _refresh_flags(self):
        if not self.cfg.get("show_flags"):
            return

        # make flags scale with zoom/DPI AND boosted by FLAG_BOOST
        fw = max(30, int(FLAG_W * self.scale * FLAG_BOOST))
        fh = max(20, int(FLAG_H * self.scale * FLAG_BOOST))

        img = self._load_flag_image(self.cfg["code1"], fw, fh)
        if img:
            self._blue_flag_img = img
            self.blue_flag.config(image=self._blue_flag_img)

        img = self._load_flag_image(self.cfg["code2"], fw, fh)
        if img:
            self._green_flag_img = img
            self.green_flag.config(image=self._green_flag_img)


    def _refresh_logo(self):
        if not hasattr(self, "ika_logo"):
            return

        if not os.path.exists(IKA_LOGO_PATH):
            return

        # target logo roughly same height and double width of athlete flags
        flag_w = max(30, int(FLAG_W * self.scale * FLAG_BOOST))
        flag_h = max(20, int(FLAG_H * self.scale * FLAG_BOOST))
        max_w = max(40, int(flag_w * 1.0))
        max_h = max(20, int(flag_h * 1.0))

        try:
            with Image.open(IKA_LOGO_PATH) as img:
                ow, oh = img.size
                if ow == 0 or oh == 0:
                    return
                scale = min(max_w / ow, max_h / oh)
                new_size = (max(10, int(ow * scale)), max(10, int(oh * scale)))
                resized = img.resize(new_size, RESAMPLE)
                self._ika_logo_img = ImageTk.PhotoImage(resized)
                self.ika_logo.config(image=self._ika_logo_img)
        except Exception:
            pass


    def _sound_file(self): return os.path.join(SOUNDS_DIR, f"Ring{int(self.cfg.get('ring',1)):02d}.wav")
    def _buzz(self):
        path=self._sound_file()
        try:
            if os.name=="nt":
                import winsound
                if os.path.exists(path): winsound.PlaySound(path, winsound.SND_FILENAME|winsound.SND_ASYNC)
                else: winsound.MessageBeep(winsound.MB_ICONEXCLAMATION); return
                return
            if os.path.exists(path):
                if sys.platform=="darwin" and shutil.which("afplay"): subprocess.Popen(["afplay",path]); return
                if sys.platform.startswith("linux") and shutil.which("aplay"): subprocess.Popen(["aplay","-q",path]); return
                try:
                    import simpleaudio as sa; sa.WaveObject.from_wave_file(path).play(); return
                except Exception: pass
            self.bell()
        except Exception: self.bell()

    # ---------- build ----------
    def _build(self):
        # Top bar grid L/C/R
        top = tk.Frame(self, bg="black"); top.pack(fill="x", pady=(8,0))
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=2)
        top.grid_columnconfigure(2, weight=1)

        self.top_left_meta = tk.Label(top, text=self.cfg.get("event_left",""),
                                      fg="white", bg="black", font=self.f_topmeta)
        self.top_left_meta.grid(row=0, column=0, sticky="w", padx=20)

        left_detail = f"{self.cfg['gender']}   {self.cfg['weight']}"
        self.top_left_detail = tk.Label(top, text=left_detail, fg="#cccccc", bg="black", font=self.f_submeta)
        self.top_left_detail.grid(row=1, column=0, sticky="w", padx=20, pady=(0,0))

        self.time_lbl = tk.Label(top, text="00:00", fg="red", bg="black", font=self.f_time)
        self.time_lbl.grid(row=0, column=1, rowspan=2, sticky="n", pady=(0,4))

        self.ika_logo = tk.Label(top, bg="black")
        self.ika_logo.grid(row=0, column=2, rowspan=2, sticky="e", padx=20)
        self._refresh_logo()

        # Middle area
        mid = tk.Frame(self, bg="black"); mid.pack(expand=True, fill="both", pady=6)

        # ----- BLUE row (centered) -----
        blue_row = tk.Frame(mid, bg="black"); blue_row.pack(fill="x", pady=4)
        tk.Frame(blue_row, bg="black").pack(side="left", expand=True)

        # Flag
        self.blue_flag = tk.Label(blue_row, bg="black")
        if self.cfg.get("show_flags"): self.blue_flag.pack(side="left", padx=(20,10))

        # NEW: vertical stack for name (blue box) + code
        self.blue_id = tk.Frame(blue_row, bg="black")
        self.blue_id.pack(side="left", padx=(0,30))
        self.blue_id.pack_propagate(False)

        self.blue_name = tk.Label(
            self.blue_id, text=self.cfg.get("name1",""),
            bg="#1976d2", fg="white", font=self.f_name, padx=12, pady=4,
            anchor="w", justify="left"
        )
        self.blue_name.pack(side="top", fill="x")

        self.blue_code = tk.Label(
            self.blue_id, text=self.cfg["code1"],
            fg="white", bg="black", font=self.f_code, anchor="w", justify="left"
        )
        self.blue_code.pack(side="top", fill="x")

        # digits + labels in one grid
        self.b_digits_frame = tk.Frame(blue_row, bg="black"); self.b_digits_frame.pack(side="left")
        self.b_digits, self.b_cells = [], []
        for i, letter in enumerate(SCORE_LABELS):
            cell = tk.Frame(self.b_digits_frame, bg="#222"); cell.grid(row=0, column=i, padx=24)
            digit_color = "#ff5252" if letter in ("D","T") else "white"
            lbl  = tk.Label(cell, text="0", fg=digit_color, bg="#222", font=self.f_digit, width=2); lbl.pack()
            self.b_cells.append(cell); self.b_digits.append(lbl)
            # NEW: make the box clickable for Blue
            self._attach_score_clicks(cell, lbl, is_blue=True, idx=i)

            fg = LABEL_COLORS.get(letter, "#ffe000")
            tk.Label(self.b_digits_frame, text=letter,
                    fg=fg, bg="black", font=self.f_label).grid(row=1, column=i, pady=(8,0))
        
        self._create_timeout_control(blue_row, is_blue=True)

        tk.Frame(blue_row, bg="black").pack(side="left", expand=True)


        # Winner ribbon (center)
        self.winner_area = tk.Frame(mid, bg="black")
        self.winner_area.pack(fill="x", pady=6)

        self.winner_lbl = tk.Label(
            self.winner_area, text="",
            font=self.f_winner, fg="black", bg="black",
            padx=30, pady=10
        )
        self.winner_lbl.pack()


        # ----- GREEN row (centered) -----
        green_row = tk.Frame(mid, bg="black"); green_row.pack(fill="x", pady=4)
        tk.Frame(green_row, bg="black").pack(side="left", expand=True)

        # Flag
        self.green_flag = tk.Label(green_row, bg="black")
        if self.cfg.get("show_flags"): self.green_flag.pack(side="left", padx=(20,10))

        # NEW: vertical stack for code + name (green box)
        self.green_id = tk.Frame(green_row, bg="black")
        self.green_id.pack(side="left", padx=(0,30))
        self.green_id.pack_propagate(False)

        self.green_code = tk.Label(
            self.green_id, text=self.cfg["code2"],
            fg="white", bg="black", font=self.f_code, anchor="w", justify="left"
        )
        self.green_code.pack(side="top", fill="x")

        self.green_name = tk.Label(
            self.green_id, text=self.cfg.get("name2",""),
            bg="#2e7d32", fg="white", font=self.f_name, padx=12, pady=4,
            anchor="w", justify="left"
        )
        self.green_name.pack(side="top", fill="x")

        # digits + labels in one grid
        self.g_digits_frame = tk.Frame(green_row, bg="black"); self.g_digits_frame.pack(side="left")
        self.g_digits, self.g_cells = [], []
        for i, letter in enumerate(SCORE_LABELS):
            cell = tk.Frame(self.g_digits_frame, bg="#222"); cell.grid(row=0, column=i, padx=24)
            digit_color = "#ff5252" if letter in ("D","T") else "white"
            lbl  = tk.Label(cell, text="0", fg=digit_color, bg="#222", font=self.f_digit, width=2); lbl.pack()
            self.g_cells.append(cell); self.g_digits.append(lbl)

            # Make the green box clickable as well
            self._attach_score_clicks(cell, lbl, is_blue=False, idx=i)

            fg = LABEL_COLORS.get(letter, "#ffe000")
            tk.Label(self.g_digits_frame, text=letter,
                    fg=fg, bg="black", font=self.f_label).grid(row=1, column=i, pady=(8,0))

        self._create_timeout_control(green_row, is_blue=False)

        tk.Frame(green_row, bg="black").pack(side="left", expand=True)

        # Controls (also add small helpers for fullscreen/zoom)
        # Controls (centered row, responsive wrap)
        self.ctrl = tk.Frame(self, bg="black"); self.ctrl.pack(fill="x", pady=6)

        # Container for buttons; we will grid them responsively in multiple rows
        self.ctrl_btns = tk.Frame(self.ctrl, bg="black")
        self.ctrl_btns.pack()

        self._control_buttons = []
        def add_btn(text, cmd):
            b = tk.Button(self.ctrl_btns, text=text, command=cmd)
            self._control_buttons.append(b)
            return b

        add_btn("Start/Pause (Space)", self._toggle_timer)
        add_btn("Reset Time (t)", self._reset_time)
        add_btn("All Reset (0)", self._reset_all)
        add_btn("New Match",     self._new_match)
        add_btn("Blue WINNER (b)",  lambda: self._show_winner("BLUE"))
        add_btn("Green WINNER (g)", lambda: self._show_winner("GREEN"))
        add_btn("Blue HALOL (Shift+B)",  lambda: self._handle_halal_hotkey("BLUE"))
        add_btn("Green HALOL (Shift+G)", lambda: self._handle_halal_hotkey("GREEN"))
        add_btn("Resume JAZZO (J)",  self._resume_from_jaza)
        add_btn("Fullscreen (F11)", lambda: self._toggle_fullscreen())
        add_btn("Zoom +",           self._zoom_in)
        add_btn("Zoom -",           self._zoom_out)
        add_btn("Zoom 100% (Ctrl+0)", self._zoom_reset)

        # Initial responsive layout
        self._layout_control_buttons()



        self._apply_scale()  # initial

    # ---------- timer / scoring ----------
    def _update_time(self):
        m,s = divmod(self.time_left,60)
        self.time_lbl.config(text=f"{m:02d}:{s:02d}")

    def _tick(self):
        if not self.running:
            return

        # clear previous handle; we'll set a new one if needed
        self.after_id = None

        if self.time_left > 0:
            self.time_left -= 1
            self._update_time()
            if self.time_left <= 0:
                self._handle_time_expired()
                return
            if self._maybe_trigger_jaza_pause():
                return
            self.after_id = self.after(1000, self._tick)
        else:
            self._handle_time_expired()


    def _handle_time_expired(self):
        """Stop timer immediately and show final result."""
        if self.time_left < 0:
            self.time_left = 0

        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None

        self.running = False
        self.jaza_active = False
        self.final_reason = ""
        self._update_time()
        self._buzz()

        # decide winner and show full-screen overlay
        winner = self._winner_by_point_advantage()
        if winner:
            self._schedule_auto_win(winner, "POINT ADVANTAGE")
        else:
            resolved = self._resolve_draw_by_last_event()
            if resolved:
                w, reason = resolved
                self._schedule_auto_win(w, reason)
            else:
                self._show_tie_screen()


    def _toggle_timer(self,_=None):
        if self.jaza_active:
            return
        self.running = not self.running
        if self.running: self.after_id = self.after(1000, self._tick)
        elif self.after_id: self.after_cancel(self.after_id); self.after_id=None

    def _reset_time(self,_=None):
        self.running=False
        if self.after_id: self.after_cancel(self.after_id); self.after_id=None
        self.time_left = self.cfg["mm"]*60 + self.cfg["ss"]
        self.total_match_time = self.time_left
        if self.jaza_active:
            self._show_winner("")
        self.jaza_active = False
        self.jaza_consumed = False
        self.final_reason = ""
        self._update_time()

    def _refresh_digits(self):
        for i,l in enumerate(self.b_digits): l.config(text=str(self.blue[i]))
        for i,l in enumerate(self.g_digits): l.config(text=str(self.green[i]))

    def _cancel_pending_auto_winner(self):
        if self._auto_winner_after_id:
            try:
                self.after_cancel(self._auto_winner_after_id)
            except Exception:
                pass
            self._auto_winner_after_id = None
        self._pending_auto_winner = None
        self.auto_deciding = False

    def _record_score_event(self, side: str, label: str, delta: int):
        if delta <= 0:
            return
        self._event_counter += 1
        seq = self._event_counter
        if label in ("C", "Y"):
            self._last_cy_event = (side, label, seq)
        elif label in ("D", "T"):
            self._last_dt_event = (side, label, seq)

    def _attach_score_clicks(self, cell_widget, lbl_widget, is_blue: bool, idx: int):
        """Bind mouse actions to a score cell (and its label)."""
        def flash(bg="#444"):
            old = cell_widget.cget("bg")
            cell_widget.config(bg=bg)
            cell_widget.after(120, lambda: cell_widget.config(bg=old))

        def inc(_=None):
            self._blue_delta(idx, +1) if is_blue else self._green_delta(idx, +1)
            flash("#3a3a3a")

        def dec(_=None):
            self._blue_delta(idx, -1) if is_blue else self._green_delta(idx, -1)
            flash("#2a2a2a")

        def reset_bucket(_=None):
            if is_blue:
                self.blue[idx] = 0
            else:
                self.green[idx] = 0
            self._refresh_digits()
            flash("#1f1f1f")

        # Bind on the cell AND the inner label so either area works
        for w in (cell_widget, lbl_widget):
            w.bind("<Button-1>", inc)          # left click  +1
            w.bind("<Control-Button-1>", dec)  # ctrl+click -1
            w.bind("<Double-Button-1>", reset_bucket)  # double-left resets this bucket


    def _create_timeout_control(self, parent, is_blue: bool):
        """Create the circular timeout control for a competitor."""
        holder = tk.Frame(parent, bg="black")
        holder.pack(side="left", padx=(20, 10))

        canvas = tk.Canvas(holder, width=80, height=80, bg="black", highlightthickness=0, cursor="hand2")
        canvas.pack()

        color = "#1976d2" if is_blue else "#00e676"
        circle = canvas.create_oval(10, 10, 70, 70, outline=color, width=4)
        font = tkfont.Font(family="Arial", weight="bold", size=32)
        text = canvas.create_text(40, 40, text="+", fill=color, font=font, anchor="center")

        side = "BLUE" if is_blue else "GREEN"
        data = {
            "canvas": canvas,
            "circle": circle,
            "text": text,
            "font": font,
            "color": color,
            "holder": holder,
            "side": side,
        }
        self.timeout_widgets[side] = data

        canvas.bind("<Button-1>", lambda e, s=side: self._handle_timeout_click(s))
        canvas.bind("<Return>", lambda e, s=side: self._handle_timeout_click(s))
        self._update_timeout_widget(side)


    def _timeout_display_text(self, side: str) -> str:
        count = self.timeout_counts.get(side, 0)
        return "+" if count == 0 else str(count)


    def _update_timeout_widget(self, side: str):
        data = self.timeout_widgets.get(side)
        if not data:
            return

        canvas = data["canvas"]
        size = max(64, int(120 * self.scale))
        margin = max(6, int(size * 0.12))
        canvas.config(width=size, height=size)
        canvas.coords(data["circle"], margin, margin, size - margin, size - margin)

        font_size = max(18, int(size * 0.4))
        data["font"].configure(size=font_size)
        canvas.itemconfig(data["text"],
                          text=self._timeout_display_text(side),
                          font=data["font"],
                          fill=data["color"])
        canvas.coords(data["text"], size/2, size/2)
        canvas.itemconfig(data["circle"],
                          outline=data["color"],
                          width=max(3, int(size * 0.08)))


    def _update_timeout_widgets(self):
        for side in ("BLUE", "GREEN"):
            self._update_timeout_widget(side)


    def _handle_timeout_click(self, side: str):
        if self.match_over:
            return

        current = self.timeout_counts.get(side, 0)
        if current >= MAX_TIMEOUTS:
            opponent = "GREEN" if side == "BLUE" else "BLUE"
            self._schedule_auto_win(opponent, "Time out")
            return

        self.timeout_counts[side] = current + 1
        self._update_timeout_widget(side)


    def _handle_halal_hotkey(self, side: str, event=None):
        if self.match_over:
            return "break" if event is not None else None
        winner = "BLUE" if side == "BLUE" else "GREEN"
        self._finish_match_with_winner(winner, reason="HALOL")
        return "break" if event is not None else None




    def _maybe_trigger_jaza_pause(self) -> bool:
        if self._should_trigger_jaza_pause():
            self._enter_jaza_pause()
            return True
        return False


    def _should_trigger_jaza_pause(self) -> bool:
        if self.jaza_active or self.jaza_consumed or self.match_over:
            return False
        if self.total_match_time <= 0:
            return False
        if self.time_left > self.total_match_time / 2:
            return False
        if any(self.blue) or any(self.green):
            return False
        return True


    def _enter_jaza_pause(self):
        if self.jaza_active or self.auto_deciding:
            return
        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None
        self.running = False
        self.jaza_active = True
        self.jaza_consumed = True
        self.winner_lbl.config(text="JAZZO", bg="#ffe000", fg="black")


    def _resume_from_jaza(self):
        if self.match_over:
            return
        if self.auto_deciding:
            self._cancel_pending_auto_winner()
        if not self.jaza_active:
            return
        self.jaza_active = False
        self._show_winner("")
        self.running = True
        self.after_id = self.after(1000, self._tick)

    def _schedule_auto_win(self, winner: str, reason: str = ""):
        """Stop the bout and delay automatic winner for 5s to allow overrides."""
        if not winner:
            return
        existing = self._pending_auto_winner
        if self.auto_deciding and existing and existing[0] == winner and existing[1] == reason:
            return

        self._cancel_pending_auto_winner()
        self.auto_deciding = True
        self.final_reason = reason or ""

        # Halt timers / pauses
        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None
        self.running = False
        self.jaza_active = False
        self._clear_final_screen()

        self._pending_auto_winner = (winner, reason)

        name = self.cfg["name1"] if winner == "BLUE" else self.cfg["name2"]
        bg = "#1976d2" if winner == "BLUE" else "#00e676"
        fg = "white" if winner == "BLUE" else "black"
        reason_text = reason or "AUTO DECISION"
        self.winner_lbl.config(text="", bg="black", fg="black")
        self._auto_winner_after_id = self.after(5000, self._apply_pending_auto_winner)

    def _apply_pending_auto_winner(self):
        pending = self._pending_auto_winner
        self._cancel_pending_auto_winner()
        if not pending or self.match_over:
            return
        winner, reason = pending
        self._finish_match_with_winner(winner, reason)


    def _apply_penalty_side_effects(self, is_blue: bool, idx: int, delta: int):
        """Mirror T/D penalties to the opponent (gives them C or Y)."""
        if delta == 0:
            return

        opponent = self.green if is_blue else self.blue
        opponent_side = "GREEN" if is_blue else "BLUE"

        label = SCORE_LABELS[idx]
        if label == "G":
            winner = "GREEN" if is_blue else "BLUE"
            self._schedule_auto_win(winner, "G PENALTY")
            return
        if label == "T":  # T gives opponent a C
            c_idx = LABEL_TO_INDEX["C"]
            before_c = opponent[c_idx]
            new_c = clamp(before_c + delta)
            opponent[c_idx] = new_c
            gained_c = new_c - before_c
            if gained_c > 0:
                self._record_score_event(opponent_side, "C", gained_c)
        elif label == "D":  # D gives opponent a Y and removes any mirrored C from previous T
            y_idx = LABEL_TO_INDEX["Y"]
            before_y = opponent[y_idx]
            new_y = clamp(before_y + delta)
            opponent[y_idx] = new_y
            gained_y = new_y - before_y
            if gained_y > 0:
                self._record_score_event(opponent_side, "Y", gained_y)
                c_idx = LABEL_TO_INDEX["C"]
                opponent[c_idx] = clamp(opponent[c_idx] - 1)
                penalized = self.blue if is_blue else self.green
                t_idx = LABEL_TO_INDEX["T"]
                if penalized[t_idx] > 0:
                    penalized[t_idx] = clamp(penalized[t_idx] - 1)


    def _finish_match_with_winner(self, winner: str, reason: str = ""):
        """Stop the match immediately and declare the winner."""
        if self.match_over:
            return
        self._cancel_pending_auto_winner()
        self.running = False
        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None
        self.jaza_active = False
        self.final_reason = reason or ""
        self.match_over = True
        self._show_winner(winner, reason)


    def _check_penalty_end(self):
        """End the match if penalty thresholds reached."""
        if self.match_over or self.auto_deciding:
            return True

        y_idx = LABEL_TO_INDEX["Y"]

        if self.blue[y_idx] >= 2:
            self._schedule_auto_win("GREEN", "Y PENALTIES")
            return True
        if self.green[y_idx] >= 2:
            self._schedule_auto_win("BLUE", "Y PENALTIES")
            return True
        return False


    def _winner_by_point_advantage(self) -> str:
        """Compare scores with Y outranking any number of C points.

        Returns "BLUE", "GREEN", or "" if equal by Y and C (true draw).
        """
        y_idx = LABEL_TO_INDEX["Y"]
        c_idx = LABEL_TO_INDEX["C"]
        blue_pair = (self.blue[y_idx], self.blue[c_idx])
        green_pair = (self.green[y_idx], self.green[c_idx])
        if blue_pair > green_pair:
            return "BLUE"
        if green_pair > blue_pair:
            return "GREEN"
        return ""


    def _resolve_draw_by_last_event(self):
        latest = None
        if self._last_cy_event:
            side, label, seq = self._last_cy_event
            latest = ("CY", side, label, seq)
        if self._last_dt_event:
            side, label, seq = self._last_dt_event
            if not latest or seq > latest[3]:
                latest = ("DT", side, label, seq)
        if not latest:
            return None

        kind, side, label, _ = latest
        if kind == "CY":
            if label == "Y":
                return side, 'Last "Y" score'
            if label == "C":
                return side, 'Last "C" score'
            return side, f"Last {label}"

        winner = "GREEN" if side == "BLUE" else "BLUE"
        if label == "D":
            return winner, 'Last "Y" score'
        if label == "T":
            return winner, 'Last "C" score'
        return winner, f"LAST {label} PENALTY"


    def _clear_final_screen(self):
        """Remove final overlay if present."""
        if getattr(self, "final_frame", None):
            try:
                self.final_frame.destroy()
            except Exception:
                pass
        self.final_frame = None
        self._winner_flag_img = None


    def _show_final_winner_screen(self, who: str, reason: str = ""):
        """Cover the UI with a full-screen winner card."""
        self.match_over = True
        self._clear_final_screen()

        if who == "BLUE":
            bg, fg = "#1976d2", "white"
            name, code = self.cfg.get("name1",""), self.cfg.get("code1","")
        elif who == "GREEN":
            bg, fg = "#00e676", "black"
            name, code = self.cfg.get("name2",""), self.cfg.get("code2","")
        else:
            # Fallback to tie screen if unknown
            return self._show_tie_screen()

        s = self._calc_scale()
        name_font = tkfont.Font(family="Arial", weight="bold", size=max(48, int(BASE["TIME"] * 0.7 * s)))
        code_font = tkfont.Font(family="Arial", weight="bold", size=max(40, int(BASE["TIME"] * 0.45 * s)))
        hint_font = tkfont.Font(family="Arial", weight="bold", size=max(24, int(28 * s)))

        self._winner_flag_img = None
        self.final_frame = tk.Frame(self, bg=bg)
        self.final_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        tk.Label(self.final_frame, text="WINNER", bg=bg, fg=fg, font=code_font, pady=10).pack(pady=(30, 10))
        info = tk.Frame(self.final_frame, bg=bg)
        info.pack(pady=(10, 10))

        tk.Label(info, text=name, bg=bg, fg=fg, font=name_font).pack(pady=(0, 6))

        code_row = tk.Frame(info, bg=bg)
        code_row.pack()

        if self.cfg.get("show_flags"):
            flag_w = max(40, int(FLAG_W * self.scale * FLAG_BOOST))
            flag_h = max(28, int(FLAG_H * self.scale * FLAG_BOOST))
            flag_img = self._load_flag_image(code, flag_w, flag_h)
            if flag_img:
                self._winner_flag_img = flag_img
                tk.Label(code_row, image=self._winner_flag_img, bg=bg).pack(side="left", padx=(0, 16))

        tk.Label(code_row, text=code, bg=bg, fg=fg, font=code_font).pack(side="left")

        if reason == "HALOL":
            tk.Label(self.final_frame, text='WINS BY "HALOL"', bg=bg, fg=fg, font=code_font).pack(pady=(10, 0))
        elif reason:
            tk.Label(self.final_frame, text=reason, bg=bg, fg=fg, font=code_font).pack(pady=(10, 0))

        tk.Label(self.final_frame, text="Press 0 to reset", bg=bg, fg=fg, font=hint_font).pack(pady=(20, 10))


    def _show_tie_screen(self):
        """Show neutral screen for tie; lets you pick winner with keys w/m or reset with 0."""
        self.match_over = True
        self._clear_final_screen()

        s = self._calc_scale()
        big_font  = tkfont.Font(family="Arial", weight="bold", size=max(60, int(BASE["TIME"] * 0.8 * s)))
        mid_font  = tkfont.Font(family="Arial", weight="bold", size=max(40, int(BASE["TIME"] * 0.4 * s)))
        hint_font = tkfont.Font(family="Arial", weight="bold", size=max(24, int(28 * s)))

        bg, fg, acc = "black", "#ffe000", "#cccccc"
        self.final_frame = tk.Frame(self, bg=bg)
        self.final_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        tk.Label(self.final_frame, text="TIME UP - TIE", bg=bg, fg=fg, font=big_font).pack(pady=(40, 20))
        tk.Label(self.final_frame, text=f"{self.cfg.get('name1','')} ({self.cfg.get('code1','')})",
                bg=bg, fg=acc, font=mid_font).pack(pady=5)
        tk.Label(self.final_frame, text=f"{self.cfg.get('name2','')} ({self.cfg.get('code2','')})",
                bg=bg, fg=acc, font=mid_font).pack(pady=5)
        tk.Label(self.final_frame, text="Press B for Blue win, G for Green win, or 0 to reset.",
                bg=bg, fg=fg, font=hint_font).pack(pady=(20, 10))

    def _blue_delta(self, idx, d):
        if self.match_over or self.auto_deciding: return
        prev = self.blue[idx]
        new_val = clamp(prev + d)
        delta = new_val - prev
        if delta == 0:
            return

        self.blue[idx] = new_val
        self._record_score_event("BLUE", SCORE_LABELS[idx], delta)
        self._apply_penalty_side_effects(is_blue=True, idx=idx, delta=delta)
        self._refresh_digits()
        if self._check_penalty_end():
            return

    def _green_delta(self, idx, d):
        if self.match_over or self.auto_deciding: return
        prev = self.green[idx]
        new_val = clamp(prev + d)
        delta = new_val - prev
        if delta == 0:
            return

        self.green[idx] = new_val
        self._record_score_event("GREEN", SCORE_LABELS[idx], delta)
        self._apply_penalty_side_effects(is_blue=False, idx=idx, delta=delta)
        self._refresh_digits()
        if self._check_penalty_end():
            return


    def _reset_all(self, _=None):
        self.blue = [0]*SCORE_COUNT
        self.green = [0]*SCORE_COUNT
        self.timeout_counts = {"BLUE": 0, "GREEN": 0}
        self.match_over = False
        self._clear_final_screen()
        self._reset_time()
        self._refresh_digits()
        self._update_timeout_widgets()
        # Relayout control buttons on scale/resize
        self._layout_control_buttons()

    def _layout_control_buttons(self):
        """Lay out control buttons in multiple rows to fit available width.
        Works well on smaller screens where a single row would overflow.
        """
        if not hasattr(self, "_control_buttons") or not self._control_buttons:
            return

        parent = getattr(self, "ctrl_btns", None)
        if parent is None:
            return

        try:
            self.update_idletasks()
        except Exception:
            pass

        # Available width for buttons (fallback to window width if not realized yet)
        avail = parent.winfo_width()
        if avail <= 1:
            avail = max(300, self.winfo_width() - 40)

        pad = max(4, int(8 * self.scale))

        # Clear any existing grid placements
        for b in self._control_buttons:
            try:
                b.grid_forget()
            except Exception:
                pass

        row = 0
        col = 0
        curw = 0
        for b in self._control_buttons:
            # Ask each button how wide it wants to be
            bw = b.winfo_reqwidth() + pad * 2
            # Wrap to next row if exceeding available width
            if col > 0 and (curw + bw > avail):
                row += 1
                col = 0
                curw = 0
            b.grid(row=row, column=col, padx=pad, pady=(pad//2))
            col += 1
            curw += bw
        self.final_reason = ""
        self._show_winner("")  # clear mini ribbon
        self._event_counter = 0
        self._last_cy_event = None
        self._last_dt_event = None
        self._cancel_pending_auto_winner()


    def _new_match(self):
        baseline_time = self.cfg["mm"]*60 + self.cfg["ss"]
        in_progress = self.running or (
            not self.match_over and (
                any(self.blue) or any(self.green) or
                self.timeout_counts.get("BLUE", 0) or
                self.timeout_counts.get("GREEN", 0) or
                self.time_left != baseline_time
            )
        )
        if in_progress:
            confirm = messagebox.askyesno(
                "Confirm New Match",
                "The current match is still in progress.\nReturn to setup for new players?"
            )
            if not confirm:
                return
        self._close()


    def _auto_winner(self):
        w = self._winner_by_point_advantage()
        self._show_winner(w)

    def _show_winner(self, who: str, reason: str = ""):
        # Keep small ribbon (if you still want it mid-match)
        was_auto_deciding = self.auto_deciding
        if who:
            self._cancel_pending_auto_winner()
        if not who:
            self.winner_lbl.config(text="", bg="black", fg="black")
            self.final_reason = ""
            return

        self.final_reason = reason or ""
        reason_display = self.final_reason

        if who == "BLUE":
            if reason_display == "HALOL":
                text = 'Blue competitor wins by "HALOL"'
            else:
                text = f"{self.cfg['name1']} WINS"
            self.winner_lbl.config(text=text, bg="#1976d2", fg="white")
        elif who == "GREEN":
            if reason_display == "HALOL":
                text = 'Green competitor wins by "HALOL"'
            else:
                text = f"{self.cfg['name2']} WINS"
            self.winner_lbl.config(text=text, bg="#00e676", fg="black")

        # If match already ended (or you just want to force the final screen), show overlay too
        if was_auto_deciding:
            self.match_over = True
        if (not self.running and self.time_left == 0) or self.match_over or was_auto_deciding:
            self._show_final_winner_screen(who, reason_display)



    # ---------- fullscreen / keys ----------
    def _toggle_fullscreen(self, force=None):
        cur = bool(self.attributes("-fullscreen"))
        new = (not cur) if force is None else bool(force)
        self.attributes("-fullscreen", new)
        # Apply scaling shortly after fullscreen change to stabilize layout
        self.after(60, self._apply_scale)

    def _bind(self):
        # bind_all so keys work regardless of focus
        b = self.bind_all

        # Timer / reset
        b("<space>", self._toggle_timer)
        b("t", self._reset_time)
        b("0", self._reset_all)
        b("<Key-0>", self._reset_all)
        b("<KP_0>", self._reset_all)

        # Fullscreen
        b("<F11>", lambda e: self._toggle_fullscreen())
        b("<Alt-Return>", lambda e: self._toggle_fullscreen())
        b("<Escape>", lambda e: (self._toggle_fullscreen(False) if self.attributes("-fullscreen") else self._close()))

        # Zoom
        b("<Key-equal>",       lambda e: self._zoom_in())     # '='
        b("<Key-plus>",        lambda e: self._zoom_in())     # '+'
        b("<KP_Add>",          lambda e: self._zoom_in())     # numpad +
        b("<Key-minus>",       lambda e: self._zoom_out())    # '-'
        b("<KP_Subtract>",     lambda e: self._zoom_out())    # numpad -
        b("<Control-Key-0>",   lambda e: self._zoom_reset())  # ctrl+0

        # Blue +/- (Y C D T)
        idx_y = LABEL_TO_INDEX["Y"]
        idx_c = LABEL_TO_INDEX["C"]
        idx_d = LABEL_TO_INDEX["D"]
        idx_t = LABEL_TO_INDEX["T"]

        b("r", lambda e: self._blue_delta(idx_y,+1)); b("R", lambda e: self._blue_delta(idx_y,-1))
        b("h", lambda e: self._blue_delta(idx_y,+1)); b("H", lambda e: self._blue_delta(idx_y,-1))
        b("y", lambda e: self._blue_delta(idx_c,+1)); b("Y", lambda e: self._blue_delta(idx_c,-1))
        b("c", lambda e: self._blue_delta(idx_d,+1)); b("C", lambda e: self._blue_delta(idx_d,-1))
        b("v", lambda e: self._blue_delta(idx_t,+1)); b("V", lambda e: self._blue_delta(idx_t,-1))

        # Green +/- (Y C D T)
        b("n", lambda e: self._green_delta(idx_y,+1)); b("N", lambda e: self._green_delta(idx_y,-1))
        b("k", lambda e: self._green_delta(idx_c,+1)); b("K", lambda e: self._green_delta(idx_c,-1))
        b("l", lambda e: self._green_delta(idx_d,+1)); b("L", lambda e: self._green_delta(idx_d,-1))
        b(";", lambda e: self._green_delta(idx_t,+1)); b(":", lambda e: self._green_delta(idx_t,-1))

        # Winner & auto
        b("b", lambda e: self._show_winner("BLUE"))
        b("g", lambda e: self._show_winner("GREEN"))
        b("A", lambda e: self.auto_winner.set(not self.auto_winner.get()))
        b("j", lambda e: self._resume_from_jaza())
        b("J", lambda e: self._resume_from_jaza())
        b("<Shift-B>", lambda e: self._handle_halal_hotkey("BLUE", e))
        b("<Shift-G>", lambda e: self._handle_halal_hotkey("GREEN", e))

       

    def _on_resize(self, _): self.after_idle(self._apply_scale)
    def _close(self):
        if self.after_id:
            try:
                self.after_cancel(self.after_id)
            except Exception:
                pass
            self.after_id = None
        self._cancel_pending_auto_winner()
        self.running = False
        self.destroy()
        self.root.deiconify()
        self.root.focus_force()

# ---------------- main ----------------
def main(): ConfigWindow().mainloop()
if __name__ == "__main__": main()
