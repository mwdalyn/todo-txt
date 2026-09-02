import subprocess
import sys
from pathlib import Path
from datetime import datetime
import re
import traceback

# =========================
# Set paths
# =========================
if getattr(sys, "frozen", False):
	BASE_DIR = Path(sys.executable).parent
else:
	BASE_DIR = Path(__file__).parent

MEETINGNOTES_DIR = BASE_DIR / "meetings"

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]')


def get_next_default_name(date_str):
	"""Finds the next available 'meeting-N' name for today based on existing files."""
	pattern = re.compile(rf"^{re.escape(date_str)}-meeting-(\d+)\.txt$")
	existing_nums = []
	for f in MEETINGNOTES_DIR.glob(f"{date_str}-meeting-*.txt"):
		match = pattern.match(f.name)
		if match:
			existing_nums.append(int(match.group(1)))
	next_num = max(existing_nums, default=0) + 1
	return f"meeting-{next_num}"


def main():
	MEETINGNOTES_DIR.mkdir(parents=True, exist_ok=True)

	now = datetime.now()
	date_str = now.strftime("%Y-%m-%d")
	default_name = get_next_default_name(date_str)

	meeting_name = input(f"Enter meeting name (default: {default_name}): ").strip() or default_name

	safe_name = INVALID_FILENAME_CHARS.sub("", meeting_name).strip()
	filename = f"{date_str}-{safe_name}.txt"
	notes_file = MEETINGNOTES_DIR / filename

	if not notes_file.exists():
		time_str = now.strftime("%H:%M")

		lines = [
			f"# {meeting_name}",
			f"Date: {date_str}",
			f"Time: {time_str}",
			"",
			"",
			"",
			"",
			"## Next Steps",
			"- [ ] ",
			"",
		]
		notes_file.write_text("\n".join(lines), encoding="utf-8")

	subprocess.Popen(["notepad.exe", str(notes_file)])


if __name__ == "__main__":
	try:
		main()
	except Exception:
		error_log = BASE_DIR / "error.log"
		with error_log.open("a", encoding="utf-8") as f:
			f.write(f"\n[{datetime.now().isoformat()}]\n")
			f.write(traceback.format_exc())