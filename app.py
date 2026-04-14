"""
EVI Work Log — Web Application
================================
Launch:  python3 app.py
Open:    http://localhost:5050
"""

import sqlite3, os, json, re
from datetime import datetime, date, timedelta
from flask import Flask, render_template_string, request, redirect, url_for, jsonify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE  = os.path.join(BASE_DIR, "worklog.db")

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────
# AI SUMMARY (Anthropic Claude API)
# ─────────────────────────────────────────────────────────────
def get_ai_summary(logs_text, week_num, year):
    """Generate AI summary using Claude. Falls back to smart summary on failure."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None, "No ANTHROPIC_API_KEY set. Using auto-summary."
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{"role": "user", "content": f"""You are a datacenter operations assistant.
Below are the work log entries for Week {week_num}, {year} at Datacenter EVI01.

{logs_text}

Write a concise weekly summary (3-5 sentences) answering:
"What did you focus on this week?"

Requirements:
- Professional tone suitable for a weekly status report
- Mention key locations (DH1-DH6) and types of work done
- Highlight any notable completions or follow-ups needed
- Keep it under 100 words
- Do NOT use bullet points — write it as a flowing paragraph
- Start directly with "This week..." """}]
        )
        return msg.content[0].text.strip(), None
    except Exception as e:
        return None, str(e)

def generate_smart_summary(rows, week_num, year):
    """Rule-based smart summary when AI is unavailable."""
    if not rows:
        return "No work log entries recorded for this week."

    locations = {}
    tasks = []
    dates_set = set()
    for r in rows:
        d = dict(r)
        loc = d["location"] or "Unknown"
        locations[loc] = locations.get(loc, 0) + 1
        dates_set.add(d["entry_date"])
        desc = d["description"] or ""
        # Take first sentence or first 80 chars
        short = desc.split('.')[0].strip()
        if len(short) > 80:
            short = short[:77] + "..."
        tasks.append({"loc": loc, "desc": short, "date": d["entry_date"]})

    total = len(rows)
    num_days = len(dates_set)
    loc_list = sorted(locations.items(), key=lambda x: -x[1])
    loc_str = ", ".join(f"{loc} ({cnt})" for loc, cnt in loc_list)

    # Build key activities list (up to 5)
    key_acts = []
    seen = set()
    for t in tasks:
        if t["desc"] and t["desc"] not in seen:
            key_acts.append(f"{t['desc']} ({t['loc']})")
            seen.add(t["desc"])
        if len(key_acts) >= 5:
            break

    summary = f"This week (Week {week_num}, {year}) I focused on datacenter operations at EVI01, "
    summary += f"completing {total} task{'s' if total != 1 else ''} across {num_days} day{'s' if num_days != 1 else ''}. "
    summary += f"Work was distributed across: {loc_str}. "
    summary += "Key activities included: " + "; ".join(key_acts) + ". "

    if any("follow" in (dict(r).get("add_info") or "").lower() or
           "update" in (dict(r).get("add_info") or "").lower() or
           "pending" in (dict(r).get("add_info") or "").lower()
           for r in rows):
        summary += "Some tasks have follow-up items pending for the next week."

    return summary

# ─────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS worklog (
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
        db.commit()
        count = db.execute("SELECT COUNT(*) FROM worklog").fetchone()[0]
        if count == 0:
            samples = [
                ("2026-04-06", "Monday",    "Replaced faulty PDU breaker on rack A-14; tested all circuits OK.",    "DH3", "EVI01", "Completed without downtime",       14, 2026),
                ("2026-04-06", "Monday",    "Monthly visual inspection of racks B1-B20.",                           "DH1", "EVI01", "No issues found",                   14, 2026),
                ("2026-04-07", "Tuesday",   "Installed 2x new UPS units in Row C.",                                "DH5", "EVI01", "Requires firmware update next shift",14, 2026),
                ("2026-04-07", "Tuesday",   "Network cabling audit on DH2 top-of-rack switches.",                  "DH2", "EVI01", "3 loose cables re-seated",          14, 2026),
                ("2026-04-08", "Wednesday", "Cooling unit PM — cleaned filters, checked airflow.",                  "DH4", "EVI01", "All readings normal",               14, 2026),
            ]
            db.executemany("""
                INSERT INTO worklog (entry_date, day_name, description, location, dc_code, add_info, week_number, year)
                VALUES (?,?,?,?,?,?,?,?)
            """, samples)
            db.commit()

# ─────────────────────────────────────────────────────────────
# HTML TEMPLATE
# ─────────────────────────────────────────────────────────────
HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EVI Work Log — EVI01</title>
<style>
  /* ══════════════════════════════════════════════════════════ */
  /* THEME SYSTEM — Light / Dark / System                      */
  /* ══════════════════════════════════════════════════════════ */

  /* ── LIGHT MODE (default) ─────────────────────────────── */
  :root, [data-theme="light"] {
    --accent:     #2E75B6;
    --accent-dk:  #1F3864;
    --accent-lt:  #DEEAF1;
    --accent-bg:  #EBF3FB;
    --bg-body:    #F0F4F8;
    --bg-card:    #FFFFFF;
    --bg-input:   #EBF3FB;
    --bg-table-even: #DEEAF1;
    --bg-table-hover: #C8DDF0;
    --text:       #1F3864;
    --text-sec:   #595959;
    --text-inv:   #FFFFFF;
    --border:     #DEEAF1;
    --orange:     #FF6600;
    --green:      #27AE60;
    --red:        #C0392B;
    --warn-bg:    #FFF2CC;
    --warn-fg:    #7D6608;
    --ok-bg:      #E2EFDA;
    --ok-fg:      #375623;
    --shadow:     rgba(0,0,0,0.08);
    --shadow-lg:  rgba(0,0,0,0.15);
    --radius:     8px;
    --cal-icon-filter: invert(27%) sepia(79%) saturate(1200%) hue-rotate(195deg);
  }

  /* ── DARK MODE ────────────────────────────────────────── */
  [data-theme="dark"] {
    --accent:     #4A9BE8;
    --accent-dk:  #1A2740;
    --accent-lt:  #1E3250;
    --accent-bg:  #162335;
    --bg-body:    #0D1B2A;
    --bg-card:    #14253A;
    --bg-input:   #1B3048;
    --bg-table-even: #162335;
    --bg-table-hover: #1E3A56;
    --text:       #D4E4F7;
    --text-sec:   #8BA3BF;
    --text-inv:   #FFFFFF;
    --border:     #1E3250;
    --orange:     #E8780A;
    --green:      #2ECC71;
    --red:        #E74C3C;
    --warn-bg:    #3D3200;
    --warn-fg:    #F0D060;
    --ok-bg:      #1A3320;
    --ok-fg:      #7DDE8F;
    --shadow:     rgba(0,0,0,0.3);
    --shadow-lg:  rgba(0,0,0,0.5);
    --cal-icon-filter: invert(60%) sepia(60%) saturate(600%) hue-rotate(180deg) brightness(1.2);
  }

  /* ── SYSTEM PREFERENCE (auto) ─────────────────────────── */
  @media (prefers-color-scheme: dark) {
    [data-theme="system"] {
      --accent:     #4A9BE8;
      --accent-dk:  #1A2740;
      --accent-lt:  #1E3250;
      --accent-bg:  #162335;
      --bg-body:    #0D1B2A;
      --bg-card:    #14253A;
      --bg-input:   #1B3048;
      --bg-table-even: #162335;
      --bg-table-hover: #1E3A56;
      --text:       #D4E4F7;
      --text-sec:   #8BA3BF;
      --text-inv:   #FFFFFF;
      --border:     #1E3250;
      --orange:     #E8780A;
      --green:      #2ECC71;
      --red:        #E74C3C;
      --warn-bg:    #3D3200;
      --warn-fg:    #F0D060;
      --ok-bg:      #1A3320;
      --ok-fg:      #7DDE8F;
      --shadow:     rgba(0,0,0,0.3);
      --shadow-lg:  rgba(0,0,0,0.5);
      --cal-icon-filter: invert(60%) sepia(60%) saturate(600%) hue-rotate(180deg) brightness(1.2);
    }
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: 'Segoe UI', Arial, sans-serif;
    background: var(--bg-body); color: var(--text);
    transition: background 0.3s, color 0.3s;
  }

  /* ── BANNER ─────────────────────────────────────────── */
  .banner {
    background: linear-gradient(135deg, var(--accent-dk), var(--accent));
    color: var(--text-inv); text-align: center;
    padding: 14px 20px; font-size: 24px; font-weight: 700;
    letter-spacing: 1px;
    box-shadow: 0 3px 12px var(--shadow-lg);
    display: flex; align-items: center; justify-content: center;
    position: relative;
  }
  .banner-text { flex: 1; }
  .banner small { font-size: 13px; font-weight: 400; opacity: 0.8; display: block; margin-top: 2px; }

  /* ── SETTINGS GEAR ──────────────────────────────────── */
  .settings-btn {
    background: none; border: none; cursor: pointer;
    font-size: 22px; color: var(--text-inv); opacity: 0.8;
    padding: 6px 10px; border-radius: 50%;
    transition: all 0.2s; position: relative;
  }
  .settings-btn:hover { opacity: 1; background: rgba(255,255,255,0.15); transform: rotate(30deg); }

  /* ── SETTINGS PANEL ─────────────────────────────────── */
  .settings-panel {
    display: none; position: absolute; top: 60px; right: 16px;
    background: var(--bg-card); border: 2px solid var(--accent);
    border-radius: var(--radius); padding: 20px;
    box-shadow: 0 8px 30px var(--shadow-lg);
    z-index: 1000; min-width: 310px; color: var(--text);
  }
  .settings-panel.open { display: block; }
  .settings-panel h3 {
    font-size: 14px; font-weight: 700; text-transform: uppercase;
    color: var(--accent); margin-bottom: 12px; letter-spacing: 0.5px;
    border-bottom: 2px solid var(--border); padding-bottom: 6px;
  }
  .settings-panel h4 {
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    color: var(--text-sec); margin: 14px 0 8px 0; letter-spacing: 0.5px;
  }

  /* Theme toggle buttons */
  .theme-toggles { display: flex; gap: 6px; }
  .theme-btn {
    flex: 1; padding: 10px 8px; border: 2px solid var(--border);
    border-radius: 6px; cursor: pointer; font-size: 12px;
    font-weight: 700; text-align: center; background: var(--bg-input);
    color: var(--text); transition: all 0.2s;
  }
  .theme-btn:hover { border-color: var(--accent); }
  .theme-btn.active {
    background: var(--accent); color: var(--text-inv);
    border-color: var(--accent); box-shadow: 0 2px 8px var(--shadow);
  }
  .theme-btn span { display: block; font-size: 18px; margin-bottom: 3px; }

  /* Accent color picker */
  .color-options { display: flex; gap: 8px; flex-wrap: wrap; }
  .color-swatch {
    width: 36px; height: 36px; border-radius: 50%; cursor: pointer;
    border: 3px solid transparent; transition: all 0.2s;
    box-shadow: 0 2px 6px var(--shadow);
  }
  .color-swatch:hover { transform: scale(1.15); }
  .color-swatch.active { border-color: var(--text); transform: scale(1.15); }

  /* Font size control */
  .font-size-ctrl { display: flex; align-items: center; gap: 8px; }
  .font-size-ctrl button {
    width: 32px; height: 32px; border-radius: 6px;
    border: 2px solid var(--border); background: var(--bg-input);
    color: var(--text); font-weight: 700; font-size: 16px;
    cursor: pointer; transition: 0.2s;
  }
  .font-size-ctrl button:hover { background: var(--accent); color: white; border-color: var(--accent); }
  .font-size-ctrl span { font-size: 13px; font-weight: 600; min-width: 40px; text-align: center; }

  /* ── CONTAINER ──────────────────────────────────────── */
  .container { max-width: 1200px; margin: 0 auto; padding: 16px; }

  /* ── FORM CARD ──────────────────────────────────────── */
  .form-card {
    background: var(--bg-card); border-radius: var(--radius);
    box-shadow: 0 2px 10px var(--shadow);
    padding: 24px; margin-bottom: 16px;
    transition: background 0.3s, box-shadow 0.3s;
  }
  .form-title {
    font-size: 15px; font-weight: 700; color: var(--text-inv);
    background: var(--accent); display: inline-block;
    padding: 6px 18px; border-radius: var(--radius) var(--radius) 0 0;
    margin: -24px -24px 20px -24px; width: calc(100% + 48px);
    text-align: center; letter-spacing: 0.5px;
  }

  /* ── FORM GRID ──────────────────────────────────────── */
  .form-row {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 16px; margin-bottom: 16px;
  }
  .form-row.full { grid-template-columns: 1fr; }
  .form-group { display: flex; flex-direction: column; }
  .form-group label {
    font-size: 11px; font-weight: 700; text-transform: uppercase;
    color: var(--accent); margin-bottom: 5px; letter-spacing: 0.5px;
  }
  .form-group input[type="date"],
  .form-group input[type="text"],
  .form-group textarea,
  .form-group select {
    padding: 10px 12px; border: 2px solid var(--border);
    border-radius: 6px; font-size: 14px; font-family: inherit;
    background: var(--bg-input); color: var(--text); transition: 0.2s;
  }
  .form-group input:focus, .form-group textarea:focus, .form-group select:focus {
    border-color: var(--accent); outline: none;
    box-shadow: 0 0 0 3px rgba(46,117,182,0.15);
  }
  .form-group textarea { resize: vertical; min-height: 60px; }

  /* ── DATE INPUT ─────────────────────────────────────── */
  input[type="date"] { cursor: pointer; font-weight: 600; font-size: 15px; }
  input[type="date"]::-webkit-calendar-picker-indicator {
    cursor: pointer; font-size: 18px; filter: var(--cal-icon-filter);
  }
  .day-badge {
    display: inline-block; margin-top: 6px;
    padding: 4px 14px; border-radius: 20px;
    background: var(--orange); color: white;
    font-weight: 700; font-size: 13px; text-align: center;
  }

  /* ── LOCATION RADIO BUTTONS ─────────────────────────── */
  .loc-grid { display: flex; gap: 6px; flex-wrap: wrap; }
  .loc-grid input[type="radio"] { display: none; }
  .loc-grid label {
    padding: 10px 18px; border-radius: 6px; cursor: pointer;
    border: 2px solid var(--border); background: var(--bg-card);
    font-weight: 700; font-size: 14px; color: var(--text);
    transition: all 0.2s; text-align: center; min-width: 60px;
  }
  .loc-grid input:checked + label {
    background: var(--accent); color: var(--text-inv);
    border-color: var(--accent); box-shadow: 0 2px 8px var(--shadow);
    transform: scale(1.05);
  }
  .loc-grid label:hover { border-color: var(--accent); background: var(--accent-lt); }

  /* ── BUTTONS ────────────────────────────────────────── */
  .btn-row { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
  .btn {
    padding: 12px 28px; border: none; border-radius: 6px;
    font-size: 14px; font-weight: 700; cursor: pointer;
    color: white; transition: all 0.2s; letter-spacing: 0.3px;
  }
  .btn:hover { transform: translateY(-1px); box-shadow: 0 4px 12px var(--shadow-lg); }
  .btn-save   { background: var(--green); }
  .btn-clear  { background: var(--orange); }
  .btn-del    { background: var(--red); }
  .btn-update { background: var(--orange); }
  .btn-cancel { background: #7F8C8D; }

  /* ── RECALL TOOLBAR ─────────────────────────────────── */
  .recall-bar {
    background: var(--accent-dk); border-radius: var(--radius);
    padding: 12px 18px; display: flex; align-items: center;
    gap: 10px; flex-wrap: wrap; margin-bottom: 16px;
  }
  .recall-bar label { color: var(--text-inv); font-size: 12px; font-weight: 700; }
  .recall-bar input, .recall-bar select {
    padding: 6px 10px; border-radius: 4px; border: 1px solid var(--accent);
    font-size: 13px; background: var(--bg-input); color: var(--text);
  }
  .btn-recall {
    padding: 8px 16px; border: none; border-radius: 4px;
    font-size: 12px; font-weight: 700; cursor: pointer;
    color: white; background: var(--accent); transition: 0.2s;
  }
  .btn-recall:hover { background: var(--orange); }
  .badge {
    padding: 4px 12px; border-radius: 20px;
    font-size: 12px; font-weight: 700;
    background: var(--ok-bg); color: var(--ok-fg);
    margin-left: auto;
  }

  /* ── TABLE ──────────────────────────────────────────── */
  .table-wrap {
    background: var(--bg-card); border-radius: var(--radius);
    box-shadow: 0 2px 10px var(--shadow); overflow: auto;
    transition: background 0.3s;
  }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th {
    background: var(--accent); color: var(--text-inv);
    padding: 10px 12px; text-align: center; font-weight: 700;
    position: sticky; top: 0; z-index: 1;
    white-space: nowrap; font-size: 12px; text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  td {
    padding: 9px 12px; border-bottom: 1px solid var(--border);
    text-align: center; vertical-align: middle; color: var(--text);
  }
  td.desc, td.info { text-align: left; max-width: 300px; }
  tr:nth-child(even) { background: var(--bg-table-even); }
  tr:hover { background: var(--bg-table-hover); }
  .loc-tag {
    display: inline-block; padding: 2px 10px; border-radius: 12px;
    background: var(--accent); color: var(--text-inv); font-weight: 700; font-size: 12px;
  }
  .edit-link { color: var(--accent); cursor: pointer; font-weight: 700; text-decoration: none; margin-right: 8px; }
  .edit-link:hover { text-decoration: underline; color: var(--orange); }
  .del-link { color: var(--red); cursor: pointer; font-weight: 700; text-decoration: none; }
  .del-link:hover { text-decoration: underline; }

  /* ── EDIT MODE ──────────────────────────────────────── */
  .form-card.editing { border: 3px solid var(--orange); box-shadow: 0 0 20px rgba(255,102,0,0.25); }
  .form-card.editing .form-title { background: var(--orange); }

  /* ── TOAST ──────────────────────────────────────────── */
  .toast {
    position: fixed; top: 20px; right: 20px; z-index: 999;
    padding: 14px 24px; border-radius: 8px; color: white;
    font-weight: 700; font-size: 14px;
    box-shadow: 0 4px 16px var(--shadow-lg);
    animation: slideIn 0.4s ease, fadeOut 0.4s ease 2.6s;
  }
  .toast.success { background: var(--green); }
  .toast.error   { background: var(--red); }
  @keyframes slideIn { from { transform: translateX(100px); opacity: 0; } }
  @keyframes fadeOut  { to   { opacity: 0; transform: translateY(-10px); } }

  /* ── WEEKLY SUMMARY PANEL ─────────────────────────────── */
  .summary-card {
    background: var(--bg-card); border-radius: var(--radius);
    box-shadow: 0 2px 10px var(--shadow);
    margin-bottom: 16px; overflow: hidden;
    transition: background 0.3s;
  }
  .summary-header {
    background: linear-gradient(135deg, var(--accent-dk), var(--accent));
    color: var(--text-inv); padding: 12px 20px;
    display: flex; align-items: center; justify-content: space-between;
    cursor: pointer;
  }
  .summary-header h3 { font-size: 14px; letter-spacing: 0.5px; }
  .summary-header h3 span { font-size: 16px; margin-right: 6px; }
  .summary-controls { display: flex; gap: 8px; align-items: center; }
  .summary-controls select, .summary-controls input {
    padding: 5px 8px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.3);
    background: rgba(255,255,255,0.15); color: white;
    font-size: 12px; font-weight: 600;
  }
  .summary-controls option { color: #333; background: white; }
  .btn-summary {
    padding: 7px 16px; border: none; border-radius: 4px;
    font-size: 12px; font-weight: 700; cursor: pointer;
    transition: 0.2s;
  }
  .btn-ai { background: linear-gradient(135deg, #8B5CF6, #6D28D9); color: white; }
  .btn-ai:hover { transform: scale(1.03); box-shadow: 0 2px 12px rgba(139,92,246,0.4); }
  .btn-auto { background: var(--green); color: white; }
  .btn-auto:hover { transform: scale(1.03); }

  .summary-body { padding: 20px; display: none; }
  .summary-body.open { display: block; }

  .summary-text {
    background: var(--bg-input); border: 2px solid var(--border);
    border-radius: 8px; padding: 16px 20px;
    font-size: 14px; line-height: 1.7; color: var(--text);
    min-height: 60px; white-space: pre-wrap; position: relative;
  }
  .summary-text.placeholder {
    color: var(--text-sec); font-style: italic;
  }
  .summary-actions { display: flex; gap: 8px; margin-top: 12px; align-items: center; }
  .btn-copy {
    padding: 8px 20px; border: 2px solid var(--accent); border-radius: 6px;
    background: var(--bg-card); color: var(--accent);
    font-weight: 700; font-size: 13px; cursor: pointer; transition: 0.2s;
  }
  .btn-copy:hover { background: var(--accent); color: var(--text-inv); }
  .copy-msg {
    font-size: 12px; font-weight: 600; color: var(--green);
    opacity: 0; transition: opacity 0.3s;
  }
  .copy-msg.show { opacity: 1; }

  .summary-loading {
    display: none; align-items: center; gap: 10px;
    padding: 16px 20px; color: var(--text-sec);
  }
  .summary-loading.active { display: flex; }
  .spinner {
    width: 20px; height: 20px; border: 3px solid var(--border);
    border-top-color: var(--accent); border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .ai-badge {
    display: inline-block; padding: 2px 8px; border-radius: 10px;
    font-size: 10px; font-weight: 700; letter-spacing: 0.5px;
    vertical-align: middle; margin-left: 6px;
  }
  .ai-badge.ai { background: linear-gradient(135deg, #8B5CF6, #6D28D9); color: white; }
  .ai-badge.auto { background: var(--green); color: white; }

  /* ── RESPONSIVE ─────────────────────────────────────── */
  @media (max-width: 768px) {
    .form-row { grid-template-columns: 1fr; }
    .settings-panel { right: 4px; left: 4px; min-width: auto; }
    .summary-header { flex-direction: column; gap: 8px; }
    .summary-controls { flex-wrap: wrap; }
  }
</style>
</head>
<body>

<!-- ════════════════════════════════════════════════════════ -->
<!-- BANNER + SETTINGS GEAR                                  -->
<!-- ════════════════════════════════════════════════════════ -->
<div class="banner">
  <div class="banner-text">
    EVI WORK LOG
    <small>Datacenter EVI01 — Daily Work Record System</small>
  </div>
  <button class="settings-btn" onclick="toggleSettings()" title="Appearance Settings">&#9881;</button>
  <div class="settings-panel" id="settingsPanel">

    <h3>Appearance Settings</h3>

    <!-- Theme Mode -->
    <h4>Theme Mode</h4>
    <div class="theme-toggles">
      <div class="theme-btn" data-theme-val="light"  onclick="setTheme('light')"><span>&#9728;</span>Light</div>
      <div class="theme-btn" data-theme-val="dark"   onclick="setTheme('dark')"><span>&#9790;</span>Dark</div>
      <div class="theme-btn" data-theme-val="system" onclick="setTheme('system')"><span>&#128187;</span>System</div>
    </div>

    <!-- Accent Color -->
    <h4>Accent Color</h4>
    <div class="color-options">
      <div class="color-swatch" style="background:#2E75B6" data-color="blue"    onclick="setAccent('blue')"   title="Blue (Default)"></div>
      <div class="color-swatch" style="background:#7B2D8E" data-color="purple"  onclick="setAccent('purple')" title="Purple"></div>
      <div class="color-swatch" style="background:#217346" data-color="green"   onclick="setAccent('green')"  title="Green"></div>
      <div class="color-swatch" style="background:#C0392B" data-color="red"     onclick="setAccent('red')"    title="Red"></div>
      <div class="color-swatch" style="background:#E67E22" data-color="orange"  onclick="setAccent('orange')" title="Orange"></div>
      <div class="color-swatch" style="background:#1ABC9C" data-color="teal"    onclick="setAccent('teal')"   title="Teal"></div>
      <div class="color-swatch" style="background:#34495E" data-color="slate"   onclick="setAccent('slate')"  title="Slate"></div>
    </div>

    <!-- Font Size -->
    <h4>Font Size</h4>
    <div class="font-size-ctrl">
      <button onclick="changeFontSize(-1)">A-</button>
      <span id="fontSizeLabel">100%</span>
      <button onclick="changeFontSize(+1)">A+</button>
      <button onclick="resetFontSize()" style="font-size:11px;width:auto;padding:0 10px;">Reset</button>
    </div>

  </div>
</div>

<div class="container">

<!-- ════════════════════════════════════════════════════════ -->
<!-- ENTRY FORM                                              -->
<!-- ════════════════════════════════════════════════════════ -->
<div class="form-card {{ 'editing' if edit_record else '' }}" id="formCard">
  <div class="form-title" id="formTitle">{{ 'EDIT RECORD #' ~ edit_record.id if edit_record else 'NEW WORK LOG ENTRY' }}</div>
  <form method="POST" action="{{ '/update/' ~ edit_record.id if edit_record else '/save' }}" id="entryForm">
    <input type="hidden" name="edit_id" value="{{ edit_record.id if edit_record else '' }}">

    <div class="form-row">
      <div class="form-group">
        <label>Date (click to open calendar)</label>
        <input type="date" name="entry_date" id="entryDate"
               value="{{ edit_record.entry_date if edit_record else today }}" required>
        <div class="day-badge" id="dayBadge">{{ edit_record.day_name if edit_record else today_day }}</div>
      </div>
      <div class="form-group">
        <label>Location (Datahall)</label>
        <div class="loc-grid">
          {% set current_loc = edit_record.location if edit_record else 'DH1' %}
          {% set is_other = current_loc not in ["DH1","DH2","DH3","DH4","DH5","DH6"] %}
          {% for dh in ["DH1","DH2","DH3","DH4","DH5","DH6","Others"] %}
          <input type="radio" name="location" id="loc{{ dh }}" value="{{ dh }}"
                 {% if (dh == current_loc) or (dh == "Others" and is_other) %}checked{% endif %}
                 {% if dh == "Others" %}onclick="document.getElementById('otherLoc').style.display='inline-block';document.getElementById('otherLoc').focus()"
                 {% else %}onclick="document.getElementById('otherLoc').style.display='none';document.getElementById('otherLoc').value=''"{% endif %}>
          <label for="loc{{ dh }}">{{ dh }}</label>
          {% endfor %}
          <input type="text" name="other_location" id="otherLoc"
                 placeholder="Specify location..."
                 value="{{ current_loc if is_other else '' }}"
                 style="{{ 'display:inline-block' if is_other else 'display:none' }};padding:8px 12px;border:2px solid var(--accent);border-radius:6px;font-size:13px;width:160px;margin-top:6px;background:var(--bg-input);color:var(--text);">
        </div>
      </div>
      <div class="form-group">
        <label>Datacenter Code</label>
        <input type="text" name="dc_code" value="{{ edit_record.dc_code if edit_record else 'EVI01' }}" placeholder="EVI01">
      </div>
    </div>

    <div class="form-row full">
      <div class="form-group">
        <label>Description</label>
        <textarea name="description" rows="3"
                  placeholder="Describe the work performed..." required>{{ edit_record.description if edit_record else '' }}</textarea>
      </div>
    </div>

    <div class="form-row full">
      <div class="form-group">
        <label>Additional Information (optional)</label>
        <textarea name="add_info" rows="2"
                  placeholder="Notes, follow-ups, observations...">{{ edit_record.add_info if edit_record else '' }}</textarea>
      </div>
    </div>

    <div class="btn-row">
      {% if edit_record %}
      <button type="submit" class="btn btn-update">UPDATE RECORD #{{ edit_record.id }}</button>
      <a href="/" class="btn btn-cancel" style="text-decoration:none;text-align:center;line-height:1;">CANCEL</a>
      {% else %}
      <button type="submit" class="btn btn-save">SAVE ENTRY</button>
      <button type="reset" class="btn btn-clear" onclick="resetDay()">CLEAR FORM</button>
      {% endif %}
    </div>
  </form>
</div>

<!-- ════════════════════════════════════════════════════════ -->
<!-- RECALL TOOLBAR                                          -->
<!-- ════════════════════════════════════════════════════════ -->
<div class="recall-bar">
  <label>RECALL:</label>

  <form method="GET" action="/recall/date" style="display:flex;gap:6px;align-items:center;">
    <input type="date" name="d" value="{{ today }}">
    <button class="btn-recall" type="submit">By Date</button>
  </form>

  <form method="GET" action="/recall/week" style="display:flex;gap:6px;align-items:center;">
    <label>Week</label>
    <input type="number" name="w" value="{{ current_week }}" min="1" max="53" style="width:55px">
    <label>Year</label>
    <input type="number" name="y" value="{{ current_year }}" min="2020" max="2035" style="width:70px">
    <button class="btn-recall" type="submit">By Week</button>
  </form>

  <a href="/" class="btn-recall" style="text-decoration:none;">All Records</a>

  {% if record_count is defined %}
  <span class="badge">{{ record_count }} record(s) found</span>
  {% endif %}
</div>

<!-- ════════════════════════════════════════════════════════ -->
<!-- WEEKLY SUMMARY (AI + Auto)                              -->
<!-- ════════════════════════════════════════════════════════ -->
<div class="summary-card" id="summaryCard">
  <div class="summary-header" onclick="toggleSummary()">
    <h3><span>&#9997;</span> WEEKLY SUMMARY — "What did you focus on this week?"</h3>
    <div class="summary-controls" onclick="event.stopPropagation()">
      <select id="summaryWeek" title="Week number">
        {% for w in range(1, 54) %}
        <option value="{{ w }}" {{ 'selected' if w == current_week else '' }}>Week {{ w }}</option>
        {% endfor %}
      </select>
      <input type="number" id="summaryYear" value="{{ current_year }}" min="2020" max="2035"
             style="width:70px" title="Year">
      <button class="btn-summary btn-ai" onclick="generateSummary('ai')" title="AI-powered summary using Claude">
        &#10024; AI Summary
      </button>
      <button class="btn-summary btn-auto" onclick="generateSummary('auto')" title="Auto-generated summary (no API needed)">
        &#9881; Auto Summary
      </button>
    </div>
  </div>
  <div class="summary-body" id="summaryBody">
    <div class="summary-loading" id="summaryLoading">
      <div class="spinner"></div>
      <span>Generating summary with Claude AI...</span>
    </div>
    <div class="summary-text placeholder" id="summaryText">
      Click "AI Summary" or "Auto Summary" above to generate your weekly focus summary.
      You can then copy-paste it into your status report.
    </div>
    <div class="summary-actions">
      <button class="btn-copy" onclick="copySummary()" id="copyBtn" style="display:none">
        &#128203; Copy to Clipboard
      </button>
      <span class="copy-msg" id="copyMsg">Copied!</span>
    </div>
  </div>
</div>

<!-- ════════════════════════════════════════════════════════ -->
<!-- RECORDS TABLE                                           -->
<!-- ════════════════════════════════════════════════════════ -->
<div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>#</th><th>Date</th><th>Day</th><th>Description</th>
        <th>Location</th><th>DC Code</th><th>Additional Info</th>
        <th>Saved At</th><th>Action</th>
      </tr>
    </thead>
    <tbody>
      {% for r in records %}
      <tr>
        <td>{{ r.id }}</td>
        <td><strong>{{ r.entry_date }}</strong></td>
        <td>{{ r.day_name }}</td>
        <td class="desc">{{ r.description }}</td>
        <td><span class="loc-tag">{{ r.location }}</span></td>
        <td>{{ r.dc_code }}</td>
        <td class="info">{{ r.add_info or '' }}</td>
        <td style="font-size:11px;">{{ r.saved_at }}</td>
        <td>
          <a class="edit-link" href="/edit/{{ r.id }}">Edit</a>
          <a class="del-link" href="/delete/{{ r.id }}"
               onclick="return confirm('Delete record #{{ r.id }}?')">Delete</a>
        </td>
      </tr>
      {% endfor %}
      {% if not records %}
      <tr><td colspan="9" style="padding:30px;color:var(--text-sec);font-style:italic;">
        No records found. Add your first work log entry above.
      </td></tr>
      {% endif %}
    </tbody>
  </table>
</div>

</div> <!-- /container -->

{% if message %}
<div class="toast {{ msg_type }}" id="toast">{{ message }}</div>
<script>setTimeout(()=>document.getElementById('toast').remove(), 3000);</script>
{% endif %}

<script>
  // ═══════════════════════════════════════════════════════
  // DAY NAME AUTO-UPDATE
  // ═══════════════════════════════════════════════════════
  const dateInput = document.getElementById('entryDate');
  const dayBadge  = document.getElementById('dayBadge');
  const days = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  dateInput.addEventListener('change', function() {
    const d = new Date(this.value + 'T00:00:00');
    dayBadge.textContent = days[d.getDay()];
  });
  function resetDay() {
    setTimeout(() => {
      const d = new Date(dateInput.value + 'T00:00:00');
      dayBadge.textContent = days[d.getDay()];
    }, 50);
  }

  // ═══════════════════════════════════════════════════════
  // SETTINGS PANEL
  // ═══════════════════════════════════════════════════════
  function toggleSettings() {
    document.getElementById('settingsPanel').classList.toggle('open');
  }
  // Close panel when clicking outside
  document.addEventListener('click', function(e) {
    const panel = document.getElementById('settingsPanel');
    const btn = document.querySelector('.settings-btn');
    if (!panel.contains(e.target) && !btn.contains(e.target)) {
      panel.classList.remove('open');
    }
  });

  // ═══════════════════════════════════════════════════════
  // THEME MODE: light / dark / system
  // ═══════════════════════════════════════════════════════
  const accentPalettes = {
    blue:   { light: {a:'#2E75B6', dk:'#1F3864', lt:'#DEEAF1', bg:'#EBF3FB'},
              dark:  {a:'#4A9BE8', dk:'#1A2740', lt:'#1E3250', bg:'#162335'} },
    purple: { light: {a:'#7B2D8E', dk:'#4A1259', lt:'#EEDCF4', bg:'#F5EBF9'},
              dark:  {a:'#B06CC8', dk:'#2A1438', lt:'#3A1E4A', bg:'#2A1438'} },
    green:  { light: {a:'#217346', dk:'#0E4429', lt:'#D5EAE0', bg:'#E8F5EE'},
              dark:  {a:'#3CB371', dk:'#0D2818', lt:'#163828', bg:'#112D1F'} },
    red:    { light: {a:'#C0392B', dk:'#7B241C', lt:'#F5D0CC', bg:'#FBEAE8'},
              dark:  {a:'#E74C3C', dk:'#3C1410', lt:'#4A1A15', bg:'#3C1410'} },
    orange: { light: {a:'#D35400', dk:'#873600', lt:'#FAE5CC', bg:'#FDF2E9'},
              dark:  {a:'#E8780A', dk:'#3D2000', lt:'#4A2A0A', bg:'#3D2000'} },
    teal:   { light: {a:'#1ABC9C', dk:'#0E6655', lt:'#D1F2EB', bg:'#E8FAF5'},
              dark:  {a:'#48D1B5', dk:'#0A3028', lt:'#134038', bg:'#0E352D'} },
    slate:  { light: {a:'#34495E', dk:'#1C2833', lt:'#D5D8DC', bg:'#EAECEE'},
              dark:  {a:'#5D788A', dk:'#151D26', lt:'#1E2D3D', bg:'#161F2A'} },
  };

  function setTheme(mode) {
    localStorage.setItem('evi-theme', mode);
    document.documentElement.setAttribute('data-theme', mode);
    updateThemeButtons();
    reapplyAccent();
  }

  function getEffectiveMode() {
    const mode = localStorage.getItem('evi-theme') || 'light';
    if (mode === 'system') {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return mode;
  }

  function updateThemeButtons() {
    const current = localStorage.getItem('evi-theme') || 'light';
    document.querySelectorAll('.theme-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.themeVal === current);
    });
  }

  // ═══════════════════════════════════════════════════════
  // ACCENT COLOR
  // ═══════════════════════════════════════════════════════
  function setAccent(color) {
    localStorage.setItem('evi-accent', color);
    reapplyAccent();
    updateAccentButtons();
  }

  function reapplyAccent() {
    const color = localStorage.getItem('evi-accent') || 'blue';
    const mode = getEffectiveMode();
    const pal = accentPalettes[color];
    if (!pal) return;
    const c = pal[mode] || pal.light;
    const r = document.documentElement.style;
    r.setProperty('--accent',    c.a);
    r.setProperty('--accent-dk', c.dk);
    r.setProperty('--accent-lt', c.lt);
    r.setProperty('--accent-bg', c.bg);
  }

  function updateAccentButtons() {
    const current = localStorage.getItem('evi-accent') || 'blue';
    document.querySelectorAll('.color-swatch').forEach(s => {
      s.classList.toggle('active', s.dataset.color === current);
    });
  }

  // ═══════════════════════════════════════════════════════
  // FONT SIZE
  // ═══════════════════════════════════════════════════════
  let fontScale = parseInt(localStorage.getItem('evi-fontscale') || '100');

  function changeFontSize(dir) {
    fontScale = Math.min(130, Math.max(80, fontScale + dir * 5));
    applyFontSize();
  }
  function resetFontSize() {
    fontScale = 100;
    applyFontSize();
  }
  function applyFontSize() {
    document.documentElement.style.fontSize = fontScale + '%';
    document.getElementById('fontSizeLabel').textContent = fontScale + '%';
    localStorage.setItem('evi-fontscale', fontScale);
  }

  // ═══════════════════════════════════════════════════════
  // WEEKLY SUMMARY
  // ═══════════════════════════════════════════════════════
  function toggleSummary() {
    document.getElementById('summaryBody').classList.toggle('open');
  }
  // Open by default
  document.getElementById('summaryBody').classList.add('open');

  function generateSummary(mode) {
    const week = document.getElementById('summaryWeek').value;
    const year = document.getElementById('summaryYear').value;
    const textEl = document.getElementById('summaryText');
    const loadEl = document.getElementById('summaryLoading');
    const copyBtn = document.getElementById('copyBtn');
    const bodyEl = document.getElementById('summaryBody');

    bodyEl.classList.add('open');
    textEl.style.display = 'none';
    loadEl.classList.add('active');
    loadEl.querySelector('span').textContent =
      mode === 'ai' ? 'Generating summary with Claude AI...' : 'Generating auto summary...';
    copyBtn.style.display = 'none';

    fetch(`/summary?w=${week}&y=${year}&mode=${mode}`)
      .then(r => r.json())
      .then(data => {
        loadEl.classList.remove('active');
        textEl.style.display = 'block';
        textEl.classList.remove('placeholder');

        const badge = data.source === 'ai'
          ? '<span class="ai-badge ai">AI CLAUDE</span>'
          : '<span class="ai-badge auto">AUTO</span>';

        if (data.summary) {
          textEl.innerHTML = data.summary + ' ' + badge;
          if (data.note) {
            textEl.innerHTML += `<br><br><small style="color:var(--text-sec);font-style:italic">${data.note}</small>`;
          }
          copyBtn.style.display = 'inline-block';
        } else {
          textEl.innerHTML = `<span style="color:var(--red)">${data.error || 'Failed to generate summary.'}</span> ${badge}`;
        }
      })
      .catch(err => {
        loadEl.classList.remove('active');
        textEl.style.display = 'block';
        textEl.innerHTML = `<span style="color:var(--red)">Error: ${err.message}</span>`;
      });
  }

  function copySummary() {
    const textEl = document.getElementById('summaryText');
    // Get plain text (strip HTML tags)
    const temp = document.createElement('div');
    temp.innerHTML = textEl.innerHTML;
    // Remove badge and small tags
    temp.querySelectorAll('.ai-badge, small').forEach(el => el.remove());
    const plainText = temp.textContent.trim();

    navigator.clipboard.writeText(plainText).then(() => {
      const msg = document.getElementById('copyMsg');
      msg.classList.add('show');
      setTimeout(() => msg.classList.remove('show'), 2000);
    });
  }

  // ═══════════════════════════════════════════════════════
  // INIT ON LOAD
  // ═══════════════════════════════════════════════════════
  (function init() {
    const theme = localStorage.getItem('evi-theme') || 'light';
    document.documentElement.setAttribute('data-theme', theme);
    updateThemeButtons();
    reapplyAccent();
    updateAccentButtons();
    applyFontSize();
    // Listen for system theme changes
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (localStorage.getItem('evi-theme') === 'system') reapplyAccent();
    });
  })();
</script>

</body>
</html>
"""

