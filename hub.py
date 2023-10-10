import serial
import time
from datetime import datetime
import sqlite3
import requests
import json
import hashlib
import cv2
from tflite_support.task import core
from tflite_support.task import processor
from tflite_support.task import vision
import utils
from multiprocessing import Process, Queue
import sys

env = dict(map(lambda x:(x.strip().split("=")[0].strip(), x.strip().split("=")[1].strip()), map(lambda x:x.split("#")[0] if "=" in x.split("#")[0] else "None=None", open("./.env", "r").read().strip().split("\n"))))

HUB_NAME = env["HUB_NAME"]
UPDATE_SERVER_POLL_FREQUENCY = 2
CLOUD_IP = env["CLOUD_IP"]
CLOUD_PORT = env["CLOUD_PORT"]
HEADERS = {'content-type': 'application/json'}
BASE_URL = 'http://{}:{}/api'.format(CLOUD_IP, CLOUD_PORT)

CAMERA_NAMES = env["CAMERA_NAMES"].split(",") if "CAMERA_NAMES" in env else []
CAMERA_IDS = env["CAMERA_IDS"].split(",") if "CAMERA_IDS" in env else []
MAX_CAMERA_DETECTION_WINDOW = 2

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

def poll_sensor_data(valid_sensors, radioGroup):
    if len(valid_sensors) == 0:
        return dict() 
    
    # Broadcast radio group and sensors
    for sensor in valid_sensors:
        sendCommand("bct"+sensor+"|"+str(radioGroup))
        time.sleep(0.1)

    # Clears buffer
    while (test := waitResponse()):
        # print("test",test)
        time.sleep(0.1)
        continue
    sendCommand("pol")
    time.sleep(0.5)
    sendCommand("pol")
    time.sleep(0.5)
    print("Polling sensor data...")
    time.sleep(1)
    poll_result = dict() 
    dat = waitResponse()
    while dat:
        if dat is None: break
        # print("dat",dat)
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

    res = requests.post(BASE_URL + "/assetFacility/pushSensorReadings/" + HUB_NAME, 
        headers = HEADERS, 
        json = {
        "jsonPayloadString" : json_payload_string,
        "sha256" : hash_obj.hexdigest()
        }, 
        timeout=5).json()
    
    if "sensors" in res:
        mycursor.execute('UPDATE sensordb SET sent = 1 WHERE sent = 0')
        valid_sensors = res["sensors"]
        print("Sent data to server.")
    else: print("Unable to connect to hub!")
    return valid_sensors, res["radioGroup"] if "radioGroup" in res else 255
    

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

def camera_CV_AI(
        output_queue: Queue,
        output_img: str,
        model: str='efficientdet_lite0.tflite', 
        camera_id: int=0, 
        width: int=640, 
        height: int=480, 
        num_threads: int=4,
        enable_edgetpu: bool=False,
        show_fps: bool = True) -> None:
    try:
        # Variables to calculate FPS
        counter, fps = 0, 0
        start_time = time.time()

        # Start capturing video input from the camera
        cap = cv2.VideoCapture(camera_id)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        # Visualization parameters
        row_size = 20  # pixels
        left_margin = 24  # pixels
        text_color = (0, 0, 255)  # red
        font_size = 1
        font_thickness = 1
        fps_avg_frame_count = 10

        #   detection_options DetectionOptions(score_threshold=0.3, category_name_allowlist=None, category_name_denylist=None, display_names_locale=None, max_results=3)
        #   base_options BaseOptions(file_name='efficientdet_lite0.tflite', file_content=None, num_threads=4, use_coral=False)

        # Initialize the object detection model
        base_options = core.BaseOptions(
            file_name=model, use_coral=enable_edgetpu, num_threads=num_threads)
        detection_options = processor.DetectionOptions(category_name_allowlist=["person"],
            max_results=20, score_threshold=0.2)
        options = vision.ObjectDetectorOptions(
            base_options=base_options, detection_options=detection_options)
        detector = vision.ObjectDetector.create_from_options(options)

        # Continuously capture images from the camera and run inference
        while cap.isOpened():
            success, image = cap.read()
            if not success:
                sys.exit('ERROR: Unable to read from webcam. Please verify your webcam settings.')

            counter += 1
            image = cv2.flip(image, 1)

            # Convert the image from BGR to RGB as required by the TFLite model.
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

            # Create a TensorImage object from the RGB image.
            input_tensor = vision.TensorImage.create_from_array(rgb_image)

            # Run object detection estimation using the model.
            detection_result = detector.detect(input_tensor)

            if output_queue.full(): output_queue.get()
            output_queue.put(len(detection_result))

            # Draw keypoints and edges on input image
            image = utils.visualize(image, detection_result)

            if counter % fps_avg_frame_count == 0:
                end_time = time.time()
                fps = fps_avg_frame_count / (end_time - start_time)
                start_time = time.time()

            if show_fps:
                fps_text = 'FPS = {:.2f}'.format(fps)
                text_location = (left_margin, row_size)
                cv2.putText(image, fps_text, text_location, cv2.FONT_HERSHEY_PLAIN,
                            font_size, text_color, font_thickness)

            cv2.imwrite(output_img + '.jpeg', image)
    except:
        cap.release()
        cv2.destroyAllWindows()

def main_function(camera_reading_queues:list[Queue]):
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
    valid_sensors, radioGroup = publish_local_sensor_to_server([], token, mydb)
    try:
        polls = 0
        while True:
            polls += 1
            sensor_values = poll_sensor_data(valid_sensors, radioGroup)
            for q_c in camera_reading_queues:
                if q_c[1] in valid_sensors:
                    reading = q_c[0].get()
                    while not q_c[0].empty():
                        reading = max(reading , q_c[0].get())
                    sensor_values[q_c[1]] = {
                        "reading" : reading,
                        "time" : datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
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
                valid_sensors, radioGroup = publish_local_sensor_to_server(valid_sensors, token, mydb) # Must use token 
                print("valid_sensors, radioGroup",valid_sensors, radioGroup)
                polls = 0

            temp_buffer = []
            time.sleep(0.5)

    except KeyboardInterrupt:
        if ser.is_open:
            ser.close()
        print("Program terminated!")


if __name__ == "__main__":
    queues = []
    if len(CAMERA_NAMES) != len(CAMERA_IDS): sys.exit("Number of camera id does not match number of cameras! Please check your env file settings! Hint: seperated by commas.")
    for i in range(len(CAMERA_NAMES)):
        queue = Queue(maxsize=MAX_CAMERA_DETECTION_WINDOW)
        queues.append((queue, CAMERA_NAMES[i]))
        process = Process(target=camera_CV_AI, kwargs={"output_queue":queue, "output_img":CAMERA_NAMES[i], "camera_id":CAMERA_IDS[i]}, daemon=False)
        process.start()
    main_function(queues)

