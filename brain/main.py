"""brain のエントリポイント。中継（8010）、操作 API（8011）、写真の受け口（8012）、判定ループを起動する。"""

import asyncio
import logging
import os
from pathlib import Path

from aiohttp import web

from judge import Judge
from relay import create_app, create_control_app
from vision import create_vision_app


async def serve() -> None:
    relay_app = create_app()
    control_app = create_control_app(relay_app["relay"])
    if os.environ.get("BRAIN_JUDGE_ENABLED", "1") == "1":
        judge = Judge(relay_app["relay"], Path(os.environ.get("BRAIN_JUDGMENT_DIR", "/data/judgments")))
        control_app.on_startup.append(judge.start)
        control_app.on_cleanup.append(judge.stop)
    vision_app = create_vision_app(relay_app["relay"], Path(os.environ.get("BRAIN_CAMERA_DIR", "/data/camera")))
    runners = []
    for app, port in ((relay_app, int(os.environ.get("BRAIN_PORT", "8010"))),
                      (control_app, int(os.environ.get("BRAIN_CONTROL_PORT", "8011"))),
                      (vision_app, int(os.environ.get("BRAIN_VISION_PORT", "8012")))):
        runner = web.AppRunner(app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", port).start()
        runners.append(runner)
    try:
        await asyncio.Event().wait()
    finally:
        for runner in runners:
            await runner.cleanup()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    asyncio.run(serve())


if __name__ == "__main__":
    main()
