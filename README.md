# 美国本土文化音频定时推群

每日抓取美区热点（社会 / 科技 / 影视 / 音乐 / 八卦），按 40+ 眼睛产品线视角写成口语简报，转成可播放音频，并在每天固定时间推到飞书群。

## 准备

1. Python 3.11+
2. 安装 [ffmpeg](https://ffmpeg.org/download.html) 并加入 PATH（飞书语音必须转成 opus）
3. 安装依赖：

```bat
pip install -r requirements.txt
```

4. 复制 `.env.example` 为 `.env` 并填写：

- `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL`：任意 OpenAI 兼容接口
- `FEISHU_APP_ID` / `FEISHU_APP_SECRET`：飞书自建应用，开通 `im:message`、`im:resource`，机器人拉进目标群
- `FEISHU_CHAT_IDS`：群 ID，多个群用英文逗号分隔

查群 ID：

```bat
python -m us_culture chats
```

定时点在 `config.yaml` 的 `schedule`（默认北京时间每天 08:00）。

## 命令

```bat
python -m us_culture fetch
python -m us_culture run
python -m us_culture run --skip-push --play
python -m us_culture play
python -m us_culture serve
```

`serve` 会同时打开语音播放台（默认 http://127.0.0.1:8787 ）和每日定时任务。Windows 也可以双击 `scripts\serve.bat`，或把 `scripts\run-once.bat` 交给系统计划任务。
