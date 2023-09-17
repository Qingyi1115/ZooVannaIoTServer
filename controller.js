let messageCounter: number
let command_counter: number
let rxMessagesHistory: string[]
let rxCommandsHistory: string[]
let neighbours: string[]
let neighbourvals: number[]
let fogRelay: boolean
let MAX_HISTORY: number
let bitName: string
let testingSerial: boolean
let command_str: string
let hasSensor: boolean

bitName = "00" // ascii names
messageCounter = 0
command_counter = 0
rxMessagesHistory = []
rxCommandsHistory = []
neighbours = []
neighbourvals = [] // [weight, height]
fogRelay = true
testingSerial = false
hasSensor = true
MAX_HISTORY = 30

HX711.SetPIN_DOUT(DigitalPin.P0)
HX711.SetPIN_SCK(DigitalPin.P8)
HX711.begin()
basic.pause(200)
HX711.set_scale(50000)
HX711.tare(10)
basic.pause(2000)
radio.setGroup(212)
radio.setTransmitPower(7)
basic.showIcon(IconNames.Yes)


basic.forever(function () {
})

function getSensorValues() {
    if (hasSensor) {
        HX711.power_up()
        let distance = grove.measureInCentimeters(DigitalPin.P1)
        basic.pause(300)
        let avgWeight = HX711.get_units(5)
        avgWeight = Math.max((avgWeight - 334) / 0.01034, 0)
        distance = Math.round(distance)
        avgWeight = Math.round(avgWeight)
        HX711.power_down()
        return [distance, avgWeight]
    } else {
        return [0.0, 0.0]
    }
}

input.onButtonPressed(Button.A, function () {
    basic.showString(bitName)
})

radio.onReceivedValue(function (sender_relayer_type, val) {
    let sender = sender_relayer_type[0] + sender_relayer_type[1]
    let relayer = sender_relayer_type[2] + sender_relayer_type[3]
    let count_str = sender_relayer_type[4] + sender_relayer_type[5]
    let message_count = parseInt(count_str)
    let dtype = sender_relayer_type[6] + sender_relayer_type[7]

    if (testingSerial) {
        serial.writeLine("radio rcv key, val: " + sender_relayer_type + ", " + val)
    }

    for (let rxMsgHis of rxMessagesHistory) {
        let msgHisSender = rxMsgHis[0] + rxMsgHis[1]
        let msgHisCount = parseInt(rxMsgHis[4] + rxMsgHis[5])
        if (sender == msgHisSender && message_count == msgHisCount) {
            return 0;
        }
    }

    // // Updates the nearest neighbour sensor values
    // if (relayer == sender) {
    //     let neighbourNotFound = true
    //     for (let i = 0; i < neighbours.length; i++) {
    //         if (neighbours[i] == relayer) {
    //             neighbourNotFound = false
    //             if (dtype == "we") {
    //                 neighbourvals[i][0] = val
    //             } else if (dtype == "hi") {
    //                 neighbourvals[i][1] = val
    //             } else if (testingSerial) {
    //                 serial.writeLine("unkwn dtype: " + dtype)
    //             }
    //         }
    //     }
    //     if (neighbourNotFound) {
    //         neighbours.push(relayer)
    //         let sensorVals = [0, 0]
    //         if (dtype == "we") {
    //             sensorVals[0] = val
    //         } else if (dtype == "hi") {
    //             sensorVals[1] = val
    //         } else if (testingSerial) {
    //             serial.writeLine("unkwn dtype: " + dtype)
    //         }
    //         neighbourvals.push(sensorVals)
    //     }
    // }

    // radio.sendValue(sender + bitName + count_str + dtype, val)
    // rxMessagesHistory.push(sender_relayer_type)

    // while (rxMessagesHistory.length > MAX_HISTORY) {
    //     rxMessagesHistory.shift()
    // }

    if (fogRelay) {
        serial.writeLine(sender_relayer_type + val)
    }

    return 0
})

serial.onDataReceived(serial.delimiters(Delimiters.NewLine), function () {
    let data = serial.readLine()
    command_str = bitName + Math.floor(command_counter / 10) + "" + command_counter % 10 + data
    radio.sendString(command_str)
    command_counter += 1
    if (command_counter > 99) {
        command_counter = 0
    }
    rxCommandsHistory.push(command_str)

    switch (data) {
        case "pol":
            let distanceWeight = getSensorValues()

            let count_str = "" + Math.floor(command_counter / 10) + "" + command_counter % 10
            serial.writeLine(bitName + bitName + count_str + "hi" + distanceWeight[0])
            command_counter += 1
            if (command_counter > 99) {
                command_counter = 0
            }
            count_str = "" + Math.floor(command_counter / 10) + "" + command_counter % 10
            serial.writeLine(bitName + bitName + count_str + "we" + distanceWeight[1])
            command_counter += 1
            if (command_counter > 99) {
                command_counter = 0
            }
            break;
    }
})

function substring(inputString: string, start: number, end: number) {
    let result = '',
        length = Math.min(inputString.length, end),
        i = start;

    while (i < length) result += inputString[i++];
    return result;
}

radio.onReceivedString(function (receivedString) {
    if (testingSerial) {
        serial.writeLine("radio rcv str: " + receivedString)
    }

    for (let command of rxCommandsHistory) {
        if (command == receivedString) {
            return;
        }
    }

    radio.sendString(receivedString)
    rxCommandsHistory.push(receivedString)

    while (rxCommandsHistory.length > MAX_HISTORY) {
        rxCommandsHistory.shift()
    }

    let command_type = substring(receivedString, 4, 7)

    switch (command_type) {
        case "pol":
            let distanceWeight = getSensorValues()

            let count_str = "" + Math.floor(command_counter / 10) + "" + command_counter % 10
            radio.sendValue(bitName + bitName + count_str + "hi", distanceWeight[0])
            command_counter += 1
            if (command_counter > 99) {
                command_counter = 0
            }
            count_str = "" + Math.floor(command_counter / 10) + "" + command_counter % 10
            radio.sendValue(bitName + bitName + count_str + "we", distanceWeight[1])
            command_counter += 1
            if (command_counter > 99) {
                command_counter = 0
            }
            break;

        case "command2":
            // Handle logic
            break;

        default:
            if (testingSerial) {
                serial.writeLine("radio rcv unkwn cmd: " + command_type)
            }
    }
})