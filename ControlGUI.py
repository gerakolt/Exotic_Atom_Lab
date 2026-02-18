import tkinter as tk
from tkinter import messagebox
from Devices import PfeifferTurboPump, open_serial_port

class PumpControlGUI:
    def __init__(self, root, pumps):
        self.root = root
        self.root.title("Exotic Atom Lab - Pump Control")
        self.pumps = pumps

        for i, pump in enumerate(self.pumps):
            frame = tk.LabelFrame(root, text=pump.name, padx=10, pady=10)
            frame.grid(row=i, column=0, padx=20, pady=10, sticky="ew")

            tk.Button(frame, text="TURN ON", fg="green", width=15,
                      command=lambda p=pump: self.toggle_pump(p, True)).pack(side=tk.LEFT, padx=5)
            
            tk.Button(frame, text="TURN OFF", fg="red", width=15,
                      command=lambda p=pump: self.toggle_pump(p, False)).pack(side=tk.LEFT, padx=5)

    def toggle_pump(self, pump, state):
        confirm = messagebox.askyesno("Confirm", f"Are you sure you want to {'START' if state else 'STOP'} {pump.name}?")
        if confirm:
            try:
                pump.set_pumping_state(state)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to command pump: {e}")

# Setup connections (Mirroring your monitor.py settings)
ser0 = open_serial_port("/dev/ttyUSB0", 9600)
ser2 = open_serial_port("/dev/ttyUSB2", 9600)

lab_pumps = [
    PfeifferTurboPump("Target Chamber Pump", ser0, address=5),
    PfeifferTurboPump("Beam Bending Pump", ser2, address=1)
]

root = tk.Tk()
gui = PumpControlGUI(root, lab_pumps)
root.mainloop()