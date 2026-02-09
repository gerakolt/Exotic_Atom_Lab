from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import datetime

class InfluxLogger:
    def __init__(self, url, token, org, bucket):
        self.bucket = bucket
        self.org = org
        
        # Connect to InfluxDB
        self.client = InfluxDBClient(url=url, token=token, org=org)
        
        # Create the Write API (Synchronous means "wait until saved")
        self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        print(f"✅ Connected to InfluxDB at {url}")

    def log_reading(self, device_name, data_dict):
        """
        Converts your device dictionary into an InfluxDB Point.
        Now supports dynamic field names (e.g., pressure, motor_temp, power_consumption).
        """
        # 1. Skip if there is no valid number to plot
        if data_dict.get('value') is None:
            return
    
        # 2. Determine the field name. 
        # Use the 'field' key if it exists, otherwise default to "value"
        field_name = data_dict.get('field', 'value')
    
        # 3. Create the Data Point
        p = Point("sensor_data") \
            .tag("device", device_name) \
            .tag("unit", data_dict['unit']) \
            .field(field_name, float(data_dict['value'])) \
            .time(datetime.datetime.utcnow())
    
        # 4. Write to DB
        try:
            self.write_api.write(bucket=self.bucket, org=self.org, record=p)
        except Exception as e:
            print(f"⚠️ DB Write Failed for {device_name} ({field_name}): {e}")

    def close(self):
        self.client.close()