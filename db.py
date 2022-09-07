import datetime
import os
import sqlite3

bot_home = os.getenv("BOT_HOME") or os.getcwd()
validations_version = 1
validations_db_file = bot_home + f'/validations_v{validations_version}.db'
warnings_version = 2
warnings_db_file = bot_home + f'/warnings_v{warnings_version}.db'

class database:
    def __init__(self, max_leniency, logger):
        # Initialize db
        logger.debug(f"Checking db file '{validations_db_file}'")
        if not os.path.exists(validations_db_file):
            logger.info(f"CREATING db file '{validations_db_file}'")
            con = sqlite3.connect(validations_db_file)
            cur = con.cursor()
            cur.execute('''
            CREATE TABLE validations (
                user int NOT NULL,
                leniency int NOT NULL,
                greeting int NOT NULL,
                PRIMARY KEY (user)
            );''')
            cur.execute('''
            CREATE TABLE kicks (
                user int NOT NULL,
                PRIMARY KEY (user)
            );''')
            cur.execute('''
            CREATE TABLE age_data (
                user int NOT NULL,
                age int NOT NULL,
                date TIMESTAMP,
                PRIMARY KEY (user)
            );''')
            con.commit()
            con.close()

        if not os.path.exists(warnings_db_file):
            logger.info(f"CREATING db file '{warnings_db_file}'")
            con = sqlite3.connect(warnings_db_file)
            cur = con.cursor()
            cur.execute('''
            CREATE TABLE warnings (
                user int NOT NULL,
                moderator int NOT NULL,
                reason TEXT,
                date TIMESTAMP
            );''')
            con.commit()
            con.close()
        
        self.logger = logger
        self.max_leniency = max_leniency

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
        cur.execute("INSERT INTO validations VALUES (?, ?, ?)", [user, self.max_leniency, greeting_id])
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