# ─────────────────────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM worklog ORDER BY entry_date DESC, saved_at DESC"
        ).fetchall()
    today = date.today()
    return render_template_string(HTML,
        records=rows, today=today.isoformat(),
        today_day=today.strftime("%A"),
        current_week=int(today.strftime("%W")),
        current_year=today.year,
        record_count=len(rows),
        edit_record=None,
        message=request.args.get("msg"),
        msg_type=request.args.get("t", "success"))

@app.route("/save", methods=["POST"])
def save():
    entry_date  = request.form.get("entry_date")
    description = request.form.get("description", "").strip()
    location    = request.form.get("location", "DH1")
    if location == "Others":
        other_loc = request.form.get("other_location", "").strip()
        location = other_loc if other_loc else "Others"
    dc_code     = request.form.get("dc_code", "EVI01").strip() or "EVI01"
    add_info    = request.form.get("add_info", "").strip()

    if not description:
        return redirect(url_for("index", msg="Description is required.", t="error"))

    d = datetime.strptime(entry_date, "%Y-%m-%d").date()
    day_name    = d.strftime("%A")
    week_number = int(d.strftime("%W"))
    year        = d.year

    with get_db() as db:
        db.execute("""
            INSERT INTO worklog (entry_date, day_name, description, location,
                                  dc_code, add_info, week_number, year)
            VALUES (?,?,?,?,?,?,?,?)
        """, (d.isoformat(), day_name, description, location,
              dc_code, add_info, week_number, year))
        db.commit()

    return redirect(url_for("index",
        msg=f"Saved — {d.strftime('%d-%b-%Y')} ({day_name}) | {location} | {dc_code}",
        t="success"))

