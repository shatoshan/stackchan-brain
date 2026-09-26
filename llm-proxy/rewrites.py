"""xiaozhi-server が LLM に渡す中国語の固定文言 → 日本語の置換表。

llm-proxy が使い、scripts/check_upstream_strings.py がイメージ更新時に「置換対象がまだ存在するか」を検査する。
文言は xiaozhi-server のイメージ（docker-compose.yml の tag）に依存する。イメージを上げたら必ず検査すること。
"""

# xiaozhi-server server_0.9.6 が差し込む中国語の固定文言 → 日本語。完全一致のみ置換する。
# 出典: core/connection.py _inject_tool_call_fewshot、core/handle/textHandler/listenMessageHandler.py
REWRITES = {
    "给我讲个故事吧": "お話を聞かせて",
    "好呀，你想听什么类型的呀？童话、冒险还是搞笑的？选一个我给你开讲~": "いいよ、どんなお話がいい？昔話、冒険、おもしろい話から選んでね。",
    "已直接回复": "直接返答しました",
    "拜拜": "バイバイ",
    "再见，下次再聊~": "またね、また話そうね。",
    "退出意图已处理": "終了処理をしました",
    "嘿，你好呀": "スタックチャン、こんにちは",
}

# 文中に埋め込まれる中国語の固定指示 → 日本語（部分置換）。
# 出典: core/providers/vllm/openai.py（画像説明の質問末尾に「(请使用中文回复)」を固定で付ける。結果はそのまま読み上げられる）
SUBSTRING_REWRITES = {
    "(请使用中文回复)": "（日本語で、1〜2文の短い話し言葉で答えてください）",
}

# 置換対象の出典（検査スクリプトが、この文言がイメージ内のどのファイルにあるべきかを知るため）
SOURCES = {
    "给我讲个故事吧": "core/connection.py",
    "好呀，你想听什么类型的呀？童话、冒险还是搞笑的？选一个我给你开讲~": "core/connection.py",
    "已直接回复": "core/connection.py",
    "拜拜": "core/connection.py",
    "再见，下次再聊~": "core/connection.py",
    "退出意图已处理": "core/connection.py",
    "嘿，你好呀": "core/handle/textHandler/listenMessageHandler.py",
    "(请使用中文回复)": "core/providers/vllm/openai.py",
}
# few-shot の tool_call id の接頭辞（core/connection.py _inject_tool_call_fewshot）
FEWSHOT_ID_PREFIX = "fewshot_"
