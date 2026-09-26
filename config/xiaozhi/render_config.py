"""config.template.yaml の ${VAR} を環境変数で展開して data/.config.yaml を書く。

xiaozhi-esp32-server は設定ファイル内の環境変数を展開しないため、
秘密情報を .env だけに置く目的でコンテナ起動時に実行する（本体は改変しない）。
"""

import os
import re
import sys

TEMPLATE = os.environ.get("XIAOZHI_CONFIG_TEMPLATE", "/opt/stackchan/config.template.yaml")
OUTPUT = os.environ.get("XIAOZHI_CONFIG_OUTPUT", "/opt/xiaozhi-esp32-server/data/.config.yaml")
PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def main() -> int:
    with open(TEMPLATE, encoding="utf-8") as f:
        text = f.read()

    missing = sorted({name for name in PATTERN.findall(text) if not os.environ.get(name)})
    if missing:
        print(f"render_config: missing env vars: {', '.join(missing)}", file=sys.stderr)
        return 1

    rendered = PATTERN.sub(lambda m: os.environ[m.group(1)], text)
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    fd = os.open(OUTPUT, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(rendered)
    print(f"render_config: wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
