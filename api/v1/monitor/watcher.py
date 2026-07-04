from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class FileChange:
    filepath: str
    status: str
    lines_added: int = 0
    lines_removed: int = 0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    @property
    def extension(self) -> str:
        ext = Path(self.filepath).suffix.lower()
        return ext if ext else "(无扩展名)"

    @property
    def status_label(self) -> str:
        return {"M": "modified", "A": "added", "D": "deleted",
                "R": "renamed", "??": "untracked"}.get(self.status.strip(), self.status)


class GitMonitor:
    def __init__(self, repo_path: Optional[str] = None, poll_interval: float = 2.0):
        self.repo_path = repo_path or os.getcwd()
        self.poll_interval = poll_interval
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self.start_time: Optional[datetime] = None

        self.total_files_changed: int = 0
        self.total_lines_added: int = 0
        self.total_lines_removed: int = 0

        self.changes: list[FileChange] = []
        self.timeline: list[dict] = []
        self._prev_status: dict[str, str] = {}

        self._git_available = self._check_git()
        self.start()

    def _check_git(self) -> bool:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True, text=True, cwd=self.repo_path, timeout=3,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _run_git(self, args: list[str]) -> str:
        try:
            result = subprocess.run(
                ["git"] + args,
                capture_output=True, text=True, cwd=self.repo_path, timeout=5,
            )
            return result.stdout
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""

    def _current_status(self) -> dict[str, str]:
        output = self._run_git(["status", "--porcelain"])
        if not output.strip():
            return {}
        result = {}
        for line in output.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            status = line[:2].strip()
            filepath = line[3:].strip()
            if " -> " in filepath:
                filepath = filepath.split(" -> ")[1]
            result[filepath] = status
        return result

    def _parse_diff_stat(self) -> tuple[int, int]:
        added = 0
        removed = 0
        for args in (["diff", "--stat"], ["diff", "--cached", "--stat"]):
            output = self._run_git(args)
            if not output.strip():
                continue
            for line in output.strip().split("\n"):
                m = re.search(r"(\d+)\s+insertion", line)
                if m:
                    added += int(m.group(1))
                m = re.search(r"(\d+)\s+deletion", line)
                if m:
                    removed += int(m.group(1))
        return added, removed

    def _poll_loop(self):
        self._seed_initial()
        while self._running:
            try:
                self._poll_once()
            except Exception:
                pass
            time.sleep(self.poll_interval)

    def _poll_once(self):
        current_status = self._current_status()

        with self._lock:
            prev_keys = set(self._prev_status.keys())
            curr_keys = set(current_status.keys())

            new_files = curr_keys - prev_keys
            modified_files = {
                f for f in curr_keys & prev_keys
                if current_status[f] != self._prev_status[f]
            }
            changed_files = new_files | modified_files

            total_added, total_removed = self._parse_diff_stat()

            if changed_files:
                now_iso = datetime.now(timezone.utc).isoformat()

                for filepath in changed_files:
                    status = current_status[filepath]
                    change = FileChange(
                        filepath=filepath,
                        status=status,
                        lines_added=total_added,
                        lines_removed=total_removed,
                        timestamp=now_iso,
                    )
                    self.changes.append(change)
                    if len(self.changes) > 2000:
                        self.changes = self.changes[-1000:]

                self.total_files_changed += len(changed_files)
                self.total_lines_added = total_added
                self.total_lines_removed = total_removed

                self.timeline.append({
                    "timestamp": now_iso,
                    "cumulative_files": self.total_files_changed,
                    "cumulative_lines_added": total_added,
                    "cumulative_lines_removed": total_removed,
                })
                if len(self.timeline) > 1000:
                    self.timeline = self.timeline[-500:]

            self._prev_status = current_status

    def start(self):
        if self._running or not self._git_available:
            return
        self._running = True
        self.start_time = datetime.now(timezone.utc)
        self._prev_status = {}
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def _seed_initial(self):
        """Record all currently changed files as the initial data point."""
        current_status = self._current_status()
        if not current_status:
            return
        with self._lock:
            total_added, total_removed = self._parse_diff_stat()
            now_iso = datetime.now(timezone.utc).isoformat()
            for filepath, status in current_status.items():
                change = FileChange(
                    filepath=filepath,
                    status=status,
                    lines_added=total_added,
                    lines_removed=total_removed,
                    timestamp=now_iso,
                )
                self.changes.append(change)

            self.total_files_changed = len(current_status)
            self.total_lines_added = total_added
            self.total_lines_removed = total_removed

            self.timeline.append({
                "timestamp": now_iso,
                "cumulative_files": self.total_files_changed,
                "cumulative_lines_added": total_added,
                "cumulative_lines_removed": total_removed,
            })

            self._prev_status = current_status

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None

    @property
    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> dict:
        fresh_added, fresh_removed = self._parse_diff_stat()
        with self._lock:
            if fresh_added or fresh_removed:
                self.total_lines_added = fresh_added
                self.total_lines_removed = fresh_removed

            duration = (
                (datetime.now(timezone.utc) - self.start_time).total_seconds()
                if self.start_time else 0
            )
            total = self.total_lines_added + self.total_lines_removed
            velocity = round(total / (duration / 60), 1) if duration > 0 else 0
            return {
                "git_available": self._git_available,
                "monitoring": self._running,
                "start_time": self.start_time.isoformat() if self.start_time else "",
                "duration_seconds": round(duration, 1),
                "total_files_changed": self.total_files_changed,
                "total_lines_added": self.total_lines_added,
                "total_lines_removed": self.total_lines_removed,
                "change_velocity": velocity,
                "recent_changes_count": len(self.changes),
            }

    def get_changes(self, limit: int = 100) -> list[dict]:
        with self._lock:
            recent = list(reversed(self.changes[-limit:]))
            return [
                {
                    "filepath": c.filepath,
                    "status": c.status,
                    "status_label": c.status_label,
                    "extension": c.extension,
                    "lines_added": c.lines_added,
                    "lines_removed": c.lines_removed,
                    "timestamp": c.timestamp,
                }
                for c in recent
            ]

    def get_timeline(self) -> list[dict]:
        with self._lock:
            return list(self.timeline)

    def get_file_type_distribution(self) -> list[dict]:
        with self._lock:
            ext_counter: Counter = Counter()
            for c in self.changes:
                ext_counter[c.extension] += 1
            total = sum(ext_counter.values()) or 1
            return [
                {"extension": ext, "count": count, "percentage": round(count / total * 100, 1)}
                for ext, count in ext_counter.most_common()
            ]

    def get_most_changed_files(self, top_n: int = 10) -> list[dict]:
        with self._lock:
            file_counter: Counter = Counter(c.filepath for c in self.changes)
            total = sum(file_counter.values()) or 1
            return [
                {"filepath": filepath, "change_count": count,
                 "percentage": round(count / total * 100, 1)}
                for filepath, count in file_counter.most_common(top_n)
            ]


_monitor: Optional[GitMonitor] = None


def get_monitor() -> GitMonitor:
    global _monitor
    if _monitor is None:
        _monitor = GitMonitor()
    return _monitor
