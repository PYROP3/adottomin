import asyncio
import country_converter as coco
import discord
import inspect
import json
import msg_handler_manager
import queue
import random
import re
import string
import subprocess
import time
import traceback
import typing

import botlogger
import db
import ghostpings
import propervider as p

from datetime import datetime, timedelta
from discord.ext import commands
try:
    from ipcqueue import sysvmq
except ImportError:
    sysvmq = None

AVATAR_CDN_URL = "https://cdn.discordapp.com/avatars/{}/{}.png"

MSG_NOT_ALLOWED = "You're not allowed to use this command :3"

EMBED_COLORS = [
    discord.Colour.magenta(),
    discord.Colour.blurple(),
    discord.Colour.dark_teal(),
    discord.Colour.blue(),
    discord.Colour.dark_blue(),
    discord.Colour.dark_gold(),
    discord.Colour.dark_green(),
    discord.Colour.dark_grey(),
    discord.Colour.dark_magenta(),
    discord.Colour.dark_orange(),
    discord.Colour.dark_purple(),
    discord.Colour.dark_red(),
    discord.Colour.darker_grey(),
    discord.Colour.gold(),
    discord.Colour.green(),
    discord.Colour.greyple(),
    discord.Colour.orange(),
    discord.Colour.purple(),
    discord.Colour.magenta(),
]

queen_role_id = 1002077481156743259
owner_role_id = 1014556813821214780
divine_role_id = 1021892234829906043
secretary_role_id = 1002385294152179743

attachments_channel_ids = [1002078229168922785]
# attachments_channel_ids = [471017843459358733]
attachment_save_location = "attachments"

ad_channel = p.pint('AD_CHANNEL_ID')
ad_poster_role_id = p.pint('AD_POSTER_ROLE_ID')
horny_channel_id = p.pint('HORNY_CHANNEL_ID')
log_channel_id = p.pint('LOG_CHANNEL_ID')

puppeteer_prog = re.compile(r"<@([0-9]+)>")
file_ext_prog = re.compile(r".+\.([a-zA-Z0-9]+)$", flags=re.IGNORECASE)

def quote_each_line(msg: str, additional:str=""):
    lines = msg.split('\n') + (additional.split('\n') if len(additional) else [])
    return "".join([f"> {line}\n" for line in lines])

def get_attachments(self, msg: discord.Message):
    extras = {
        "attachment": len(msg.attachments),
        "embed": len(msg.embeds),
        "sticker": len(msg.stickers)
    }
    return " ".join(["<{} {}>".format(amount, self.plural(item, amount)) for item, amount in extras.items() if amount])

class HandlerException(Exception):
    pass

class HandlerIgnoreException(HandlerException):
    pass

invite_prog = re.compile(r"(https:\/\/)?(www\.)?(((discord(app)?)?\.com\/invite)|((discord(app)?)?\.gg))\/(.+)")

