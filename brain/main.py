"""brain のエントリポイント。現時点では端末 ⇔ xiaozhi-server の中継だけを起動する。"""

import logging
import os

from aiohttp import web

from relay import create_app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    web.run_app(create_app(), host="0.0.0.0", port=int(os.environ.get("BRAIN_PORT", "8010")), print=None)


if __name__ == "__main__":
    main()
