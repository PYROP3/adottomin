# Adottomin

Discord bot to manage new users in servers

## Installation

### Packages

Install the required packages from `requirements.txt`

```sh
pip install -r requirements.txt
```

### Configuration

Rename `template.env` to `.env` and replace the values with the correct IDs and tokens. Remember to also select the required feature flags (FEATURE_ENABLE_XYZ) by setting them to `y` for "yes", and anything else for "no".

### Extra executables and fonts

TODO

## Execution

The following environment variables must be set prior to execution:

 - `TOKEN`: Discord bot token
 - `GUILD_IDS`: Discord Guild IDs that the bot will be allowed to operate in, joined by `.`
 - `CHANNEL_IDS`: Discord Channel IDs that the bot will send messages, joined by `.`
 - `BOT_HOME`: Directory pointing to the folder containing `adottomin.py`

 You may also set the `LOG_LEVEL` variable to determine the verbosity of logs (according to the `logging` python module); defaults to DEBUG.

 The available values, in order of verbosity, are:

 > CRITICAL = FATAL < ERROR < WARNING = WARN < INFO < DEBUG

 Then you can execute the bot standalone using

 ```sh
python3 adottomin.py
 ```

You can also use [Bismuth](https://github.com/PYROP3/Bismuth) in order to execute the bot automatically.
