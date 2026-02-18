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


class PfeifferGauge(LabDevice):
    def __init__(self, name, serial_conn, address):
        super().__init__(name, serial_conn)
        self.address = address

    def read_data(self):
        param = 740  # Pressure reading parameter
        cmd = f"{self.address:03d}00{param:03d}02=?"
        chk = calculate_checksum(cmd)
        full_cmd = f"{cmd}{chk:03d}\r"

        try:
            self.ser.reset_input_buffer()
            self.ser.write(full_cmd.encode('ascii'))
            
            # Robust timing loop for the lab's RS-485 bus
            start_time = time.time()
            while (time.time() - start_time) < 2.0:
                if self.ser.in_waiting:
                    line = self.ser.read_until(b'\r').decode('ascii', errors='ignore').strip()
                    
                    # Valid response check
                    if line.startswith(f"{self.address:03d}10{param:03d}"):
                        data_str = line[10:-3].strip()
                        
                        # Filter echoes or transient noise
                        if "?" in data_str or len(data_str) < 6:
                            continue

                        # Parse the scientific notation format: mantissa (4 digits) + exponent (2 digits)
                        if data_str.isdigit():
                            # Pfeiffer exponential format logic: Mantissa/1000 * 10^(exp - 20)
                            mantissa = float(data_str[:4]) / 1000.0
                            exponent = int(data_str[4:]) - 20
                            pressure = mantissa * (10 ** exponent)
                            
                            # Return a LIST to match the new universal loop
                            return [{
                                "field": "pressure",
                                "value": pressure, 
                                "unit": "mbar", 
                                "status": "OK"
                            }]
                        
                        # Handle specific Pfeiffer gauge status codes
                        if data_str == "999999": 
                            return [{"field": "pressure", "value": None, "unit": "mbar", "status": "Over-range"}]
                        if data_str == "000000": 
                            return [{"field": "pressure", "value": None, "unit": "mbar", "status": "Low-vac"}]
            
            return [{"field": "pressure", "value": None, "unit": "mbar", "status": "Timeout"}]

        except Exception as e:
            return [{"field": "pressure", "value": None, "unit": "mbar", "status": f"Error: {e}"}]

class PfeifferTurboPump(LabDevice):
    def __init__(self, name, serial_conn, address):
        super().__init__(name, serial_conn)
        self.address = address

    def read_data(self):
        # Hz, Temp[C], Power[W]
        params = [309, 346, 330]
        # These keys will become the "Field" names in InfluxDB/Grafana
        keys = ['frequency', 'motor_temp', 'power_consumption']
        units = ['Hz', 'C', 'W']
        
        result = []
        
        for i, param in enumerate(params):
            # Construct the Pfeiffer protocol command
            # {address}00{parameter}02=? (02 is the length of the data request)
            cmd = f"{self.address:03d}00{param:03d}02=?"
            chk = calculate_checksum(cmd)
            full_cmd = f"{cmd}{chk:03d}\r"

            try:
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                self.ser.write(full_cmd.encode('ascii'))
                
                # Pfeiffer pumps need a moment to process; 0.15s is the "sweet spot"
                time.sleep(0.15) 
                
                if self.ser.in_waiting:
                    response = self.ser.read_until(b'\r').decode('ascii', errors='ignore').strip()
                    
                    # Validation: Response must start with address and include the parameter
                    if len(response) > 10 and response.startswith(f"{self.address:03d}"):
                        data_str = response[10:-3].strip()
                        
                        if data_str.isdigit():
                            value = int(data_str)
                            # We use keys[i] and units[i] so the data isn't all labeled "Hz"
                            result.append({
                                "field": keys[i],
                                "value": value, 
                                "unit": units[i], 
                                "status": "OK"
                            })
                        else:
                            result.append({"field": keys[i], "value": None, "unit": units[i], "status": f"Bad Data: {data_str}"})
                    else:
                        result.append({"field": keys[i], "value": None, "unit": units[i], "status": "Bad Packet"})
                else:
                    result.append({"field": keys[i], "value": None, "unit": units[i], "status": "Timeout"})
    
            except Exception as e:
                result.append({"field": keys[i], "value": None, "unit": units[i], "status": f"Error: {e}"})
        
        return result

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

