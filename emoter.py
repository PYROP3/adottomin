import botlogger

logger = botlogger.get_logger(__name__)
try:
    import emote_data
    _data = emote_data.emotes
except:
    logger.warning("Emote data not found")
    _data = {}

class Emoter:
    def __init__(self):
        self._data = {}
        self.logger = logger
        for emote in _data:
            self._data[emote] = f"<:{emote}:{_data[emote]}>"

    def _emote(self, text):
        if text[0] != ':': text = f":{text}:"
        return text

    def e(self, emote: str, fallback: str=""):
        if emote not in self._data: 
            self.logger.warning(f"Could not find emote {emote}")
            return self._emote(fallback)
        return self._data[emote]

