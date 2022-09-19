import discord
import traceback

import db

from discord.ext import commands

VALID_NOTIFY_STATUS = [discord.Status.offline]

def quote_each_line(msg):
    return "\n".join(f"> {line}" for line in msg.split('\n'))

class utils:
    def __init__(self, bot: commands.Bot, database: db.database, logger):
        self.database = database
        self.bot = bot
        self.logger = logger

    async def _dm_user(self, original_msg: discord.Message, pinger: discord.Member, user_id):
        try:
            user = self.bot.get_user(user_id)
            dm_chan = user.dm_channel or await user.create_dm()
            msg = f"Hi {user.name}! {pinger.mention} pinged you in {original_msg.channel.name} while you were offline:\n{quote_each_line(original_msg.content)}\n"
            if original_msg.reference is not None:
                ref_msg = original_msg.reference.resolved
                if ref_msg is None:
                    msg += f"As a reply to a message\n"
                else:
                    try:
                        _sender = "you" if (user_id == ref_msg.author.id) else "someone else"
                        msg += f"As a reply to a message {_sender} sent:\n{quote_each_line(ref_msg.content)}\n"
                    except Exception as e:
                        msg += f"As a reply to a deleted message\n"
                        self.logger.warning(f"Error while trying to get message contents: {e}\n{traceback.format_exc()}")
                    
            msg += "You can disable these notifications with `/offlinepings off` in the server if you want!"
            self.logger.info(f"[_dm_user] Trying to send notification to {user_id}")
            self.logger.debug(f"[_dm_user] [{msg}]")
            await dm_chan.send(content=msg)
        except discord.Forbidden as e:
            self.logger.warn(f"Forbidden from sending message to user {user_id}")
        except Exception as e:
            self.logger.error(f"Error while trying to dm user: {e}\n{traceback.format_exc()}")

    async def handle_offline_mentions(self, msg: discord.Message):
        for member in msg.mentions:
            will_send = member.status in VALID_NOTIFY_STATUS and not self.database.is_in_offline_ping_blocklist(member.id)
            self.logger.debug(f"[handle_offline_mentions] User {member} status = {member.status} // will_send = {will_send}")
            if will_send:
                await self._dm_user(msg, msg.author, member.id)