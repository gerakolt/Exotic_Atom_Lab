import serial
import serial.tools.list_ports
import time

def calculate_checksum(cmd):
    return sum(ord(c) for c in cmd) % 256

def get_pfeiffer_response(ser, address, param):
    """Reads a specific parameter from a Pfeiffer device."""
    cmd = f"{address:03d}00{param:03d}02=?"
    chk = calculate_checksum(cmd)
    full_cmd = f"{cmd}{chk:03d}\r"
    
    ser.reset_input_buffer()
    ser.write(full_cmd.encode('ascii'))
    
    # Pfeiffer is usually fast, but we give it 100ms now for stability
    time.sleep(1) 
    start_time=time.time()
    while (time.time() - start_time) < 2.0:
            if ser.in_waiting:
                line = ser.read_until(b'\r').decode('ascii',
                                                    errors='ignore').strip()
                if param==349 and 'MPT200' in line: return 'MPT200'
                if line.startswith(f"{address:03d}10{param:03d}"):
                    data = line[10:-3].strip()
                    # FILTER: Ignore echoes (e.g. "=?" returned as data)
                    if "?" in data or len(data) < 2:
                        return None
                    return data
    return None


def parse_pfeiffer_pressure(val_str):
    try:
        if val_str == "999999": return "Over-range"
        if val_str == "000000": return "Low-vac"
        if val_str.isdigit():
            return f"{float(val_str[:4])/1000 * (10**(int(val_str[4:])-20)):.2E} mbar"
    except: pass
    return val_str


def ping_vacuum_gauge(com, adress):
    ser = serial.Serial(com, 9600,
            parity=serial.PARITY_NONE,bytesize=serial.EIGHTBITS, timeout=2.0)
    name=get_pfeiffer_response(ser, adress, 349)
    P=parse_pfeiffer_pressure(get_pfeiffer_response(ser, adress, 740))
    print(name, P)
    



def ping_turbo_pump(com, address):
    # Note: xonxoff=False is crucial to prevent freezing if noise occurs
    ser = serial.Serial(com, 9600, timeout=2.0, xonxoff=False)
    
    # There is no name for the vacuume gauge.
    name = get_pfeiffer_response(ser, address, 349)
    
    # Param 309 = Actual Rotation Speed in Hz
    speed = get_pfeiffer_response(ser, address, 309)
    
    print(f"Pump: {name} | Speed: {speed} Hz")
    ser.close()
    

def debug(com, address, par):
    print('in debug')
    ser = serial.Serial(com, 9600,
            parity=serial.PARITY_NONE,bytesize=serial.EIGHTBITS, timeout=2.0)
    cmd = f"{address:03d}00{par:03d}02=?"
    chk = calculate_checksum(cmd)
    full_cmd = f"{cmd}{chk:03d}\r"
    time.sleep(1) 
    ser.reset_input_buffer()
    ser.write(full_cmd.encode('ascii'))
    
    # Pfeiffer is usually fast, but we give it 100ms now for stability
    time.sleep(1) 
    start_time=time.time()
    while (time.time() - start_time) < 2.0:
        if ser.in_waiting:
            line = ser.read_until(b'\r')
            print('-------------------------')
            print(line)
            print(line.decode('ascii', errors='ignore').strip())
            print('---------------------')
ping_turbo_pump("/dev/ttyUSB0", 5)
ping_vacuum_gauge("/dev/ttyUSB1", 3)
#debug("/dev/ttyUSB0", 5, 349)
