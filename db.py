import datetime
import os
import sqlite3

db_home = os.getenv("DB_HOME") or os.getenv("BOT_HOME") or os.getcwd()

def _dbfile(id: str, version: int):
    return db_home + f'/data/{id}_v{version}.db'

validations_version = 1
validations_db_file = _dbfile('validations', validations_version)
warnings_version = 2
warnings_db_file = _dbfile('warnings', warnings_version)
offline_ping_blocklist_version = 1
offline_ping_blocklist_db_file = _dbfile('offline_ping_blocklist', offline_ping_blocklist_version)
activity_version = 2
activity_db_file = _dbfile('activity', activity_version)
autoblocklist_version = 1
autoblocklist_db_file = _dbfile('autoblocklist', autoblocklist_version)

sql_files = [
    validations_db_file,
    warnings_db_file,
    offline_ping_blocklist_db_file,
    activity_db_file,
    autoblocklist_db_file
]

schemas = {
    validations_db_file: ['''
            CREATE TABLE validations (
                user int NOT NULL,
                leniency int NOT NULL,
                greeting int NOT NULL,
                PRIMARY KEY (user)
            );''',
            '''
            CREATE TABLE kicks (
                user int NOT NULL,
                PRIMARY KEY (user)
            );''',
            '''
            CREATE TABLE age_data (
                user int NOT NULL,
                age int NOT NULL,
                date TIMESTAMP,
                PRIMARY KEY (user)
            );'''],
    warnings_db_file: ['''
            CREATE TABLE warnings (
                user int NOT NULL,
                moderator int NOT NULL,
                reason TEXT,
                date TIMESTAMP
            );'''],
    offline_ping_blocklist_db_file: ['''
            CREATE TABLE blocklist (
                user int NOT NULL,
                PRIMARY KEY (user)
            );'''],
    activity_db_file: ['''
            CREATE TABLE messages (
                user int NOT NULL,
                message_id int NOT NULL,
                channel it NOT NULL,
                date TIMESTAMP
            );'''],
    autoblocklist_db_file: ['''
            CREATE TABLE blocks (
                user int NOT NULL,
                mod int NOT NULL,
                reason TEXT,
                date TIMESTAMP,
                PRIMARY KEY (user)
            );''']
}