@app.route("/delete/<int:rid>")
def delete(rid):
    with get_db() as db:
        db.execute("DELETE FROM worklog WHERE id=?", (rid,))
        db.commit()
    return redirect(url_for("index", msg=f"Record #{rid} deleted.", t="error"))

@app.route("/recall/date")
def recall_date():
    target = request.args.get("d", date.today().isoformat())
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM worklog WHERE entry_date=? ORDER BY saved_at",
            (target,)).fetchall()
    today = date.today()
    return render_template_string(HTML,
        records=rows, today=today.isoformat(),
        today_day=today.strftime("%A"),
        current_week=int(today.strftime("%W")),
        current_year=today.year,
        record_count=len(rows),
        edit_record=None,
        message=f"Showing records for {target}",
        msg_type="success")

@app.route("/recall/week")
def recall_week():
    yr = int(request.args.get("y", date.today().year))
    wk = int(request.args.get("w", int(date.today().strftime("%W"))))
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM worklog WHERE year=? AND week_number=? ORDER BY entry_date, saved_at",
            (yr, wk)).fetchall()
    today = date.today()
    return render_template_string(HTML,
        records=rows, today=today.isoformat(),
        today_day=today.strftime("%A"),
        current_week=wk, current_year=yr,
        record_count=len(rows),
        edit_record=None,
        message=f"Showing Week {wk}, Year {yr}",
        msg_type="success")

