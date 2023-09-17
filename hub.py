import serial
import time
from datetime import datetime
import sqlite3
import requests
import json

env = dict(map(lambda x:(x.strip().split("=")[0].strip(), x.strip().split("=")[1].strip()), map(lambda x:x.split("#")[0] if "=" in x.split("#")[0] else "None=None", open("./.env", "r").read().strip().split("\n"))))

HUB_NAME = env["HUB_NAME"]
UPDATE_SERVER_POLL_FREQUENCY = 2
CLOUD_IP = env["CLOUD_IP"]
HEADERS = {'content-type': 'application/json'}
BASE_URL = 'http://{}:5000/api'.format(CLOUD_IP)

# ser = serial.Serial(port='/dev/ttyACM0', baudrate=115200, timeout=1)

COM_PORT = env["COM_PORT"]
ser = serial.Serial(port=COM_PORT, baudrate=115200)
ser.timeout = 1

def create_db():
    try: 
        mydb = sqlite3.connect("processor.db")
        mycursor = mydb.cursor()
        query = "CREATE TABLE hubdb(datetime TIMESTAMP, sensor CHAR, reading NUMERIC)"
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
        print("response {}".format(response.decode('utf-8').strip()))
        return response.decode('utf-8').strip()
    return None

def poll_microbit_data(valid_sensors):
    # Polls for the temperature of the microbits. Returns a dictionary
    # flushes data
    time.sleep(1)
    while waitResponse():
        continue
    sendCommand("pol")
    time.sleep(0.5)
    sendCommand("pol")
    time.sleep(0.5)
    sendCommand("pol")
    time.sleep(0.5)
    print("Polling sensor data...")
    time.sleep(3)
    poll_result = dict() 
    dat = waitResponse()
    while dat:
        if dat is None: break
        # need to check data
        if dat[6:8] not in  ["we", "hi"] or len(dat) > 23 or len(dat) < 9: 
            dat = waitResponse()
            continue
        #  Do store logic
        binName = dat[0:2]
        dtype = dat[6:8]
        if binName not in valid_sensors:
            pass
        value = float(dat[8:])
        
        if binName in poll_result:
            poll_result[binName][dtype] = value
        else:
            poll_result[binName] = {
                dtype: value,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        dat = waitResponse()
        time.sleep(0.3)

    print("Polling Completed!")
    return poll_result

def publish_local_sensor_to_server(new_data):
    results = requests.put(BASE_URL + "/serverData/" + HUB_NAME, 
        headers = HEADERS, 
        data = json.dumps(new_data), 
        timeout=5).json()
    
    return results["sensors"]

def get_token():
    try:
        return open("./SECRET", "r").read()
    except:
        return None

def initialize_connection_to_cloud():
    payload = requests.put(BASE_URL + "/assetFacility/initializeHub", json={"processorName":HUB_NAME}).json()
    while "token" not in payload:
        payload = requests.put(BASE_URL + "/assetFacility/initializeHub", json={"processorName":HUB_NAME}).json()
    return payload["token"]
    
def save_token(token):
    f = open("SECRET", "w")
    f.write(token)

if __name__ == "__main__":
    create_db()
    token = get_token()
    if token is None:
        while token is None:
            token = initialize_connection_to_cloud()
        time.sleep(5)
        save_token(token)

    temp_buffer = []
    valid_sensors = []
    mydb = sqlite3.connect("processor.db")
    try:
        print("Starting program...\n")
        polls = 0
        
        while True:
            polls += 1
            sensor_values = poll_microbit_data(valid_sensors)
            mycursor = mydb.cursor()
            fire_alert = False
            
            for microbit, data in sensor_values.items():
                weight = height = 0.0
                if "we" in data:
                    weight = data["we"]
                if "hi" in data:
                    height = data["hi"]
                timestamp = data["time"]

                query = 'INSERT INTO hubdb(datetime, microbit, weight, height) VALUES (?, ?, ?, ?)'
                temp_buffer.append([timestamp, microbit, weight, height])
                val = (timestamp, microbit, weight, height)
                print("adding ", val)
                mycursor.execute(query, val)

            mydb.commit()
            print("Inserted records into database!")

            if polls >= UPDATE_SERVER_POLL_FREQUENCY:
                valid_sensors = publish_local_sensor_to_server(temp_buffer) # Must use token 
                print("Success!")
                polls = 0

            temp_buffer = []
            time.sleep(3)

    except KeyboardInterrupt:
        if ser.is_open:
            ser.close()
        print("Program terminated!")
