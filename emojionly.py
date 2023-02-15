import discord
import emoji
import re

import botlogger
import db

from discord.ext import commands

emoji_prog = re.compile(r"^((<a?:[^:]+:[0-9]+>)|(:[^: ]+:)|([ \n]))+$")

class emojionly_handler:
    def __init__(self, bot: commands.Bot, database: db.database, emojichat_id: int):
        self.database = database
        self.bot = bot
        self.emojichat = None
        self.emojichat_id = emojichat_id

        self.logger = botlogger.get_logger(__name__)

    # def inject_chat(self, emojichat: discord.TextChannel):
    #     self.emojichat = emojichat

    async def handle_emoji_chat(self, msg: discord.Message):
        if msg.channel.id != self.emojichat_id: return
        m = emoji_prog.search(emoji.demojize(msg.content))
        if m: 
            self.logger.debug(f"Message [{msg.content}] contains only emojis")
            return
        self.logger.debug(f"Message [{msg.content}] contains non-emojis")
        await msg.delete()
        await msg.channel.send(content=f"Hey {msg.author.mention}, emojis only~", delete_after=5)
