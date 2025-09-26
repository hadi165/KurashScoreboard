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

# --- Windows DPI awareness to avoid blurry UI ---
if sys.platform == "win32":
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# --- Robust resource paths (works inside PyInstaller onefile) ---
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    ROOT_DIR = sys._MEIPASS

FLAGS_DIR  = os.path.join(ROOT_DIR, "Flags")
SOUNDS_DIR = os.path.join(ROOT_DIR, "Sounds")

APP_TITLE = "Kurash Scoreboard (Photo Theme – Responsive)"
ROOT_DIR   = os.path.dirname(__file__)


DEFAULT_MEN_MMSS   = (5, 0)
DEFAULT_WOMEN_MMSS = (4, 0)

# ---------- Baseline & big font sizes ----------
BASE_W, BASE_H = 1920, 1080
BASE = dict(
    TIME   = 280,  # red timer
    DIGIT  = 230,  # Y/C/D/T digits
    CODE   = 90,   # IOC codes (TKM/UZB)
    NAME   = 48,
    LABEL  = 36,   # Y C D T
    TOPMETA= 70    # top-left & top-right info
)
FLAG_W, FLAG_H = 288, 192  # baseline flag size
FLAG_BOOST = 1.6 

# Default zoom for initial layout and Ctrl+0 reset (tune to your preference)
DEFAULT_ZOOM = 0.6

# If False, ignore OS DPI scaling to avoid oversized UI on high scaling
RESPECT_DPI = False

COUNTRIES = [
    ("India","IND"),("Chinese Taipei","TPE"),("Singapore","SGP"),("Malaysia","MAS"),
    ("Indonesia","INA"),("Philippines","PHI"),("Thailand","THA"),("South Korea","KOR"),
    ("Vietnam","VIE"),("Japan","JPN"),("Uzbekistan","UZB"),("Afghanistan","AFG"),
    ("Aruba (example AHO)","AHO"),
]
WEIGHTS = ["-48Kg","-52Kg","-57Kg","-60Kg","-63Kg","-66Kg","-70Kg","-73Kg",
           "-78Kg","-81Kg","-87Kg","+87Kg","-90Kg","-100Kg","+100Kg","-120Kg","+120Kg"]

def country_values(): return [f"{n} ({c})" for n,c in COUNTRIES]
def parse_code(s:str)->str:
    m=re.search(r"\(([A-Za-z]{2,3})\)$", s.strip()); return (m.group(1) if m else s.strip())[:3].upper()
def clamp(n, lo=0, hi=99): return max(lo, min(hi, n))

