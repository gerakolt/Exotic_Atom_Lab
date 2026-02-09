import serial
import serial.tools.list_ports
import time
import csv
import os
from datetime import datetime
from abc import ABC, abstractmethod
# Make sure Devices.py and Database.py are in the same folder on the Pi!
from Devices import PfeifferGauge, PfeifferTurboPump, KeithleyMeter, open_serial_port, reconnect_device
from Database import InfluxLogger

DB_URL = "http://localhost:8086"
DB_TOKEN = "iwnt16rn6MvE7-JoWD7RPQlSXVj7xEjWgp3yPdQcjUiC1WEJB2e0D5y5O_-kXQvaTvCstUcG6KNhQTqXh4xPvw=="
DB_ORG = "Exotic_atoms_lab"
DB_BUCKET = "Slow Control"

print("Connecting to Database...")
try:
    db = InfluxLogger(DB_URL, DB_TOKEN, DB_ORG, DB_BUCKET)
    print("✅ Database Connected.")
except Exception as e:
    print(f"❌ Database Error: {e}")
    exit()

devices = []

###################################################################################################
# MPT200 Gauge (Address 3) -> Found on /dev/ttyUSB0
name = 'Target chamber vacuum gauge'
com = "/dev/ttyUSB1"
baud = 9600
adress = 3

print(f"Opening connections to {name}...")
try: 
    com_connection = open_serial_port(com, baud)   
except Exception as e:
    print(f"CRITICAL ERROR: Could not open {com}. {e}")
    exit()
devices.append(PfeifferGauge(name, com_connection, address=adress))

###################################################################################################
# TC 400 Pump (Address 5) -> Found on /dev/ttyUSB1
name = 'Target chamber turbo pump'
com = "/dev/ttyUSB0"
baud = 9600
adress = 5

print(f"Opening connections to {name}...")
try: 
    com_connection = open_serial_port(com, baud)   
except Exception as e:
    print(f"CRITICAL ERROR: Could not open {com}. {e}")
    exit()
devices.append(PfeifferTurboPump(name, com_connection, address=adress))

###################################################################################################
# TC 400 Pump (Address 1) -> Found on /dev/ttyUSB2
name = 'Beam bending chamber turbo pump'
com = "/dev/ttyUSB2"
baud = 9600
adress = 1

print(f"Opening connections to {name}...")
try: 
    com_connection = open_serial_port(com, baud)   
except Exception as e:
    print(f"CRITICAL ERROR: Could not open {com}. {e}")
    exit()
devices.append(PfeifferTurboPump(name, com_connection, address=adress))

###################################################################################################

print("Starting Monitor...")
try:
    while True:
        for device in devices:
            # We wrap this in a try/except so one bad read doesn't crash the whole loop
            try:
                data = device.read_data()
                
                if data.get('value') is not None:
                    db.log_reading(device.name, data)
                    print(f"   [Saved to DB] {device.name}: {data['value']:.2E} {data['unit']}")

                # Check specifically for permission errors/disconnects
                if "Access is denied" in str(data.get('status', '')) or "Input/output error" in str(data.get('status', '')):
                    print(f"⚡ USB Crash detected. Attempting to reconnect to {device.name}")
                    reconnect_device(device, devices)
            
            except Exception as e:
                print(f"⚠️ Error reading {device.name}: {e}")

        time.sleep(2)

except KeyboardInterrupt:
    print("\nStopping...")
    
    closed_ports = set()
    for device in devices:
        try:
            if device.ser not in closed_ports:
                if device.ser.is_open:
                    device.ser.close()
                    print(f"   -> Closed port: {device.ser.port}")
                closed_ports.add(device.ser)
        except Exception as e:
            print(f"   -> Error closing {device.name}: {e}")

    print("Bye.")
