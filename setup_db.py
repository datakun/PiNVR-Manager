import sqlite3

db = sqlite3.connect("pinvr.db")
cursor = db.cursor()

cursor.execute("CREATE TABLE if not exists camera_list( \
                id INTEGER PRIMARY KEY, \
                camera_name TEXT, \
                root_dir TEXT, \
                server_port INTEGhER, \
                stream_url TEXT \
                );")


cursor.execute("CREATE TABLE if not exists user( \
                username TEXT PRIMARY KEY, \
                password TEXT \
                );")

db.commit()
