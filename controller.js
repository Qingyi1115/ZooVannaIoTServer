function substring(inputString: string, start: number, end: number) {
    length = Math.min(inputString.length, end)
    i = start
    result = ""
    while (i < length) {
        result = result + inputString[i++]
    }
    return result
}
input.onButtonPressed(Button.A, function () {
    basic.showString(sensorName)
})
function getSensorValues() {
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
    cmd = substring(receivedString, 0, 3)
    params = substring(receivedString, 3, receivedString.length)
    switch (cmd) {
        case "pol":
            if (radioGroup == 255) {
                break;
            }
            let value = getSensorValues()
            radio.sendValue(sensorName, value)
            break;
        case "bct":
            let sensorRadio = params.split("|")
            if (sensorName == sensorRadio[0]) {
                radioGroup = parseInt(sensorRadio[1])
                radio.setGroup(radioGroup)
            }
            break;
    }
})
serial.onDataReceived(serial.delimiters(Delimiters.NewLine), function () {
    data = serial.readLine()
    cmd2 = substring(data, 0, 3)
    params2 = substring(data, 3, data.length)
    switch (cmd2) {
        case "pol":
            if (radioGroup == 255) {
                break;
            }
            radio.sendString(data);
            let value2 = getSensorValues()
            serial.writeLine(sensorName + "|" + value2)
            break;
        case "bct":
            let sensorRadio2 = params2.split("|")
            if (sensorName == sensorRadio2[0]) {
                radioGroup = parseInt(sensorRadio2[1])
            }
            radio.setGroup(255)
            radio.sendString(data);
            radio.setGroup(radioGroup)
            break;
    }
})
let result = ""
let length = 0
let data = ""
let i = 0
let cmd = ""
let params = ""
let cmd2 = ""
let params2 = ""
let sensorName: string
let sensorType: string
let writeSerial: boolean
let testingSerial: boolean
let radioGroup = 255
// ascii names
sensorName = "light1"
sensorType = "LIGH"
writeSerial = true
testingSerial = false
radio.setGroup(radioGroup)
radio.setTransmitPower(7)
basic.showIcon(IconNames.Yes)
basic.forever(function () {

})
