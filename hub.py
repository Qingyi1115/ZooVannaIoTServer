import serial
import time
from datetime import datetime
import sqlite3
import requests
import json
import hashlib

env = dict(map(lambda x:(x.strip().split("=")[0].strip(), x.strip().split("=")[1].strip()), map(lambda x:x.split("#")[0] if "=" in x.split("#")[0] else "None=None", open("./.env", "r").read().strip().split("\n"))))

HUB_NAME = env["HUB_NAME"]
UPDATE_SERVER_POLL_FREQUENCY = 2
CLOUD_IP = env["CLOUD_IP"]
CLOUD_PORT = env["CLOUD_PORT"]
HEADERS = {'content-type': 'application/json'}
BASE_URL = 'http://{}:{}/api'.format(CLOUD_IP, CLOUD_PORT)

# ser = serial.Serial(port='/dev/ttyACM0', baudrate=115200, timeout=1)

COM_PORT = env["COM_PORT"]
ser = serial.Serial(port=COM_PORT, baudrate=115200)
ser.timeout = 1

def attempt_create_db():
    try: 
        mydb = sqlite3.connect("processor.db")
        mycursor = mydb.cursor()
        query = "CREATE TABLE sensordb(readingDate TIMESTAMP, sensor CHAR, reading NUMERIC, sent INTEGER)"
        mycursor.execute(query)
        mydb.commit()
        mydb.close()
    except:
        mydb.close()

def sendCommand(command:str):
    command = command + '\n'
    ser.write(str.encode(command))

def waitResponse():
    response = ser.readline()
    if response is not None and len(response) > 0:
        return response.decode('utf-8').strip()
    return None

def poll_sensor_data(valid_sensors):
    if len(valid_sensors) == 0:
        return dict() 
    while waitResponse():
        time.sleep(0.5)
        continue
    sendCommand("pol")
    time.sleep(0.5)
    sendCommand("pol")
    time.sleep(0.5)
    print("Polling sensor data...")
    time.sleep(2)
    poll_result = dict() 
    dat = waitResponse()
    while dat:
        if dat is None: break
        # need to check data
        sensorName = dat.split("|")[0]
        if sensorName not in  valid_sensors: 
            dat = waitResponse()
            continue
        #  Do store logic
        try:
            value = float(dat.split("|")[1])
        except:
            continue

        if sensorName in poll_result:
            poll_result[sensorName]["reading"] = poll_result[sensorName]["reading"]* 0.6 + value*0.4
        else:
            poll_result[sensorName] = {
                "reading": value,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        dat = waitResponse()
        time.sleep(0.3)

    print("Polling Completed!")
    return poll_result

def publish_local_sensor_to_server(valid_sensors, token, conn):
    mycursor = conn.cursor()
    mycursor.execute('SELECT readingDate, sensor, reading FROM sensordb WHERE sent = 0')
    results = mycursor.fetchall()
    
    json_payload = dict()
    for result in results:
        if result[1] not in valid_sensors: continue
        if result[1] in json_payload:
            json_payload[result[1]].append({
                "readingDate": result[0],
                "reading" : result[2]
            })
        else:
            json_payload[result[1]] = [{
                "readingDate": result[0],
                "reading" : result[2]
            }]

    json_payload_string = json.dumps(json_payload)
    hash_obj = hashlib.sha256()
    hash_obj.update((json_payload_string + token).encode())

    new_valid_sensors = requests.post(BASE_URL + "/assetFacility/pushSensorReadings/" + HUB_NAME, 
        headers = HEADERS, 
        json = {
        "jsonPayloadString" : json_payload_string,
        "sha256" : hash_obj.hexdigest()
        }, 
        timeout=5).json()
    
    if "sensors" in new_valid_sensors:
        mycursor.execute('UPDATE sensordb SET sent = 1 WHERE sent = 0')
        valid_sensors = new_valid_sensors["sensors"]
        print("Sent data to server.")
    else: print("Unable to connect to hub!")
    return valid_sensors
    

def get_token():
    try:
        return None if len(open("./SECRET", "r").read().strip()) == 0 else open("./SECRET", "r").read().strip()
    except:
        return None

def initialize_connection_to_cloud():
    payload = requests.put(BASE_URL + "/assetFacility/initializeHub", json={"processorName":HUB_NAME}).json()
    return payload["token"] if "token" in payload else None
    
def save_token(token):
    f = open("SECRET", "w")
    f.write(token)

if __name__ == "__main__":
    attempt_create_db()
    token = get_token()
    if token is None:
        while token is None:
            print("Initializing connection with cloud!")
            token = initialize_connection_to_cloud()
            print("Token obtained results: ", token)
            if token: break
            time.sleep(3)
        save_token(token)

    print("Starting program...\n")
    temp_buffer = []
    mydb = sqlite3.connect("processor.db")
    valid_sensors = publish_local_sensor_to_server([], token, mydb)
    try:
        polls = 0
        while True:
            polls += 1
            sensor_values = poll_sensor_data(valid_sensors)
            mycursor = mydb.cursor()
            
            for sensor, data in sensor_values.items():
                reading = data["reading"]
                readingDate = data["time"]
                query = 'INSERT INTO sensordb(readingDate, sensor, reading, sent) VALUES (?, ?, ?, ?)'
                val = (readingDate, sensor, reading, 0)
                mycursor.execute(query, val)

            mydb.commit()
            if len(sensor_values): print("Inserted records into database!")
            else: print("No data")

            if polls >= UPDATE_SERVER_POLL_FREQUENCY:
                valid_sensors = publish_local_sensor_to_server(valid_sensors, token, mydb) # Must use token 
                polls = 0

            temp_buffer = []
            time.sleep(0.5)

    except KeyboardInterrupt:
        if ser.is_open:
            ser.close()
        print("Program terminated!")
