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
<title>EVI Daily Task Log</title>
<style>
  :root {
    --navy: #1F3864; --blue: #2E75B6; --ltblue: #DEEAF1;
    --pale: #EBF3FB; --orange: #FF6600; --green: #27AE60;
    --red: #C0392B; --warn-bg: #FFF2CC; --green-bg: #E2EFDA;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: Arial, sans-serif; background: #f4f6f9; color: #333; }

  /* Banner */
  .banner { background: var(--navy); color: #fff; text-align: center;
            padding: 14px 0; font-size: 22px; font-weight: bold; letter-spacing: 1px; }

  .container { max-width: 1200px; margin: 0 auto; padding: 16px; }

  /* Form area */
  .form-section { display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }

  /* Calendar card */
  .cal-card { background: var(--ltblue); border: 2px solid var(--blue);
              border-radius: 8px; padding: 16px; min-width: 280px; }
  .cal-card h3 { color: var(--navy); margin-bottom: 10px; text-align: center; }
  input[type="date"] { width: 100%; padding: 10px; font-size: 16px; border: 2px solid var(--blue);
                       border-radius: 6px; background: #fff; color: var(--navy); }
  .date-display { display: flex; gap: 8px; margin-top: 10px; }
  .date-display .date-val { background: var(--orange); color: #fff; padding: 6px 14px;
                             border-radius: 4px; font-weight: bold; font-size: 14px; }
  .date-display .day-val  { background: var(--navy); color: #fff; padding: 6px 14px;
                             border-radius: 4px; font-weight: bold; font-size: 14px; flex: 1; text-align: center; }

  /* Details card */
  .details-card { flex: 1; background: #fff; border: 2px solid var(--blue);
                  border-radius: 8px; padding: 16px; min-width: 400px; }
  .details-card h3 { color: var(--navy); margin-bottom: 12px; }

  .form-row { display: flex; align-items: flex-start; margin-bottom: 10px; gap: 8px; }
  .form-row label { background: var(--blue); color: #fff; padding: 8px 12px;
                    border-radius: 4px; font-weight: bold; font-size: 13px;
                    min-width: 110px; text-align: center; white-space: nowrap; }
  .form-row input[type="text"], .form-row textarea {
    flex: 1; padding: 8px 10px; font-size: 14px; border: 1px solid #ccc;
    border-radius: 4px; background: var(--pale); color: var(--navy); font-family: Arial; }
  .form-row textarea { resize: vertical; min-height: 50px; }

  /* Radio group */
  .radio-group { display: flex; flex-wrap: wrap; gap: 6px; flex: 1; align-items: center; }
  .radio-group label { background: transparent; color: var(--navy); min-width: auto;
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
                                     border: 1px solid #ccc; border-radius: 4px; }
  .record-count { background: var(--green-bg); color: #375623; padding: 6px 14px;
                  border-radius: 4px; font-weight: bold; font-size: 13px; margin-left: auto; }

  /* Table */
  .table-wrap { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  thead th { background: var(--blue); color: #fff; padding: 10px 8px;
             text-align: center; font-weight: bold; position: sticky; top: 0; }
  tbody td { padding: 8px; border-bottom: 1px solid #e0e0e0; }
  tbody tr:nth-child(even) { background: var(--ltblue); }
  tbody tr:nth-child(odd)  { background: #fff; }
  tbody tr:hover { background: #d4e6f1; }
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
  .modal { background:#fff; border-radius:10px; max-width:900px; width:100%;
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

  .ai-summary-box { background: linear-gradient(135deg, #1F3864 0%, #2E75B6 100%);
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
  .day-tasks { border:1px solid #ddd; border-top:none; border-radius:0 0 6px 6px; }
  .day-task-row { display:flex; padding:8px 16px; font-size:13px; border-bottom:1px solid #eee;
                  align-items:flex-start; gap:12px; }
  .day-task-row:last-child { border-bottom:none; }
  .day-task-row:nth-child(even) { background:var(--pale); }
  .task-loc { background:var(--navy); color:#fff; padding:2px 10px; border-radius:3px;
              font-size:12px; font-weight:bold; white-space:nowrap; }
  .task-dc { background:var(--orange); color:#fff; padding:2px 8px; border-radius:3px;
             font-size:11px; font-weight:bold; white-space:nowrap; }
  .task-desc { flex:1; color:#333; }
  .task-info { color:#888; font-size:12px; font-style:italic; max-width:200px; }

  @media print {
    body * { visibility: hidden; }
    .modal, .modal * { visibility: visible; }
    .modal { position:absolute; left:0; top:0; width:100%; box-shadow:none; }
    .modal-close, .modal-actions { display:none !important; }
  }
</style>
</head>
<body>

<div class="banner">EVI DAILY TASK LOG &mdash; Datacenter EVI01</div>

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
        <button class="btn btn-save" onclick="saveEntry()">SAVE ENTRY</button>
        <button class="btn btn-clear" onclick="clearForm()">CLEAR FORM</button>
      </div>
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
    <span style="margin-left:16px; font-weight:bold; color:var(--navy);">Week #:</span>
    <input type="number" id="weekNum" min="1" max="53">
    <span style="font-weight:bold; color:var(--navy);">Year:</span>
    <input type="number" id="yearNum" min="2020" max="2035">
    <span class="record-count" id="recordCount"></span>
  </div>

  <!-- TABLE -->
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
  const start = new Date(d.getFullYear(), 0, 1);
  const diff = (d - start + (start.getTimezoneOffset() - d.getTimezoneOffset()) * 60000);
  return Math.floor(diff / 604800000);
}

function getLocation() {
  const checked = document.querySelector('input[name="location"]:checked');
  return checked ? checked.value : "DH1";
}

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
    recallAll();
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
    recallAll();
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
  const radio = document.getElementById("edit-loc-" + loc);
  if (radio) radio.checked = true;
  $("editTitle").textContent = "EDIT RECORD #" + r.id;
  $("editModal").classList.add("open");
}

async function submitEdit() {
  const id = $("editId").value;
  const desc = $("editDescription").value.trim();
  if (!desc) { toast("Description is required.", "error"); $("editDescription").focus(); return; }
  const locRadio = document.querySelector('input[name="editLocation"]:checked');
  const body = {
    entry_date: $("editDate").value,
    description: desc,
    location: locRadio ? locRadio.value : "DH1",
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
    recallAll();
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
