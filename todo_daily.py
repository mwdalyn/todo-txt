import subprocess
import sys
from pathlib import Path
from datetime import datetime
import json
import re
import traceback

# =========================
# Set paths
# =========================
if getattr(sys, "frozen", False):
	BASE_DIR = Path(sys.executable).parent
else:
	BASE_DIR = Path(__file__).parent

TODOS_DIR = BASE_DIR / "todos" / "daily"
CATEGORIES_FILE = BASE_DIR / "categories.json"

def main():
	# =========================
	# Setup dir
	# =========================

	TODOS_DIR.mkdir(exist_ok=True)

	# =========================
	# Load categories
	# =========================
	DEFAULT_CATEGORIES = ["Please create and update categories.json file in base directory for your todo-app!"]

	if not CATEGORIES_FILE.exists(): # If categories.json missing, infill with default 
		CATEGORIES_FILE.write_text(json.dumps({"categories": DEFAULT_CATEGORIES}, indent=2), encoding="utf-8")

	with CATEGORIES_FILE.open("r", encoding="utf-8") as f: # Update live categories
		categories = json.load(f).get("categories", DEFAULT_CATEGORIES) # NOTE: Stopgap solution, want to prompt user directly if categories is "missing"

	# =========================
	# Load recurring tasks
	# =========================
	RECURRING_FILE = BASE_DIR / "recurring.json"

	if not RECURRING_FILE.exists():
		RECURRING_FILE.write_text(json.dumps({cat: [] for cat in categories}, indent=2), encoding="utf-8")

	with RECURRING_FILE.open("r", encoding="utf-8") as f:
		recurring = json.load(f)

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
	# TASK_PATTERN = re.compile(r"- \[(.)\] (.*)") # More permissive X case formatting
	TASK_PATTERN = re.compile(r"- (!)?\[(.)\] (.*)") # More permissive and allows for urgency marker '- ![ ]'

	def get_unfinished_tasks(file_path, category):
		"""Returns unfinished tasks as list of (is_priority: bool, text: str), priority first."""
		priority_tasks = []
		normal_tasks = []
		if not file_path or not file_path.exists():
			return []
		current_cat = None
		for line in file_path.read_text(encoding="utf-8").splitlines():
			line = line.strip()
			if line.startswith("## "):
				current_cat = line[3:].strip()
				continue
			match = TASK_PATTERN.match(line)
			if match and current_cat == category:
				is_priority, state, text = bool(match.group(1)), match.group(2), match.group(3)
				if state == " ":
					(priority_tasks if is_priority else normal_tasks).append(text)
		return [(True, t) for t in priority_tasks] + [(False, t) for t in normal_tasks]

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
				if match.group(2) == " ": # Updated to account for '!' priority optional tagging
					orphaned.append(f"[{current_cat}] {match.group(3)}")
		return orphaned

	# =========================
	# Check and create today's file if not found
	# =========================
	if not today_file.exists():
		lines = []
		for cat in categories:
			lines.append(f"## {cat}") # Start section
			carried_texts = set()
			if last_file: # Carry over unfinished tasks from previous day(s); include priority
				for is_priority, task_text in get_unfinished_tasks(last_file, cat):
					prefix = "- ![ ] " if is_priority else "- [ ] "
					lines.append(f"{prefix}{task_text}")
					carried_texts.add(task_text)
			for recurring_text in recurring.get(cat, []): # Add recurring tasks, skip if already carried over
				if recurring_text not in carried_texts:
					lines.append(f"- [ ] {recurring_text}")
			lines.append("- [ ] ") # Add one empty checkbox
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
	# Cleanup: remove no-progress days
	# =========================
	def get_all_tasks(file_path):
		"""Returns (list of (category, text) for every task line, has_any_completed: bool)."""
		tasks = []
		has_completed = False
		current_cat = None
		for line in file_path.read_text(encoding="utf-8").splitlines():
			line = line.strip()
			if line.startswith("## "):
				current_cat = line[3:].strip()
				continue
			match = TASK_PATTERN.match(line)
			if match:
				state, text = match.group(2), match.group(3).strip()
				tasks.append((current_cat, text))
				if state != " ":
					has_completed = True
		return tasks, has_completed

	def cleanup_stale_days():
		"""Deletes any day (except the first ever and today) that had zero completions
		and whose task contents exactly match the prior *kept* day — i.e. no progress
		was recorded that day."""
		all_files = sorted(TODOS_DIR.glob("todo_*.txt"))
		if len(all_files) <= 1:
			return  # nothing to compare against

		keep_file = all_files[0]  # first day ever — never eligible for deletion
		keep_tasks, _ = get_all_tasks(keep_file)

		for f in all_files[1:]:
			if f == today_file:
				continue  # never touch today's file, it's still in progress
			tasks, has_completed = get_all_tasks(f)
			if not has_completed and tasks == keep_tasks:
				f.unlink()
				# keep_file/keep_tasks stay as the last *real* day for next comparison
			else:
				keep_file = f
				keep_tasks = tasks

	cleanup_stale_days()
 
	# =========================
	# Open today's file
	# =========================
	subprocess.Popen(["notepad.exe", str(today_file)])

if __name__ == "__main__":
	try:
		main()
	except Exception:
		error_log = BASE_DIR / "error.log"
		with error_log.open("a", encoding="utf-8") as f:
			f.write(f"\n[{datetime.now().isoformat()}]\n")
			f.write(traceback.format_exc())