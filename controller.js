function substring (inputString: string, start: number, end: number) {
    length = Math.min(inputString.length, end)
    i = start
    while (i < length) {
        result = "" + result + [0][i++]
    }
    return result
}
input.onButtonPressed(Button.A, function () {
    basic.showString(sensorName)
})
function getSensorValues () {
    if (sensorType == "TEMP") {
        return input.temperature()
    } else if (sensorType == "LIGH") {
        return input.lightLevel()
    }
    return null
}
radio.onReceivedValue(function (sender, val) {
    if (testingSerial) {
        serial.writeLine("radio rcv key, val: " + sender + ", " + val)
    }
    if (writeSerial) {
        serial.writeLine("" + sender + "|" + val)
    }
    return 0;
})
radio.onReceivedString(function (receivedString) {
    if (testingSerial) {
        serial.writeLine("radio rcv str: " + receivedString)
    }
    switch (receivedString) {
        case "pol":

            let value2 = getSensorValues()
            radio.sendValue(sensorName, value2)
            break;
    }
})
serial.onDataReceived(serial.delimiters(Delimiters.NewLine), function () {
    data = serial.readLine()
    radio.sendString(data)
    switch (data) {
        case "pol":
            let value = getSensorValues()
            serial.writeLine(sensorName+ "|" + value)
            break;
    }
})
let data = ""
let result = ""
let i = 0
let length = 0
let sensorName: string
let sensorType: string
let writeSerial: boolean
let testingSerial: boolean
// ascii names
sensorName = "light1"
sensorType = "LIGH"
writeSerial = true
testingSerial = false
radio.setGroup(212)
radio.setTransmitPower(7)
basic.showIcon(IconNames.Yes)
basic.forever(function () {
	
})
