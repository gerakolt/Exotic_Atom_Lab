import serial
import time

# CONFIG
PORT = "/dev/ttyUSB1"
BAUD = 9600

def calculate_checksum(cmd):
    return sum(ord(c) for c in cmd) % 256

def raw_ping(addr, param):
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1.0)
        
        # Build Command: Address + Param + "02=?"
        cmd_str = f"{addr:03d}00{param:03d}02=?"
        chk = calculate_checksum(cmd_str)
        full_cmd = f"{cmd_str}{chk:03d}\r"
        
        print(f"\n--- Sending to Addr {addr} (Param {param}) ---")
        print(f"OUT: {repr(full_cmd)}")
        
        ser.reset_input_buffer()
        ser.write(full_cmd.encode('ascii'))
        time.sleep(0.2)
        
        # Read whatever comes back
        raw = ser.read_until(b'\r')
        ser.close()
        
        if raw:
            print(f"IN : {raw}")
            print(f"STR: {raw.decode('ascii', errors='ignore')}")
        else:
            print("IN : [NO RESPONSE]")
            
    except Exception as e:
        print(f"Error: {e}")

# Try the most likely combinations
print(f"Opening {PORT}...")

# Test 1: Pressure (740) at Address 2 (Scanner found this address)
raw_ping(2, 740)

# Test 2: Pressure (740) at Address 3 (Your old config)
raw_ping(3, 740)

# Test 3: Pressure (740) at Address 1 (Factory Default)
raw_ping(1, 740)

# Test 4: Name (349) at Address 2 - Just to see if it replies "Error" again
raw_ping(2, 349)
