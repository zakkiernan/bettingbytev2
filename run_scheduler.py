from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

from ingestion.scheduler import start_scheduler

log_dir = Path(__file__).resolve().parent / "logs"
log_dir.mkdir(exist_ok=True)
log_path = log_dir / "scheduler_runner.log"
pid_path = log_dir / "scheduler_runner.pid"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.FileHandler(log_path, encoding="utf-8")],
)


def main() -> int:
    pid_path.write_text(str(os.getpid()), encoding="utf-8")
    scheduler = start_scheduler()
    logging.getLogger(__name__).info("Scheduler runner active")

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Scheduler runner interrupted")
    except BaseException:
        logging.getLogger(__name__).exception("Scheduler runner crashed")
        raise
    finally:
        try:
            scheduler.shutdown(wait=False)
        except BaseException:
            logging.getLogger(__name__).exception("Scheduler shutdown failed")
        try:
            if pid_path.exists() and pid_path.read_text(encoding="utf-8").strip() == str(os.getpid()):
                pid_path.unlink()
        except BaseException:
            logging.getLogger(__name__).exception("Scheduler pid cleanup failed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
