import subprocess
import sys
from pathlib import Path
from datetime import datetime
import json
import re

# =========================
# Set paths
# =========================
if getattr(sys, "frozen", False):
	BASE_DIR = Path(sys.executable).parent
else:
	BASE_DIR = Path(__file__).parent

TODOS_DIR = BASE_DIR / "todos" / "daily"
CATEGORIES_FILE = BASE_DIR / "categories.json"

TODOS_DIR.mkdir(exist_ok=True)

# =========================
# Load categories
# =========================
DEFAULT_CATEGORIES = ["Please create and update categories.json file in base directory"]

if not CATEGORIES_FILE.exists(): # If categories.json missing, infill with default 
	CATEGORIES_FILE.write_text(json.dumps({"categories": DEFAULT_CATEGORIES}, indent=2), encoding="utf-8")

with CATEGORIES_FILE.open("r", encoding="utf-8") as f: # Update live categories
	categories = json.load(f).get("categories", DEFAULT_CATEGORIES) # NOTE: Stopgap solution, want to prompt user directly if categories is "missing"

# =========================
# Determine today & latest file
# =========================
today_str = datetime.now().strftime("%Y-%m-%d")
today_file = TODOS_DIR / f"todo_{today_str}.txt"

existing_files = sorted(TODOS_DIR.glob("todo_*.txt"))
last_file = existing_files[-1] if existing_files else None

# =========================
# Carrover for unfinished tasks
# =========================
# TASK_PATTERN = re.compile(r"- \[( |x)\] (.*)")
TASK_PATTERN = re.compile(r"- \[(.)\] (.*)") # More permissive

def get_unfinished_tasks(file_path, category):
	"""Unfinished tasks to carry over with persistent category."""
	unfinished = []
	if not file_path or not file_path.exists():
		return unfinished
	current_cat = None
	for line in file_path.read_text(encoding="utf-8").splitlines():
		line = line.strip()
		if line.startswith("## "):
			current_cat = line[3:].strip()
			continue
		match = TASK_PATTERN.match(line)
		if match and current_cat == category:
			if match.group(1) == " ":
				unfinished.append(match.group(2))
	return unfinished

def get_orphaned_tasks(file_path, known_categories):
	"""Unfinished tasks whose category no longer exists."""
	orphaned = []
	if not file_path or not file_path.exists():
		return orphaned
	current_cat = None
	for line in file_path.read_text(encoding="utf-8").splitlines():
		line = line.strip()
		if line.startswith("## "):
			current_cat = line[3:].strip()
			continue
		match = TASK_PATTERN.match(line)
		if match and current_cat not in known_categories:
			if match.group(1) == " ":
				orphaned.append(f"[{current_cat}] {match.group(2)}")
	return orphaned

# =========================
# Check and create today's file if not found
# =========================
if not today_file.exists():
	lines = []
	for cat in categories:
		lines.append(f"## {cat}") # Start section
		lines.append("- [ ] ") # Add one empty checkbox
		if last_file: # Carry over unfinished tasks from previous day(s)
			for task_text in get_unfinished_tasks(last_file, cat):
				lines.append(f"- [ ] {task_text}")
		lines.append("")  # Add empty line after category
  
	orphans = get_orphaned_tasks(last_file, set(categories)) if last_file else []
	if orphans:
		lines.append("## Orphaned")
		for task_text in orphans:
			lines.append(f"- [ ] {task_text}")
		lines.append("")
		
	# Write today's file
	today_file.write_text("\n".join(lines), encoding="utf-8")

# =========================
# Open today's file
# =========================
subprocess.Popen(["notepad.exe", str(today_file)])
