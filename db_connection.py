# db_connection.py

import pymysql


import pymysql

def get_db(database="MeirNiv$default"):
    conn = pymysql.connect(
        host="MeirNiv.mysql.pythonanywhere-services.com",
        user="MeirNiv",
        password="mayyam28",
        database=database,
        cursorclass=pymysql.cursors.DictCursor,
    )
    return conn