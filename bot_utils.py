import discord
import traceback
import random
import requests
import string

import db

from datetime import datetime
from discord.ext import commands
from discord_slash import SlashContext

VALID_NOTIFY_STATUS = [discord.Status.offline]

AVATAR_CDN_URL = "https://cdn.discordapp.com/avatars/{}/{}.png"

def quote_each_line(msg):
    return "\n".join(f"> {line}" for line in msg.split('\n'))

class utils:
    def __init__(self, bot: commands.Bot, database: db.database, logger):
        self.database = database
        self.bot = bot
        self.logger = logger
        self.admin = None

    def inject_admin(self, admin):
        self.admin = admin

    async def _get_msg_chain(self, original_msg: discord.Message, max_depth = None):
        current = original_msg
        chain = [current]
        while current.reference is not None:
            ref = current.reference.resolved
            if ref is None:
                fetched = await original_msg.channel.fetch_message(current.reference.message_id)
                if fetched is None:
                    chain += [None]
                    break
                ref = fetched
            current = ref
            chain += [current]
            if max_depth is not None:
                max_depth -= 1
                if max_depth <= 0:
                    break
        return chain

    async def _format_msg_chain(self, user: discord.User, original_msg: discord.Message, max_size: int = 1500):
        msg_chain = await self._get_msg_chain(original_msg)
        msg_fmt = quote_each_line(msg_chain[0].content).replace(user.mention, user.display_name) + "\n"
        for message in msg_chain[1:]:
            if message is None:
                new_line = "As a reply to an unknown message\n"
            else:
                try:
                    _sender = "you" if (user.id == message.author.id) else f"{message.author.mention}"
                    new_line = f"As a reply to a message {_sender} sent:\n{quote_each_line(message.content).replace(user.mention, user.display_name)}\n"
                except Exception as e:
                    new_line = f"As a reply to a deleted message\n"
                    self.logger.warning(f"Error while trying to get message contents: {e}\n{traceback.format_exc()}")
            if len(msg_fmt + new_line) > max_size:
                self.logger.debug(f"Trimming message size ({len(msg_fmt + new_line)})")
                msg_fmt += "[...]"
                break
            msg_fmt += new_line
        return msg_fmt.replace(user.mention, user.display_name)

    async def _dm_user(self, msg: str, user):
        try:
            # user = self.bot.get_user(user_id)
            dm_chan = user.dm_channel or await user.create_dm()
            
            # self.logger.debug(f"[_dm_user] Trying to send notification to {user_id}")
            # self.logger.debug(f"[_dm_user] [{msg}]")
            return await dm_chan.send(content=msg)
        except discord.Forbidden as e:
            self.logger.info(f"Forbidden from sending message to user {user.id}")
        except Exception as e:
            self.logger.error(f"Error while trying to dm user: {e}\n{traceback.format_exc()}")

    async def handle_offline_mentions(self, msg: discord.Message):
        # if msg.author.bot: return
        if msg.channel.type == discord.ChannelType.private: return
        for member in msg.mentions:
            will_send = member.status in VALID_NOTIFY_STATUS and not self.database.is_in_offline_ping_blocklist(member.id)
            # self.logger.debug(f"[handle_offline_mentions] User {member} status = {member.status} // will_send = {will_send}")
            if not will_send: continue
            fmt_msg_chain = await self._format_msg_chain(member, msg)

            if msg.author.bot: # TODO after update to discord.py 2.0, check if there is a msg.interaction to find out original user who used command
                content = f"Hi {member.name}! {self._bot_name(msg.author)} pinged you in {msg.channel.name} while you were offline:\n{fmt_msg_chain}\n"
            else:
                content = f"Hi {member.name}! {msg.author.mention} pinged you in {msg.channel.name} while you were offline:\n{fmt_msg_chain}\n"
            content += "You can disable these notifications with `/offlinepings off` in the server if you want!"
            await self._split_dm(content, member)

    async def get_icon_default(self, **kwargs):
        if "user" not in kwargs: return None
        return await self.get_user_icon(kwargs["user"])

    async def get_user_icon(self, user):
        try:
            self.logger.debug(f"avatar={user.avatar}")
            av_url = AVATAR_CDN_URL.format(user.id, user.avatar)
            icon_name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=20)) + ".png"
            self.logger.debug(f"icon_name={icon_name}")

            file = open(icon_name, "wb")
            file.write(requests.get(av_url).content)
            file.close()

            return icon_name
        except Exception as e:
            self.logger.error(f"Error while trying to get avatar: {e}\n{traceback.format_exc()}")
            return None

    def _get_display_name(self, **kwargs):
        if "user" not in kwargs: return None
        try:
            return kwargs["user"].display_name
        except:
            return None

    def _fallback_get_text(self, **kwargs):
        try:
            return kwargs["user"]
        except:
            return None

    def get_text(self, **kwargs):
        return self._get_display_name(**kwargs) or self._fallback_get_text(**kwargs)

    def to_ord(self, num):
        _num = int(num) % 10
        if _num == 1: return "st"
        if _num == 2: return "nd"
        if _num == 3: return "rd"
        return "th"

    def to_date(self, date: datetime):
        return date.strftime("%B %-d") + self.to_ord(date.day)

    def to_mention(self, user: str):
        return f"<@{user}>"

    def to_podium(self, pos: int):
        if pos == 1: return ":first_place:"
        if pos == 2: return ":second_place:"
        if pos == 3: return ":third_place:"
        return str(pos)

    async def handle_dm(self, msg: discord.Message):
        if msg.channel.type != discord.ChannelType.private: return
        content = f"{msg.author.mention} ({msg.author}) messaged me:\n{quote_each_line(msg.content)}\n"
        await self._split_dm(content, self.admin)

    async def _split_dm(self, content, user):
        msg = await self._dm_user(content[:2000], user)
        content = content[2000:]
        while len(content) > 0:
            msg = await msg.reply(content=content[:2000])
            content = content[2000:]

    def _bot_name(self, bot):
        return "I" if bot.id == self.bot.user.id else bot.mention
        