# ---------------- Config ----------------
class ConfigWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} – Config"); self.geometry("980x720"); self.resizable(True, True)
        self.show_flags = tk.BooleanVar(value=True)
        self.show_names = tk.BooleanVar(value=False)
        self.country1 = tk.StringVar(value="Turkmenistan (TKM)")
        self.country2 = tk.StringVar(value="Uzbekistan (UZB)")
        self.name1 = tk.StringVar(value="OMIROV DAYANCH")
        self.name2 = tk.StringVar(value="TOJIEV ARSLONBEK")
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

        self.blue=[0,0,0,0]; self.green=[0,0,0,0]
        self.scale=1.0
        self.zoom=DEFAULT_ZOOM  # default zoom (you can adjust in-app)
        self.match_over = False  # lock scoring once the match is finished

        # Named fonts (resize together)
        self.f_time    = tkfont.Font(family="Arial", weight="bold", size=BASE["TIME"])
        self.f_digit   = tkfont.Font(family="Arial", weight="bold", size=BASE["DIGIT"])
        self.f_code    = tkfont.Font(family="Arial", weight="bold", size=BASE["CODE"])
        self.f_topmeta = tkfont.Font(family="Arial", weight="bold", size=BASE["TOPMETA"])
        self.f_label   = tkfont.Font(family="Arial", weight="bold", size=BASE["LABEL"])
        self.f_name    = tkfont.Font(family="Arial", weight="bold", size=BASE["NAME"])

        self._blue_flag_img=None; self._green_flag_img=None
        self._build(); self._bind(); self._update_time()
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
        s = self._calc_scale(); self.scale = s
        def setsize(fontobj, base): fontobj.configure(size=max(10, int(base*s)))
        setsize(self.f_time,   BASE["TIME"])
        setsize(self.f_digit,  BASE["DIGIT"])
        setsize(self.f_code,   BASE["CODE"])
        setsize(self.f_topmeta,BASE["TOPMETA"])
        setsize(self.f_label,  BASE["LABEL"])
        setsize(self.f_name,   BASE["NAME"])

        self._refresh_flags()

        pad = max(12, int(24*s))
        for cell in getattr(self, "b_cells", []): cell.grid_configure(padx=pad)
        for cell in getattr(self, "g_cells", []): cell.grid_configure(padx=pad)

    def _zoom_in(self):  self.zoom = min(3.0, self.zoom*1.08); self._apply_scale()
    def _zoom_out(self): self.zoom = max(0.35, self.zoom/1.08); self._apply_scale()
    def _zoom_reset(self): self.zoom = DEFAULT_ZOOM; self._apply_scale()

    # ---------- assets ----------
    def _load_flag_image(self, code, w, h):
        for ext in (".jpg",".png",".jpeg"):
            p = os.path.join(FLAGS_DIR, f"{code.upper()}{ext}")
            if os.path.exists(p):
                try: return ImageTk.PhotoImage(Image.open(p).resize((w,h), Image.LANCZOS))
                except Exception: return None
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

        self.time_lbl = tk.Label(top, text="00:00", fg="red", bg="black", font=self.f_time)
        self.time_lbl.grid(row=0, column=1, sticky="n", pady=(0,4))

        right_meta = f"{self.cfg['gender']}   {self.cfg['weight']}"
        self.top_right_meta = tk.Label(top, text=right_meta, fg="white", bg="black", font=self.f_topmeta)
        self.top_right_meta.grid(row=0, column=2, sticky="e", padx=20)

        # Middle area
        mid = tk.Frame(self, bg="black"); mid.pack(expand=True, fill="both", pady=6)

        # ----- BLUE row (centered) -----
        blue_row = tk.Frame(mid, bg="black"); blue_row.pack(fill="x", pady=4)
        tk.Frame(blue_row, bg="black").pack(side="left", expand=True)

        # Flag
        self.blue_flag = tk.Label(blue_row, bg="black")
        if self.cfg.get("show_flags"): self.blue_flag.pack(side="left", padx=(20,10))

        # NEW: vertical stack for name (blue box) + code
        blue_id = tk.Frame(blue_row, bg="black"); blue_id.pack(side="left", padx=(0,30))

        self.blue_name = tk.Label(
            blue_id, text=self.cfg.get("name1",""),
            bg="#1976d2", fg="white", font=self.f_name, padx=12, pady=4
        )
        self.blue_name.pack(side="top", anchor="w")

        self.blue_code = tk.Label(
            blue_id, text=self.cfg["code1"],
            fg="white", bg="black", font=self.f_code
        )
        self.blue_code.pack(side="top", anchor="w")

        # digits + labels in one grid
        self.b_digits_frame = tk.Frame(blue_row, bg="black"); self.b_digits_frame.pack(side="left")
        self.b_digits, self.b_cells = [], []
        for i in range(4):
            cell = tk.Frame(self.b_digits_frame, bg="#222"); cell.grid(row=0, column=i, padx=24)
            lbl  = tk.Label(cell, text="0", fg="white", bg="#222", font=self.f_digit, width=2); lbl.pack()
            self.b_cells.append(cell); self.b_digits.append(lbl)
            # NEW: make the box clickable for Blue
            self._attach_score_clicks(cell, lbl, is_blue=True, idx=i)

            tk.Label(self.b_digits_frame, text=("Y","C","D","T")[i],
                    fg="#ffe000", bg="black", font=self.f_label).grid(row=1, column=i, pady=(8,0))
        
        tk.Frame(blue_row, bg="black").pack(side="left", expand=True)


        # Winner ribbon (center)
        self.winner_area = tk.Frame(mid, bg="black")
        self.winner_area.pack(fill="x", pady=6)

        self.winner_lbl = tk.Label(
            self.winner_area, text="",
            font=self.f_code, fg="black", bg="black",
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
        green_id = tk.Frame(green_row, bg="black"); green_id.pack(side="left", padx=(0,30))

        self.green_code = tk.Label(
            green_id, text=self.cfg["code2"],
            fg="white", bg="black", font=self.f_code
        )
        self.green_code.pack(side="top", anchor="w")

        self.green_name = tk.Label(
            green_id, text=self.cfg.get("name2",""),
            bg="#2e7d32", fg="white", font=self.f_name, padx=12, pady=4
        )
        self.green_name.pack(side="top", anchor="w")

        # digits + labels in one grid
        self.g_digits_frame = tk.Frame(green_row, bg="black"); self.g_digits_frame.pack(side="left")
        self.g_digits, self.g_cells = [], []
        for i in range(4):
            cell = tk.Frame(self.g_digits_frame, bg="#222"); cell.grid(row=0, column=i, padx=24)
            lbl  = tk.Label(cell, text="0", fg="white", bg="#222", font=self.f_digit, width=2); lbl.pack()
            self.g_cells.append(cell); self.g_digits.append(lbl)

            # ✅ Make the green box clickable (this line was missing)
            self._attach_score_clicks(cell, lbl, is_blue=False, idx=i)

            tk.Label(self.g_digits_frame, text=("Y","C","D","T")[i],
                    fg="#ffe000", bg="black", font=self.f_label).grid(row=1, column=i, pady=(8,0))

        tk.Frame(green_row, bg="black").pack(side="left", expand=True)

        # Controls (also add small helpers for fullscreen/zoom)
     # Controls (centered row)
        ctrl = tk.Frame(self, bg="black"); ctrl.pack(fill="x", pady=6)

        # Inner frame shrinks to content; packing it (no side=left/right) centers it within 'ctrl'
        btns = tk.Frame(ctrl, bg="black")
        btns.pack()

        def btn(t, cmd):
            tk.Button(btns, text=t, command=cmd).pack(side="left", padx=6)

        btn("Start/Pause (Space)", self._toggle_timer)
        btn("Reset Time (t)", self._reset_time)
        btn("All Reset (0)", self._reset_all)
        btn("Blue WINNER (b)",  lambda: self._show_winner("BLUE"))
        btn("Green WINNER (g)", lambda: self._show_winner("GREEN"))
        btn("Clear WINNER",     lambda: self._show_winner(""))
        btn("Fullscreen (F11)", lambda: self._toggle_fullscreen())
        btn("Zoom +",           self._zoom_in)
        btn("Zoom -",           self._zoom_out)
        btn("Zoom 100% (Ctrl+0)", self._zoom_reset)



        self._apply_scale()  # initial

    # ---------- timer / scoring ----------
    def _update_time(self):
        m,s = divmod(self.time_left,60)
        self.time_lbl.config(text=f"{m:02d}:{s:02d}")

    def _tick(self):
        if not self.running:
            return

        if self.time_left > 0:
            self.time_left -= 1
            self._update_time()
            self.after_id = self.after(1000, self._tick)
        else:
            self.running = False
            self._buzz()

            # decide winner and show full-screen overlay
            b, g = sum(self.blue), sum(self.green)
            if b > g:
                self._show_final_winner_screen("BLUE")
            elif g > b:
                self._show_final_winner_screen("GREEN")
            else:
                self._show_tie_screen()


    def _toggle_timer(self,_=None):
        self.running = not self.running
        if self.running: self.after_id = self.after(1000, self._tick)
        elif self.after_id: self.after_cancel(self.after_id); self.after_id=None

    def _reset_time(self,_=None):
        self.running=False
        if self.after_id: self.after_cancel(self.after_id); self.after_id=None
        self.time_left = self.cfg["mm"]*60 + self.cfg["ss"]; self._update_time()

    def _refresh_digits(self):
        for i,l in enumerate(self.b_digits): l.config(text=str(self.blue[i]))
        for i,l in enumerate(self.g_digits): l.config(text=str(self.green[i]))

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
            w.bind("<Button-3>", dec)          # right click -1 (on macOS, ctrl+click also generates this)
            w.bind("<Double-Button-1>", reset_bucket)  # double-left resets this bucket

        def _clear_final_screen(self):
            """Remove final overlay if present."""
            if hasattr(self, "final_frame") and self.final_frame:
                try:
                    self.final_frame.destroy()
                except Exception:
                    pass
                self.final_frame = None

        def _show_final_winner_screen(self, who: str):
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
            name_font = tkfont.Font(family="Arial", weight="bold", size=max(60, int(BASE["TIME"] * s)))
            code_font = tkfont.Font(family="Arial", weight="bold", size=max(48, int(BASE["TIME"] * 0.5 * s)))
            hint_font = tkfont.Font(family="Arial", weight="bold", size=max(24, int(28 * s)))

            self.final_frame = tk.Frame(self, bg=bg)
            self.final_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

            tk.Label(self.final_frame, text="WINNER", bg=bg, fg=fg, font=code_font, pady=10).pack(pady=(30, 10))
            tk.Label(self.final_frame, text=name,   bg=bg, fg=fg, font=name_font).pack(pady=(10, 10))
            tk.Label(self.final_frame, text=code,   bg=bg, fg=fg, font=code_font).pack(pady=(0, 30))
            tk.Label(self.final_frame, text="Press 0 to reset", bg=bg, fg=fg, font=hint_font).pack(pady=(10, 10))

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

            tk.Label(self.final_frame, text="TIME UP — TIE", bg=bg, fg=fg, font=big_font).pack(pady=(40, 20))
            tk.Label(self.final_frame, text=f"{self.cfg.get('name1','')} ({self.cfg.get('code1','')})",
                    bg=bg, fg=acc, font=mid_font).pack(pady=5)
            tk.Label(self.final_frame, text=f"{self.cfg.get('name2','')} ({self.cfg.get('code2','')})",
                    bg=bg, fg=acc, font=mid_font).pack(pady=5)
            tk.Label(self.final_frame, text="Press W for Blue win, M for Green win, or 0 to reset.",
                    bg=bg, fg=fg, font=hint_font).pack(pady=(20, 10))


    def _blue_delta(self, idx, d):
        if self.match_over: return
        self.blue[idx] = clamp(self.blue[idx] + d)
        self._refresh_digits()
 
    def _green_delta(self, idx, d):
        if self.match_over: return
        self.green[idx] = clamp(self.green[idx] + d)
        self._refresh_digits()


    def _reset_all(self, _=None):
        self.blue = [0,0,0,0]
        self.green = [0,0,0,0]
        self.match_over = False
        self._clear_final_screen()
        self._reset_time()
        self._refresh_digits()
        self._show_winner("")  # clear mini ribbon


    def _auto_winner(self):
        b,g = sum(self.blue), sum(self.green)
        self._show_winner("BLUE" if b>g else "GREEN" if g>b else "")

    def _show_winner(self, who: str):
        # Keep small ribbon (if you still want it mid-match)
        if not who:
            self.winner_lbl.config(text="", bg="black", fg="black")
            return

        if who == "BLUE":
            self.winner_lbl.config(text=f"{self.cfg['name1']} WINS", bg="#1976d2", fg="white")
        elif who == "GREEN":
            self.winner_lbl.config(text=f"{self.cfg['name2']} WINS", bg="#00e676", fg="black")

        # If match already ended (or you just want to force the final screen), show overlay too
        if not self.running and self.time_left == 0 or self.match_over:
            self._show_final_winner_screen(who)



    # ---------- fullscreen / keys ----------
    def _toggle_fullscreen(self, force=None):
        cur = bool(self.attributes("-fullscreen"))
        new = (not cur) if force is None else bool(force)
        self.attributes("-fullscreen", new)

    def _bind(self):
        # bind_all so keys work regardless of focus
        b = self.bind_all

        # Timer / reset
        b("<space>", self._toggle_timer)
        b("t", self._reset_time)
        b("0", self._reset_all)

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
        b("r", lambda e: self._blue_delta(0,+1)); b("R", lambda e: self._blue_delta(0,-1))
        b("h", lambda e: self._blue_delta(0,+1)); b("H", lambda e: self._blue_delta(0,-1))
        b("y", lambda e: self._blue_delta(1,+1)); b("Y", lambda e: self._blue_delta(1,-1))
        b("c", lambda e: self._blue_delta(2,+1)); b("C", lambda e: self._blue_delta(2,-1))
        b("v", lambda e: self._blue_delta(3,+1)); b("V", lambda e: self._blue_delta(3,-1))

        # Green +/- (Y C D T)
        b("b", lambda e: self._green_delta(0,+1)); b("B", lambda e: self._green_delta(0,-1))
        b("n", lambda e: self._green_delta(0,+1)); b("N", lambda e: self._green_delta(0,-1))
        b("k", lambda e: self._green_delta(1,+1)); b("K", lambda e: self._green_delta(1,-1))
        b("l", lambda e: self._green_delta(2,+1)); b("L", lambda e: self._green_delta(2,-1))
        b(";", lambda e: self._green_delta(3,+1)); b(":", lambda e: self._green_delta(3,-1))

        # Winner & auto
        b("b", lambda e: self._show_winner("BLUE"))
        b("g", lambda e: self._show_winner("GREEN"))
        b("A", lambda e: self.auto_winner.set(not self.auto_winner.get()))

       

    def _on_resize(self, _): self.after_idle(self._apply_scale)
    def _close(self): self.destroy(); self.root.deiconify()

# ---------------- main ----------------
def main(): ConfigWindow().mainloop()
if __name__ == "__main__": main()
