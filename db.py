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
simps_db_file = _dbfile('simps', simps_version)
aliases_version = 1
aliases_db_file = _dbfile('aliases', aliases_version)
worldmap_version = 1
worldmap_db_file = _dbfile('worldmap', worldmap_version)
nnn_2022_version = 1
nnn_2022_db_file = _dbfile('nnn_2022', nnn_2022_version)
nuts_version = 1
nuts_db_file = _dbfile('nuts', nuts_version)
attachments_version = 1
attachments_db_file = _dbfile('attachments', attachments_version)
kinks_version = 1
kinks_db_file = _dbfile('kinks', kinks_version)
kinks_visibility_version = 1
kinks_visibility_db_file = _dbfile('kinks_visibility', kinks_visibility_version)
kinks_flist_version = 1
kinks_flist_db_file = _dbfile('kinks_flist', kinks_flist_version)
member_analytics_version = 1
member_analytics_db_file = _dbfile('member_analytics', member_analytics_version)
cmds_analytics_version = 1
cmds_analytics_db_file = _dbfile('cmds_analytics', cmds_analytics_version)

sql_files = [
    validations_db_file,
    warnings_db_file,
    offline_ping_blocklist_db_file,
    activity_db_file,
    autoblocklist_db_file,
    pins_archive_db_file,
    aliases_db_file,
    worldmap_db_file,
    nnn_2022_db_file,
    nuts_db_file,
    attachments_db_file,
    kinks_db_file,
    kinks_visibility_db_file,
    kinks_flist_db_file,
    member_analytics_db_file,
    cmds_analytics_db_file
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
    aliases_db_file: ['''
            CREATE TABLE aliases (
                user int NOT NULL,
                alias TEXT,
                date TIMESTAMP
            );'''],
    worldmap_db_file: ['''
            CREATE TABLE world (
                user int NOT NULL,
                location TEXT,
                created_at TIMESTAMP,
                PRIMARY KEY (user)
            );'''],
    nnn_2022_db_file: ['''
            CREATE TABLE users (
                user int NOT NULL,
                wager int,
                created_at TIMESTAMP,
                PRIMARY KEY (user)
            );''',
            '''
            CREATE TABLE failed (
                user int NOT NULL,
                created_at TIMESTAMP,
                PRIMARY KEY (user)
            );'''],
    nuts_db_file: ['''
            CREATE TABLE nuts (
                user int NOT NULL,
                amount int NOT NULL,
                PRIMARY KEY (user)
            );'''],
    attachments_db_file: ['''
            CREATE TABLE attachments (
                user int NOT NULL,
                channel int,
                attachment int NOT NULL,
                created_at TIMESTAMP
            );'''],
    kinks_db_file: ['''
            CREATE TABLE kinks (
                user int NOT NULL,
                kink TEXT NOT NULL,
                conditional TEXT NOT NULL,
                category TEXT NOT NULL,
                rating int NOT NULL,
                updated_at TIMESTAMP,
                PRIMARY KEY (user, kink, conditional, category)
            );'''],
    kinks_visibility_db_file: ['''
            CREATE TABLE allowlist (
                user int NOT NULL,
                created_at TIMESTAMP,
                PRIMARY KEY (user)
            );'''],
    kinks_flist_db_file: ['''
            CREATE TABLE flist (
                user int NOT NULL,
                flist TEXT NOT NULL,
                updated_at TIMESTAMP,
                PRIMARY KEY (user)
            );'''],
    member_analytics_db_file: ['''
            CREATE TABLE leavers (
                user int NOT NULL,
                age int NOT NULL,
                created_at TIMESTAMP
            );''',
            '''
            CREATE TABLE joiners (
                user int NOT NULL,
                age int NOT NULL,
                created_at TIMESTAMP
            );'''],
    cmds_analytics_db_file: ['''
            CREATE TABLE commands (
                user INTEGER NOT NULL,
                channel INTEGER NOT NULL,
                command TEXT NOT NULL,
                args TEXT NOT NULL,
                failed INTEGER NOT NULL,
                created_at TIMESTAMP
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
        now = datetime.datetime.now()
        try:
            cur.execute("INSERT INTO age_data VALUES (?, ?, ?)", [user, age, now])
            con.commit()
        except sqlite3.IntegrityError:
            self.logger.warning(f"Duplicated user id {user} in age_data")
            if force:
                self.logger.debug(f"Updating {user} age in age_data -> {age}")
                cur.execute("UPDATE age_data SET age=:age, date=:date WHERE user=:id", {"id": user, "age": age, "date": now})
                con.commit()
        con.close()

        self.register_joiner(user, age, force_update=force)

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
            # self.logger.debug(f"get_dailytopten query: {_q}")
            res = cur.execute(_q).fetchall()
            con.commit()
            con.close()
            return res 
        except Exception as e:
            self.logger.error(f"get_dailytopten error: {e}")
            return None

    def _schema_activity(self, user, time_range, ignorelist):
        schema = f'SELECT date(substr(date, 1, 10)), count(*) as "messages" FROM messages WHERE user = "{user}" AND date > date("now","-{time_range} day")'
        schema += ''.join([f' AND channel != {channel}' for channel in ignorelist])
        schema += ' GROUP BY date(substr(date, 1, 10)) ORDER BY date(substr(date, 1, 10)) DESC LIMIT 14'
        return schema

    def get_activity(self, user, ignorelist, time_range=14):
        try:
            con = sqlite3.connect(activity_db_file)
            cur = con.cursor()
            _q = self._schema_activity(user, time_range, ignorelist)
            # self.logger.debug(f"get_dailytopten query: {_q}")
            res = cur.execute(_q).fetchall()
            con.commit()
            con.close()
            return res 
        except Exception as e:
            self.logger.error(f"get_activity error: {e}")
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

    def create_alias(self, user, alias):
        con = sqlite3.connect(aliases_db_file)
        cur = con.cursor()
        cur.execute("INSERT INTO aliases VALUES (?, ?, ?)", [user, alias, datetime.datetime.now()])
        con.commit()
        con.close()
    
    def get_aliases(self, user):
        try:
            con = sqlite3.connect(aliases_db_file)
            cur = con.cursor()
            res = cur.execute("SELECT alias, date FROM aliases WHERE user = :id", {"id": user}).fetchall()
            con.commit()
            con.close()
            return res
        except:
            return None

    def insert_worldmap(self, user, location):
        con = sqlite3.connect(worldmap_db_file)
        cur = con.cursor()
        try:
            cur.execute("INSERT INTO world VALUES (?, ?, ?)", [user, location, datetime.datetime.now()])
            updated = False
        except sqlite3.IntegrityError:
            cur.execute("UPDATE world SET location=:location WHERE user=:id", {"id": user, "location": location})
            updated = True
        con.commit()
        con.close()
        return updated

    def get_worldmap(self):
        try:
            con = sqlite3.connect(worldmap_db_file)
            cur = con.cursor()
            res = cur.execute("SELECT location, COUNT(location) FROM world GROUP BY location").fetchall()
            con.commit()
            con.close()
            return res
        except:
            return []
    
    def count_worldmap(self):
        try:
            con = sqlite3.connect(worldmap_db_file)
            cur = con.cursor()
            res = cur.execute("SELECT count(*) FROM world").fetchone()
            con.commit()
            con.close()
            return int(res[0])
        except:
            return 0
    
    def nnn_join(self, user, wager=False):
        try:
            con = sqlite3.connect(nnn_2022_db_file)
            cur = con.cursor()
            cur.execute("INSERT INTO users VALUES (?, ?, ?)", [user, 1 if wager else 0, datetime.datetime.now()])
            con.commit()
            con.close()
            return True
        except:
            return False

    def nnn_status(self, user):
        try:
            con = sqlite3.connect(nnn_2022_db_file)
            cur = con.cursor()
            res = cur.execute("SELECT * FROM users WHERE user=:id", {"id": user}).fetchone()
            con.commit()
            con.close()
            return res
        except:
            return None
    
    def nnn_fail(self, user):
        try:
            con = sqlite3.connect(nnn_2022_db_file)
            cur = con.cursor()
            cur.execute("INSERT INTO failed VALUES (?, ?)", [user, datetime.datetime.now()])
            con.commit()
            con.close()
            return True
        except:
            return False

    def nnn_count(self):
        try:
            con = sqlite3.connect(nnn_2022_db_file)
            cur = con.cursor()
            res1 = cur.execute("SELECT count(*) FROM users").fetchone()
            res2 = cur.execute("SELECT count(*) FROM failed").fetchone()
            con.commit()
            con.close()
            return (res1[0], res2[0])
        except:
            return (0, 0)

    def add_nut(self, user):
        con = sqlite3.connect(nuts_db_file)
        cur = con.cursor()
        try:
            cur.execute("INSERT INTO nuts VALUES (?, ?)", [user, 1])
            total = 1
        except sqlite3.IntegrityError:
            cur.execute("UPDATE nuts SET amount=amount+1 WHERE user=:id", {"id": user})
            total = cur.execute("SELECT amount FROM nuts WHERE user=:id", {"id": user}).fetchone()[0]
        con.commit()
        con.close()
        return total
    
    def create_attachment(self, user, channel, attachment):
        try:
            con = sqlite3.connect(attachments_db_file)
            cur = con.cursor()
            cur.execute("INSERT INTO attachments VALUES (?, ?, ?, ?)", [user, channel, attachment, datetime.datetime.now()])
            con.commit()
            con.close()
        except:
            pass

    def create_or_update_kink(self, user, kink, conditional, category, rating):
        con = sqlite3.connect(kinks_db_file)
        cur = con.cursor()
        try:
            cur.execute("INSERT INTO kinks VALUES (?, ?, ?, ?, ?, ?)", [user, kink, conditional, category, rating, datetime.datetime.now()])
            self.logger.debug(f"Inserted new {kink}/{conditional} for {user}: {rating}")
        except sqlite3.IntegrityError:
            cur.execute("UPDATE kinks SET rating=:rating, updated_at=:updated_at WHERE user=:id AND kink=:kink AND conditional=:conditional AND category=:category", {"id": user, "kink": kink, "conditional": conditional, "category": category, "rating": rating, "updated_at": datetime.datetime.now()})
            self.logger.debug(f"Updated {kink}/{conditional} for {user}: {rating}")
        con.commit()
        con.close()

    def get_kinks(self, user, unknown):
        con = sqlite3.connect(kinks_db_file)
        cur = con.cursor()
        res = cur.execute("SELECT * FROM kinks WHERE user=:user AND rating!=:unknown", {'user': user, 'unknown': unknown}).fetchall()
        con.commit()
        con.close()
        return res

    def iterate_kinks(self, user, ratings):
        con = sqlite3.connect(kinks_db_file)
        cur = con.cursor()
        for rating in ratings:
            yield (rating, cur.execute("SELECT kink, conditional, category FROM kinks WHERE user=:user AND rating=:rating", {'user': user, 'rating': rating}).fetchall())
        con.close()

    def clear_kinks(self, user):
        con = sqlite3.connect(kinks_db_file)
        cur = con.cursor()
        cur.execute("DELETE FROM kinks WHERE user=:user", {'user': user})
        con.commit()
        con.close()

    def get_kink(self, user, kink, conditional, category):
        con = sqlite3.connect(kinks_db_file)
        cur = con.cursor()
        res = cur.execute("SELECT rating FROM kinks WHERE user=:user AND kink=:kink AND conditional=:conditional AND category=:category", {'user': user, "kink": kink, "conditional": conditional, "category": category}).fetchone()
        con.commit()
        con.close()
        return None if (res is None or len(res) == 0) else int(res[0])

    def set_kinklist_visibility(self, user, visibilty):
        con = sqlite3.connect(kinks_visibility_db_file)
        cur = con.cursor()
        if visibilty:
            try:
                cur.execute("INSERT INTO allowlist VALUES (?, ?)", [user, datetime.datetime.now()])
            except sqlite3.IntegrityError: # Already publicised
                pass
        else:
            cur.execute("DELETE FROM allowlist WHERE user=:user", {"user": user})
        con.commit()
        con.close()

    def get_kinklist_visibility(self, user):
        con = sqlite3.connect(kinks_visibility_db_file)
        cur = con.cursor()
        res = cur.execute("SELECT * FROM allowlist WHERE user=:user", {"user": user}).fetchone()
        con.commit()
        con.close()
        return res is not None

    def create_or_update_flist(self, user, flist):
        con = sqlite3.connect(kinks_flist_db_file)
        cur = con.cursor()
        try:
            cur.execute("INSERT INTO flist VALUES (?, ?, ?)", [user, flist, datetime.datetime.now()])
        except sqlite3.IntegrityError:
            cur.execute("UPDATE flist SET flist=:flist, updated_at=:updated_at WHERE user=:id", {"id": user, "flist": flist, "updated_at": datetime.datetime.now()})
        con.commit()
        con.close()

    def _last_leave(self, user, cur: sqlite3.Cursor):
        data = cur.execute("SELECT created_at FROM leavers WHERE user = :id ORDER BY date(created_at) DESC LIMIT 1", {"id": user}).fetchone()
        return data and datetime.datetime.strptime(data[0], "%Y-%m-%d %H:%M:%S.%f")

    def _last_join(self, user, cur: sqlite3.Cursor):
        data = cur.execute("SELECT created_at FROM joiners WHERE user = :id ORDER BY date(created_at) DESC LIMIT 1", {"id": user}).fetchone()
        return data and datetime.datetime.strptime(data[0], "%Y-%m-%d %H:%M:%S.%f")

    def register_joiner(self, user, age=-1, force_update=False):
        now = datetime.datetime.now()
        con = sqlite3.connect(member_analytics_db_file)
        cur = con.cursor()
        _lj = self._last_join(user, cur)
        _ll = self._last_leave(user, cur)
        if not _lj or (_ll and _ll > _lj):
            cur.execute("INSERT INTO joiners VALUES (?, ?, ?)", [user, age, now])
        elif force_update: # If we get an updated age
            cur.execute("UPDATE joiners SET age=:age WHERE user=:user AND created_at=:created_at", {"user": user, "age": age, "created_at": _lj})
        con.commit()
        con.close()

    def register_leaver(self, user):
        con = sqlite3.connect(member_analytics_db_file)
        cur = con.cursor()
        age = cur.execute("SELECT age FROM joiners WHERE user = :id ORDER BY date(created_at) DESC LIMIT 1", {"id": user}).fetchone()
        age = age and age[0] or self.get_age(user) or -1
        cur.execute("INSERT INTO leavers VALUES (?, ?, ?)", [user, age, datetime.datetime.now()])
        con.commit()
        con.close()

    def register_command(self, user, command, channel, args='', failed=False):
        self.logger.debug(f"Register command user={user}, command={command}, channel={channel}, args={args}, failed={failed}")
        con = sqlite3.connect(cmds_analytics_db_file)
        cur = con.cursor()
        cur.execute("INSERT INTO commands VALUES (?, ?, ?, ?, ?, ?)", [user, channel, command, args, 1 if failed else 0, datetime.datetime.now()])
        con.commit()
        con.close()
