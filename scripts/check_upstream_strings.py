"""llm-proxy の置換対象（xiaozhi-server が差し込む中国語の固定文言）が、使用中の xiaozhi-server イメージにまだ存在するか検査する。

xiaozhi-server のイメージ tag を上げたら必ず実行する。見つからない文言があれば終了コード 1。

    python3 scripts/check_upstream_strings.py
"""
import importlib.util
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("rewrites", ROOT / "llm-proxy" / "rewrites.py")
rewrites = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rewrites)

compose = (ROOT / "docker-compose.yml").read_text()
image = re.search(r"image:\s*(ghcr\.io/xinnan-tech/xiaozhi-esp32-server:\S+)", compose).group(1)

checker = r'''
import json, sys, pathlib
targets = json.loads(sys.argv[1])
base = pathlib.Path("/opt/xiaozhi-esp32-server")
result = {}
for text, rel in targets.items():
    p = base / rel
    result[text] = p.exists() and text in p.read_text(encoding="utf-8")
print(json.dumps(result, ensure_ascii=False))
'''
targets = dict(rewrites.SOURCES)
targets[rewrites.FEWSHOT_ID_PREFIX] = "core/connection.py"
out = subprocess.run(["docker", "run", "--rm", "--entrypoint", "python", image, "-c", checker, json.dumps(targets, ensure_ascii=False)],
                     capture_output=True, text=True, check=True).stdout
found = json.loads(out)
missing = [t for t, ok in found.items() if not ok]
print(f"image: {image}")
for t, ok in found.items():
    print(f"  {'OK     ' if ok else 'MISSING'} {targets[t]}: {t}")
if missing:
    print(f"{len(missing)} 件の置換対象が見つからない。llm-proxy/rewrites.py を更新すること", file=sys.stderr)
    sys.exit(1)
