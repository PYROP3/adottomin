import discord
import traceback
import typing

import bot_utils
import botlogger

logger = botlogger.get_logger(__name__)

class HandlerManager:
    def __init__(self, admin_id: int, bot: discord.Client) -> None:
        self._dyn_handler_locks = {}
        self._dyn_handlers = set()
        self._sta_handlers = []
        self.admin_id = admin_id
        self.bot = bot

    def register_static(self, handler: typing.Callable):
        self._sta_handlers += [handler]

    def register_static_list(self, handlers: typing.List[typing.Callable]):
        self._sta_handlers += handlers

    def register_dynamic(self, handler: typing.Callable):
        self._dyn_handler_locks[handler] = set()

    def create_dyn_lock(self, handler: typing.Callable, lock: int):
        logger.debug(f"add lock {lock} to {handler} (prev {len(self._dyn_handler_locks[handler])})")
        if len(self._dyn_handler_locks[handler]) == 0:
            logger.debug(f"activate {handler}")
            self._dyn_handlers.add(handler)
        self._dyn_handler_locks[handler].add(lock)

    def remove_dyn_lock(self, handler: typing.Callable, lock: int):
        logger.debug(f"remove lock {lock} from {handler} (prev {len(self._dyn_handler_locks[handler])})")
        self._dyn_handler_locks[handler].discard(lock)
        if len(self._dyn_handler_locks[handler]) == 0:
            logger.debug(f"deactivate {handler}")
            self._dyn_handlers.discard(handler)
        
    def is_lock(self, handler: typing.Callable, lock: int):
        if handler not in self._dyn_handler_locks:
            logger.warning(f"handler {handler} not in lock list")
            return False
        return lock in self._dyn_handler_locks[handler]

    async def on_message(self, msg: discord.Message):
        for handle in self._sta_handlers + list(self._dyn_handlers):
            try:
                # logger.debug(f"Running handler {handle.__name__}")
                await handle(msg)
            except bot_utils.HandlerIgnoreException:
                pass
            except Exception as e:
                logger.error(f"[{msg.channel}] Error during {handle.__qualname__}: {e}\n{traceback.format_exc()}")
                await self._dm_log_error(f"[{msg.channel}] on_message::{handle.__qualname__}\n{e}\n{traceback.format_exc()}")

    async def _dm_log_error(self, msg: str):
        if self.admin_id is None: return
        try:
            admin_user = self.bot.get_user(self.admin_id)
            dm_chan = admin_user.dm_channel or await admin_user.create_dm()
            await dm_chan.send(content=f"Error thrown during operation:\n```\n{msg}\n```")
        except Exception as e:
            logger.error(f"Error while trying to log error: {e}\n{traceback.format_exc()}")