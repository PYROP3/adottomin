import discord
import re

REASON_MINOR = "minor"
REASON_TIMEOUT = "did not say age"
REASON_SPAM = "spam"
REASON_RAID = "raid"

MSG_GREETING = ":wave: Hello {}! May I ask your age, pls?"
MSG_TRY_AGAIN = "Try again, {}"
MSG_WELCOME = "Thank you {}! :space_invader: Welcome to the server! Tags are in <#1005395967429836851> if you want ^^"
MSG_WELCOME_NO_TAGS = "Thank you {}! :space_invader: Welcome to the server!"

AGE_MAX = 50

DELETE_GREETINGS = False

class age_handler:
    def __init__(self, bot, sql, logger, greeting_channel, tally_channel):
        self.bot = bot
        self.sql = sql
        self.logger = logger
        self.greeting_channel = greeting_channel
        self.tally_channel = tally_channel
        
        # Age regex
        self.age_prog = re.compile(r"(18|19|[2-9][0-9]+)") # 18, 19 or 20+
        self.minor_prog = re.compile(r"(?: |^)\b(1[0-7])\b") # 0-9 or 10-17
        self.minor_prog_2 = re.compile(r"not 18") # 0-9 or 10-17

    async def handle_age(self, msg: discord.Message):
        leniency = self.sql.get_leniency(msg.author.id)
        if leniency is None or leniency < 0: return
        
        self.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} is still on watchlist, parsing message")

        if self.is_insta_ban(msg.content):
            age = self.get_ban_age(msg.content)
            self.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} said a non-valid age ({age})")
            await self.kick_or_ban(msg.author, msg.channel, age=age, force_ban=True, force_update_age=True, reason=REASON_MINOR)

        elif self.is_valid_age(msg.content):
            age = self.get_age(msg.content)
            if age > AGE_MAX:
                self.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} said a questionable age ({age}), ignoring")
                self.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} said a non-valid message ({leniency} left)")
                self.sql.decr_leniency(msg.author.id)

                await msg.channel.send(MSG_TRY_AGAIN.format(msg.author.mention))
            else:
                self.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} said a valid age ({age})")
            
                self.sql.delete_entry(msg.author.id)
                self.sql.set_age(msg.author.id, age, force=True)

                await msg.channel.send(MSG_WELCOME.format(msg.author.mention))

        elif leniency > 0:
            self.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} said a non-valid message ({leniency} left)")
            self.sql.decr_leniency(msg.author.id)

        else:
            self.logger.debug(f"[{msg.channel.guild.name} / {msg.channel}] {msg.author} is out of messages")
            await self.kick_or_ban(msg.author, msg.channel, reason=REASON_TIMEOUT)

    async def kick_or_ban(self, member, channel, age=-1, force_ban=False, force_update_age=False, reason=REASON_MINOR):
        if force_ban or self.sql.is_kicked(member.id):
            self.logger.debug(f"[{channel}] Will ban user (force={force_ban})")
            await self.do_ban(channel, member, reason=reason)
            self.sql.remove_kick(member.id)

        else:
            self.logger.debug(f"[{channel}] User was NOT previously kicked")
            await self.do_kick(channel, member, reason=reason)
            self.sql.create_kick(member.id)

        greeting = self.sql.delete_entry(member.id)
        await self.try_delete_greeting(greeting, channel)
        self.sql.set_age(member.id, age, force=force_update_age)

    async def try_delete_greeting(self, greeting, channel):
        if greeting is None: return

        if not DELETE_GREETINGS:
            self.logger.debug(f"[{channel}] Will NOT delete greeting {greeting}")
            return

        try:
            channel = self.bot.get_channel(self.greeting_channel)
            greeting_msg = await channel.fetch_message(greeting)
            await greeting_msg.delete()

        except discord.NotFound:
            self.logger.debug(f"[{channel}] Greeting {greeting} already deleted")

        except Exception as e:
            self.logger.warning(f"[{channel}] failed to delete greeting {greeting}")
            self.logger.debug(f"[{channel}] {e}")

    def is_valid_age(self, msg: str):
        return self.age_prog.search(msg) is not None

    def get_age(self, msg: str):
        return int(self.age_prog.search(msg).group())

    def is_insta_ban(self, msg: str): # TODO add filters? racism, etc.
        return self.minor_prog.search(msg) is not None or self.minor_prog_2.search(msg) is not None

    def get_ban_age(self, msg: str):
        return int(self.minor_prog.search(msg).group())

    async def do_tally(self):
        if self.tally_channel is None: return
        try:
            await self.bot.get_channel(self.tally_channel).send(f"x")
        except Exception as e:
            self.logger.error(f"Failed to tally! {e}")

    async def do_ban(self, channel, user, reason=REASON_MINOR):
        try:
            await channel.guild.ban(user, reason=reason.capitalize())
            await channel.send(f"User {user.mention} banned | {reason.capitalize()}")
            await self.do_tally()
        except discord.NotFound:
            self.logger.debug(f"User id {user} already left!")
        except:
            self.logger.error(f"Failed to ban user id {user}!")
            # await channel.send(f"Failed to ban user {user.mention} | {reason.capitalize()}")

    async def do_kick(self, channel, user, reason=REASON_TIMEOUT):
        try:
            await channel.guild.kick(user, reason=reason.capitalize())
            await channel.send(f"User {user.mention} kicked | {reason.capitalize()}")
        except discord.NotFound:
            self.logger.debug(f"User id {user} already left!")
        except:
            self.logger.error(f"Failed to kick user id {user}!")
            # await channel.send(f"Failed to kick user {user.mention} | {reason.capitalize()}")