class database:
    def __init__(self, max_leniency, logger):
        # Initialize db
        for db_file in schemas:
            logger.debug(f"Checking db file '{db_file}'")
            if not os.path.exists(db_file):
                logger.info(f"CREATING db file '{db_file}'")
                try:
                    con = sqlite3.connect(db_file)
                    cur = con.cursor()
                    for table_schema in schemas[db_file]:
                        cur.execute(table_schema)
                    con.commit()
                    con.close()
                except:
                    logger.error(f"[__init__] Error creating {db_file}")
        
        self.logger = logger
        self.max_leniency = max_leniency

    def raw_sql(self, file, query):
        con = sqlite3.connect(file)
        cur = con.cursor()
        res = cur.execute(query).fetchall()
        con.close()
        return res

    def get_leniency(self, user):
        con = sqlite3.connect(validations_db_file)
        cur = con.cursor()
        res = cur.execute("SELECT * FROM validations WHERE user = :id", {"id": user}).fetchone()
        con.close()
        if res is None: return None
        return int(res[1])

    def create_entry(self, user, greeting_id):
        con = sqlite3.connect(validations_db_file)
        cur = con.cursor()
        try:
            cur.execute("INSERT INTO validations VALUES (?, ?, ?)", [user, self.max_leniency, greeting_id])
        except sqlite3.IntegrityError:
            self.logger.warning(f"[create_entry] Duplicated key {user} in validations, overwriting...")
            cur.execute("UPDATE validations SET leniency=:leniency, greeting=:greeting_id WHERE user=:id", {"id": user, "leniency": self.max_leniency, "greeting_id": greeting_id})
        con.commit()
        con.close()

    def decr_leniency(self, user):
        con = sqlite3.connect(validations_db_file)
        cur = con.cursor()
        cur.execute("UPDATE validations SET leniency=leniency - 1 WHERE user=:id", {"id": user})
        con.commit()
        con.close()

    def delete_entry(self, user):
        try:
            con = sqlite3.connect(validations_db_file)
            cur = con.cursor()
            res = cur.execute("SELECT * FROM validations WHERE user = :id", {"id": user}).fetchone()
            cur.execute("DELETE FROM validations WHERE user=:id", {"id": user})
            con.commit()
            con.close()
            return int(res[2]) # Return greeting ID in case it should be deleted
        except:
            return None

    def create_kick(self, user):
        con = sqlite3.connect(validations_db_file)
        cur = con.cursor()
        try:
            cur.execute("INSERT INTO kicks VALUES (?)", [user])
            con.commit()
        except sqlite3.IntegrityError:
            self.logger.warning(f"Duplicated user id {user} in kicks")
        con.close()

    def is_kicked(self, user):
        try:
            con = sqlite3.connect(validations_db_file)
            cur = con.cursor()
            res = cur.execute("SELECT * FROM kicks WHERE user = :id", {"id": user}).fetchone()
            con.commit()
            con.close()
            return res is not None
        except:
            return False

    def remove_kick(self, user):
        con = sqlite3.connect(validations_db_file)
        cur = con.cursor()
        try:
            cur.execute("DELETE FROM kicks WHERE user=:id", {"id": user})
            con.commit()
        except:
            pass
        con.close()

    def set_age(self, user, age, force=False):
        con = sqlite3.connect(validations_db_file)
        cur = con.cursor()
        try:
            cur.execute("INSERT INTO age_data VALUES (?, ?, ?)", [user, age, datetime.datetime.now()])
            con.commit()
        except sqlite3.IntegrityError:
            self.logger.warning(f"Duplicated user id {user} in age_data")
            if force:
                self.logger.debug(f"Updating {user} age in age_data -> {age}")
                cur.execute("UPDATE age_data SET age=:age, date=:date WHERE user=:id", {"id": user, "age": age, "date": datetime.datetime.now()})
                con.commit()
        con.close()

    def get_age(self, user):
        try:
            con = sqlite3.connect(validations_db_file)
            cur = con.cursor()
            res = cur.execute("SELECT age FROM age_data WHERE user = :id", {"id": user}).fetchone()
            con.commit()
            con.close()
            return res[0]
        except:
            return None

    def create_warning(self, user, moderator, reason="", time_range=None):
        con = sqlite3.connect(warnings_db_file)
        cur = con.cursor()
        cur.execute("INSERT INTO warnings VALUES (?, ?, ?)", [user, reason, moderator, datetime.datetime.now()])
        con.commit()
        min_date = datetime.datetime.min if time_range is None else datetime.datetime.now() - datetime.timedelta(days=time_range)
        data = cur.execute("SELECT * FROM warnings WHERE date > :date AND user = :id", {"id": user, "date": min_date}).fetchall()
        con.close()
        return len(data)
    
    def get_warnings(self, user, time_range=None):
        con = sqlite3.connect(warnings_db_file)
        cur = con.cursor()
        min_date = datetime.datetime.min if time_range is None else datetime.datetime.now() - datetime.timedelta(days=time_range)
        data = cur.execute("SELECT moderator, reason, date FROM warnings WHERE date > :date AND user = :id", {"id": user, "date": min_date}).fetchall()
        con.close()
        return data

    def add_to_offline_ping_blocklist(self, user):
        con = sqlite3.connect(offline_ping_blocklist_db_file)
        cur = con.cursor()
        try:
            cur.execute("INSERT INTO blocklist VALUES (?)", [user])
            con.commit()
        except sqlite3.IntegrityError:
            self.logger.warning(f"Duplicated user id {user} in blocklist")
        con.close()

    def remove_from_offline_ping_blocklist(self, user):
        con = sqlite3.connect(offline_ping_blocklist_db_file)
        cur = con.cursor()
        try:
            cur.execute("DELETE FROM blocklist WHERE user=:id", {"id": user})
            con.commit()
        except:
            pass
        con.close()

    def is_in_offline_ping_blocklist(self, user):
        try:
            con = sqlite3.connect(offline_ping_blocklist_db_file)
            cur = con.cursor()
            res = cur.execute("SELECT user FROM blocklist WHERE user = :id", {"id": user}).fetchone()
            con.commit()
            con.close()
            return res is not None
        except:
            return False

    def register_message(self, user, message_id, channel_id):
        con = sqlite3.connect(activity_db_file)
        cur = con.cursor()
        cur.execute("INSERT INTO messages VALUES (?, ?, ?, ?)", [user, message_id, channel_id, datetime.datetime.now()])
        con.commit()
        con.close()

    def get_messages(self, user=None, time_range=None):
        con = sqlite3.connect(activity_db_file)
        cur = con.cursor()
        min_date = datetime.datetime.min if time_range is None else datetime.datetime.now() - datetime.timedelta(days=time_range)
        if user is not None:
            data = cur.execute("SELECT * FROM messages WHERE date > :date AND user = :id", {"id": user, "date": min_date}).fetchall()
        else:
            data = cur.execute("SELECT * FROM messages WHERE date > :date", {"date": min_date}).fetchall()
        con.close()
        return data

    def try_autoblock(self, user, mod, reason):
        con = sqlite3.connect(autoblocklist_db_file)
        cur = con.cursor()
        try:
            cur.execute("INSERT INTO blocks VALUES (?, ?, ?, ?)", [user, mod, reason, datetime.datetime.now()])
            con.commit()
            res = None
        except sqlite3.IntegrityError:
            res = cur.execute("SELECT mod, reason, date FROM blocks WHERE user = :id", {"id": user}).fetchone()
        con.close()
        return res

    def is_autoblocked(self, user):
        try:
            con = sqlite3.connect(autoblocklist_db_file)
            cur = con.cursor()
            res = cur.execute("SELECT mod, reason, date FROM blocks WHERE user = :id", {"id": user}).fetchone()
            con.commit()
            con.close()
            return res 
        except:
            return None

    def _schema_dailytopten(self, date, ignorelist):
        schema = f'SELECT user, count(*) as "messages" FROM messages WHERE date(substr(date, 1, 10)) = "{date}" AND '
        schema += " AND ".join([f"channel != {channel}" for channel in ignorelist])
        schema += ' GROUP BY date(substr(date, 1, 10)), user ORDER BY date(substr(date, 1, 10)) DESC, messages DESC LIMIT 10'
        return schema

    def get_dailytopten(self, date, ignorelist):
        try:
            con = sqlite3.connect(activity_db_file)
            cur = con.cursor()
            _q = self._schema_dailytopten(date, ignorelist)
            self.logger.debug(f"get_dailytopten query: {_q}")
            res = cur.execute(_q).fetchall()
            con.commit()
            con.close()
            return res 
        except Exception as e:
            self.logger.error(f"get_dailytopten error: {e}")
            return None
