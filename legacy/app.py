from flask import Flask
from flask import request, session, redirect, url_for, g
from datetime import datetime
import json
from flask_mysqldb import MySQL
# import MySQLdb.cursors
import re

env = dict(map(lambda x:(x.strip().split("=")[0].strip(), x.strip().split("=")[1].strip()), map(lambda x:x.split("#")[0] if "=" in x.split("#")[0] else "None=None", open("./.env", "r").read().strip().split("\n"))))

app = Flask(__name__)
app.config["DEBUG"] = True
 
# mysql = MySQL(app)
# app.secret_key = env["SECRET_KEY"]

def get_db():

    mysql = MySQL()
    app.config['MYSQL_HOST'] = env["MYSQL_HOST"]
    app.config['MYSQL_USER'] = env["MYSQL_USER"]
    app.config['MYSQL_PASSWORD'] = env["MYSQL_PASSWORD"]
    app.config['MYSQL_DB'] = env["MYSQL_DB"]
    mysql.init_app(app)
    dbcon = mysql.connect()
    return dbcon

@app.route('/', methods=["GET", "POST"])
def index():
    db_conn = get_db()
    cursor = db_conn.cursor()
    #... do my SQL stuff here ...#

 
    cursor.execute(''' CREATE TABLE table_name(field1, field2) ''')
    cursor.execute(''' INSERT INTO table_name VALUES(v1,v2) ''')
    cursor.execute(''' DELETE FROM table_name ''')
    
    cursor.commit()
    cursor.close()
    return 


@app.route('/api/serverData/sensorData/<hubID>', methods=['POST'])
def sensorData(hubID):
    return
    # sensors_data = request.json()
    # mycursor = mysql.connection.cursor()

    # for microbit, sensor in sensors_data:
    #     query = 'INSERT INTO cloudData (hubid, datetime, microbit, temperature, light) VALUES (%s, %s, %s, %s, %s)'
    #     val = (hubID, sensor[2], microbit, sensor[0], sensor[1])
    #     mycursor.execute(query, val)
