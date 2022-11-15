import argparse
import datetime
import os
import shutil
import sqlite3
import subprocess

import db

parser = argparse.ArgumentParser()
parser.add_argument('location', type=str)

args = parser.parse_args()

dbfile = os.path.join(args.location, 'backup_main_table.db')

def create_main_table():
    if os.path.exists(dbfile): return
    print("create_main_table")
    con = sqlite3.connect(dbfile)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE backups (
            bkp_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file TEXT NOT NULL,
            hash TEXT NOT NULL,
            created_at DATETIME
        );
    """)
    con.commit()
    con.close()

def backup_needed():
    con = sqlite3.connect(dbfile)
    cur = con.cursor()
    for file in db.sql_files:
        qual = os.path.split(file)[-1]
        print(f"{file} qual={qual}")
        md5 = subprocess.run(["md5sum", file], capture_output=True).stdout.split()[0].decode(encoding='UTF-8')
        last_md5 = cur.execute("SELECT hash FROM backups WHERE file=:f ORDER BY bkp_id DESC LIMIT 1", {'f': qual}).fetchone()
        if not last_md5 or last_md5 != md5:
            print(f"backup_needed {file}")
            shutil.copy2(file, os.path.join(args.location, 'tables', f'{md5}_{qual}'))
            cur.execute("INSERT INTO backups (file, hash, created_at) VALUES (?, ?, ?)", [qual, md5, datetime.datetime.now()])
            con.commit()
    con.close()

if __name__ == '__main__':
    create_main_table()
    backup_needed()