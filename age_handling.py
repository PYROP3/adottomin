import datetime
import discord
import re

import bot_utils
import botlogger
import emoter
import db
import moderation

em = emoter.Emoter()

REASON_MINOR = "minor"
REASON_TIMEOUT = "did not say age"
REASON_SPAM = "spam"
REASON_RAID = "raid"
REASON_WARNINGS = "you've been warned"

MSG_GREETING = f"{em.e('NekoHi', 'wave')} Hello {'{}'}! May I ask your age, pls?"
MSG_TRY_AGAIN = "Try again, {}"
MSG_TRY_AGAIN_JOKE = "First time I heard that one... You're a riot, {}!"
MSG_GREETING_REMINDER = f"{em.e('NekoGun', 'wave')} Hey {'{}'}! Could you tell me your age? Or I'll have to do something drastic~"
MSG_APPEND = "Tags are in <#1005395967429836851> if you want ^^\nYou may also create your f-list here with `/kink`, or contribute to the server worldmap with `/locate`!\nYou may also try `/ghostpings settings` so I'll notify you whenever people ping you here!"
MSG_DIFFERENT_AGE_BIRTHDAY = "Oh, last time you said you were {}... So happy late birthday, {}~! :tada: :birthday: And welcome back to the server! " + MSG_APPEND
MSG_DIFFERENT_AGE = "Are you sure, {}? Cuz last time you were here, you said you were {}... :thinking: But in any case, welcome back to the server! " + MSG_APPEND
MSG_WELCOME = f"Thank you {'{}'}! {em.e('NekoPat', 'space_invader')} Welcome to the server! " + MSG_APPEND
MSG_WELCOME_NO_TAGS = f"Thank you {'{}'}! {em.e('NekoPat', 'space_invader')} Welcome to the server!\nYou may create your f-list here with `/kink`, or contribute to the server worldmap with `/locate`!\nYou may also try `/ghostpings settings` so I'll notify you whenever people ping you here!"
MSG_AGE_IN_DMS = f"{'{}'} told me their age in DMs and they're chill! :sunglasses:"
MSG_ROLES_RETURNED = f"Also just cuz I dig your vibes, imma give your old roles, {'{}'}! Welcome back, furiend~"
MSG_MISSING_ROLES = f"\nUnfortunately I can't give ya {'{}'}, but ig you can ask someone else lol"

AGE_MAX = 40

DELETE_GREETINGS = False

