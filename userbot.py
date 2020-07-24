#!/usr/bin/env python3

"""telegram userbot."""

import configparser
import io
from collections import defaultdict
from datetime import datetime, timedelta

import aiocron
import jieba
from dateutil.relativedelta import relativedelta
from dateutil.tz import tzlocal
from telethon import TelegramClient, events, utils, hints, errors
from wordcloud import WordCloud

config = configparser.ConfigParser()
config.read("config.ini")
if "SteamedFish" in config:
    api_id = config["SteamedFish"]["api_id"]
    api_hash = config["SteamedFish"]["api_hash"]
if "emacs-china" in config:
    bot_token = config["emacs-china"]["token"]

userbot = TelegramClient("SteamedFish", api_id, api_hash).start()
rssbot = TelegramClient("rssbot", api_id, api_hash).start(bot_token=bot_token)

with open("StopWords-simple.txt", mode="r", encoding="utf-8") as file:
    stop_words = set(file.read().splitlines())


async def generate_word_cloud(
    channel: hints.EntityLike,
    from_user: hints.EntityLike,
    from_time: datetime,
    end_time: datetime,
):
    """生成词云."""
    words = defaultdict(int)

    if isinstance(channel, str):
        # 转换成 entity 才能有更多方法
        channel = await userbot.get_entity(channel)

    async for msg in userbot.iter_messages(
        channel, from_user=from_user, offset_date=end_time
    ):
        if msg.date < from_time:
            break
        fromuser = await userbot.get_entity(msg.from_id)
        if fromuser.is_self and msg.text.endswith("的消息词云"):
            # 忽略之前自己发送的词云消息
            continue
        if fromuser.bot:
            # ignore messages from bot
            continue
        if msg.text:
            for word in jieba.cut(msg.text):
                if word.lower() not in stop_words:
                    words[word.lower()] += 1

    if words:
        image = (
            WordCloud(
                font_path="/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
                width=800,
                height=400,
            )
            .generate_from_frequencies(words)
            .to_image()
        )
        stream = io.BytesIO()
        image.save(stream, "PNG")

    await userbot.send_message(
        channel,
        f"{utils.get_display_name(channel)} 频道 "
        f"{'' if from_user is None else utils.get_display_name(from_user)}"
        f" 从 {from_time.isoformat(sep=' ',timespec='seconds')} 到 "
        f"{end_time.isoformat(sep=' ',timespec='seconds')} 的消息词云",
        file=(stream.getvalue() if words else None),
    )


@rssbot.on(events.NewMessage(pattern="/start"))
async def start(event):
    """Send a message when the command /start is issued."""
    await event.respond("不许瞎撩 bot!")
    raise events.StopPropagation


@userbot.on(events.NewMessage(pattern="/wordcloud"))
async def generate_word_cloud_from_event(event) -> None:
    """generate word cloud based on event."""
    msg = event.message
    if (not msg.text) or (not msg.text.lower().startswith("/wordcloud")):
        return
    to_chat = await event.get_chat()

    _, *rest = msg.text.lower().split(" ")

    if len(rest) > 1 and rest[1] == "full":
        # 生成所有用户的词云
        user = None
    elif msg.is_reply:
        # 生成被回复用户的
        reply = await msg.get_reply_message()
        user = await reply.get_sender()
    else:
        # 生成发送者的
        user = await msg.get_sender()

    if not rest:
        days = "1"
    else:
        days = rest[0]

    try:
        days = int(days)
    except ValueError:
        days = 1

    await generate_word_cloud(
        to_chat,
        user,
        datetime.now(tzlocal()) - timedelta(days=days),
        datetime.now(tzlocal()),
    )


@aiocron.crontab("0 0 * * *")
async def generate_word_cloud_for_channels_daily() -> None:
    channels = ["@emacs_zh", "@keyboard_cn"]
    from_time = datetime.now(tzlocal()) - timedelta(days=1)
    end_time = datetime.now(tzlocal())
    for channel in channels:
        await generate_word_cloud(channel, None, from_time, end_time)


@aiocron.crontab("0 0 * * 1")
async def generate_word_cloud_for_channels_weekly() -> None:
    channels = ["@emacs_zh", "@keyboard_cn"]
    from_time = datetime.now(tzlocal()) - timedelta(weeks=1)
    end_time = datetime.now(tzlocal())
    for channel in channels:
        await generate_word_cloud(channel, None, from_time, end_time)


@aiocron.crontab("0 0 1 * *")
async def generate_word_cloud_for_channels_monthly() -> None:
    channels = ["@emacs_zh", "@keyboard_cn"]
    from_time = datetime.now(tzlocal()) - relativedelta(months=1)
    end_time = datetime.now(tzlocal())
    for channel in channels:
        await generate_word_cloud(channel, None, from_time, end_time)


@aiocron.crontab("0 0 1 1 *")
async def generate_word_cloud_for_channels_yealy() -> None:
    channels = ["@emacs_zh", "@keyboard_cn"]
    from_time = datetime.now(tzlocal()) - relativedelta(years=1)
    end_time = datetime.now(tzlocal())
    for channel in channels:
        await generate_word_cloud(channel, None, from_time, end_time)


@userbot.on(events.ChatAction(chats="@emacszh"))
async def remove_join_messages(event) -> None:
    """remove messages of join."""
    if event.user_joined:
        await event.delete()


@aiocron.crontab("* 2 * * *")
async def remove_deleted_account(channel: str = "@emacszh") -> None:
    """remove all deleted account from channel everyday."""
    async for user in userbot.iter_participants(channel):
        if user.deleted:
            try:
                await userbot.kick_participant(channel, user)
            except errors.rpcerrorlist.UserAdminInvalidError:
                # 群主踢不掉
                pass


def main():
    userbot.run_until_disconnected()


if __name__ == "__main__":
    main()
