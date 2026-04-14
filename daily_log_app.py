"""
EVI Daily Task Log — GUI Application
=====================================
A desktop app with a real calendar date-picker, dropdown menus,
and full database save/recall functionality.

Launch:   python3 daily_log_app.py
"""

import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont
from tkcalendar import Calendar
from datetime import datetime, date, timedelta
import sqlite3, os

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DB_FILE    = os.path.join(BASE_DIR, "tasks.db")
EXCEL_FILE = os.path.join(BASE_DIR, "DailyTaskLog.xlsx")

# ── Colors ────────────────────────────────────────────────────
NAVY       = "#1F3864"
BLUE       = "#2E75B6"
LTBLUE     = "#DEEAF1"
PALE       = "#EBF3FB"
WHITE      = "#FFFFFF"
ORANGE     = "#FF6600"
GREEN_BG   = "#E2EFDA"
WARN_BG    = "#FFF2CC"
RED        = "#C0392B"

# ─────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date    TEXT NOT NULL,
                day_name      TEXT NOT NULL,
                description   TEXT,
                location      TEXT,
                dc_code       TEXT DEFAULT 'EVI01',
                add_info      TEXT,
                week_number   INTEGER,
                year          INTEGER,
                saved_at      TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        conn.commit()

def save_record(entry_date, description, location, dc_code="EVI01", add_info=""):
    if isinstance(entry_date, str):
        entry_date = datetime.strptime(entry_date, "%Y-%m-%d").date()
    day_name    = entry_date.strftime("%A")
    week_number = int(entry_date.strftime("%W"))
    year        = entry_date.year
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO tasks (entry_date, day_name, description, location,
                               dc_code, add_info, week_number, year)
            VALUES (?,?,?,?,?,?,?,?)
        """, (entry_date.isoformat(), day_name, description, location,
              dc_code, add_info, week_number, year))
        conn.commit()
        return cur.lastrowid

def fetch_by_date(target_date):
    if isinstance(target_date, date):
        target_date = target_date.isoformat()
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM tasks WHERE entry_date=? ORDER BY saved_at",
            (target_date,)).fetchall()

def fetch_by_week(year, week):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM tasks WHERE year=? AND week_number=? ORDER BY entry_date, saved_at",
            (year, week)).fetchall()

def fetch_all():
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM tasks ORDER BY entry_date DESC, saved_at DESC"
        ).fetchall()

def delete_record(record_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM tasks WHERE id=?", (record_id,))
        conn.commit()

# ─────────────────────────────────────────────────────────────
# EXPORT TO EXCEL (reuse task_manager)
# ─────────────────────────────────────────────────────────────
def export_to_excel():
    try:
        import task_manager as tm
        tm.init_db()
        tm.rebuild_excel()
        os.system(f'open "{EXCEL_FILE}"')
        return True
    except Exception as e:
        return str(e)

# ─────────────────────────────────────────────────────────────
# MAIN APPLICATION
# ─────────────────────────────────────────────────────────────
class DailyLogApp:
    def __init__(self, root):
        self.root = root
        self.root.title("EVI Daily Task Log — Datacenter EVI01")
        self.root.geometry("1100x820")
        self.root.configure(bg=WHITE)
        self.root.resizable(True, True)

        # Fonts
        self.font_title  = tkfont.Font(family="Arial", size=18, weight="bold")
        self.font_header = tkfont.Font(family="Arial", size=12, weight="bold")
        self.font_label  = tkfont.Font(family="Arial", size=11, weight="bold")
        self.font_input  = tkfont.Font(family="Arial", size=11)
        self.font_btn    = tkfont.Font(family="Arial", size=11, weight="bold")
        self.font_small  = tkfont.Font(family="Arial", size=9)
        self.font_table  = tkfont.Font(family="Arial", size=10)

        # Style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Navy.TFrame", background=NAVY)
        style.configure("White.TFrame", background=WHITE)
        style.configure("Blue.TLabel", background=BLUE, foreground=WHITE,
                        font=self.font_label, padding=6)
        style.configure("Input.TLabel", background=PALE, foreground=NAVY,
                        font=self.font_input, padding=6)
        style.configure("Treeview", font=self.font_table, rowheight=26)
        style.configure("Treeview.Heading", font=self.font_label,
                        background=BLUE, foreground=WHITE)

        self.build_ui()
        self.refresh_table()

    def build_ui(self):
        # ── TITLE BANNER ──────────────────────────────────────
        banner = tk.Frame(self.root, bg=NAVY, height=50)
        banner.pack(fill="x", padx=0, pady=0)
        banner.pack_propagate(False)
        tk.Label(banner, text="EVI DAILY TASK LOG  —  Datacenter EVI01",
                 font=self.font_title, bg=NAVY, fg=WHITE).pack(expand=True)

        # ── MAIN CONTAINER ────────────────────────────────────
        main = tk.Frame(self.root, bg=WHITE)
        main.pack(fill="both", expand=True, padx=10, pady=5)

        # ── TOP SECTION: Entry Form ───────────────────────────
        form_frame = tk.Frame(main, bg=WHITE)
        form_frame.pack(fill="x", pady=(5, 5))

        # LEFT: Calendar
        cal_frame = tk.LabelFrame(form_frame, text="  SELECT DATE  ",
                                   font=self.font_header, fg=NAVY, bg=LTBLUE,
                                   bd=2, relief="groove")
        cal_frame.pack(side="left", padx=(0, 10), pady=0, fill="y")

        self.calendar = Calendar(
            cal_frame,
            selectmode="day",
            year=date.today().year,
            month=date.today().month,
            day=date.today().day,
            date_pattern="yyyy-mm-dd",
            font=tkfont.Font(family="Arial", size=10),
            background=NAVY,
            foreground=WHITE,
            selectbackground=ORANGE,
            selectforeground=WHITE,
            normalbackground=WHITE,
            normalforeground=NAVY,
            weekendbackground="#F2D7D5",
            weekendforeground=RED,
            headersbackground=BLUE,
            headersforeground=WHITE,
            othermonthbackground="#F5F5F5",
            othermonthforeground="#CCCCCC",
            othermonthwebackground="#F5F5F5",
            othermonthweforeground="#CCCCCC",
            borderwidth=2,
            bordercolor=BLUE,
            showweeknumbers=True,
        )
        self.calendar.pack(padx=8, pady=(5, 5))
        self.calendar.bind("<<CalendarSelected>>", self.on_date_select)

        # Selected date + day display
        date_display = tk.Frame(cal_frame, bg=LTBLUE)
        date_display.pack(fill="x", padx=8, pady=(0, 8))

        self.lbl_sel_date = tk.Label(date_display,
                                      text=date.today().strftime("%d-%b-%Y"),
                                      font=self.font_header, bg=ORANGE, fg=WHITE,
                                      padx=10, pady=4)
        self.lbl_sel_date.pack(side="left", padx=(0, 5))

        self.lbl_sel_day = tk.Label(date_display,
                                     text=date.today().strftime("%A"),
                                     font=self.font_header, bg=NAVY, fg=WHITE,
                                     padx=10, pady=4)
        self.lbl_sel_day.pack(side="left", fill="x", expand=True)

        # RIGHT: Input fields
        input_frame = tk.LabelFrame(form_frame, text="  TASK DETAILS  ",
                                     font=self.font_header, fg=NAVY, bg=WHITE,
                                     bd=2, relief="groove")
        input_frame.pack(side="left", fill="both", expand=True, pady=0)

        # Row of column titles + inputs
        # ── Location (DH1-DH6) ────────────────────────────────
        row1 = tk.Frame(input_frame, bg=WHITE)
        row1.pack(fill="x", padx=8, pady=(8, 0))

        tk.Label(row1, text="Location", font=self.font_label,
                 bg=BLUE, fg=WHITE, width=12, anchor="center",
                 padx=5, pady=4).pack(side="left", padx=(0, 5))

        self.loc_var = tk.StringVar(value="DH1")
        loc_frame = tk.Frame(row1, bg=WHITE)
        loc_frame.pack(side="left", fill="x", expand=True)

        for dh in ["DH1", "DH2", "DH3", "DH4", "DH5", "DH6"]:
            rb = tk.Radiobutton(loc_frame, text=dh, variable=self.loc_var,
                                value=dh, font=self.font_input, bg=WHITE,
                                fg=NAVY, activebackground=LTBLUE,
                                selectcolor=LTBLUE, indicatoron=1,
                                padx=6, pady=2)
            rb.pack(side="left", padx=2)

        # ── DC Code ───────────────────────────────────────────
        row2 = tk.Frame(input_frame, bg=WHITE)
        row2.pack(fill="x", padx=8, pady=(6, 0))

        tk.Label(row2, text="DC Code", font=self.font_label,
                 bg=BLUE, fg=WHITE, width=12, anchor="center",
                 padx=5, pady=4).pack(side="left", padx=(0, 5))

        self.dc_var = tk.StringVar(value="EVI01")
        dc_entry = tk.Entry(row2, textvariable=self.dc_var,
                            font=self.font_input, bg=PALE, fg=NAVY,
                            relief="solid", bd=1, width=15)
        dc_entry.pack(side="left", padx=0, ipady=3)

        # ── Description ───────────────────────────────────────
        row3 = tk.Frame(input_frame, bg=WHITE)
        row3.pack(fill="x", padx=8, pady=(6, 0))

        tk.Label(row3, text="Description", font=self.font_label,
                 bg=BLUE, fg=WHITE, width=12, anchor="center",
                 padx=5, pady=4).pack(side="left", padx=(0, 5), anchor="n")

        self.desc_text = tk.Text(row3, font=self.font_input, bg=PALE, fg=NAVY,
                                  relief="solid", bd=1, height=3, wrap="word")
        self.desc_text.pack(side="left", fill="x", expand=True, ipady=2)

        # ── Additional Info ───────────────────────────────────
        row4 = tk.Frame(input_frame, bg=WHITE)
        row4.pack(fill="x", padx=8, pady=(6, 0))

        tk.Label(row4, text="Add. Info", font=self.font_label,
                 bg=BLUE, fg=WHITE, width=12, anchor="center",
                 padx=5, pady=4).pack(side="left", padx=(0, 5), anchor="n")

        self.addinfo_text = tk.Text(row4, font=self.font_input, bg=PALE, fg=NAVY,
                                     relief="solid", bd=1, height=2, wrap="word")
        self.addinfo_text.pack(side="left", fill="x", expand=True, ipady=2)

        # ── Buttons row ───────────────────────────────────────
        btn_row = tk.Frame(input_frame, bg=WHITE)
        btn_row.pack(fill="x", padx=8, pady=(10, 8))

        self.btn_save = tk.Button(
            btn_row, text="   SAVE ENTRY   ", font=self.font_btn,
            bg="#27AE60", fg=WHITE, activebackground="#1E8449",
            activeforeground=WHITE, relief="raised", bd=2, cursor="hand2",
            command=self.save_entry)
        self.btn_save.pack(side="left", padx=(0, 8), ipady=4)

        self.btn_clear = tk.Button(
            btn_row, text="  CLEAR FORM  ", font=self.font_btn,
            bg="#E67E22", fg=WHITE, activebackground="#D35400",
            activeforeground=WHITE, relief="raised", bd=2, cursor="hand2",
            command=self.clear_form)
        self.btn_clear.pack(side="left", padx=(0, 8), ipady=4)

        self.btn_excel = tk.Button(
            btn_row, text="  EXPORT TO EXCEL  ", font=self.font_btn,
            bg=BLUE, fg=WHITE, activebackground=NAVY,
            activeforeground=WHITE, relief="raised", bd=2, cursor="hand2",
            command=self.export_excel)
        self.btn_excel.pack(side="left", padx=(0, 8), ipady=4)

        self.btn_delete = tk.Button(
            btn_row, text="  DELETE SELECTED  ", font=self.font_btn,
            bg=RED, fg=WHITE, activebackground="#922B21",
            activeforeground=WHITE, relief="raised", bd=2, cursor="hand2",
            command=self.delete_selected)
        self.btn_delete.pack(side="right", ipady=4)

        # ── Status bar ────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready — select a date and fill in the form.")
        status_bar = tk.Label(main, textvariable=self.status_var,
                              font=self.font_small, bg=WARN_BG, fg="#7D6608",
                              anchor="w", padx=10, pady=3, relief="sunken")
        status_bar.pack(fill="x", pady=(5, 5))

        # ── RECALL SECTION ────────────────────────────────────
        recall_frame = tk.Frame(main, bg=WHITE)
        recall_frame.pack(fill="x", pady=(0, 5))

        tk.Label(recall_frame, text="RECALL:", font=self.font_label,
                 bg=NAVY, fg=WHITE, padx=8, pady=3).pack(side="left", padx=(0, 5))

        self.btn_recall_date = tk.Button(
            recall_frame, text="By Selected Date", font=self.font_btn,
            bg=BLUE, fg=WHITE, cursor="hand2", command=self.recall_by_date)
        self.btn_recall_date.pack(side="left", padx=3, ipady=2)

        self.btn_recall_week = tk.Button(
            recall_frame, text="By This Week", font=self.font_btn,
            bg=BLUE, fg=WHITE, cursor="hand2", command=self.recall_by_week)
        self.btn_recall_week.pack(side="left", padx=3, ipady=2)

        self.btn_recall_all = tk.Button(
            recall_frame, text="All Records", font=self.font_btn,
            bg=BLUE, fg=WHITE, cursor="hand2", command=self.recall_all)
        self.btn_recall_all.pack(side="left", padx=3, ipady=2)

        # Week selector
        tk.Label(recall_frame, text="  Week #:", font=self.font_label,
                 bg=WHITE, fg=NAVY).pack(side="left", padx=(15, 2))
        self.week_var = tk.StringVar(value=str(int(date.today().strftime("%W"))))
        week_spin = tk.Spinbox(recall_frame, from_=1, to=53,
                                textvariable=self.week_var, width=4,
                                font=self.font_input, bg=PALE)
        week_spin.pack(side="left", padx=(0, 5))

        tk.Label(recall_frame, text="Year:", font=self.font_label,
                 bg=WHITE, fg=NAVY).pack(side="left", padx=(5, 2))
        self.year_var = tk.StringVar(value=str(date.today().year))
        year_spin = tk.Spinbox(recall_frame, from_=2020, to=2035,
                                textvariable=self.year_var, width=6,
                                font=self.font_input, bg=PALE)
        year_spin.pack(side="left", padx=(0, 5))

        self.lbl_count = tk.Label(recall_frame, text="",
                                   font=self.font_label, bg=GREEN_BG, fg="#375623",
                                   padx=8, pady=2)
        self.lbl_count.pack(side="right", padx=5)

        # ── TABLE ─────────────────────────────────────────────
        table_frame = tk.Frame(main, bg=WHITE)
        table_frame.pack(fill="both", expand=True, pady=(0, 5))

        cols = ("#", "Date", "Day", "Description", "Location", "DC Code",
                "Add. Info", "Saved At")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings",
                                  selectmode="browse")

        col_widths = [40, 100, 80, 280, 70, 70, 200, 140]
        for col_name, w in zip(cols, col_widths):
            self.tree.heading(col_name, text=col_name, anchor="center")
            anchor = "w" if col_name in ("Description", "Add. Info") else "center"
            self.tree.column(col_name, width=w, minwidth=40, anchor=anchor)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")

        # Alternating row colors
        self.tree.tag_configure("even", background=LTBLUE)
        self.tree.tag_configure("odd", background=WHITE)

    # ── EVENTS ────────────────────────────────────────────────
    def on_date_select(self, event=None):
        sel = self.calendar.get_date()
        d = datetime.strptime(sel, "%Y-%m-%d").date()
        self.lbl_sel_date.config(text=d.strftime("%d-%b-%Y"))
        self.lbl_sel_day.config(text=d.strftime("%A"))
        self.status_var.set(f"Date selected: {d.strftime('%A, %d-%b-%Y')}  (Week {int(d.strftime('%W'))})")

    def get_selected_date(self):
        sel = self.calendar.get_date()
        return datetime.strptime(sel, "%Y-%m-%d").date()

    def save_entry(self):
        d = self.get_selected_date()
        desc = self.desc_text.get("1.0", "end-1c").strip()
        loc  = self.loc_var.get()
        dc   = self.dc_var.get().strip() or "EVI01"
        info = self.addinfo_text.get("1.0", "end-1c").strip()

        if not desc:
            messagebox.showwarning("Missing Description",
                                   "Please enter a task description.")
            self.desc_text.focus_set()
            return

        row_id = save_record(d, desc, loc, dc, info)
        self.status_var.set(
            f"SAVED  Record #{row_id} — {d.strftime('%d-%b-%Y')} {d.strftime('%A')}  |  {loc}  |  {dc}")
        self.refresh_table()
        self.clear_form()
        messagebox.showinfo("Saved",
                            f"Entry #{row_id} saved successfully!\n\n"
                            f"Date: {d.strftime('%d-%b-%Y')} ({d.strftime('%A')})\n"
                            f"Location: {loc}\nDC Code: {dc}")

    def clear_form(self):
        self.desc_text.delete("1.0", "end")
        self.addinfo_text.delete("1.0", "end")
        self.loc_var.set("DH1")
        self.dc_var.set("EVI01")
        self.calendar.selection_set(date.today())
        self.on_date_select()
        self.status_var.set("Form cleared — ready for new entry.")

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select a row to delete.")
            return
        item = self.tree.item(sel[0])
        rec_id = item["values"][0]
        if messagebox.askyesno("Confirm Delete",
                               f"Delete record #{rec_id}?\nThis cannot be undone."):
            delete_record(rec_id)
            self.refresh_table()
            self.status_var.set(f"Record #{rec_id} deleted.")

    def export_excel(self):
        result = export_to_excel()
        if result is True:
            self.status_var.set(f"Excel exported & opened: {EXCEL_FILE}")
        else:
            messagebox.showerror("Export Error", str(result))

    # ── RECALL ────────────────────────────────────────────────
    def recall_by_date(self):
        d = self.get_selected_date()
        rows = fetch_by_date(d)
        self.populate_table(rows)
        self.lbl_count.config(text=f"{len(rows)} record(s) for {d.strftime('%d-%b-%Y')}")
        self.status_var.set(f"Recall by date: {d.strftime('%d-%b-%Y')} — {len(rows)} found")

    def recall_by_week(self):
        yr = int(self.year_var.get())
        wk = int(self.week_var.get())
        rows = fetch_by_week(yr, wk)
        self.populate_table(rows)
        self.lbl_count.config(text=f"{len(rows)} record(s) — Year {yr}, Week {wk}")
        self.status_var.set(f"Recall by week: Year {yr}, Week {wk} — {len(rows)} found")

    def recall_all(self):
        rows = fetch_all()
        self.populate_table(rows)
        self.lbl_count.config(text=f"{len(rows)} total record(s)")
        self.status_var.set(f"All records — {len(rows)} total")

    # ── TABLE ─────────────────────────────────────────────────
    def populate_table(self, rows):
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(rows):
            d = dict(row)
            tag = "even" if i % 2 == 0 else "odd"
            self.tree.insert("", "end", values=(
                d["id"],
                d["entry_date"],
                d["day_name"],
                d["description"] or "",
                d["location"] or "",
                d["dc_code"] or "EVI01",
                d["add_info"] or "",
                d["saved_at"] or "",
            ), tags=(tag,))

    def refresh_table(self):
        self.recall_all()

# ─────────────────────────────────────────────────────────────
# LAUNCH
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    root = tk.Tk()
    app = DailyLogApp(root)
    root.mainloop()
