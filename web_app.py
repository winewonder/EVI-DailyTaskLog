"""
EVI Daily Task Log — Web Application
=====================================
A browser-based version of the Daily Task Log with the same
database backend and EVI branding.

Launch:   python3 web_app.py
Open:     http://localhost:5050
"""

from flask import Flask, request, jsonify, render_template_string
from datetime import datetime, date
import sqlite3, os

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
DB_FILE    = os.path.join(BASE_DIR, "tasks.db")

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────
# DATABASE (shared with desktop app)
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

def save_record(entry_date_str, description, location, dc_code="EVI01", add_info=""):
    d = datetime.strptime(entry_date_str, "%Y-%m-%d").date()
    day_name    = d.strftime("%A")
    week_number = int(d.strftime("%W"))
    year        = d.year
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO tasks (entry_date, day_name, description, location,
                               dc_code, add_info, week_number, year)
            VALUES (?,?,?,?,?,?,?,?)
        """, (d.isoformat(), day_name, description, location,
              dc_code, add_info, week_number, year))
        conn.commit()
        return cur.lastrowid

def rows_to_list(rows):
    return [dict(r) for r in rows]

# ─────────────────────────────────────────────────────────────
# API ROUTES
# ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template_string(HTML_PAGE)

@app.route("/api/save", methods=["POST"])
def api_save():
    data = request.json
    desc = (data.get("description") or "").strip()
    if not desc:
        return jsonify({"error": "Description is required"}), 400
    row_id = save_record(
        data["entry_date"],
        desc,
        data.get("location", "DH1"),
        data.get("dc_code", "EVI01") or "EVI01",
        data.get("add_info", ""),
    )
    return jsonify({"id": row_id, "message": f"Entry #{row_id} saved successfully!"})

@app.route("/api/tasks")
def api_tasks():
    mode = request.args.get("mode", "all")
    with get_conn() as conn:
        if mode == "date":
            target = request.args.get("date", date.today().isoformat())
            rows = conn.execute(
                "SELECT * FROM tasks WHERE entry_date=? ORDER BY saved_at",
                (target,)).fetchall()
        elif mode == "week":
            yr = int(request.args.get("year", date.today().year))
            wk = int(request.args.get("week", int(date.today().strftime("%W"))))
            rows = conn.execute(
                "SELECT * FROM tasks WHERE year=? AND week_number=? ORDER BY entry_date, saved_at",
                (yr, wk)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY entry_date DESC, saved_at DESC"
            ).fetchall()
    return jsonify(rows_to_list(rows))

@app.route("/api/task/<int:record_id>")
def api_get_task(record_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (record_id,)).fetchone()
    if not row:
        return jsonify({"error": "Record not found"}), 404
    return jsonify(dict(row))

@app.route("/api/update/<int:record_id>", methods=["PUT"])
def api_update(record_id):
    data = request.json
    desc = (data.get("description") or "").strip()
    if not desc:
        return jsonify({"error": "Description is required"}), 400
    entry_date = data["entry_date"]
    d = datetime.strptime(entry_date, "%Y-%m-%d").date()
    day_name    = d.strftime("%A")
    week_number = int(d.strftime("%W"))
    year        = d.year
    with get_conn() as conn:
        conn.execute("""
            UPDATE tasks SET entry_date=?, day_name=?, description=?, location=?,
                             dc_code=?, add_info=?, week_number=?, year=?
            WHERE id=?
        """, (d.isoformat(), day_name, desc,
              data.get("location", "DH1"),
              data.get("dc_code", "EVI01") or "EVI01",
              data.get("add_info", ""),
              week_number, year, record_id))
        conn.commit()
    return jsonify({"message": f"Record #{record_id} updated successfully!"})

@app.route("/api/delete/<int:record_id>", methods=["DELETE"])
def api_delete(record_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM tasks WHERE id=?", (record_id,))
        conn.commit()
    return jsonify({"message": f"Record #{record_id} deleted."})

@app.route("/api/weekly-summary")
def api_weekly_summary():
    yr = int(request.args.get("year", date.today().year))
    wk = int(request.args.get("week", int(date.today().strftime("%W"))))
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE year=? AND week_number=? ORDER BY entry_date, saved_at",
            (yr, wk)).fetchall()

    tasks = rows_to_list(rows)
    total = len(tasks)

    # Group by day
    days_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    by_day = {}
    for t in tasks:
        day = t["day_name"]
        if day not in by_day:
            by_day[day] = []
        by_day[day].append(t)
    days_sorted = [{"day": d, "date": by_day[d][0]["entry_date"], "tasks": by_day[d]}
                   for d in days_order if d in by_day]

    # Stats by location
    loc_counts = {}
    for t in tasks:
        loc = t["location"] or "Unknown"
        loc_counts[loc] = loc_counts.get(loc, 0) + 1

    # Date range
    dates = sorted(set(t["entry_date"] for t in tasks))
    date_range = f"{dates[0]} to {dates[-1]}" if dates else "No records"

    # Generate AI summary
    ai_summary = generate_ai_summary(tasks, yr, wk, date_range, loc_counts, days_sorted)

    return jsonify({
        "year": yr,
        "week": wk,
        "total_tasks": total,
        "total_days": len(by_day),
        "date_range": date_range,
        "by_location": loc_counts,
        "by_day": days_sorted,
        "ai_summary": ai_summary,
    })


def generate_ai_summary(tasks, year, week, date_range, loc_counts, days_sorted):
    """Generate a smart built-in weekly summary from task data."""
    if not tasks:
        return "No tasks recorded for this week."

    total = len(tasks)
    num_days = len(days_sorted)
    day_names = [d["day"] for d in days_sorted]

    # Find busiest location
    top_loc = max(loc_counts, key=loc_counts.get)
    top_loc_count = loc_counts[top_loc]
    all_locs = sorted(loc_counts.keys())

    # Find busiest day
    busiest_day = max(days_sorted, key=lambda d: len(d["tasks"]))
    busiest_day_name = busiest_day["day"]
    busiest_day_count = len(busiest_day["tasks"])

    # Collect all descriptions for keyword analysis
    all_descs = [t["description"].lower() for t in tasks if t.get("description")]

    # Detect common task categories
    categories = []
    keywords = {
        "installation": ["install", "installed", "setup", "set up", "deploy", "mounted"],
        "maintenance": ["maintenance", "repair", "replace", "fix", "cleaned", "cleaning"],
        "rack work": ["rack", "racking", "rail", "shelf", "cabinet"],
        "cabling": ["cable", "cabling", "fiber", "patch", "wiring", "wire"],
        "inspection": ["inspect", "check", "audit", "survey", "verify", "test"],
        "decommission": ["decommission", "removal", "removed", "decom", "tear down"],
        "power work": ["power", "pdu", "ups", "breaker", "circuit", "electrical"],
        "network": ["network", "switch", "router", "firewall", "port"],
        "server work": ["server", "blade", "node", "compute", "host"],
        "cooling": ["cooling", "hvac", "crac", "temperature", "airflow"],
        "labeling": ["label", "labeling", "tagged", "tagging"],
        "inventory": ["inventory", "asset", "count", "stock"],
        "adjustment": ["adjust", "adjustment", "realign", "reposition"],
    }
    for cat, kws in keywords.items():
        for desc in all_descs:
            if any(kw in desc for kw in kws):
                categories.append(cat)
                break

    # Build summary sentences
    sentences = []

    # Sentence 1: Overview
    loc_list = ", ".join(all_locs) if len(all_locs) <= 3 else ", ".join(all_locs[:3]) + f" and {len(all_locs)-3} more"
    sentences.append(
        f"During this week, a total of {total} task{'s were' if total != 1 else ' was'} "
        f"completed across {num_days} working day{'s' if num_days != 1 else ''} "
        f"covering {len(all_locs)} location{'s' if len(all_locs) != 1 else ''} ({loc_list})."
    )

    # Sentence 2: Key location focus
    if len(loc_counts) == 1:
        sentences.append(f"All work was concentrated at {top_loc}.")
    else:
        pct = round(top_loc_count / total * 100)
        others = [f"{l} ({c})" for l, c in sorted(loc_counts.items(), key=lambda x: -x[1]) if l != top_loc]
        sentences.append(
            f"The primary focus was at {top_loc} with {top_loc_count} task{'s' if top_loc_count != 1 else ''} "
            f"({pct}% of total), followed by {', '.join(others[:2])}."
        )

    # Sentence 3: Task categories
    if categories:
        cat_text = ", ".join(categories[:3])
        sentences.append(f"Key activities included {cat_text}.")
    else:
        # Use first few task descriptions as highlights
        highlights = list(set(t["description"][:60] for t in tasks[:3] if t.get("description")))
        if highlights:
            sentences.append(f"Notable tasks: {'; '.join(highlights)}.")

    # Sentence 4: Busiest day
    if num_days > 1:
        sentences.append(
            f"The busiest day was {busiest_day_name} ({busiest_day['date']}) with "
            f"{busiest_day_count} task{'s' if busiest_day_count != 1 else ''} logged."
        )

    # Sentence 5: Workload assessment
    avg = round(total / num_days, 1) if num_days else 0
    if avg >= 5:
        load = "a high-intensity"
    elif avg >= 3:
        load = "a moderate"
    elif avg >= 1.5:
        load = "a steady"
    else:
        load = "a light"
    sentences.append(
        f"Overall workload was {load} week with an average of {avg} task{'s' if avg != 1 else ''} per day."
    )

    return " ".join(sentences)

# ─────────────────────────────────────────────────────────────
# HTML PAGE (single-file template)
# ─────────────────────────────────────────────────────────────
HTML_PAGE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📋</text></svg>">
<title>EVI Daily Task Log</title>
<style>
  /* ── THEMES ─────────────────────────────────────── */
  :root, [data-theme="classic-blue"] {
    --navy: #1F3864; --blue: #2E75B6; --ltblue: #DEEAF1;
    --pale: #EBF3FB; --orange: #FF6600; --green: #27AE60;
    --red: #C0392B; --warn-bg: #FFF2CC; --green-bg: #E2EFDA;
    --bg: #f4f6f9; --text: #333; --card-bg: #fff;
    --input-bg: #EBF3FB; --input-border: #ccc;
    --row-even: #DEEAF1; --row-odd: #fff; --row-hover: #d4e6f1;
    --modal-bg: #fff; --border-col: #e0e0e0;
    --gradient-start: #1F3864; --gradient-end: #2E75B6;
  }
  [data-theme="dark"] {
    --navy: #0d1b2a; --blue: #1b4965; --ltblue: #1e2d3d;
    --pale: #162029; --orange: #e07020; --green: #2ecc71;
    --red: #e74c3c; --warn-bg: #3a2e0a; --green-bg: #1a2e1a;
    --bg: #0a0f14; --text: #d0d8e0; --card-bg: #111a24;
    --input-bg: #162029; --input-border: #2a3a4a;
    --row-even: #111a24; --row-odd: #0d1520; --row-hover: #1b2a3a;
    --modal-bg: #111a24; --border-col: #1e2d3d;
    --gradient-start: #0d1b2a; --gradient-end: #1b4965;
  }
  [data-theme="emerald"] {
    --navy: #064e3b; --blue: #059669; --ltblue: #d1fae5;
    --pale: #ecfdf5; --orange: #d97706; --green: #10b981;
    --red: #dc2626; --warn-bg: #fef3c7; --green-bg: #d1fae5;
    --bg: #f0fdf4; --text: #1e3a2f; --card-bg: #fff;
    --input-bg: #ecfdf5; --input-border: #a7f3d0;
    --row-even: #d1fae5; --row-odd: #fff; --row-hover: #a7f3d0;
    --modal-bg: #fff; --border-col: #a7f3d0;
    --gradient-start: #064e3b; --gradient-end: #059669;
  }
  [data-theme="sunset"] {
    --navy: #7c2d12; --blue: #c2410c; --ltblue: #fed7aa;
    --pale: #fff7ed; --orange: #ea580c; --green: #16a34a;
    --red: #dc2626; --warn-bg: #fef9c3; --green-bg: #dcfce7;
    --bg: #fef6ee; --text: #431407; --card-bg: #fff;
    --input-bg: #fff7ed; --input-border: #fdba74;
    --row-even: #fed7aa; --row-odd: #fff; --row-hover: #fdba74;
    --modal-bg: #fff; --border-col: #fdba74;
    --gradient-start: #7c2d12; --gradient-end: #c2410c;
  }
  [data-theme="purple"] {
    --navy: #3b0764; --blue: #7c3aed; --ltblue: #ede9fe;
    --pale: #f5f3ff; --orange: #f59e0b; --green: #22c55e;
    --red: #ef4444; --warn-bg: #fef3c7; --green-bg: #dcfce7;
    --bg: #f5f0ff; --text: #2e1065; --card-bg: #fff;
    --input-bg: #f5f3ff; --input-border: #c4b5fd;
    --row-even: #ede9fe; --row-odd: #fff; --row-hover: #ddd6fe;
    --modal-bg: #fff; --border-col: #c4b5fd;
    --gradient-start: #3b0764; --gradient-end: #7c3aed;
  }
  [data-theme="steel"] {
    --navy: #1e293b; --blue: #475569; --ltblue: #e2e8f0;
    --pale: #f1f5f9; --orange: #f97316; --green: #22c55e;
    --red: #ef4444; --warn-bg: #fefce8; --green-bg: #dcfce7;
    --bg: #f8fafc; --text: #1e293b; --card-bg: #fff;
    --input-bg: #f1f5f9; --input-border: #cbd5e1;
    --row-even: #e2e8f0; --row-odd: #fff; --row-hover: #cbd5e1;
    --modal-bg: #fff; --border-col: #cbd5e1;
    --gradient-start: #1e293b; --gradient-end: #475569;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: Arial, sans-serif; background: var(--bg); color: var(--text);
         transition: background 0.3s, color 0.3s; }

  /* Banner */
  .banner { background: var(--navy); color: #fff; text-align: center;
            padding: 14px 20px; font-size: 22px; font-weight: bold; letter-spacing: 1px;
            display: flex; justify-content: center; align-items: center; position: relative; }
  .banner-title { flex: 1; text-align: center; }

  /* Theme switcher */
  .theme-picker { position: absolute; right: 20px; display: flex; align-items: center; gap: 6px; }
  .theme-picker span { font-size: 12px; opacity: 0.7; margin-right: 4px; }
  .theme-dot { width: 22px; height: 22px; border-radius: 50%; border: 2px solid rgba(255,255,255,0.4);
               cursor: pointer; transition: transform 0.15s, border-color 0.15s; }
  .theme-dot:hover { transform: scale(1.2); border-color: #fff; }
  .theme-dot.active { border-color: #fff; transform: scale(1.25);
                      box-shadow: 0 0 8px rgba(255,255,255,0.5); }

  .container { max-width: 1200px; margin: 0 auto; padding: 16px; }

  /* Form area */
  .form-section { display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }

  /* Calendar card */
  .cal-card { background: var(--ltblue); border: 2px solid var(--blue);
              border-radius: 8px; padding: 16px; min-width: 280px; }
  .cal-card h3 { color: var(--navy); margin-bottom: 10px; text-align: center; }
  input[type="date"] { width: 100%; padding: 10px; font-size: 16px; border: 2px solid var(--blue);
                       border-radius: 6px; background: var(--card-bg); color: var(--navy); }
  .date-display { display: flex; gap: 8px; margin-top: 10px; }
  .date-display .date-val { background: var(--orange); color: #fff; padding: 6px 14px;
                             border-radius: 4px; font-weight: bold; font-size: 14px; }
  .date-display .day-val  { background: var(--navy); color: #fff; padding: 6px 14px;
                             border-radius: 4px; font-weight: bold; font-size: 14px; flex: 1; text-align: center; }

  /* Details card */
  .details-card { flex: 1; background: var(--card-bg); border: 2px solid var(--blue);
                  border-radius: 8px; padding: 16px; min-width: 400px; }
  .details-card h3 { color: var(--navy); margin-bottom: 12px; }

  .form-row { display: flex; align-items: flex-start; margin-bottom: 10px; gap: 8px; }
  .form-row label { background: var(--blue); color: #fff; padding: 8px 12px;
                    border-radius: 4px; font-weight: bold; font-size: 13px;
                    min-width: 110px; text-align: center; white-space: nowrap; }
  .form-row input[type="text"], .form-row textarea {
    flex: 1; padding: 8px 10px; font-size: 14px; border: 1px solid var(--input-border);
    border-radius: 4px; background: var(--input-bg); color: var(--text); font-family: Arial; }
  .form-row textarea { resize: vertical; min-height: 50px; }

  /* Radio group */
  .radio-group { display: flex; flex-wrap: wrap; gap: 6px; flex: 1; align-items: center; }
  .radio-group label { background: var(--card-bg); color: var(--text); min-width: auto;
                       padding: 6px 10px; border: 2px solid var(--blue); border-radius: 4px;
                       cursor: pointer; font-size: 13px; transition: all 0.15s; }
  .radio-group input[type="radio"] { display: none; }
  .radio-group input[type="radio"]:checked + label {
    background: var(--blue); color: #fff; }

  /* Buttons */
  .btn-row { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
  .btn { padding: 10px 20px; font-size: 14px; font-weight: bold; color: #fff;
         border: none; border-radius: 5px; cursor: pointer; transition: opacity 0.15s; }
  .btn:hover { opacity: 0.85; }
  .btn-save   { background: var(--green); }
  .btn-clear  { background: var(--orange); }
  .btn-delete { background: var(--red); }
  .btn-blue   { background: var(--blue); }

  /* Status */
  .status-bar { background: var(--warn-bg); color: #7D6608; padding: 8px 14px;
                border-radius: 4px; font-size: 13px; margin-bottom: 12px; }

  /* Recall section */
  .recall-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
  .recall-label { background: var(--navy); color: #fff; padding: 6px 14px;
                  border-radius: 4px; font-weight: bold; font-size: 13px; }
  .recall-bar input[type="number"] { width: 70px; padding: 6px; font-size: 14px;
                                     border: 1px solid var(--input-border); border-radius: 4px;
                                     background: var(--input-bg); color: var(--text); }
  .record-count { background: var(--green-bg); color: #375623; padding: 6px 14px;
                  border-radius: 4px; font-weight: bold; font-size: 13px; margin-left: auto; }

  /* Table */
  .table-wrap { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  thead th { background: var(--blue); color: #fff; padding: 10px 8px;
             text-align: center; font-weight: bold; position: sticky; top: 0; }
  tbody td { padding: 8px; border-bottom: 1px solid var(--border-col); }
  tbody tr:nth-child(even) { background: var(--row-even); }
  tbody tr:nth-child(odd)  { background: var(--row-odd); }
  tbody tr:hover { background: var(--row-hover); }
  td.desc-col, td.info-col { text-align: left; max-width: 300px; word-wrap: break-word; }
  td.center { text-align: center; }
  td.actions { text-align: center; white-space: nowrap; }
  .act-btn { padding: 4px 10px; font-size: 12px; font-weight: bold; color: #fff;
             border: none; border-radius: 3px; cursor: pointer; margin: 0 2px; transition: opacity 0.15s; }
  .act-btn:hover { opacity: 0.8; }
  .act-edit { background: var(--blue); }
  .act-del  { background: var(--red); }

  /* Toast */
  .toast { position: fixed; top: 20px; right: 20px; padding: 14px 24px;
           border-radius: 6px; color: #fff; font-weight: bold; font-size: 14px;
           z-index: 9999; opacity: 0; transition: opacity 0.3s; pointer-events: none; }
  .toast.show { opacity: 1; }
  .toast-success { background: var(--green); }
  .toast-error   { background: var(--red); }

  /* Weekly Summary Modal */
  .modal-overlay { display:none; position:fixed; inset:0; background:rgba(0,0,0,0.5);
                   z-index:10000; justify-content:center; align-items:flex-start;
                   padding:30px; overflow-y:auto; }
  .modal-overlay.open { display:flex; }
  .modal { background:var(--modal-bg); border-radius:10px; max-width:900px; width:100%;
           box-shadow: 0 8px 32px rgba(0,0,0,0.25); overflow:hidden; }
  .modal-header { background:var(--navy); color:#fff; padding:16px 24px;
                  display:flex; justify-content:space-between; align-items:center; }
  .modal-header h2 { font-size:20px; letter-spacing:0.5px; }
  .modal-close { background:none; border:none; color:#fff; font-size:28px;
                 cursor:pointer; line-height:1; padding:0 4px; }
  .modal-close:hover { color:var(--orange); }
  .modal-body { padding:24px; }
  .modal-actions { padding:0 24px 20px; display:flex; gap:10px; }

  /* Summary cards */
  .summary-stats { display:flex; gap:12px; margin-bottom:20px; flex-wrap:wrap; }
  .stat-card { flex:1; min-width:140px; background:var(--pale); border:2px solid var(--blue);
               border-radius:8px; padding:14px; text-align:center; }
  .stat-card .stat-num { font-size:28px; font-weight:bold; color:var(--navy); }
  .stat-card .stat-label { font-size:12px; color:var(--blue); font-weight:bold; margin-top:4px; }

  .ai-summary-box { background: linear-gradient(135deg, var(--gradient-start) 0%, var(--gradient-end) 100%);
                     color: #fff; padding: 20px 24px; border-radius: 8px; margin-bottom: 20px;
                     line-height: 1.7; font-size: 14px; position: relative; }
  .ai-summary-box::before { content: "AI SUMMARY"; position: absolute; top: -10px; left: 16px;
                             background: var(--orange); color: #fff; padding: 2px 12px;
                             border-radius: 4px; font-size: 11px; font-weight: bold; letter-spacing: 1px; }
  .ai-loading { text-align:center; padding:30px; color:var(--blue); font-size:16px; }
  .ai-loading .spinner { display:inline-block; width:20px; height:20px; border:3px solid var(--ltblue);
                         border-top:3px solid var(--blue); border-radius:50%;
                         animation: spin 0.8s linear infinite; margin-right:10px; vertical-align:middle; }
  @keyframes spin { to { transform: rotate(360deg); } }

  .loc-badges { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:20px; }
  .loc-badge { padding:6px 16px; border-radius:20px; font-weight:bold; font-size:13px;
               background:var(--ltblue); color:var(--navy); border:1px solid var(--blue); }
  .loc-badge span { background:var(--blue); color:#fff; border-radius:10px;
                    padding:2px 8px; margin-left:6px; font-size:12px; }

  .day-section { margin-bottom:16px; }
  .day-header { background:var(--blue); color:#fff; padding:8px 16px; border-radius:6px 6px 0 0;
                font-weight:bold; font-size:14px; display:flex; justify-content:space-between; }
  .day-tasks { border:1px solid var(--border-col); border-top:none; border-radius:0 0 6px 6px;
               background: var(--card-bg); }
  .day-task-row { display:flex; padding:8px 16px; font-size:13px; border-bottom:1px solid var(--border-col);
                  align-items:flex-start; gap:12px; }
  .day-task-row:last-child { border-bottom:none; }
  .day-task-row:nth-child(even) { background:var(--pale); }
  .task-loc { background:var(--navy); color:#fff; padding:2px 10px; border-radius:3px;
              font-size:12px; font-weight:bold; white-space:nowrap; }
  .task-dc { background:var(--orange); color:#fff; padding:2px 8px; border-radius:3px;
             font-size:11px; font-weight:bold; white-space:nowrap; }
  .task-desc { flex:1; color:var(--text); }
  .task-info { color:var(--text); opacity:0.6; font-size:12px; font-style:italic; max-width:200px; }

  /* View Tabs */
  .view-tabs { display:flex; gap:0; margin-bottom:0; }
  .view-tab { padding:10px 24px; font-size:14px; font-weight:bold; cursor:pointer;
              border:2px solid var(--blue); border-bottom:none; border-radius:8px 8px 0 0;
              background:var(--pale); color:var(--text); transition:all 0.15s; margin-right:2px; }
  .view-tab:hover { background:var(--ltblue); }
  .view-tab.active { background:var(--blue); color:#fff; }
  .tab-content { border:2px solid var(--blue); border-radius:0 8px 8px 8px; padding:0;
                 background:var(--card-bg); }
  .tab-panel { display:none; }
  .tab-panel.active { display:block; }
  .week-header { background:var(--navy); color:#fff; padding:12px 20px; display:flex;
                 justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; }
  .week-header h3 { font-size:16px; letter-spacing:0.5px; }
  .week-day-cards { padding:16px; display:flex; flex-direction:column; gap:12px; }
  .day-card { border:1px solid var(--border-col); border-radius:6px; overflow:hidden; }
  .day-card-header { background:var(--blue); color:#fff; padding:8px 16px; font-weight:bold;
                     font-size:14px; display:flex; justify-content:space-between; align-items:center; }
  .day-card-body { background:var(--card-bg); }
  .day-card-row { display:flex; padding:8px 16px; font-size:13px; border-bottom:1px solid var(--border-col);
                  align-items:center; gap:10px; }
  .day-card-row:last-child { border-bottom:none; }
  .day-card-row:nth-child(even) { background:var(--pale); }
  .day-card-num { background:var(--navy); color:#fff; padding:2px 8px; border-radius:3px;
                  font-size:11px; font-weight:bold; min-width:30px; text-align:center; }
  .day-card-loc { background:var(--orange); color:#fff; padding:2px 10px; border-radius:3px;
                  font-size:12px; font-weight:bold; white-space:nowrap; }
  .day-card-desc { flex:1; color:var(--text); }
  .day-card-info { color:var(--text); opacity:0.6; font-size:12px; font-style:italic; max-width:180px; }
  .day-card-actions { display:flex; gap:4px; }
  .week-empty { text-align:center; padding:40px; color:var(--text); opacity:0.5; font-size:16px; }
  .week-stats { display:flex; gap:8px; }
  .week-stat-badge { background:rgba(255,255,255,0.2); padding:3px 10px; border-radius:12px;
                     font-size:12px; font-weight:bold; }

  /* Search bar */
  .search-bar { display:flex; align-items:center; gap:8px; padding:10px 16px;
                background:var(--pale); border-bottom:1px solid var(--border-col); }
  .search-bar input { flex:1; padding:8px 12px; font-size:14px; border:1px solid var(--input-border);
                      border-radius:4px; background:var(--input-bg); color:var(--text); }
  .search-bar input::placeholder { color:var(--text); opacity:0.4; }
  .search-bar .search-icon { color:var(--blue); font-weight:bold; font-size:16px; }
  .search-bar .search-count { font-size:12px; color:var(--text); opacity:0.6; font-weight:bold; }

  /* Stats dashboard */
  .stats-dash { display:flex; gap:10px; margin-bottom:12px; flex-wrap:wrap; }
  .mini-stat { display:flex; align-items:center; gap:8px; background:var(--card-bg);
               border:2px solid var(--blue); border-radius:8px; padding:8px 16px; }
  .mini-stat .mini-num { font-size:22px; font-weight:bold; color:var(--navy); }
  .mini-stat .mini-label { font-size:11px; font-weight:bold; color:var(--blue);
                           text-transform:uppercase; line-height:1.2; }
  .mini-stat .mini-sub { font-size:10px; color:var(--text); opacity:0.5; }

  /* DUP button */
  .act-dup { background:var(--orange); }

  /* Export button */
  .btn-export { background:var(--navy); }

  /* Version label */
  .version-label { position:fixed; bottom:10px; left:14px; font-size:11px; font-weight:bold;
                   color:var(--text); opacity:0.35; letter-spacing:0.5px; z-index:100;
                   pointer-events:none; }

  /* Keyboard hint */
  .kbd-hint { font-size:11px; color:var(--text); opacity:0.4; margin-left:4px; }
  kbd { background:var(--pale); border:1px solid var(--input-border); border-radius:3px;
        padding:1px 5px; font-size:10px; font-family:monospace; }

  @media print {
    body * { visibility: hidden; }
    .modal, .modal * { visibility: visible; }
    .modal { position:absolute; left:0; top:0; width:100%; box-shadow:none; }
    .modal-close, .modal-actions { display:none !important; }
  }
</style>
</head>
<body>

<div class="banner">
  <span class="banner-title">EVI DAILY TASK LOG &mdash; Datacenter EVI01</span>
  <div class="theme-picker">
    <span>THEME</span>
    <div class="theme-dot active" data-theme="classic-blue" style="background:linear-gradient(135deg,#1F3864,#2E75B6);" title="Classic Blue"></div>
    <div class="theme-dot" data-theme="dark" style="background:linear-gradient(135deg,#0a0f14,#1b4965);" title="Dark"></div>
    <div class="theme-dot" data-theme="emerald" style="background:linear-gradient(135deg,#064e3b,#059669);" title="Emerald"></div>
    <div class="theme-dot" data-theme="sunset" style="background:linear-gradient(135deg,#7c2d12,#c2410c);" title="Sunset"></div>
    <div class="theme-dot" data-theme="purple" style="background:linear-gradient(135deg,#3b0764,#7c3aed);" title="Purple"></div>
    <div class="theme-dot" data-theme="steel" style="background:linear-gradient(135deg,#1e293b,#475569);" title="Steel"></div>
  </div>
</div>

<div class="container">
  <!-- FORM SECTION -->
  <div class="form-section">
    <!-- Calendar -->
    <div class="cal-card">
      <h3>SELECT DATE</h3>
      <input type="date" id="entryDate">
      <div class="date-display">
        <span class="date-val" id="dispDate"></span>
        <span class="day-val" id="dispDay"></span>
      </div>
    </div>

    <!-- Task Details -->
    <div class="details-card">
      <h3>TASK DETAILS</h3>

      <div class="form-row">
        <label>Location</label>
        <div class="radio-group" id="locGroup">
          <input type="radio" name="location" id="loc-DH1" value="DH1" checked><label for="loc-DH1">DH1</label>
          <input type="radio" name="location" id="loc-DH2" value="DH2"><label for="loc-DH2">DH2</label>
          <input type="radio" name="location" id="loc-DH3" value="DH3"><label for="loc-DH3">DH3</label>
          <input type="radio" name="location" id="loc-DH4" value="DH4"><label for="loc-DH4">DH4</label>
          <input type="radio" name="location" id="loc-DH5" value="DH5"><label for="loc-DH5">DH5</label>
          <input type="radio" name="location" id="loc-DH6" value="DH6"><label for="loc-DH6">DH6</label>
          <input type="radio" name="location" id="loc-Other" value="Other"><label for="loc-Other">Others</label>
          <input type="text" id="locOther" placeholder="Enter location..." style="width:140px; padding:6px 8px; font-size:13px; border:1px solid var(--input-border); border-radius:4px; background:var(--input-bg); color:var(--text); display:none;">
        </div>
      </div>

      <div class="form-row">
        <label>DC Code</label>
        <input type="text" id="dcCode" value="EVI01" style="max-width:160px;">
      </div>

      <div class="form-row">
        <label>Description</label>
        <textarea id="description" rows="3" placeholder="Enter task description..."></textarea>
      </div>

      <div class="form-row">
        <label>Add. Info</label>
        <textarea id="addInfo" rows="2" placeholder="Optional additional information..."></textarea>
      </div>

      <div class="btn-row">
        <button class="btn btn-save" onclick="saveEntry()">SAVE ENTRY <span class="kbd-hint"><kbd>Ctrl</kbd>+<kbd>S</kbd></span></button>
        <button class="btn btn-clear" onclick="clearForm()">CLEAR FORM</button>
      </div>
    </div>
  </div>

  <!-- STATS DASHBOARD -->
  <div class="stats-dash" id="statsDash">
    <div class="mini-stat">
      <span class="mini-num" id="statToday">-</span>
      <span><span class="mini-label">Today</span><br><span class="mini-sub" id="statTodayDate"></span></span>
    </div>
    <div class="mini-stat">
      <span class="mini-num" id="statWeek">-</span>
      <span><span class="mini-label">This Week</span><br><span class="mini-sub" id="statWeekLabel"></span></span>
    </div>
    <div class="mini-stat">
      <span class="mini-num" id="statTotal">-</span>
      <span><span class="mini-label">All Time</span><br><span class="mini-sub">total records</span></span>
    </div>
  </div>

  <!-- STATUS -->
  <div class="status-bar" id="statusBar">Ready &mdash; select a date and fill in the form.</div>

  <!-- RECALL BAR -->
  <div class="recall-bar">
    <span class="recall-label">RECALL</span>
    <button class="btn btn-blue" onclick="recallByDate()">By Selected Date</button>
    <button class="btn btn-blue" onclick="recallByWeek()">By This Week</button>
    <button class="btn btn-blue" onclick="recallAll()">All Records</button>
    <button class="btn btn-save" onclick="showWeeklySummary()" style="margin-left:4px;">WEEKLY SUMMARY</button>
    <button class="btn btn-export" onclick="exportCSV()" style="margin-left:4px;">EXPORT CSV</button>
    <span style="margin-left:16px; font-weight:bold; color:var(--text);">Week #:</span>
    <input type="number" id="weekNum" min="1" max="53">
    <span style="font-weight:bold; color:var(--text);">Year:</span>
    <input type="number" id="yearNum" min="2020" max="2035">
    <span class="record-count" id="recordCount"></span>
  </div>

  <!-- TABS -->
  <div class="view-tabs">
    <div class="view-tab active" onclick="switchTab('all')">All Records</div>
    <div class="view-tab" onclick="switchTab('week')">Current Week</div>
  </div>
  <div class="tab-content">
    <!-- All Records Tab -->
    <div class="tab-panel active" id="tabAll">
      <div class="search-bar">
        <span class="search-icon">SEARCH</span>
        <input type="text" id="searchInput" placeholder="Filter by description, location, date..." oninput="filterTable()">
        <span class="search-count" id="searchCount"></span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th><th>Date</th><th>Day</th><th>Description</th>
              <th>Location</th><th>DC Code</th><th>Add. Info</th><th>Saved At</th><th>Actions</th>
            </tr>
          </thead>
          <tbody id="taskBody"></tbody>
        </table>
      </div>
    </div>
    <!-- Current Week Tab -->
    <div class="tab-panel" id="tabWeek">
      <div class="week-header" id="cwHeader">
        <h3 id="cwTitle">Current Week</h3>
        <div class="week-stats" id="cwStats"></div>
      </div>
      <div class="week-day-cards" id="cwBody">
        <div class="week-empty">Loading...</div>
      </div>
    </div>
  </div>
</div>

<!-- Weekly Summary Modal -->
<div class="modal-overlay" id="summaryModal">
  <div class="modal">
    <div class="modal-header">
      <h2 id="summaryTitle">WEEKLY SUMMARY</h2>
      <button class="modal-close" onclick="closeSummary()">&times;</button>
    </div>
    <div class="modal-body" id="summaryBody"></div>
    <div class="modal-actions">
      <button class="btn btn-blue" onclick="window.print()">PRINT SUMMARY</button>
      <button class="btn btn-clear" onclick="closeSummary()">CLOSE</button>
    </div>
  </div>
</div>

<!-- Edit Record Modal -->
<div class="modal-overlay" id="editModal">
  <div class="modal" style="max-width:600px;">
    <div class="modal-header">
      <h2 id="editTitle">EDIT RECORD</h2>
      <button class="modal-close" onclick="closeEdit()">&times;</button>
    </div>
    <div class="modal-body">
      <input type="hidden" id="editId">
      <div class="form-row">
        <label>Date</label>
        <input type="date" id="editDate" style="flex:1; padding:8px; font-size:14px; border:1px solid #ccc; border-radius:4px; background:var(--pale); color:var(--navy);">
      </div>
      <div class="form-row">
        <label>Location</label>
        <div class="radio-group" id="editLocGroup">
          <input type="radio" name="editLocation" id="edit-loc-DH1" value="DH1"><label for="edit-loc-DH1">DH1</label>
          <input type="radio" name="editLocation" id="edit-loc-DH2" value="DH2"><label for="edit-loc-DH2">DH2</label>
          <input type="radio" name="editLocation" id="edit-loc-DH3" value="DH3"><label for="edit-loc-DH3">DH3</label>
          <input type="radio" name="editLocation" id="edit-loc-DH4" value="DH4"><label for="edit-loc-DH4">DH4</label>
          <input type="radio" name="editLocation" id="edit-loc-DH5" value="DH5"><label for="edit-loc-DH5">DH5</label>
          <input type="radio" name="editLocation" id="edit-loc-DH6" value="DH6"><label for="edit-loc-DH6">DH6</label>
          <input type="radio" name="editLocation" id="edit-loc-Other" value="Other"><label for="edit-loc-Other">Others</label>
          <input type="text" id="editLocOther" placeholder="Enter location..." style="width:140px; padding:6px 8px; font-size:13px; border:1px solid var(--input-border); border-radius:4px; background:var(--input-bg); color:var(--text); display:none;">
        </div>
      </div>
      <div class="form-row">
        <label>DC Code</label>
        <input type="text" id="editDcCode" value="EVI01" style="max-width:160px;">
      </div>
      <div class="form-row">
        <label>Description</label>
        <textarea id="editDescription" rows="3" placeholder="Enter task description..."></textarea>
      </div>
      <div class="form-row">
        <label>Add. Info</label>
        <textarea id="editAddInfo" rows="2" placeholder="Optional additional information..."></textarea>
      </div>
    </div>
    <div class="modal-actions">
      <button class="btn btn-save" onclick="submitEdit()">UPDATE RECORD</button>
      <button class="btn btn-clear" onclick="closeEdit()">CANCEL</button>
    </div>
  </div>
</div>

<!-- Version Label -->
<div class="version-label">Alpha v.1.0.0</div>

<!-- Toast notification -->
<div class="toast" id="toast"></div>

<script>
const $ = id => document.getElementById(id);
let selectedRowId = null;

// ── Init ──────────────────────────────────────────
function init() {
  const today = new Date();
  const iso = today.toISOString().slice(0, 10);
  $("entryDate").value = iso;
  updateDateDisplay(iso);

  // Week / year
  const wk = getWeekNumber(today);
  $("weekNum").value = wk;
  $("yearNum").value = today.getFullYear();

  $("entryDate").addEventListener("change", () => updateDateDisplay($("entryDate").value));
  recallAll();
  updateStats();
}

function updateDateDisplay(isoStr) {
  if (!isoStr) return;
  const parts = isoStr.split("-");
  const d = new Date(parts[0], parts[1]-1, parts[2]);
  const options = { day: "2-digit", month: "short", year: "numeric" };
  $("dispDate").textContent = d.toLocaleDateString("en-GB", options).replace(/ /g, "-");
  $("dispDay").textContent = d.toLocaleDateString("en-US", { weekday: "long" });
  setStatus("Date selected: " + d.toLocaleDateString("en-US", { weekday:"long", day:"2-digit", month:"short", year:"numeric" })
            + "  (Week " + getWeekNumber(d) + ")");
}

function getWeekNumber(d) {
  // Match Python strftime("%W") — Monday-based week numbering
  const jan1 = new Date(d.getFullYear(), 0, 1);
  const jan1Day = jan1.getDay(); // 0=Sun..6=Sat
  const daysToFirstMon = jan1Day === 0 ? 1 : (jan1Day === 1 ? 0 : 8 - jan1Day);
  const firstMonday = new Date(d.getFullYear(), 0, 1 + daysToFirstMon);
  if (d < firstMonday) return 0;
  return Math.floor((d - firstMonday) / 604800000) + 1;
}

function getLocation() {
  const checked = document.querySelector('input[name="location"]:checked');
  if (checked && checked.value === "Other") return $("locOther").value.trim() || "Other";
  return checked ? checked.value : "DH1";
}

function getEditLocation() {
  const checked = document.querySelector('input[name="editLocation"]:checked');
  if (checked && checked.value === "Other") return $("editLocOther").value.trim() || "Other";
  return checked ? checked.value : "DH1";
}

// Toggle "Others" text input visibility
function setupOtherToggle(radioName, inputId) {
  document.querySelectorAll('input[name="' + radioName + '"]').forEach(r => {
    r.addEventListener("change", () => {
      $(inputId).style.display = r.value === "Other" && r.checked ? "inline-block" : "none";
      if (r.value === "Other" && r.checked) $(inputId).focus();
    });
  });
}
setupOtherToggle("location", "locOther");
setupOtherToggle("editLocation", "editLocOther");

// ── Save ──────────────────────────────────────────
async function saveEntry() {
  const desc = $("description").value.trim();
  if (!desc) { toast("Please enter a task description.", "error"); $("description").focus(); return; }

  const body = {
    entry_date: $("entryDate").value,
    description: desc,
    location: getLocation(),
    dc_code: $("dcCode").value.trim() || "EVI01",
    add_info: $("addInfo").value.trim(),
  };

  const res = await fetch("/api/save", {
    method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(body)
  });
  const data = await res.json();
  if (res.ok) {
    toast(data.message, "success");
    setStatus("SAVED  Record #" + data.id);
    clearForm();
    refreshActiveTab();
  } else {
    toast(data.error || "Save failed", "error");
  }
}

// ── Clear ─────────────────────────────────────────
function clearForm() {
  $("description").value = "";
  $("addInfo").value = "";
  $("dcCode").value = "EVI01";
  document.getElementById("loc-DH1").checked = true;
  $("locOther").value = "";
  $("locOther").style.display = "none";
  const today = new Date().toISOString().slice(0,10);
  $("entryDate").value = today;
  updateDateDisplay(today);
  setStatus("Form cleared — ready for new entry.");
}

// ── Delete ────────────────────────────────────────
async function deleteRecord(id) {
  if (!confirm("Delete record #" + id + "?\nThis cannot be undone.")) return;
  const res = await fetch("/api/delete/" + id, { method: "DELETE" });
  if (res.ok) {
    toast("Record #" + id + " deleted.", "success");
    refreshActiveTab();
  }
}

// ── Edit ──────────────────────────────────────────
async function editRecord(id) {
  const res = await fetch("/api/task/" + id);
  if (!res.ok) { toast("Could not load record.", "error"); return; }
  const r = await res.json();
  $("editId").value = r.id;
  $("editDate").value = r.entry_date;
  $("editDcCode").value = r.dc_code || "EVI01";
  $("editDescription").value = r.description || "";
  $("editAddInfo").value = r.add_info || "";
  // Set location radio
  const loc = r.location || "DH1";
  const knownLocs = ["DH1","DH2","DH3","DH4","DH5","DH6"];
  if (knownLocs.includes(loc)) {
    document.getElementById("edit-loc-" + loc).checked = true;
    $("editLocOther").style.display = "none";
    $("editLocOther").value = "";
  } else {
    document.getElementById("edit-loc-Other").checked = true;
    $("editLocOther").style.display = "inline-block";
    $("editLocOther").value = loc;
  }
  $("editTitle").textContent = "EDIT RECORD #" + r.id;
  $("editModal").classList.add("open");
}

async function submitEdit() {
  const id = $("editId").value;
  const desc = $("editDescription").value.trim();
  if (!desc) { toast("Description is required.", "error"); $("editDescription").focus(); return; }
  const body = {
    entry_date: $("editDate").value,
    description: desc,
    location: getEditLocation(),
    dc_code: $("editDcCode").value.trim() || "EVI01",
    add_info: $("editAddInfo").value.trim(),
  };
  const res = await fetch("/api/update/" + id, {
    method: "PUT", headers: {"Content-Type":"application/json"}, body: JSON.stringify(body)
  });
  const data = await res.json();
  if (res.ok) {
    toast(data.message, "success");
    closeEdit();
    refreshActiveTab();
  } else {
    toast(data.error || "Update failed", "error");
  }
}

function closeEdit() {
  $("editModal").classList.remove("open");
}

// ── Recall ────────────────────────────────────────
async function recallByDate() {
  const d = $("entryDate").value;
  const rows = await fetchTasks("date", { date: d });
  renderTable(rows);
  $("recordCount").textContent = rows.length + " record(s) for " + d;
  setStatus("Recall by date: " + d + " — " + rows.length + " found");
}

async function recallByWeek() {
  const yr = $("yearNum").value;
  const wk = $("weekNum").value;
  const rows = await fetchTasks("week", { year: yr, week: wk });
  renderTable(rows);
  $("recordCount").textContent = rows.length + " record(s) — Year " + yr + ", Week " + wk;
  setStatus("Recall by week: Year " + yr + ", Week " + wk + " — " + rows.length + " found");
}

async function recallAll() {
  const rows = await fetchTasks("all");
  renderTable(rows);
  $("recordCount").textContent = rows.length + " total record(s)";
  setStatus("All records — " + rows.length + " total");
}

async function fetchTasks(mode, params={}) {
  const qs = new URLSearchParams({ mode, ...params });
  const res = await fetch("/api/tasks?" + qs);
  return await res.json();
}

// ── Table ─────────────────────────────────────────
function renderTable(rows) {
  const tbody = $("taskBody");
  tbody.innerHTML = "";
  rows.forEach(r => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="center">${r.id}</td>
      <td class="center">${r.entry_date}</td>
      <td class="center">${r.day_name}</td>
      <td class="desc-col">${esc(r.description||"")}</td>
      <td class="center">${r.location||""}</td>
      <td class="center">${r.dc_code||"EVI01"}</td>
      <td class="info-col">${esc(r.add_info||"")}</td>
      <td class="center">${r.saved_at||""}</td>
      <td class="actions">
        <button class="act-btn act-dup" onclick="dupRecord(${r.id})">DUP</button>
        <button class="act-btn act-edit" onclick="editRecord(${r.id})">EDIT</button>
        <button class="act-btn act-del" onclick="deleteRecord(${r.id})">DEL</button>
      </td>`;
    tbody.appendChild(tr);
  });
}

function esc(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

// ── Helpers ───────────────────────────────────────
function setStatus(msg) { $("statusBar").textContent = msg; }

function toast(msg, type) {
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast toast-" + type + " show";
  setTimeout(() => t.className = "toast", 3000);
}

// ── Weekly Summary ────────────────────────────────
async function showWeeklySummary() {
  const yr = $("yearNum").value;
  const wk = $("weekNum").value;

  // Show modal immediately with loading state
  $("summaryTitle").textContent = "WEEKLY SUMMARY — Year " + yr + ", Week " + wk;
  $("summaryBody").innerHTML = '<div class="ai-loading"><span class="spinner"></span>Generating AI summary...</div>';
  $("summaryModal").classList.add("open");

  const res = await fetch("/api/weekly-summary?year=" + yr + "&week=" + wk);
  const data = await res.json();

  if (data.total_tasks === 0) {
    closeSummary();
    toast("No records found for Year " + yr + ", Week " + wk, "error");
    return;
  }

  let html = "";

  // AI Summary (top, prominent)
  if (data.ai_summary) {
    html += '<div class="ai-summary-box">' + esc(data.ai_summary) + '</div>';
  }

  // Stats cards
  html += '<div class="summary-stats">';
  html += statCard(data.total_tasks, "TOTAL TASKS");
  html += statCard(data.total_days, "ACTIVE DAYS");
  html += statCard(Object.keys(data.by_location).length, "LOCATIONS");
  html += statCard(data.date_range, "DATE RANGE", true);
  html += '</div>';

  // Location badges
  html += '<div class="loc-badges">';
  for (const [loc, cnt] of Object.entries(data.by_location).sort((a,b) => b[1]-a[1])) {
    html += '<div class="loc-badge">' + esc(loc) + '<span>' + cnt + '</span></div>';
  }
  html += '</div>';

  // Day-by-day breakdown
  data.by_day.forEach(day => {
    html += '<div class="day-section">';
    html += '<div class="day-header"><span>' + esc(day.day) + ' — ' + esc(day.date) + '</span>'
          + '<span>' + day.tasks.length + ' task(s)</span></div>';
    html += '<div class="day-tasks">';
    day.tasks.forEach(t => {
      html += '<div class="day-task-row">';
      html += '<span class="task-loc">' + esc(t.location||"") + '</span>';
      html += '<span class="task-dc">' + esc(t.dc_code||"EVI01") + '</span>';
      html += '<span class="task-desc">' + esc(t.description||"") + '</span>';
      if (t.add_info) html += '<span class="task-info">' + esc(t.add_info) + '</span>';
      html += '</div>';
    });
    html += '</div></div>';
  });

  $("summaryBody").innerHTML = html;
}

function statCard(value, label, small) {
  const cls = small ? 'font-size:16px' : '';
  return '<div class="stat-card"><div class="stat-num" style="' + cls + '">' + value + '</div>'
       + '<div class="stat-label">' + label + '</div></div>';
}

function closeSummary() {
  $("summaryModal").classList.remove("open");
}

// Close modals on overlay click
document.addEventListener("click", function(e) {
  if (e.target.id === "summaryModal") closeSummary();
  if (e.target.id === "editModal") closeEdit();
});

// ── Theme Switcher ────────────────────────────────
function setTheme(name) {
  document.documentElement.setAttribute("data-theme", name);
  document.querySelectorAll(".theme-dot").forEach(d => d.classList.remove("active"));
  const active = document.querySelector('.theme-dot[data-theme="'+name+'"]');
  if (active) active.classList.add("active");
  localStorage.setItem("evi-theme", name);
}

// Theme dot click handlers
document.querySelectorAll(".theme-dot").forEach(dot => {
  dot.addEventListener("click", () => setTheme(dot.dataset.theme));
});

// Load saved theme
const savedTheme = localStorage.getItem("evi-theme");
if (savedTheme) setTheme(savedTheme);

// ── Refresh active tab ───────────────────────────
function refreshActiveTab() {
  if (activeTab === "week") loadCurrentWeek();
  else recallAll();
  updateStats();
}

// ── Tab Switching ────────────────────────────────
let activeTab = "all";

function switchTab(tab) {
  activeTab = tab;
  document.querySelectorAll(".view-tab").forEach((t, i) => {
    t.classList.toggle("active", (i === 0 && tab === "all") || (i === 1 && tab === "week"));
  });
  $("tabAll").classList.toggle("active", tab === "all");
  $("tabWeek").classList.toggle("active", tab === "week");
  if (tab === "week") loadCurrentWeek();
}

async function loadCurrentWeek() {
  const yr = $("yearNum").value;
  const wk = $("weekNum").value;
  const rows = await fetchTasks("week", { year: yr, week: wk });

  $("cwTitle").textContent = "Week " + wk + " — " + yr;
  $("cwStats").innerHTML =
    '<span class="week-stat-badge">' + rows.length + ' task(s)</span>';

  const body = $("cwBody");
  if (rows.length === 0) {
    body.innerHTML = '<div class="week-empty">No tasks recorded for this week.</div>';
    $("recordCount").textContent = "0 record(s) — Week " + wk;
    return;
  }

  // Group by day
  const daysOrder = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"];
  const byDay = {};
  rows.forEach(r => {
    const d = r.day_name;
    if (!byDay[d]) byDay[d] = { date: r.entry_date, tasks: [] };
    byDay[d].tasks.push(r);
  });

  let html = "";
  daysOrder.forEach(day => {
    if (!byDay[day]) return;
    const g = byDay[day];
    html += '<div class="day-card">';
    html += '<div class="day-card-header"><span>' + esc(day) + ' — ' + esc(g.date) + '</span>'
          + '<span>' + g.tasks.length + ' task(s)</span></div>';
    html += '<div class="day-card-body">';
    g.tasks.forEach((t, i) => {
      html += '<div class="day-card-row">';
      html += '<span class="day-card-num">' + (i+1) + '</span>';
      html += '<span class="day-card-loc">' + esc(t.location||"") + '</span>';
      html += '<span class="day-card-desc">' + esc(t.description||"") + '</span>';
      if (t.add_info) html += '<span class="day-card-info">' + esc(t.add_info) + '</span>';
      html += '<span class="day-card-actions">'
            + '<button class="act-btn act-edit" onclick="editRecord(' + t.id + ')">EDIT</button>'
            + '<button class="act-btn act-del" onclick="deleteRecord(' + t.id + ')">DEL</button>'
            + '</span>';
      html += '</div>';
    });
    html += '</div></div>';
  });
  body.innerHTML = html;
  $("recordCount").textContent = rows.length + " record(s) — Week " + wk;
  setStatus("Current week: Year " + yr + ", Week " + wk + " — " + rows.length + " found");
}

// ── Search / Filter ──────────────────────────────
let allRows = []; // cache for filtering

function filterTable() {
  const q = $("searchInput").value.toLowerCase().trim();
  const tbody = $("taskBody");
  const rows = tbody.querySelectorAll("tr");
  let visible = 0;
  rows.forEach(tr => {
    const text = tr.textContent.toLowerCase();
    const show = !q || text.includes(q);
    tr.style.display = show ? "" : "none";
    if (show) visible++;
  });
  $("searchCount").textContent = q ? visible + " of " + rows.length + " shown" : "";
}

// ── Export CSV ───────────────────────────────────
function exportCSV() {
  const tbody = $("taskBody");
  const rows = tbody.querySelectorAll("tr");
  if (rows.length === 0) { toast("No records to export.", "error"); return; }

  const headers = ["ID","Date","Day","Description","Location","DC Code","Add. Info","Saved At"];
  let csv = headers.join(",") + "\n";

  rows.forEach(tr => {
    if (tr.style.display === "none") return; // skip filtered-out rows
    const cells = tr.querySelectorAll("td");
    const vals = [];
    for (let i = 0; i < cells.length - 1; i++) { // skip Actions column
      let v = cells[i].textContent.trim().replace(/"/g, '""');
      vals.push('"' + v + '"');
    }
    csv += vals.join(",") + "\n";
  });

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  const d = new Date();
  a.download = "EVI_Tasks_" + d.toISOString().slice(0,10) + ".csv";
  a.click();
  URL.revokeObjectURL(url);
  toast("CSV exported successfully!", "success");
}

// ── Quick Duplicate ──────────────────────────────
async function dupRecord(id) {
  const res = await fetch("/api/task/" + id);
  if (!res.ok) { toast("Could not load record.", "error"); return; }
  const r = await res.json();

  // Pre-fill form with duplicated data
  $("entryDate").value = new Date().toISOString().slice(0,10);
  updateDateDisplay($("entryDate").value);
  $("description").value = r.description || "";
  $("addInfo").value = r.add_info || "";
  $("dcCode").value = r.dc_code || "EVI01";

  // Set location
  const knownLocs = ["DH1","DH2","DH3","DH4","DH5","DH6"];
  const loc = r.location || "DH1";
  if (knownLocs.includes(loc)) {
    document.getElementById("loc-" + loc).checked = true;
    $("locOther").style.display = "none";
    $("locOther").value = "";
  } else {
    document.getElementById("loc-Other").checked = true;
    $("locOther").style.display = "inline-block";
    $("locOther").value = loc;
  }

  toast("Form filled from record #" + id + " — edit and save as new.", "success");
  $("description").focus();
  window.scrollTo({ top: 0, behavior: "smooth" });
}

// ── Stats Dashboard ──────────────────────────────
async function updateStats() {
  const today = new Date().toISOString().slice(0,10);
  const yr = new Date().getFullYear();
  const wk = getWeekNumber(new Date());

  // Fetch all three in parallel
  const [todayRows, weekRows, allRowsData] = await Promise.all([
    fetchTasks("date", { date: today }),
    fetchTasks("week", { year: yr, week: wk }),
    fetchTasks("all"),
  ]);

  $("statToday").textContent = todayRows.length;
  $("statTodayDate").textContent = today;
  $("statWeek").textContent = weekRows.length;
  $("statWeekLabel").textContent = "Week " + wk;
  $("statTotal").textContent = allRowsData.length;
}

// ── Keyboard Shortcuts ───────────────────────────
document.addEventListener("keydown", function(e) {
  // Ctrl+S / Cmd+S = Save entry
  if ((e.ctrlKey || e.metaKey) && e.key === "s") {
    e.preventDefault();
    // If edit modal is open, submit edit; otherwise save new entry
    if ($("editModal").classList.contains("open")) {
      submitEdit();
    } else {
      saveEntry();
    }
  }
  // Escape = Close modals
  if (e.key === "Escape") {
    if ($("editModal").classList.contains("open")) closeEdit();
    else if ($("summaryModal").classList.contains("open")) closeSummary();
  }
  // Ctrl+E = Export CSV
  if ((e.ctrlKey || e.metaKey) && e.key === "e") {
    e.preventDefault();
    exportCSV();
  }
  // Ctrl+F = Focus search (when not in input)
  if ((e.ctrlKey || e.metaKey) && e.key === "f" && activeTab === "all") {
    if (document.activeElement.tagName !== "INPUT" && document.activeElement.tagName !== "TEXTAREA") {
      e.preventDefault();
      $("searchInput").focus();
      $("searchInput").select();
    }
  }
});

init();
</script>
</body>
</html>
"""

# ─────────────────────────────────────────────────────────────
# LAUNCH
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("Starting EVI Daily Task Log — http://localhost:5050")
    app.run(host="127.0.0.1", port=5050, debug=False)
