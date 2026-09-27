# firmware-patches

StackChan 公式ファーム（m5stack/StackChan）に当てる stackchan-brain 独自のパッチ。
方針と範囲は `okf/decisions/010-firmware-silent-shutter.md`（原則2の例外）と `okf/decisions/012-firmware-always-on-session.md`、手順は `okf/runbooks/firmware-flash.md`。

| パッチ | 内容 |
|---|---|
| `0002-silent-camera-shutter.patch` | **適用中**。撮影時のシャッター音を鳴らさない（在席確認で定期的に撮るため、決定 010） |
| `0003-always-on-session.patch` | **適用中**。AI Agent の待機が 10 秒続いたら会話を開き、MCP 通知で brain に知らせる（常時セッション、決定 012）。新規ファイルを足すので `idf.py reconfigure` が必要 |
| `0001-proximity-wake.patch` | **不採用（参考として保存）**。近接センサで会話を開く案。センサが数 cm しか検知できず使わない（決定 009） |

当て方（StackChan リポジトリのルートで。対象コミット 1b5765599fba8aaad1811d9a79358ccc7051f5f3）。適用中のものだけ当てる:

```bash
git -C ~/esp/StackChan apply /path/to/stackchan-brain/firmware-patches/0002-silent-camera-shutter.patch
git -C ~/esp/StackChan apply /path/to/stackchan-brain/firmware-patches/0003-always-on-session.patch
cd ~/esp/StackChan/firmware && idf.py reconfigure && idf.py build && idf.py -p /dev/cu.usbmodem101 app-flash
```

新しいファイルを足すパッチの場合は、ビルド前に `idf.py reconfigure` が必要（CMake のファイル一覧が構成時に固定されるため）。