class age_handler:
    def __init__(self, bot, sql: db.database, utils: bot_utils.utils, mod: moderation.ModerationCore, valid_role_ids, leniency_reminder=None):
        self.bot = bot
        self.sql = sql
        self.utils = utils
        self.mod = mod
        self.valid_role_ids = valid_role_ids
        self.leniency_reminder = leniency_reminder + 1 if leniency_reminder is not None else None
        self.returning_users = set()

        self.logger = botlogger.get_logger(__name__)
        
        # Age regex
        self.mention_prog = re.compile(r"<@[0-9]+>")
        self.url_prog = re.compile(r"https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)")
        self.hundred_plus_prog = re.compile(r"([1-9][0-9][0-9]+)")
        self.age_prog = re.compile(r"(18|19|[2-9][0-9]+)") # 18, 19 or 20+
        self.minor_prog = re.compile(r"(?: |^)\b(1[0-7])\b") # 0-9 or 10-17
        self.minor_prog_2 = re.compile(r"not 18") # 0-9 or 10-17
        self.ignore_prog = re.compile(r"(over 18)|(18\+)")

    def inject(self, greeting_channel: discord.TextChannel, tally_channel: discord.TextChannel, log_channel: discord.TextChannel):
        self.greeting_channel = greeting_channel
        self.tally_channel = tally_channel
        self.log_channel = log_channel

    def on_returning_user(self, user: discord.Member):
        self.returning_users.add(user.id)

    async def handle_age(self, msg: discord.Message):
        if len(msg.content) == 0: return
        leniency = self.sql.get_leniency(msg.author.id)
        if leniency is None or leniency < 0: return
        
        self.logger.debug(f"[{msg.channel}] {msg.author} is still on watchlist, parsing message")

        data = self.mention_prog.sub("", msg.content)
        data = self.url_prog.sub("", data)

        if not self.is_ignore(data): 
            if self.is_insta_ban(data):
                age = self.get_ban_age(data)
                self.logger.debug(f"[{msg.channel}] {msg.author} said a non-valid age ({age})")
                await self.kick_or_ban(msg.author, age=age, force_ban=True, force_update_age=True, reason=REASON_MINOR)
                return

            elif self.is_valid_age(data):
                age = self.get_age(data)
                if age in [69, 420, 666]:
                    self.logger.debug(f"[{msg.channel}] {msg.author} said a questionable age ({age}), ignoring")

                    await msg.channel.send(MSG_TRY_AGAIN_JOKE.format(msg.author.mention))

                elif age > AGE_MAX:
                    self.logger.debug(f"[{msg.channel}] {msg.author} said a questionable age ({age}), ignoring")

                    await msg.channel.send(MSG_TRY_AGAIN.format(msg.author.mention))
                else:
                    self.logger.debug(f"[{msg.channel}] {msg.author} said a valid age ({age})")

                    sent_already = False
                    if (prev_age := self.sql.get_previous_age(msg.author.id)) and prev_age != age:
                        sent_already = True
                        if prev_age + 1 == age:
                            await msg.channel.send(MSG_DIFFERENT_AGE_BIRTHDAY.format(prev_age, msg.author.mention), allowed_mentions=discord.AllowedMentions.none())
                        else:    
                            await msg.channel.send(MSG_DIFFERENT_AGE.format(msg.author.mention, prev_age), allowed_mentions=discord.AllowedMentions.none())
                
                    self.sql.delete_entry(msg.author.id)
                    self.sql.set_age(msg.author.id, age, force=True)

                    # embed = discord.Embed()
                    # embed.set_image(url=f"https://tenor.com/view/mpeg-gif-20384897")
                    if not sent_already:
                        await msg.channel.send(MSG_WELCOME.format(msg.author.mention), allowed_mentions=discord.AllowedMentions.none())
                    if isinstance(msg.channel, discord.DMChannel):
                        self.logger.debug(f"Message sent in DMchannel")
                        await self.greeting_channel.send(MSG_AGE_IN_DMS.format(msg.author.mention), allowed_mentions=discord.AllowedMentions.none())

                    if msg.author.id in self.returning_users:
                        gave_roles, missing_roles = await self.utils.give_returnee_roles(msg.author.id)
                        if gave_roles:
                            self.logger.debug(f"Success giving returnee roles to {msg.author}")
                            content = MSG_ROLES_RETURNED.format(msg.author.mention)
                            if missing_roles:
                                content += MSG_MISSING_ROLES.format(", ".join([role.mention for role in missing_roles]))
                            await self.greeting_channel.send(content, allowed_mentions=discord.AllowedMentions.none())
                        self.returning_users.remove(msg.author.id)

                    return

        if leniency > 0:
            self.logger.debug(f"[{msg.channel}] {msg.author} said a non-valid message ({leniency} left)")
            self.sql.decr_leniency(msg.author.id)

            if leniency == self.leniency_reminder:
                await msg.channel.send(MSG_GREETING_REMINDER.format(msg.author.mention))

        else:
            self.logger.debug(f"[{msg.channel}] {msg.author} is out of messages")
            await self.kick_or_ban(msg.author, reason=REASON_TIMEOUT)

    async def kick_or_ban(self, member, age=-1, force_ban=False, force_update_age=False, reason=REASON_MINOR):
        self.sql.cache_age(member.id, age)
        if force_ban or self.sql.is_kicked(member.id):
            self.logger.debug(f"[{self.greeting_channel}] {member} Will ban user (force={force_ban})")
            await self.mod.core_ban(member, self.greeting_channel, reason_notif=reason, reason_log=f"{reason} ({age})", moderator=self.bot.user)
            self.sql.remove_kick(member.id)

        else:
            self.logger.debug(f"[{self.greeting_channel}] {member} User was NOT previously kicked")
            await self.mod.core_kick(member, self.greeting_channel, reason_notif=reason, moderator=self.bot.user)
            self.sql.create_kick(member.id)

        greeting = self.sql.delete_entry(member.id)
        await self.try_delete_greeting(greeting)
        self.sql.set_age(member.id, age, force=force_update_age)

    async def try_delete_greeting(self, greeting):
        if greeting is None: return

        if not DELETE_GREETINGS:
            self.logger.debug(f"[{self.greeting_channel}] Will NOT delete greeting {greeting}")
            return

        try:
            greeting_msg = await self.greeting_channel.fetch_message(greeting)
            await greeting_msg.delete()

        except discord.NotFound:
            self.logger.debug(f"[{self.greeting_channel}] Greeting {greeting} already deleted")

        except Exception as e:
            self.logger.warning(f"[{self.greeting_channel}] failed to delete greeting {greeting}")
            self.logger.debug(f"[{self.greeting_channel}] {e}")

    def is_valid_age(self, msg: str):
        return self.age_prog.search(msg) is not None

    def get_age(self, msg: str):
        return int(self.age_prog.search(msg).group())

    def is_insta_ban(self, msg: str): # TODO add filters? racism, etc.
        return self.minor_prog.search(msg) is not None or self.minor_prog_2.search(msg) is not None

    def is_ignore(self, msg: str):
        return self.ignore_prog.search(msg) is not None or self.hundred_plus_prog.search(msg)

    def get_ban_age(self, msg: str):
        return int(self.minor_prog.search(msg).group())

    async def do_tally(self):
        if self.tally_channel is None: return
        try:
            await self.tally_channel.send(f"x")
        except Exception as e:
            self.logger.error(f"Failed to tally! {e}")

    async def do_age_check(self, channel, member, is_reminder=False):
        leniency = self.sql.get_leniency(member.id)
        must_continue = True
        if (leniency is not None): # user hasn't answered yet
            self.logger.debug(f"[{channel}] {member} Leniency data found")
            age_role = None
            role_count = 0
            try:
                member = await channel.guild.fetch_member(member.id) # fetch the user data again cuz of cached roles
                self.logger.debug(f"[{channel}] {member} User roles => {member.roles}")
                for role in member.roles: # check if user at least has one of the correct tags
                    if role.id in self.valid_role_ids:
                        if age_role is None:
                            age_role = role
                        role_count += 1

                if age_role is None:
                    self.logger.debug(f"[{channel}] {member} No age role")
                    if not is_reminder:
                        await self.kick_or_ban(member, reason=REASON_TIMEOUT)

                elif role_count > 2:
                    self.logger.debug(f"[{channel}] {member} Too many roles")
                    await self.kick_or_ban(member, reason=REASON_SPAM)
                    must_continue = False

                else:
                    self.logger.debug(f"[{channel}] {member} Found age role: {age_role}")
                    self.sql.set_age(member.id, age_role.id, force=True) # since we don't know the exact age, save the role ID instead
                    await self.utils.give_returnee_roles(member.id)
                    must_continue = False

            except discord.NotFound:
                self.logger.debug(f"[{channel}] {member} already quit")
                must_continue = False

        else:
            self.logger.debug(f"[{channel}] {member} Leniency data NOT found")
            must_continue = False

        if not must_continue:
            self.sql.delete_entry(member.id)

        return must_continue
