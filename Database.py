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
        Converts your device dictionary into an InfluxDB Point
        data_dict format: {'value': 1.23, 'unit': 'mbar', 'status': 'OK'}
        """
        # 1. Skip if there is no valid number to plot
        if data_dict['value'] is None:
            return

        # 2. Create the Data Point
        # Measurement: The "Table" name (e.g., "vacuum_readings")
        # Tags: Metadata to filter by (e.g., Device Name, Unit)
        # Fields: The actual numbers (Value)
        p = Point("sensor_data") \
            .tag("device", device_name) \
            .tag("unit", data_dict['unit']) \
            .field("value", float(data_dict['value'])) \
            .time(datetime.datetime.utcnow())

        # 3. Write to DB
        try:
            self.write_api.write(bucket=self.bucket, org=self.org, record=p)
        except Exception as e:
            print(f"⚠️ DB Write Failed: {e}")

    def close(self):
        self.client.close()