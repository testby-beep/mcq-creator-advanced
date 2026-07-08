import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILEPATH = os.path.join(LOG_DIR, "app.log")

# A single rotating file (5 x 1MB backups) instead of a brand new timestamped
# file on every run -- keeps the logs/ folder from growing forever.
_handler = RotatingFileHandler(
    LOG_FILEPATH, maxBytes=1_000_000, backupCount=5, encoding="utf-8"
)
_handler.setFormatter(
    logging.Formatter("[%(asctime)s] %(lineno)d %(name)s - %(levelname)s - %(message)s")
)

logger = logging.getLogger("mcqgenrator")
logger.setLevel(logging.INFO)
if not logger.handlers:
    logger.addHandler(_handler)

# Keep `logging` importable/usable the same way older code expects
# (e.g. `from mcqgenrator.logger import logging`) while avoiding duplicate
# handlers being attached to the root logger.
logging.basicConfig(level=logging.INFO, handlers=[_handler])