# ─────────────────────────────────────────────────────────────
# EDIT & UPDATE
# ─────────────────────────────────────────────────────────────
@app.route("/edit/<int:rid>")
def edit(rid):
    with get_db() as db:
        rec = db.execute("SELECT * FROM worklog WHERE id=?", (rid,)).fetchone()
        rows = db.execute(
            "SELECT * FROM worklog ORDER BY entry_date DESC, saved_at DESC"
        ).fetchall()
    if not rec:
        return redirect(url_for("index", msg=f"Record #{rid} not found.", t="error"))
    today = date.today()
    return render_template_string(HTML,
        records=rows, today=today.isoformat(),
        today_day=today.strftime("%A"),
        current_week=int(today.strftime("%W")),
        current_year=today.year,
        record_count=len(rows),
        edit_record=rec,
        message=f"Editing record #{rid} — modify fields above and click Update.",
        msg_type="success")

@app.route("/update/<int:rid>", methods=["POST"])
def update(rid):
    entry_date  = request.form.get("entry_date")
    description = request.form.get("description", "").strip()
    location    = request.form.get("location", "DH1")
    if location == "Others":
        other_loc = request.form.get("other_location", "").strip()
        location = other_loc if other_loc else "Others"
    dc_code     = request.form.get("dc_code", "EVI01").strip() or "EVI01"
    add_info    = request.form.get("add_info", "").strip()

    if not description:
        return redirect(url_for("edit", rid=rid, msg="Description is required.", t="error"))

    d = datetime.strptime(entry_date, "%Y-%m-%d").date()
    day_name    = d.strftime("%A")
    week_number = int(d.strftime("%W"))
    year        = d.year

    with get_db() as db:
        db.execute("""
            UPDATE worklog
            SET entry_date=?, day_name=?, description=?, location=?,
                dc_code=?, add_info=?, week_number=?, year=?
            WHERE id=?
        """, (d.isoformat(), day_name, description, location,
              dc_code, add_info, week_number, year, rid))
        db.commit()

    return redirect(url_for("index",
        msg=f"Record #{rid} updated — {d.strftime('%d-%b-%Y')} | {location}",
        t="success"))

