import serial
import serial.tools.list_ports
import time
import csv
import os
from datetime import datetime
from abc import ABC, abstractmethod


def reconnect_device(crashed_device, all_devices):
    """
    Reconnects a crashed device and updates ALL other devices 
    sharing the same COM port to use the new connection.
    """
    print(f"⚡ Recovery Mode: Analyzing crash on {crashed_device.name}...")
    
    # 1. Extract settings from the dead object
    # The serial object remembers its settings even after crashing
    dead_conn = crashed_device.ser
    port = dead_conn.port
    baud = dead_conn.baudrate
    
    print(f"   -> Detected Port: {port} | Baud: {baud}")

    # 2. Close the dead connection (safely)
    try:
        if dead_conn.is_open:
            dead_conn.close()
    except:
        pass

    # 3. Wait for Windows Driver to reset
    print("   -> Waiting 3s for USB driver reset...")
    time.sleep(3)

    # 4. Attempt Reconnect
    try:
        new_conn = open_serial_port(port, baud)
        print(f"   -> ✅ Successfully reopened {port}")
    except Exception as e:
        print(f"   -> ❌ Reconnect failed: {e}")
        return # Exit and try again next loop

    # 5. CRITICAL: Update ALL devices sharing this port
    # If we don't do this, the other devices on COM3 will stay broken
    count = 0
    for dev in all_devices:
        # Check if this device was using the same port name (e.g. 'COM3')
        # We check the string name because the objects might be different
        if dev.ser.port == port:
            dev.ser = new_conn
            count += 1
            
    print(f"   -> 🔄 Updated {count} device(s) to the new connection.")
    

def calculate_checksum(cmd): return sum(ord(c) for c in cmd) % 256

def open_serial_port(port, baud):
    """Standardized connection logic"""
    return serial.Serial(port=port, baudrate=baud, timeout=2.0,bytesize=serial.EIGHTBITS,
                            parity=serial.PARITY_NONE,stopbits=serial.STOPBITS_ONE, xonxoff=False)

class LabDevice(ABC):
    def __init__(self, name, serial_conn):
        self.name = name
        self.ser = serial_conn
    
    @abstractmethod
    def read_data(self):
        """Returns a dict: {'value': float, 'unit': str, 'status': str}"""
        pass

# class PfeifferGauge(LabDevice):
#     def __init__(self, name, serial_conn, address):
#         super().__init__(name, serial_conn)
#         self.address = address

#     def read_data(self):
#         # Your original Pfeiffer logic wrapped here
#         param = 740 # Pressure reading
#         cmd = f"{self.address:03d}00{param:03d}02=?"
#         chk = calculate_checksum(cmd)
#         full_cmd = f"{cmd}{chk:03d}\r"

#         try:
#             self.ser.reset_input_buffer()
#             self.ser.reset_output_buffer()
#             self.ser.write(full_cmd.encode('ascii'))
#             time.sleep(0.15) 
            
#             if self.ser.in_waiting:
#                 response = self.ser.read_until(b'\r').decode('ascii', errors='ignore').strip()
#                 # Parsing logic
#                 if len(response) > 10 and response.startswith(f"{self.address:03d}"):
#                     data = response[10:-3].strip()
                    
#                     # Parse the scientific notation (e.g., "123006" -> 1.23E-4)
#                     if data.isdigit():
#                         mantissa = float(data[:4]) / 1000.0
#                         exponent = int(data[4:]) - 20
#                         pressure = mantissa * (10 ** exponent)
#                         return {"value": pressure, "unit": "mbar", "status": "OK"}
#         except Exception as e:
#             return {"value": None, "unit": "mbar", "status": f"Error: {e}"}
        
#         return {"value": None, "unit": "mbar", "status": "No Data"}

