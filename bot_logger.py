import logging

class logger:
    def __init__(self, base, dm_level=logging.getLevelName('ERROR')):
        self.base = base
        self.dm_level = dm_level

    def inject_dm(self, dm_channel):
        self.dm_channel = dm_channel

    def _format(self, msg, ctx=None):
        return f"[{ctx.channel}] {msg}" if ctx is not None else msg

    async def _dm(self, level, msg):
        if (level > self.dm_level) or self.dm_channel is None: return
        await self.dm_channel.send(content=f"{level}:\n{msg}")

    async def debug(self, msg, ctx=None):
        fmt = self._format(self, msg, ctx=ctx)
        self.base.debug(fmt)
        await self._dm('DEBUG', fmt)

    async def info(self, msg, ctx=None):
        fmt = self._format(self, msg, ctx=ctx)
        self.base.info(fmt)
        await self._dm('INFO', fmt)

    async def warning(self, msg, ctx=None):
        fmt = self._format(self, msg, ctx=ctx)
        self.base.warning(fmt)
        await self._dm('WARNING', fmt)

    async def error(self, msg, ctx=None):
        fmt = self._format(self, msg, ctx=ctx)
        self.base.error(fmt)
        await self._dm('ERROR', fmt)
