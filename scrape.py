import itertools
import requests
import sqlite3
import sys
import time

raw_endpoints = ['truth', 'dare', 'wyr', 'nhie', 'paranoia']
endpoints = itertools.cycle(raw_endpoints)
endpoint_hits = {}

api = 'https://api.truthordarebot.xyz/v1/'

con = sqlite3.connect("/home/nyx/git/adottomin/data/truthordare_questions.db")
cur = con.cursor()
try:
    cur.execute("""CREATE TABLE questions (
                    q_id TEXT,
                    q_type TEXT,
                    q_rating TEXT,
                    q_question TEXT,
                    q_translations TEXT,
                    PRIMARY KEY (q_id)
                );""")
except:
    pass
con.commit()
# con.close()

total_hits = 0
for endpoint in raw_endpoints:
    endpoint_hits[endpoint] = int(cur.execute("SELECT COUNT(*) FROM questions WHERE q_type=:type", {'type': endpoint.upper()}).fetchone()[0])
    total_hits += endpoint_hits[endpoint]

queries = 0
run_hits = 0
try:
    while True:
        queries += 1
        r = requests.get(api + next(endpoints))
        if r.status_code != 200:
            print(f"Exiting {r.status_code}")
            con.commit()
            con.close()
            exit(0)
        data = r.json()
        try:
            cur.execute("INSERT INTO questions VALUES (?, ?, ?, ?, ?)", [data['id'], data['type'], data['rating'], data['question'], str(data['translations'])])
            con.commit()
            run_hits += 1
            endpoint_hits[data['type'].lower()] += 1
            total_hits += 1
        except sqlite3.IntegrityError:
            #print(f"\nReceived duplicate id {data['id']} for type {data['type']}: {data['question']}")
            pass
        sys.stdout.write(f'\r{run_hits} hits this run / {queries} queries | ' + ' / '.join([f'{endpoint_hits[endpoint]} {endpoint}s' for endpoint in raw_endpoints]) + f' | {total_hits} hits in total')
        sys.stdout.flush()
        time.sleep(1)
except KeyboardInterrupt:
    print(f"\nExiting gracefully")
    con.commit()
    con.close()
    exit(0)