from __future__ import annotations

import os
import sys


def read_linux_status_kib(field_name: str) -> int | None:
    try:
        with open("/proc/self/status", "r", encoding="utf-8") as handle:
            for raw_line in handle:
                if not raw_line.startswith(f"{field_name}:"):
                    continue
                parts = raw_line.split()
                if len(parts) >= 2:
                    return int(parts[1])
    except Exception:
        return None
    return None


def get_process_rss_kib() -> int | None:
    if os.name == "posix":
        current_rss = read_linux_status_kib("VmRSS")
        if current_rss is not None:
            return current_rss
    return get_process_peak_rss_kib()


def get_process_peak_rss_kib() -> int | None:
    try:
        import resource
    except Exception:
        resource = None

    if os.name == "posix":
        peak_rss = read_linux_status_kib("VmHWM")
        if peak_rss is not None:
            return peak_rss
    if resource is None:
        return None
    try:
        rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    except Exception:
        return None
    if sys.platform == "darwin":
        rss //= 1024
    return rss
