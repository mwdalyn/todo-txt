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

	TODOS_DIR.mkdir(parents=True, exist_ok=True)

	# =========================
	# Load categories
	# =========================
	EXAMPLE_CATEGORIES = {
		"_comment": "List your todo categories below, in the order you want them to appear. Delete this comment line when done.",
		"categories": ["Social", "Health", "Professional"]
	}

	if not CATEGORIES_FILE.exists():
		CATEGORIES_FILE.write_text(json.dumps(EXAMPLE_CATEGORIES, indent=2), encoding="utf-8")
		print(f"No categories.json found — created an example at {CATEGORIES_FILE}. "
		      f"Edit it with your real categories, then re-run this script.")
		sys.exit(0)

	with CATEGORIES_FILE.open("r", encoding="utf-8") as f:
		try:
			categories = json.load(f)["categories"]
		except (json.JSONDecodeError, KeyError):
			print(f"categories.json at {CATEGORIES_FILE} is malformed or missing a 'categories' key. "
			      f"Expected format: {json.dumps({'categories': ['Example1', 'Example2']})}")
			sys.exit(1)
	
	# =========================
	# Load recurring tasks
	# =========================
	RECURRING_FILE = BASE_DIR / "recurring.json"

	if not RECURRING_FILE.exists():
		EXAMPLE_RECURRING = {
			"_comment": "List recurring task text under each category exactly as it's spelled in categories.json. Delete this comment line when done.",
			**{cat: [] for cat in categories}
		}
		EXAMPLE_RECURRING[categories[0]] = ["Example recurring task"]  # one filled-in sample to show the shape
		RECURRING_FILE.write_text(json.dumps(EXAMPLE_RECURRING, indent=2), encoding="utf-8")
		print(f"No recurring.json found — created an example at {RECURRING_FILE}. "
		      f"Edit it with your real recurring tasks, then re-run this script.")
		sys.exit(0)

	with RECURRING_FILE.open("r", encoding="utf-8") as f:
		try:
			recurring = json.load(f)
			recurring.pop("_comment", None)  # ignore the comment key if present
		except json.JSONDecodeError:
			print(f"recurring.json at {RECURRING_FILE} is malformed. "
			      f"Expected format: {{\"CategoryName\": [\"task 1\", \"task 2\"]}}")
			sys.exit(1)

	# =========================
	# Load streaks
	# =========================
	STREAKS_FILE = BASE_DIR / "streaks.json"

	if not STREAKS_FILE.exists():
		STREAKS_FILE.write_text(json.dumps({}), encoding="utf-8")

	with STREAKS_FILE.open("r", encoding="utf-8") as f:
		streaks = json.load(f)  # {"category": {"task text": streak_count}}

	# =========================
	# Determine today & latest file
	# =========================
	today_str = datetime.now().strftime("%Y-%m-%d")
	today_file = TODOS_DIR / f"todo_{today_str}.txt"

	existing_files = sorted(TODOS_DIR.glob("todo_*.txt"))
	last_file = existing_files[-1] if existing_files else None

	# =========================
	# Cleanup protocol for zero days
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

	def was_task_completed(file_path, category, task_text):
		"""Checks if a specific task (exact text match) was checked off in a given file."""
		if not file_path or not file_path.exists():
			return False
		current_cat = None
		for line in file_path.read_text(encoding="utf-8").splitlines():
			line = line.strip()
			if line.startswith("## "):
				current_cat = line[3:].strip()
				continue
			match = TASK_PATTERN.match(line)
			if match and current_cat == category:
				state, text = match.group(2), match.group(3).strip()
				if text == task_text and state != " ":
					return True
		return False


	def update_streaks(streaks, last_file, categories, recurring):
		for cat in categories:
			for task_text in recurring.get(cat, []):
				cat_streaks = streaks.setdefault(cat, {})
				if was_task_completed(last_file, cat, task_text):
					cat_streaks[task_text] = cat_streaks.get(task_text, 0) + 1
				else:
					cat_streaks[task_text] = 0
		return streaks

	# =========================
	# Check and create today's file if not found
	# =========================
	if not today_file.exists():
		# Update streaks quickly
		streaks = update_streaks(streaks, last_file, categories, recurring)
		STREAKS_FILE.write_text(json.dumps(streaks, indent=2), encoding="utf-8")  
		# Create and populate today's file
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
	
		# Quickly cleanup stale days before writing new file
		cleanup_stale_days()

		# Write today's file
		today_file.write_text("\n".join(lines), encoding="utf-8")
 
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