class PfeifferGauge(LabDevice):
    def __init__(self, name, serial_conn, address):
        super().__init__(name, serial_conn)
        self.address = address

    def read_data(self):
        param = 740 # Pressure reading parameter
        cmd = f"{self.address:03d}00{param:03d}02=?"
        chk = calculate_checksum(cmd)
        full_cmd = f"{cmd}{chk:03d}\r"

        try:
            self.ser.reset_input_buffer()
            self.ser.write(full_cmd.encode('ascii'))
            
            # Use the robust timing loop instead of a fixed sleep
            start_time = time.time()
            while (time.time() - start_time) < 2.0:
                if self.ser.in_waiting:
                    line = self.ser.read_until(b'\r').decode('ascii', errors='ignore').strip()
                    
                    # Check if this line is the valid response we want
                    if line.startswith(f"{self.address:03d}10{param:03d}"):
                        data_str = line[10:-3].strip()
                        
                        # FILTER: Ignore echoes or bad data
                        if "?" in data_str or len(data_str) < 6:
                            continue

                        # Parse the scientific notation (e.g., "123006")
                        if data_str.isdigit():
                            mantissa = float(data_str[:4]) / 1000.0
                            exponent = int(data_str[4:]) - 20
                            pressure = mantissa * (10 ** exponent)
                            return {"value": pressure, "unit": "mbar", "status": "OK"}
                        
                        # Handle known status codes if needed
                        if data_str == "999999": return {"value": None, "unit": "mbar", "status": "Over-range"}
                        if data_str == "000000": return {"value": None, "unit": "mbar", "status": "Low-vac"}
            
            return {"value": None, "unit": "mbar", "status": "Timeout"}

        except Exception as e:
            return {"value": None, "unit": "mbar", "status": f"Error: {e}"}

class PfeifferTurboPump(LabDevice):
    def __init__(self, name, serial_conn, address):
        super().__init__(name, serial_conn)
        self.address = address

    def read_data(self):
        # Param 309 = Actual Rotation Speed (Hz)
        # This is the standard "heartbeat" parameter for Pfeiffer Turbos
        param = 309 
        
        cmd = f"{self.address:03d}00{param:03d}02=?"
        chk = calculate_checksum(cmd)
        full_cmd = f"{cmd}{chk:03d}\r"

        try:
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            self.ser.write(full_cmd.encode('ascii'))
            time.sleep(0.15) 
            
            if self.ser.in_waiting:
                response = self.ser.read_until(b'\r').decode('ascii', errors='ignore').strip()
                
                # Validation: Check length and address match
                if len(response) > 10 and response.startswith(f"{self.address:03d}"):
                    # Extract the 6-digit data payload (characters 10 to 16)
                    data = response[10:-3].strip()
                    
                    if data.isdigit():
                        # PARSING CHANGE: 
                        # Turbo speed is typically just an integer (Hz)
                        # Example: "000820" -> 820 Hz
                        speed = int(data)
                        return {"value": speed, "unit": "Hz", "status": "OK"}
                    else:
                        return {"value": None, "unit": "Hz", "status": f"Bad Data: {data}"}
                else:
                    # Pass silently if it's just noise, or return error if you prefer
                    return {"value": None, "unit": "Hz", "status": "Bad Packet"}

        except Exception as e:
            return {"value": None, "unit": "Hz", "status": f"Error: {e}"}
        
        return {"value": None, "unit": "Hz", "status": "No Data"}

class KeithleyMeter(LabDevice):
    def __init__(self, name, serial_conn):
        super().__init__(name, serial_conn)
        # Initialize specifics for Keithley
        try:
            self.ser.dtr = True
            self.ser.rts = True
            time.sleep(0.2)
            self.ser.write(b":FORM:ELEM CURR2\r")
        except:
            print(f"Warning: Could not init Keithley on {self.name}")

    def read_data(self):
        try:
            self.ser.reset_input_buffer()
            self.ser.write(b":READ?\r")
            raw = self.ser.read_until(b'\r').decode('ascii', errors='ignore').strip()
            
            # Clean up result (remove comma, etc)
            val = raw.split(',')[0]
            return {"value": float(val), "unit": "A", "status": "OK"}
        except Exception as e:
            return {"value": None, "unit": "A", "status": "Error"}

