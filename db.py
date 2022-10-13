import datetime
import os
import sqlite3

import botlogger

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
pins_archive_version = 2
pins_archive_db_file = _dbfile('pins_archive', pins_archive_version)
simps_version = 1
simps_db_file = _dbfile('simps', autoblocklist_version)

sql_files = [
    validations_db_file,
    warnings_db_file,
    offline_ping_blocklist_db_file,
    activity_db_file,
    autoblocklist_db_file,
    pins_archive_db_file
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
                channel int NOT NULL,
                date TIMESTAMP
            );'''],
    autoblocklist_db_file: ['''
            CREATE TABLE blocks (
                user int NOT NULL,
                mod int NOT NULL,
                reason TEXT,
                date TIMESTAMP,
                PRIMARY KEY (user)
            );'''],
    pins_archive_db_file: ['''
            CREATE TABLE pins (
                original_message int NOT NULL,
                archived_message int NOT NULL,
                date TIMESTAMP
            );'''],
    simps_db_file: ['''
            CREATE TABLE simps (
                simp int NOT NULL,
                simp_for int NOT NULL,
                starred int NOT NULL,
                date TIMESTAMP
            );'''],
}

class database:
    def __init__(self, max_leniency):
        self.logger = botlogger.get_logger(__name__)
        # Initialize db
        for db_file in schemas:
            self.logger.debug(f"Checking db file '{db_file}'")
            if not os.path.exists(db_file):
                self.logger.info(f"CREATING db file '{db_file}'")
                try:
                    con = sqlite3.connect(db_file)
                    cur = con.cursor()
                    for table_schema in schemas[db_file]:
                        cur.execute(table_schema)
                    con.commit()
                    con.close()
                except:
                    self.logger.error(f"[__init__] Error creating {db_file}")
        
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

    def register_pin(self, message_id, pin_id):
        con = sqlite3.connect(pins_archive_db_file)
        cur = con.cursor()
        cur.execute("INSERT INTO pins VALUES (?, ?, ?)", [message_id, pin_id, datetime.datetime.now()])
        con.commit()
        con.close()

    def is_pinned(self, message_id):
        try:
            con = sqlite3.connect(pins_archive_db_file)
            cur = con.cursor()
            res = cur.execute("SELECT * FROM pins WHERE original_message = :id", {"id": message_id}).fetchone()
            con.commit()
            con.close()
            return res is not None
        except:
            return False

    def is_simping(self, simp, simp_for, cur=None):
        _close = False
        if cur is None:
            con = sqlite3.connect(simps_db_file)
            cur = con.cursor()
            _close = True
        res = cur.execute("SELECT * FROM simps WHERE simp = :simp AND simp_for = :simp_for", {"simp": simp, "simp_for": simp_for}).fetchone()
        if _close:
            con.commit()
            con.close()
        self.logger.debug(f"Is simping {simp}x{simp_for}: {res}")
        return res

    def start_simping(self, simp, simp_for):
        con = sqlite3.connect(simps_db_file)
        cur = con.cursor()
        res = self.is_simping(simp, simp_for, cur=cur)
        if res is None:
            cur.execute("INSERT INTO simps VALUES (?, ?, 0, ?)", [simp, simp_for, datetime.datetime.now()])
        con.commit()
        con.close()
        return res is None

    def stop_simping(self, simp, simp_for):
        con = sqlite3.connect(simps_db_file)
        cur = con.cursor()
        res = self.is_simping(simp, simp_for, cur=cur)
        if res is not None:
            cur.execute("DELETE FROM simps WHERE simp=:simp AND simp_for=:simp_for", {"simp": simp, "simp_for": simp_for})
        con.commit()
        con.close()
        return res is not None

    def star_simping(self, simp, simp_for):
        res = self._update_simping(simp, simp_for, 1) # Set to true
        if res is None: # Was not simping
            return (False, False)
        if res[2] == 1: # Was already true
            return (True, False)
        return (True, True)

    def unstar_simping(self, simp, simp_for):
        res = self._update_simping(simp, simp_for, 0) # Set to false
        if res is None: # Was not simping
            return (False, False)
        if res[2] == 0: # Was already false
            return (True, False)
        return (True, True)

    def _update_simping(self, simp, simp_for, new_state):
        con = sqlite3.connect(simps_db_file)
        cur = con.cursor()
        res = self.is_simping(simp, simp_for, cur=cur)
        if res is not None:
            cur.execute("UPDATE simps SET starred=:new_state WHERE simp=:simp AND simp_for = simp_for", {"simp": simp, "simp_for": simp_for, "new_state": new_state})
        con.commit()
        con.close()
        self.logger.debug(f"Update_simping: {simp} x {simp_for} - {new_state}: {res}")
        return res

    def get_simps(self, simp_for):
        try:
            con = sqlite3.connect(simps_db_file)
            cur = con.cursor()
            res = cur.execute("SELECT simp, starred FROM simps WHERE simp_for = :id", {"id": simp_for}).fetchall()
            con.commit()
            con.close()
            return res
        except:
            return None