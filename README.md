# Adottomin

Discord bot to manage new users in servers

## Execution

The following environment variables must be set prior to execution:

 - `TOKEN`: Discord bot token
 - `GUILD_IDS`: Discord Guild IDs that the bot will be allowed to operate in, joined by `.`
 - `CHANNEL_IDS`: Discord Channel IDs that the bot will send messages, joined by `.`
 - `BOT_HOME`: Directory pointing to the folder containing `addotomin.py`

 You may also set the `LOG_LEVEL` variable to determine the verbosity of logs (according to the `logging` python module); defaults to DEBUG.

 The available values, in order of verbosity, are:

 > CRITICAL = FATAL < ERROR < WARNING = WARN < INFO < DEBUG

 Then you can execute the bot standalone using

 ```sh
python3 adottomin.py
 ```

You can also use [Bismuth](https://github.com/PYROP3/Bismuth) in order to execute the bot automatically.
