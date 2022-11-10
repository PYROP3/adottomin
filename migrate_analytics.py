import db
import sqlite3

if __name__ == "__main__":
    sql = db.database(None)

    _orig = db.validations_db_file
    _into = db.member_analytics_db_file

    orig = sqlite3.connect(_orig)
    into = sqlite3.connect(_into)
    
    orig_cursor = orig.cursor()
    into_cursor = into.cursor()

    # data = orig_cursor.execute("SELECT * FROM age_data").fetchall()
    # for user, age, created_at in data:
    #     into_cursor.execute("INSERT INTO joiners VALUES (?, ?, ?)", [user, age, created_at])

    data = orig_cursor.execute("SELECT * FROM age_data where age < 18").fetchall()
    print(f"migrating {len(data)} datapoints")
    for user, age, created_at in data:
        into_cursor.execute("INSERT INTO leavers VALUES (?, ?, ?)", [user, age, created_at])

    into.commit()
    
    orig.close()
    into.close()