# EVI Daily Task Log

A lightweight, browser-based daily task logger for datacenter operations at **EVI01**. Runs as a static GitHub Pages site with localStorage + JSON file backend.

## Features

- **Task Logging** — Record daily tasks with date, location (DH1-DH6 + custom), DC code, description, and additional info
- **Weekly View** — Browse tasks week-by-week with prev/next navigation and a "Today" button
- **Weekly Summary** — Modal with AI-generated summary, stats, location breakdown, and day-by-day detail
- **Search & Filter** — Real-time search across all records
- **Stats Dashboard** — At-a-glance counts for today, this week, and all time
- **Inline Edit/Delete** — Edit or delete any record directly from the table
- **Duplicate** — Quick-fill the form from an existing record
- **Export/Import** — CSV export, JSON export/import for backup and transfer
- **Data Persistence** — Records stored in localStorage and seeded from `data.json` in the repo
- **CST Timezone** — All dates and timestamps locked to America/Chicago (CST/CDT)
- **Theme Switcher** — 6 themes: Classic Blue, Dark, Emerald, Sunset, Purple, Steel
- **Keyboard Shortcuts** — Ctrl+S (save), Ctrl+E (export CSV), Ctrl+F (search), Esc (close modals)
- **Print** — Print-friendly weekly summary modal

## Versioning Scheme

Format: **vX.Y.Z**

| Part | When to change | Example |
|------|---------------|---------|
| **X** (Major) | New feature release or stable version | v1.0.0 |
| **Y** (Minor) | Major bug fix or significant improvement | v0.2.0 |
| **Z** (Patch) | Minor bug fix or small tweak | v0.1.2 |

## Version History

### v0.5.0 (2026-04-17)
**New Features:**
- Attachments — insert images and PDFs into any task for more context
- Files stored in IndexedDB (separate from task records) so storage scales to many MBs
- Paperclip thumbnails in All Records table; click to open a full preview modal
- Drag-and-drop or click to add files; 10MB per-file limit; PDFs shown via embedded viewer
- Attachments follow edit/delete: removed with the task, editable from the edit modal

### v0.4.2 (2026-04-17)
**New Features:**
- Added two new themes: Rose (pink/magenta) and Teal (cyan/teal)
- Settings modal now shows 8 theme tiles

### v0.4.1 (2026-04-17)
**New Features:**
- Version badge is now clickable and opens a scrollable Version History modal
- Copy-to-clipboard icon on the weekly AI summary (top-right of the AI SUMMARY box)
- Version badge label changed from Alpha to Beta

### v0.4.0 (2026-04-17)
**New Features:**
- Task Templates — save the current form (location, DC code, description, add. info) as a named preset; one-click load to refill the form
- Bulk Entry — enter multiple descriptions (one per line) with a shared date, location, DC code and add. info; creates N records in one save
- Recurring Tasks — define daily or weekly (pick days) rules that auto-generate records from the start date onward each time the app loads; rules can be paused/resumed

### v0.3.0 (2026-04-15)
**New Features:**
- Auto-complete suggestions for description field based on previous entries
- Highlights matching text in orange, shows up to 8 suggestions
- Click a suggestion to fill the description field instantly

### v0.2.0 (2026-04-15)
**New Features:**
- Auto-detect Jira ticket numbers in descriptions and make them clickable links to CoreWeave Jira
- Supports standard keys (e.g., `DO-103333`) and bare numbers near "Jira"/"Ticket" keywords
- Links appear in All Records table, Weekly View, and Weekly Summary modal

### v0.1.2 (2026-04-15)
**Bug Fixes:**
- Fixed date input text invisible in dark mode (font color matched dark background)

### v0.1.1 (2026-04-15)
**Bug Fixes:**
- Fixed date picker showing wrong day (tomorrow instead of today) due to UTC/local timezone mismatch
- Fixed `toISOString()` returning UTC date instead of local date across all date operations
- Fixed stats dashboard showing incorrect "today" and "this week" counts

**New Features:**
- Added CST (America/Chicago) timezone enforcement for all dates and timestamps
- Added weekly view navigation with Prev/Next buttons and Today shortcut
- Added `data.json` in repo — records auto-load from git file into localStorage on page load
- Renamed "Current Week" tab to "Weekly View" with browse capability

### v0.1.0 (2026-04-13)
**Features:**
- Search and filter across all records
- Export to CSV
- Duplicate record to quickly create similar entries
- Stats dashboard (today, this week, all time)
- Keyboard shortcuts (Ctrl+S, Ctrl+E, Ctrl+F, Esc)
- Import/Export JSON for transferring records between devices

### v0.0.3 (2026-04-12)
**Features:**
- Current Week tab view with day-by-day card layout
- "Others" custom location option

### v0.0.2 (2026-04-11)
**Features:**
- 6-theme switcher (Classic Blue, Dark, Emerald, Sunset, Purple, Steel)
- Inline edit and delete records via modal
- Weekly summary modal with AI-generated insights
- Fixed record ID sequencing

### v0.0.1 (2026-04-10)
**Initial Release:**
- Daily task logging with date, location, DC code, description, and additional info
- GitHub Pages static site with localStorage backend
- Table view with all records
- Clipboard favicon for browser tab identity

## Setup

The app runs entirely in the browser. To use:

1. Visit the GitHub Pages URL, or
2. Open `docs/index.html` locally

Records are stored in the browser's localStorage. The `docs/data.json` file provides seed data that auto-merges on first load.

## Tech Stack

- Single-file HTML/CSS/JavaScript (no build step, no dependencies)
- localStorage for data persistence
- GitHub Pages for hosting
