import logging

import colorlog
import sys

from compliance_agent import execute
from compliance_agent.api import create_app

app = create_app(agent=type("Agent", (), {"execute": execute}))


def setup_logging():
    handler = colorlog.StreamHandler(sys.stdout)

    # %(log_color)s affects the level (INFO, WARNING, etc.)
    # %(cyan)s or other colors can be hardcoded for specific parts
    formatter = colorlog.ColoredFormatter(
        fmt="%(white)s%(asctime)s %(log_color)s[%(levelname)s] %(cyan)s%(name)s%(reset)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            'DEBUG': 'thin_cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'bold_red',
        }
    )

    handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


setup_logging()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
