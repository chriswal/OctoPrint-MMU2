import serial
from time import sleep

commanddata=""
port = "com3"
ser = serial.Serial(port, 115200, timeout=0)
ser.write("Start\n")
while True:
    
    data = ser.read(9999)
    if len(data) > 0:
        print 'Got:', data
        commanddata=commanddata+data
        if len(commanddata)> 1 :
            if commanddata[0]=="T":
                sleep(5)
            if commanddata[0]=="C":
                sleep(2)
            ser.write("Ok\n")
            commanddata=""


    sleep(0.5)
    print 'not blocked'

ser.close()