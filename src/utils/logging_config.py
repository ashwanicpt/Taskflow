import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOG_DIRECTORY = Path(__file__).resolve().parents[2] / "logs"
LOG_FILE = LOG_DIRECTORY / "application.log"
LOG_BACKUP_COUNT = 5
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_PATTERN = re.compile(r"^(.*?) \| (DEBUG|INFO|WARNING|ERROR|CRITICAL) \| ([^|]+) \| (.*)$")
LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def configure_application_logging():
    LOG_DIRECTORY.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S%z")

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    file_handler = next(
        (handler for handler in root_logger.handlers if getattr(handler, "_taskflow_log_file", False)),
        None,
    )
    if file_handler is None:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=2 * 1024 * 1024,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler._taskflow_log_file = True
        root_logger.addHandler(file_handler)

    for logger_name in ("uvicorn.error", "uvicorn.access"):
        server_logger = logging.getLogger(logger_name)
        if not any(getattr(handler, "_taskflow_log_file", False) for handler in server_logger.handlers):
            server_logger.addHandler(file_handler)
        server_logger.setLevel(logging.INFO)
        server_logger.propagate = False


def read_application_logs(level="ALL", search="", limit=100, offset=0):
    entries = []
    log_paths = [
        *(LOG_DIRECTORY / f"{LOG_FILE.name}.{index}" for index in range(LOG_BACKUP_COUNT, 0, -1)),
        LOG_FILE,
    ]

    for path in log_paths:
        if not path.is_file():
            continue
        with path.open("r", encoding="utf-8", errors="replace") as log_file:
            for line in log_file:
                line = line.rstrip("\r\n")
                match = LOG_PATTERN.match(line)
                if match:
                    entries.append({
                        "timestamp": match.group(1),
                        "level": match.group(2),
                        "logger": match.group(3).strip(),
                        "message": match.group(4),
                    })
                elif entries:
                    entries[-1]["message"] += f"\n{line}"
                else:
                    entries.append({
                        "timestamp": "",
                        "level": "INFO",
                        "logger": "application",
                        "message": line,
                    })

    selected_level = level.upper()
    search_text = search.casefold()
    filtered_entries = [
        entry for entry in entries
        if (selected_level == "ALL" or entry["level"] == selected_level)
        and (not search_text or search_text in " ".join(entry.values()).casefold())
    ]
    total_entries = len(filtered_entries)
    page_end = total_entries - offset
    page_start = max(0, page_end - limit)
    page_entries = list(reversed(filtered_entries[page_start:page_end]))
    return page_entries, total_entries
