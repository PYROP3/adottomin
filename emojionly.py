import discord
import emoji
import re

import botlogger
import db

from discord.ext import commands
#emoji_prog = re.compile(r"^((<a?:[^:]+:[0-9]+>)|(:[^: ]+:)|([ \n]))+$")

class emojionly_handler:
    def __init__(self, bot: commands.Bot, database: db.database, emojichat_id: int, allow_regional_indicators: bool=False):
        self.database = database
        self.bot = bot
        self.emojichat = None
        self.emojichat_id = emojichat_id

        self.logger = botlogger.get_logger(__name__)

        valid_substrings = [
            r"<a?:[^:]+:[0-9]+>",
            r":[^: ]+:",
            r"[ \n]"
        ]
        if allow_regional_indicators:
            valid_substrings += [r"[🇦🇧🇨🇩🇪🇫🇬🇭🇮🇯🇰🇱🇲🇳🇴🇵🇶🇷🇸🇹🇺🇻🇼🇽🇾🇿]"] # Arguably defeats the purpose of an emoji-only chat]
        self.emoji_prog = re.compile("(" + "|".join([f"({s})" for s in valid_substrings]) + ")+")

    async def handle_emoji_chat(self, msg: discord.Message):
        if msg.channel.id != self.emojichat_id: return
        m = self.emoji_prog.fullmatch(emoji.demojize(msg.content))
        if m: 
            # self.logger.debug(f"Message [{msg.content}] contains only emojis")
            return
        # self.logger.debug(f"Message [{msg.content}] contains non-emojis")
        await msg.delete()
        await msg.channel.send(content=f"Hey {msg.author.mention}, emojis only~", delete_after=5)

    async def handle_emoji_chat_edit(self, before: discord.Message, after: discord.Message):
        return await self.handle_emoji_chat(after)