# ─────────────────────────────────────────────────────────────
# WEEKLY SUMMARY API
# ─────────────────────────────────────────────────────────────
@app.route("/summary")
def summary_api():
    yr   = int(request.args.get("y", date.today().year))
    wk   = int(request.args.get("w", int(date.today().strftime("%W"))))
    mode = request.args.get("mode", "auto")

    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM worklog WHERE year=? AND week_number=? ORDER BY entry_date, saved_at",
            (yr, wk)).fetchall()

    if not rows:
        return jsonify({"summary": None, "source": mode,
                        "error": f"No records found for Week {wk}, {yr}. Add some entries first."})

    # Build text log for AI prompt
    logs_text = ""
    for r in rows:
        d = dict(r)
        logs_text += f"- {d['entry_date']} ({d['day_name']}) | {d['location']} | {d['description']}"
        if d.get("add_info"):
            logs_text += f" | Note: {d['add_info']}"
        logs_text += "\n"

    if mode == "ai":
        ai_text, err = get_ai_summary(logs_text, wk, yr)
        if ai_text:
            return jsonify({"summary": ai_text, "source": "ai", "note": None})
        else:
            # Fallback to auto
            auto_text = generate_smart_summary(rows, wk, yr)
            return jsonify({"summary": auto_text, "source": "auto",
                            "note": f"AI unavailable ({err}). Showing auto-generated summary instead."})
    else:
        auto_text = generate_smart_summary(rows, wk, yr)
        return jsonify({"summary": auto_text, "source": "auto", "note": None})

# ─────────────────────────────────────────────────────────────
# LAUNCH
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    print("\n" + "="*55)
    print("  EVI WORK LOG — Web Application")
    print("  Open in browser:  http://localhost:5050")
    print("="*55 + "\n")
    app.run(host="0.0.0.0", port=5050, debug=False)
