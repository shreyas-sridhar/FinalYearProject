# rfid_utils.py

import serial

def read_rfid_card(port="/dev/ttyUSB0", baudrate=9600, timeout=3):
    try:
        ser = serial.Serial(port, baudrate, timeout=timeout)
        print("Waiting for RFID card...")
        card_number = ser.readline().decode('utf-8').strip()
        ser.close()
        return card_number
    except Exception as e:
        print(f"RFID read error: {str(e)}")
        return None
