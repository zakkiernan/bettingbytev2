from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

from ingestion.scheduler import start_scheduler

log_dir = Path(__file__).resolve().parent / "logs"
log_dir.mkdir(exist_ok=True)
log_path = log_dir / "scheduler_runner.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.FileHandler(log_path, encoding="utf-8")],
)


def main() -> int:
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

    return 0


if __name__ == "__main__":
    sys.exit(main())