class utils:
    time_regex = re.compile(r"([1-9][0-9]*)([smhdw]?)")

    def __init__(self, bot: commands.Bot, database: db.database, mhm: msg_handler_manager.HandlerManager, chatting_roles_allowlist=[], chatting_servicename: str=None):
        self.database = database
        self.bot = bot
        self.mhm = mhm
        self.chatting_roles_allowlist = set(chatting_roles_allowlist)
        self.chatting_servicename = chatting_servicename
        self.admin = None
        self.pois = []
        self.guild = None

        self.logger = botlogger.get_logger(__name__)

        self._recreate_queues()

    async def _enforce_admin_only(self, msg, e: HandlerException=HandlerIgnoreException):
        if self.admin is None: 
            self.logger.warning(f"Utils admin link is still not ready")
            raise e()
        if msg.author.id != self.admin.id: raise e()

    async def _enforce_not_admin(self, msg, e: HandlerException=HandlerIgnoreException):
        if self.admin is None: 
            self.logger.warning(f"Utils admin link is still not ready")
            raise e()
        if msg.author.id == self.admin.id: raise e()

    async def _enforce_dms(self, msg, e: HandlerException=HandlerIgnoreException):
        if msg.channel.type != discord.ChannelType.private: raise e()

    async def _enforce_not_dms(self, msg, e: HandlerException=HandlerIgnoreException):
        if msg.channel.type == discord.ChannelType.private: raise e()

    async def _enforce_has_role(self, msg, roles: set[int], e: HandlerException=HandlerIgnoreException):
        if self.guild is None:
            self.logger.warning(f"Utils guild link is still not ready")
            raise e()
        # try:
        #     member = await self.guild.fetch_member(msg.author.id)
        # except discord.errors.NotFound:
        #     self.logger.warning(f"Failed to fetch {msg.author.id} as Member")
        #     raise e()
        # if member is None: 
        #     self.logger.warning(f"Got null when trying to fetch {msg.author.id} as Member")
        #     raise e()
        author_roles = await self.get_roles(msg.author.id, e=e)
        # self.logger.debug(f"Comparing user {author_roles} to {roles}")
        if set([role.id for role in author_roles]).intersection(roles) == set(): raise e()

    async def get_roles(self, author_id: int, e: HandlerException=HandlerIgnoreException):
        if self.guild is None:
            self.logger.warning(f"Utils guild link is still not ready")
            raise e()
        try:
            member = await self.guild.fetch_member(author_id)
        except discord.errors.NotFound:
            self.logger.warning(f"Failed to fetch {author_id} as Member")
            raise e()
        if member is None: 
            self.logger.warning(f"Got null when trying to fetch {author_id} as Member")
            raise e()
        return member.roles

    async def _enforce_no_roles(self, msg, roles, e: HandlerException=HandlerIgnoreException):
        await self._enforce_admin_only(msg)
        if self.guild is None:
            self.logger.warning(f"Utils guild link is still not ready")
            return
        try:
            member = await self.guild.fetch_member(msg.author.id)
        except discord.errors.NotFound:
            self.logger.warning(f"Failed to fetch {msg.author.id} as Member")
            return
        if member is None: 
            self.logger.warning(f"Got null when trying to fetch {msg.author.id} as Member")
            return
        author_roles = member.roles
        # self.logger.debug(f"Comparing user {author_roles} to {roles}")
        if set([role.id for role in author_roles]).intersection(roles) != set(): raise e()

    def inject_admin(self, admin):
        self.logger.debug(f"Injected admin {admin}")
        self.admin = admin

    def inject_pois(self, pois):
        self.logger.debug(f"Injected {len(pois)} pois")
        self.pois = pois

    async def inject_guild(self, guild: discord.Guild):
        self.logger.debug(f"Injected guild {guild}")
        self.guild = guild
        self.mbot = await guild.fetch_member(self.bot.user.id)
        
    async def on_utils_setup(self):
        self.horny_channel = await self.guild.fetch_channel(horny_channel_id)
        self.log_channel = await self.guild.fetch_channel(log_channel_id)

    def _is_chatbot_available(self):
        if self.chatting_servicename is None: return False
        return subprocess.run(["systemctl", "is-active", "--quiet", self.chatting_servicename]).returncode == 0

    def _recreate_queues(self):
        if sysvmq is not None:
            self.chatbot_queue_req = sysvmq.Queue(1022)
            self.chatbot_queue_rep = sysvmq.Queue(1023)
        else:
            self.chatbot_queue = None

    async def _get_msg_chain(self, original_msg: discord.Message, max_depth = None):
        current = original_msg
        chain = [current]
        while current.reference is not None:
            ref = current.reference.resolved
            if ref is None:
                try:
                    fetched = await original_msg.channel.fetch_message(current.reference.message_id)
                    if fetched is None:
                        chain += [None]
                        break
                    ref = fetched
                except:
                    chain += [None]
                    break
            current = ref
            chain += [current]
            if max_depth is not None:
                max_depth -= 1
                if max_depth <= 0:
                    break
            if type(current) == discord.DeletedReferencedMessage:
                break
        return chain

    async def _format_msg_chain(self, user: discord.User, original_msg: discord.Message, max_size: int = 1500):
        msg_chain = await self._get_msg_chain(original_msg)
        msg_fmt = quote_each_line(msg_chain[0].content, additional=get_attachments(self, msg_chain[0])).replace(user.mention, user.display_name) + "\n"
        for message in msg_chain[1:]:
            if message is None:
                new_line = "As a reply to an unknown message\n"
            else:
                try:
                    _sender = "you" if (user.id == message.author.id) else f"{message.author.mention}"
                    new_line = f"As a reply to a message {_sender} sent:\n{quote_each_line(message.content, additional=get_attachments(self, message)).replace(user.mention, user.display_name)}\n"
                except Exception as e:
                    new_line = f"As a reply to a deleted message\n"
                    self.logger.warning(f"Error while trying to get message contents: {e}\n{traceback.format_exc()}")
            if len(msg_fmt + new_line) > max_size:
                self.logger.debug(f"Trimming message size ({len(msg_fmt + new_line)})")
                msg_fmt += "[...]"
                break
            msg_fmt += new_line
        return msg_fmt.replace(user.mention, user.display_name)

    async def _dm_user(self, msg: str, user: discord.Member):
        try:
            # user = self.bot.get_user(user_id)
            dm_chan = user.dm_channel or await user.create_dm()
            
            # self.logger.debug(f"[_dm_user] Trying to send notification to {user_id}")
            # self.logger.debug(f"[_dm_user] [{msg}]")
            return await dm_chan.send(content=msg)
        except discord.Forbidden as e:
            self.logger.info(f"Forbidden from sending message to user {user.id}: {e}")
        except Exception as e:
            self.logger.error(f"Error while trying to dm user: {e}\n{traceback.format_exc()}")
        return None

    def _is_self_mention(self, msg: discord.Message, member: discord.Member):
        return (member.id == msg.author.id) or (msg.author.bot and msg.interaction != None and msg.interaction.user.id == member.id)

    async def handle_cork_board_post(self, msg: discord.Message):
        await self._enforce_not_dms(msg)
        if msg.channel.id != ad_channel: return
        if not self.mhm.is_lock(self.handle_cork_board_post, msg.author.id): return

        ad_role = msg.guild.get_role(ad_poster_role_id)
        try:
            await msg.author.remove_roles(ad_role, reason=f"posted in cork-board")
        except Exception as e:
            self.logger.error(f"handle_cork_board_post: {e}\n{traceback.format_exc()}")

        self.mhm.remove_dyn_lock(self.handle_cork_board_post, msg.author.id)

    async def handle_offline_mentions(self, msg: discord.Message):
        await self._enforce_not_dms(msg)
        member_list = [msg.guild.get_member(id) for id in ghostpings.get_everyone_allowlist(self.database)] if msg.mention_everyone else msg.mentions
        # self.logger.debug(f"handle_offline_mentions: {member_list}")
        who = "@everyone" if msg.mention_everyone else "you"
        for member in member_list:
            if not member: continue
            will_send = not self._is_self_mention(msg, member) and ghostpings.compute_user_bitmask(member, self.database) and msg.channel.permissions_for(member).view_channel
            # self.logger.debug(f"[handle_offline_mentions] User {member} status = {member.status} // will_send = {will_send}")
            if not will_send: continue
            fmt_msg_chain = await self._format_msg_chain(member, msg)

            if msg.author.bot:
                content = f"Hi {member.name}! {self._bot_name(msg.author)} pinged {who}{self._interaction_detail(msg.interaction)} in {msg.channel.name} while you were offline:\n{msg.jump_url}\n{fmt_msg_chain}\n"
            else:
                content = f"Hi {member.name}! {msg.author.mention} pinged {who} in {msg.channel.name} while you were offline:\n{msg.jump_url}\n{fmt_msg_chain}\n"
            if not self.database.is_alert_registered(member.id, db.once_alerts.offline_pings):
                content += "You can disable these notifications with `/offlinepings off` in the server if you want!"
                self.database.register_alert(member.id, db.once_alerts.offline_pings)
            await self._split_dm(content, member)

    def _interaction_detail(self, interaction: typing.Optional[discord.MessageInteraction]):
        if interaction is None: return ""
        return f" at the request of {interaction.user.mention}'s /{interaction.name}"

    async def get_icon_default(self, user: typing.Optional[discord.Member]):
        if user is None: return None
        return await self.get_user_icon(user)

    async def get_user_icon(self, user: discord.Member):
        try:
            icon_name = "trash/" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=20)) + ".png"
            self.logger.debug(f"icon_name={icon_name}")

            await user.avatar.save(fp=icon_name)

            return icon_name
        except Exception as e:
            self.logger.error(f"Error while trying to get avatar: {e}\n{traceback.format_exc()}")
            return None

    def _get_display_name(self, user: typing.Optional[discord.Member]):
        if user is None: return None
        try:
            return user.display_name
        except:
            return None

    def _fallback_get_text(self, user):
        try:
            return str(user)
        except:
            return None

    def get_text(self, user):
        return self._get_display_name(user) or self._fallback_get_text(user)

    def to_ord(self, num):
        if int(num) in [11,12,13]: return "th"
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

    def to_pretty_timedelta(self, seconds: int):#delta: timedelta):
        fmt = []
        _rem = int(seconds) #delta.total_seconds()
        _d = int(_rem / 86400)
        if _d:
            fmt += [f"{_d} days"]
        _rem = _rem % 86400
        _h = int(_rem / 3600)
        if _h:
            fmt += [f"{_h} hours"]
        _rem = _rem % 3600
        _m = int(_rem / 60)
        if _m:
            fmt += [f"{_m} minutes"]
        _s = _rem % 60
        if _s:
            fmt += [f"{_s} seconds"]

        return ", ".join(fmt)

    async def handle_dm(self, msg: discord.Message):
        await self._enforce_dms(msg)
        await self._enforce_not_admin(msg)
        if len(msg.content) == 0: return
        content = f"{msg.author.mention} ({msg.author.id}) messaged me:\n{quote_each_line(msg.content, additional=get_attachments(self, msg))}\n"
        await self._split_dm(content, self.admin)

    async def handle_puppeteering(self, msg: discord.Message):
        await self._enforce_dms(msg)
        await self._enforce_admin_only(msg)
        if len(msg.content) == 0: return
        target_id = puppeteer_prog.search(msg.content)
        if target_id is None: return
        target = await self.bot.fetch_user(int(target_id.group(1)))
        _crop = len(target_id.group(0)) + 1
        content = msg.content[_crop:]
        self.logger.info(f"Puppeteering message to {target_id.group(1)}/{target}: \"{content}\"")
        await self._split_dm(content, target)

    async def handle_dm_cmd(self, msg: discord.Message):
        await self._enforce_dms(msg)
        await self._enforce_not_admin(msg)
        if len(msg.content) == 0: return
        if msg.content[0] != '/': return
        content = f"Slash commands only work on the server! Try again there~"
        await msg.reply(content=content)

    async def handle_attachments(self, msg: discord.Message):
        await self._enforce_not_dms(msg)
        if msg.channel.id not in attachments_channel_ids: return
        # self.logger.debug(f"Attachments = {msg.attachments}")
        # self.logger.debug(f"Embeds = {msg.embeds}")
        if len(msg.attachments) == 0: return
        hashes = set()
        aux = []
        for attachment in msg.attachments:
            self.logger.debug(f"Attachment type {attachment.content_type}: url = {attachment.url}")
            file_format = attachment.url.split('.')[-1]
            attachment_name = f"{msg.author.id}_{msg.channel.id}_{attachment.id}.{file_format}"
            self.logger.debug(f"Saving attachment as {attachment_name}")
            filename = f"{attachment_save_location}/{attachment_name}"
            await attachment.save(fp=filename)
            subp = subprocess.run(["md5sum", filename], capture_output=True)
            hash = subp.stdout.decode('UTF-8').split()[0]
            hashes.add(hash)
            aux += [(attachment.id, file_format, hash)]
            
        if self.database.check_attachments_dejavu(hashes) > 0: # at least one image has already been seen before
            self.logger.debug(f"Adding reaction since I've already seen at least 1 repeat")
            await msg.add_reaction('👀')
            
        for attachment, file_format, hash in aux:
            self.database.create_attachment(msg.author.id, msg.channel.id, attachment, file_format, hash)
        
    async def handle_binary(self, msg: discord.Message):
        if len(msg.content) == 0: return
        if set(msg.content) != set(['0', '1', ' ']): return
        translated = ''.join([chr(self.bin2dec(int(x))) for x in msg.content.split()])
        await msg.reply(content=f"{msg.author.mention} meant\n> {translated}")

    async def handle_failed_command(self, msg: discord.Message):
        # await self._enforce_not_dms(msg)
        # await self._enforce_not_admin(msg)
        if len(msg.content) == 0: return
        content = msg.content.split()[0]
        if content[0] != '/': return
        if self.bot.tree.get_command(content[1:]) is None:
            self.logger.debug(f"{content[1:]} not in command list")
            return
        if msg.channel.type == discord.ChannelType.private:
            reply = f"Commands only work in the server~"
        else:
            reply = f"lol boomer"
        await msg.reply(content=reply)

    async def handle_invite_link(self, msg: discord.Message):
        await self._enforce_not_dms(msg)
        await self._enforce_no_roles(msg, [queen_role_id])
        if len(msg.content) == 0: return
        if invite_prog.search(msg.content) is None:
            return
        await msg.delete()
        await msg.channel.send(content=f"No discord invites, {msg.author.mention}~")

    async def handle_chat_dm(self, msg: discord.Message):
        # await self._enforce_admin_only(msg)
        await self._enforce_has_role(msg, self.chatting_roles_allowlist)
        await self._enforce_dms(msg)
        if len(msg.content) == 0: return
        if self.chatbot_queue_req is None or not self._is_chatbot_available(): 
            await self._dm_user("Sorry, but the chatting submodule is currently turned off~", msg.author)
            return

        async with msg.channel.typing():
            self.logger.debug(f"Sending {msg.author.id} request for reply")
            self.chatbot_queue_req.put([msg.author.id, msg.content])
            while True:
                try:
                    self.logger.debug(f"Waiting for {msg.author.id} reply")
                    reply = self.chatbot_queue_rep.get(msg_type=msg.author.id)
                    self.logger.debug(f"Received {msg.author.id} reply: \"{reply}\"")
                    await self._split_dm(reply, msg.author)
                    if msg.author.id != self.admin.id:
                        content = f"{msg.author.mention} ({msg.author}) responding with \"{reply}\"\n"
                        await self._split_dm(content, self.admin)
                    break
                except queue.Empty:
                    self.logger.error(f"Timeout waiting for chatbot response")
                except sysvmq.QueueError:
                    self.logger.warning(f"Queue error, recreating...")
                    self._recreate_queues()

    async def send_poi_dms(self, content):
        for user in self.pois:
            try:
                await self._split_dm(content, user)
            except Exception as e:
                self.logger.warning(f"Error while trying to send DM to POI {user}: {e}\n{traceback.format_exc()}")

    async def _split_dm(self, content, user):
        msg = await self._dm_user(content[:2000], user)
        content = content[2000:]
        while len(content) > 0:
            msg = await msg.reply(content=content[:2000])
            content = content[2000:]

    def _bot_name(self, bot):
        return "I" if bot.id == self.bot.user.id else bot.mention

    def just_joined(self, user: int):
        return self.database.get_leniency(user) is not None

    def role_ids(self, user: discord.Member):
        return set([role.id for role in user.roles])

    def get_unique_aliases(self, user: discord.Member):
        return self.get_unique_aliases_id(user.id)

    def get_unique_aliases_id(self, user_id: int):
        return {alias[0]: alias[1] for alias in self.database.get_aliases(user_id)}

    def escape(self, string: str, *chars: typing.Iterable[str]):
        for char in chars:
            string = string.replace(char, f'\\{char}')
        return string

    def markdown_surround(self, string: str, delimiter: str, delimiter_right: str=None):
        delimiter_right = delimiter_right or delimiter
        return f'{delimiter}{self.escape(string, delimiter, delimiter_right)}{delimiter_right}'

    def plural(self, word, amount):
        if int(amount) == 1: return word
        return word + 's'

    async def ensure_secretary(self, interaction):
        return await self._ensure_roles(interaction, divine_role_id, secretary_role_id)

    async def ensure_divine(self, interaction):
        return await self._ensure_roles(interaction, divine_role_id)

    async def ensure_owner(self, interaction):
        return await self._ensure_roles(interaction, owner_role_id)

    async def ensure_queen(self, interaction):
        return await self._ensure_roles(interaction, queen_role_id)

    async def ensure_admin(self, interaction):
        if (interaction.user.id != self.admin.id):
            self.logger.debug(f"{interaction.user} cannot use {inspect.getouterframes(inspect.currentframe(), 2)[1][3]}")
            await self.safe_send(interaction, content=MSG_NOT_ALLOWED, ephemeral=True)
            return False
        return True

    async def _ensure_roles(self, interaction, *roles):
        _author_roles = self.role_ids(interaction.user)
        if (interaction.user.id != self.admin.id) and set(_author_roles).intersection(roles) == set():
            self.logger.debug(f"{interaction.user} cannot use {inspect.getouterframes(inspect.currentframe(), 2)[1][3]}")
            await self.safe_send(interaction, content=MSG_NOT_ALLOWED, ephemeral=True)
            return False
        return True

    def validate_country(self, country: str):
        country = coco.convert(names=country, to='ISO3', not_found='NULL')
        return country if country != 'NULL' else None

    def country_flag(self, country: str):
        country = coco.convert(names=country, to='ISO2', not_found='NULL')
        return f':flag_{country.lower()}:' if country != 'NULL' else ''

    def _qualified_name(self, command: discord.app_commands.Command):
        name = ''
        if not isinstance(command, discord.app_commands.ContextMenu):
            parent = command.parent
            while parent:
                name = f"{parent.name}." + name
                parent = parent.parent
        return name + command.name

    async def safe_defer(self, interaction: discord.Interaction, ephemeral: bool=False, **kwargs):
        try:
            await interaction.response.defer(ephemeral=ephemeral, **kwargs)
            interaction.extras['deferred_as'] = ephemeral
            return True
        except discord.errors.NotFound:
            self.logger.warning(f"NotFound error while trying to defer interaction (ephemeral={ephemeral})")
            return False

    async def safe_send(self, interaction: discord.Interaction, is_followup: bool=False, send_anyway: bool=False, **kwargs):
        _name = self._qualified_name(interaction.command)
        try:
            if is_followup or 'deferred_as' in interaction.extras:
                res = await interaction.followup.send(**kwargs)
            else:
                res = await interaction.response.send_message(**kwargs)
            self.database.register_command(interaction.user.id, _name, interaction.channel_id, args=json.dumps('options' in interaction.data and interaction.data['options'] or {}))
            return res

        except discord.errors.NotFound:
            self.logger.warning(f"NotFound error while trying to send message (send_anyway={send_anyway})")
            self.database.register_command(interaction.user.id, _name, interaction.channel_id, args=json.dumps('options' in interaction.data and interaction.data['options'] or {}), failed=True)
            if send_anyway:
                if 'ephemeral' in kwargs and kwargs['ephemeral']:
                    self.logger.error(f"Not replying publicly to ephemeral")
                    return
                if 'content' in kwargs:
                    kwargs['content'] = f"{interaction.user.mention} used `/{_name}`\n{kwargs['content']}"
                else:
                    kwargs['content'] = f"{interaction.user.mention} used `/{_name}`"
                return await interaction.channel.send(**kwargs)
            
    async def give_returnee_roles(self, userid: int):
        member = await self.guild.fetch_member(userid)
        if member.bot:
            return False, set()
        
        role_ids = self.database.get_roles(userid)
        if role_ids:
            roles = set([self.guild.get_role(role_id) for role_id in role_ids])
            assignable_roles = set([role for role in roles if self.is_assignable(role)])

            self.logger.debug(f"Adding {assignable_roles} to returning {member}")
            try:
                await member.add_roles(*assignable_roles, reason="Returning fur-iend!")
                return True, roles.difference(assignable_roles)
            except:
                self.logger.warning(f"Failed to give roles to {userid}")
        return False, set()
            
    async def purge_user_from_channel(self, channel: discord.TextChannel, userid: int, reason: str, complete: bool=False, mod: discord.Member=None):
        total_messages = 0
        total_purged = 0
        total_ignored = 0
        async for message in channel.history(limit=None):
            total_messages += 1
            if message.author.id != userid: continue
            if (not complete) and (not message.attachments): 
                total_ignored += 1
                continue
            self.logger.info(f"Purging message {message.id} from {channel}")
            await message.delete()
            total_purged += 1

        self.logger.info(f"Purged {total_purged}, ignored {total_ignored} out of {total_messages} in {channel}")

        try:
            user = await self.bot.fetch_user(userid)
        except:
            user = None

        mod = mod or self.bot.user
        purge_embed = discord.Embed(
                colour=discord.Colour.blurple(),
                timestamp=datetime.now()
            )         
        purge_embed.add_field(name="User", value=f"<@{userid}>", inline=True)
        purge_embed.add_field(name="Moderator", value=mod.mention, inline=True)
        purge_embed.add_field(name="Channel", value=channel.mention, inline=True)
        purge_embed.add_field(name="Reason", value=reason, inline=True)
        purge_embed.add_field(name="Messages", value=f"{total_purged} purged | {total_ignored} ignored", inline=True)
        purge_embed.set_footer(text=f'ID: {userid}')
        av = user or self.bot.user
        purge_embed.set_author(name=f"Purge | {user.name if user else userid}", icon_url=av.avatar and av.avatar.url)
        await self.log_channel.send(embed=purge_embed)

    def _iterate_dec(self, number:int):
        while number >= 10:
            yield int(number % 10)
            number /= 10
        yield int(number)
            
    def _name_number(self, number:int):
        return ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine'][number]

    def n_em(self, number: int):
        return "".join([f':{self._name_number(num)}:' for num in list(self._iterate_dec(number))[::-1]])

    def bin2dec(self, binary):
        decimal, i, n = 0, 0, 0
        while binary != 0:
            dec = binary % 10
            decimal = decimal + dec * pow(2, i)
            binary = binary//10
            i += 1
        return decimal

    def db2datetime(self, when: str):
        return datetime.strptime(when, "%Y-%m-%d %H:%M:%S.%f")

    def db2timestamp(self, when: str, style: str=""):
        return self.timestamp(self.db2datetime(when), style=style)
    
    def timestamp(self, when: datetime=datetime.now(), style: str=""):
        return f"<t:{int(time.mktime(when.timetuple()))}{style}>"

    def pretty_time_delta(self, td: timedelta):
        return str(td).split(".")[0]
    #     seconds = td.seconds
    #     sign_string = '-' if seconds < 0 else ''
    #     seconds = abs(int(seconds))
    #     print(f"pretty_time_delta {seconds}")
    #     days, seconds = divmod(seconds, 86400)
    #     hours, seconds = divmod(seconds, 3600)
    #     minutes, seconds = divmod(seconds, 60)
    #     if days > 0:
    #         return '%s%dd%dh%dm%ds' % (sign_string, days, hours, minutes, seconds)
    #     elif hours > 0:
    #         return '%s%dh%dm%ds' % (sign_string, hours, minutes, seconds)
    #     elif minutes > 0:
    #         return '%s%dm%ds' % (sign_string, minutes, seconds)
    #     else:
    #         return '%s%ds' % (sign_string, seconds)

    async def core_hornyjail(self, interaction: discord.Interaction, user: discord.Member, duration: int, jail_role_id: int, message: typing.Optional[discord.Message]=None, delete_original: typing.Optional[bool]=False):
        self.logger.info(f"{interaction.user} is jailing {user} for {duration} minutes")

        if user.bot:
            await self.safe_send(interaction, content=f"Bots can't get horny, silly~", ephemeral=True)
            return

        if duration < 1: 
            await self.safe_send(interaction, content=f"Please input a valid duration (> 0)", ephemeral=True)
            return

        success = self.database.jail_try_register_jailing(user.id, interaction.user.id, duration)

        if not success:
            await self.safe_send(interaction, content=f"I think that user is already in jail~", ephemeral=True)
            return
        
        jail_role = interaction.guild.get_role(jail_role_id)
        await user.add_roles(jail_role, reason=f'{interaction.user} put them in jail')
        
        await self.safe_send(interaction, content=f"{user.mention} is now in horny jail for {duration} {self.plural('minute', duration)}! Feel free to continue the conversation in {self.horny_channel.mention}~", send_anyway=True)

        # Send embedded message to an appropriate chat
        if message:
            msg_embed, msg_attachments = await self.core_message_as_embed(message, add_jump=False)
            await self.horny_channel.send(file=msg_attachments, embed=msg_embed)
            if delete_original:
                try:
                    await message.delete()
                except Exception as e:
                    self.logger.warning(f"Failed to remove original message : {e} | {traceback.format_exc()}")

        await asyncio.sleep(duration * 60)
        
        try:
            self.logger.debug(f"Unjailing {user} after {duration} minutes")
            await user.remove_roles(jail_role, reason=f'{duration} minute timer finished')
            self.logger.debug(f"Success unjailing {user}")
        except Exception as e:
            self.logger.debug(f"Failed to remove role : {e} | {traceback.format_exc()}")

    async def core_joinhistory(self, interaction: discord.Interaction, userid: int, sql: db.database, username: str=None):
        username = username or userid
        data = sql.get_join_history(userid)
        if len(data) == 0:
            await self.safe_send(interaction, content=f"I could not find any data about {username} (they may have joined before the glorious revolution)", send_anyway=True)
            return

        content = f"Here's what I know about {username}...\n"

        created_at, last_action = data[0]
        last_datetime = self.db2datetime(created_at)
        content += "+ Joined" if last_action == 'join' else "- Left"
        content += f" @ {self.timestamp(last_datetime)}"

        if len(data) > 1:
            for created_at, action in data[1:]:
                this_datetime = self.db2datetime(created_at)
                content += " (" + ("in" if last_action == 'join' else "out") + f" for {self.pretty_time_delta(this_datetime - last_datetime)})\n"
                content += "+ Joined" if action == 'join' else "- Left"
                content += f" @ {self.timestamp(this_datetime)}"
                last_datetime = this_datetime
                last_action = action

        content += " (" + ("in" if last_action == 'join' else "out") + f" for {self.pretty_time_delta(datetime.now() - last_datetime)} so far)\n"

        await self.safe_send(interaction, content=content, send_anyway=True)

    async def core_message_as_embed(self, message: discord.Message, add_jump: bool=True):
        embed = discord.Embed(
            description=message.content if len(message.content) > 0 else None,
            colour=random.choice(EMBED_COLORS),
            timestamp=datetime.now()
        )

        attachments = message.attachments
        pinAttachmentFile = None
        if len(attachments) >= 1:
            try:
                re_file_ext = file_ext_prog.search(attachments[0].filename)
                file_ext = re_file_ext and re_file_ext.group(1) or "png"
                icon_name = ''.join(random.choices(string.ascii_uppercase + string.digits, k=20)) + "." + file_ext
                self.logger.debug(f"icon_name=trash/{icon_name}")
                
                await attachments[0].save(fp="trash/" + icon_name)

                pinAttachmentFile = discord.File("trash/" + icon_name, filename=icon_name)
                embed.set_image(url=f"attachment://{icon_name}")
            except Exception as e:
                self.logger.error(f"Error while trying to save pin attachment: {e}\n{traceback.format_exc()}")

        if add_jump:
            embed.add_field(name="Jump", value=message.jump_url, inline=False)
        
        embed.set_footer(text=f'Sent in: {message.channel.name} - at: {message.created_at}')

        embed.set_author(name=f'Sent by {message.author}', icon_url=message.author.avatar.url)

        return (embed, pinAttachmentFile)
    
    def is_assignable(self, role: discord.Role):
        return not role.is_default() and not role.managed and (self.mbot.top_role > role or self.bot.user.id == role.guild.owner_id)
    
def extract_timedelta(msg: str):
    print(f"extract_timedelta: {msg}")
    time = utils.time_regex.match(msg)
    if time:
        val, unit = time.groups()
        unit = unit or 'm'
        conv = {
            's': 'seconds',
            'm': 'minutes',
            'h': 'hours',
            'd': 'days',
            'w': 'weeks'
        }
        return timedelta(**{conv[unit]: int(val)})
    return None
