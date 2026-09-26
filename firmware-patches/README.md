# firmware-patches

StackChan 公式ファーム（m5stack/StackChan）に当てる stackchan-brain 独自のパッチ。
方針と範囲は `okf/decisions/009-firmware-proximity-wake.md`、手順は `okf/runbooks/firmware-flash.md`。

| パッチ | 内容 |
|---|---|
| `0001-proximity-wake.patch` | **不採用（参考として保存）**。近接センサで会話を開く案。センサが数 cm しか検知できず使わない（決定 009） |

当て方（StackChan リポジトリのルートで。対象コミット 1b5765599fba8aaad1811d9a79358ccc7051f5f3）:

```bash
git -C ~/esp/StackChan apply /path/to/stackchan-brain/firmware-patches/0001-proximity-wake.patch
cd ~/esp/StackChan/firmware && idf.py reconfigure && idf.py build   # 新規ファイルを拾うため reconfigure が必要
```
