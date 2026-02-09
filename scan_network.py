import serial
import serial.tools.list_ports
import time

# --- CONFIGURATION ---
BAUDRATES = [9600, 19200, 38400, 57600, 115200]
ADDRESS_RANGE = range(1, 10)

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
        # print(ser.in_waiting)
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



def get_scpi_idn(ser):
    """
    Probe for a SCPI *IDN? response from a Keithley-like instrument.

    Returns a clean IDN string if it looks valid, otherwise None.
    """
    ser.timeout = 2.0

    # Power / control lines
    ser.dtr = True
    ser.rts = True
    time.sleep(0.2)

    ser.reset_input_buffer()
    ser.reset_output_buffer()

    try:
        ser.write(b"*IDN?\r")
        time.sleep(0.3)

        raw = ser.read_until(b"\r")
        if not raw:
            return None

        response = raw.decode("ascii", errors="ignore").strip()
        response = response.replace("*IDN?", "").strip()

        # 1) Must be reasonably short (avoid long garbage blobs)
        if not (10 <= len(response) <= 200):
            return None

        # 2) Must be printable ASCII (no control chars, no NULs)
        if not response.isprintable():
            return None

        # 3) Must look like a proper SCPI IDN
        #    For your Keithley 6482 it is:
        #    "KEITHLEY INSTRUMENTS INC.,MODEL 6482,4613069,..."
        resp_up = response.upper()
        has_comma = "," in response
        is_keithley_like = "KEITHLEY" in resp_up and "MODEL" in resp_up

        if not (has_comma and is_keithley_like):
            return None

        return response

    except Exception:
        return None


def scan_network():
    print("Scanning System Ports (Deep Scan):")
    # ports = [p.device for p in serial.tools.list_ports.comports()
    #          if p.device.upper() != 'COM1']
    ports = [p.device for p in serial.tools.list_ports.comports() if "USB" in p.device or "ACM" in p.device]
    print(ports, '\n -----------------------------\n\n')
    
    found_devices = []
    
    for port in ports:
        print('In port', port)
        port_identified = False

        # ---- 1. Try SCPI/Keithley ONCE per port at 57600 ----
        try:
            ser_scpi = serial.Serial(port, 57600, timeout=2.0)
        except serial.SerialException as e:
            print(f"Could not open {port} @ 57600 for SCPI: {e}")
            ser_scpi = None

        if ser_scpi is not None:
            time.sleep(0.1)
            idn = get_scpi_idn(ser_scpi)
            print("SCPI IDN:", idn)
            ser_scpi.close()

            if idn:
                short_name = idn.split(',')[1] if ',' in idn else idn[:15]
                print(f"[+] FOUND: {port} | 57600 Bd | {short_name} (SCPI)".ljust(60))
                found_devices.append({
                    "Port": port, "Baud": 57600, "Address": None,
                    "Name": short_name, "Type": "SCPI", "Protocol": "SCPI"
                })
                port_identified = True

        # If this port is a Keithley, do NOT probe Pfeiffer on it
        if port_identified:
            print('\n---------------------\n')
            continue

        # ---- 2. If not SCPI, probe Pfeiffer over all baudrates ----
        for baud in BAUDRATES:
            try:
                ser=serial.Serial(port, baud,
                    parity=serial.PARITY_NONE,bytesize=serial.EIGHTBITS,
                              timeout=2.0)
                # ser = serial.Serial(port, baud, timeout=2.0)
            except serial.SerialException as e:
                print(f"Could not open {port} @ {baud}: {e}")
                continue
            
            time.sleep(1)
            
            for addr in ADDRESS_RANGE:
                name = get_pfeiffer_response(ser, addr, 349)
                print(f"  Baud {baud}, addr {addr} -> {name}")
                if name:
                    dev_type = "PUMP" if "TC" in name else "GAUGE"
                    print(f"[+] FOUND: {port} | {baud} Bd | {name} (Addr {addr})".ljust(60))
                    found_devices.append({
                        "Port": port, "Baud": baud, "Address": addr,
                        "Name": name, "Type": dev_type, "Protocol": "PFEIFFER"
                    })
                    port_identified = True
                    # do NOT break addr loop if you ever expect multiple devices on the same bus
            ser.close()
            if port_identified:
                break

        print('\n---------------------\n')

    return found_devices

# Run debug scan
devices = scan_network()
print("FOUND DEVICES:", devices)
