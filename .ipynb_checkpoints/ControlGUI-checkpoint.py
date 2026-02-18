import tkinter as tk
import json
import os

CONTROL_FILE = "control.txt"

class LabControlGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Exotic Atom Lab - Device Control")
        
        # Current desired state for all devices
        self.device_states = {
            "target_pump": {"state": "OFF", "pending": False},
            "beam_pump": {"state": "OFF", "pending": False}
        }
        
        # Create UI
        self.create_control_row("Target Chamber Pump", "target_pump")
        self.create_control_row("Beam Bending Pump", "beam_pump")

    def create_control_row(self, label, key):
        frame = tk.Frame(self.root, pady=5, padx=10)
        frame.pack(fill="x")
        
        tk.Label(frame, text=label, width=25, anchor="w").pack(side=tk.LEFT)
        
        # Toggle Button
        btn = tk.Button(frame, text="TURN ON", bg="red", fg="white", width=10,
                        command=lambda k=key, b=None: self.request_toggle(k))
        btn.pack(side=tk.RIGHT)
        # Store button reference to update color later if needed
        setattr(self, f"btn_{key}", btn)

    def request_toggle(self, key):
        # 1. Switch the internal desired state
        current = self.device_states[key]["state"]
        new_state = "ON" if current == "OFF" else "OFF"
        
        # 2. Update the state and SET THE PENDING FLAG
        self.device_states[key]["state"] = new_state
        self.device_states[key]["pending"] = True
        
        # 3. Update the button color immediately for feedback
        btn = getattr(self, f"btn_{key}")
        btn.config(text=f"SETTING {new_state}...", bg="orange")

        # 4. Save to the JSON file for monitor.py to find
        self.save_control_file()

    def save_control_file(self):
        with open(CONTROL_FILE, "w") as f:
            json.dump(self.device_states, f, indent=4)
        print(f"📝 Command sent: {self.device_states}")

root = tk.Tk()
app = LabControlGUI(root)
root.mainloop()