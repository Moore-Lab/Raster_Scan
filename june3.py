import serial
import time
import numpy as np
import keithley6487 # should work cause it's in the same folder
# imported the libraries from keithley cause it was giving me issues
import pyvisa
import time
import os
import datetime
import matplotlib.pyplot as plt

# Global file to store all scan data
global_data_file = f"data/full_scan_{int(time.time())}.csv"

# --------------------------------------------------------------------
# CONFIGURATION SECTION
# --------------------------------------------------------------------

PORT = 'COM3'                # Update this to match your Arduino port (e.g. '/dev/ttyACM0' on Linux)
BAUDRATE = 9600              # Must match the Arduino Serial.begin() rate
DELAY_SECONDS = 1            # Time to "measure" at each point (in seconds)

# --------------------------------------------------------------------
# CONNECT TO ARDUINO
# --------------------------------------------------------------------

try:
    # Establish serial connection to Arduino
    ser = serial.Serial(PORT, BAUDRATE, timeout=2)
    time.sleep(2)  # Wait for Arduino to finish resetting
    print(f"Connected to Arduino on port {PORT}")
except serial.SerialException:
    raise RuntimeError(f"Could not connect to Arduino on {PORT}. Check your cable and port.")

# --------------------------------------------------------------------
# Initialize the Keithley 6487
# --------------------------------------------------------------------
inst = keithley6487.initialize_keithley()
if not keithley6487.test_connection(inst):
    raise RuntimeError("Keithley 6487 failed to respond.")

# --------------------------------------------------------------------
# FUNCTION: Send move command to Arduino and wait for "OK"
# --------------------------------------------------------------------
def move_to(x_mm, y_mm):
    """
    Sends a move command in millimeters to the Arduino and waits until movement is complete.
    """
    command = f"move {round(x_mm, 4)} {round(y_mm, 4)}\n"
    ser.write(command.encode())  # Send move command over serial
    print(f"Sent: {command.strip()}")

    # Wait for Arduino to confirm it finished moving
    while True:
        line = ser.readline().decode().strip()
        if line == "OK":
            print(f"Arrived at position ({x_mm}, {y_mm})")
            break
        elif line.startswith("POS"):
            print(f"Arduino actual position: {line[4:]}")
        elif line == "ERR":
            raise RuntimeError(f"Arduino reported error at ({x_mm}, {y_mm})")
        elif line:
            print(f"Arduino says: {line}")  # Other optional debug messages

# --------------------------------------------------------------------
# FUNCTION: Simulate taking a measurement (can be replaced later) --> Changed
# --------------------------------------------------------------------
def measure(x_mm, y_mm):
    """
    Perform an IV measurement at (x, y) using the Keithley 6487.
    """
    print(f"Measuring at ({x_mm}, {y_mm})...")
    
    # customize the IV measurement parameters as needed
    data = keithley6487.precise_iv(inst, -27.9, -27.9, 1, n_measurements=3)  # or quick_iv(...)

    # Save to a single file with appended data
    if not os.path.exists("data"):
        os.makedirs("data")

    # Add column names if file does not exist
    file_exists = os.path.isfile(global_data_file)
    with open(global_data_file, 'a') as f:
        if not file_exists:
            f.write("x_mm,y_mm,voltage,current,stderr,timestamp\n")
        for row in data:
            v, i, stderr, ts = row
            f.write(f"{x_mm},{y_mm},{v},{i},{stderr},{ts}\n")

    print(f"Appended IV data at ({x_mm}, {y_mm}) to {global_data_file}")

    # Plot the IV curve
    # keithley6487.quickplot(data)
    # commenting this out cause it will be very overwhelming to plot every point

# --------------------------------------------------------------------
# FUNCTION: Snake-style scan across SiPM
# --------------------------------------------------------------------

def snake_scan(x1, x2, y1, y2, ds, func):


    direction = 1  # Initial direction: left-to-right

    for y_idx in np.append(np.arange(y1, y2, ds), y2):  # Loop through the array with the last value always in (regardless of divisibility)

        # Determine scan order for current row (left-to-right or right-to-left)
        x_range = np.append(np.arange(x1, x2, ds),x2) if direction == 1 else np.append(np.arange(x2, x1, -ds), x1)

        for i, x_idx in enumerate(x_range):

            move_to(x_idx, y_idx) # Move to this (x, y) position
            #func(x_idx, y_idx)
            #if i == 0 or i == len(x_range) - 1:
                # Only measure at the first and last point of each row
                #time.sleep(5)

        direction *= -1  # Reverse direction for snake pattern

    print("Finished full scan of SiPM.")


# --------------------------------------------------------------------
# FUNCTION: Return stage to (0, 0) after scanning
# --------------------------------------------------------------------
def flush_to_limit():
    """
    Sends a 'flush' command to Arduino to return motors to limit switch position.
    """
    ser.write(b"flush\n")
    print("Sent: flush")

    while True:
        line = ser.readline().decode().strip()
        if line == "OK":
            print("Returned to limit switch")
            break
        elif line:
            print(f"Arduino: {line}")  # Other debug messages

# --------------------------------------------------------------------
# MAIN PROGRAM
# --------------------------------------------------------------------
# customize the ranges and increments

if __name__ == "__main__":
    try:
        snake_scan(0, 7, 0, 7, .1, measure)        # Start scanning the full sensor
        flush_to_limit()   # Return to home position when done
    except KeyboardInterrupt:
        print("\n Scan aborted by user.")
    finally:
        ser.close()         # Close the serial connection
        print("Serial connection closed.")
