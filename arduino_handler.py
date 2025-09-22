import serial
import time
import config


class ArduinoHandler:
    """Handles serial communication with the Arduino."""

    def __init__(self, port=config.SERIAL_PORT, baud_rate=config.BAUD_RATE):
        self.port = port
        self.baud_rate = baud_rate
        self.ser = None
        self.connected = False
        self.last_state = [False, False, False, False]
        self.connect()

    def connect(self):
        """Attempts to establish a serial connection with the Arduino."""
        try:
            self.ser = serial.Serial(self.port, self.baud_rate, timeout=0.01)
            time.sleep(2)  # Wait for the connection to initialize
            self.connected = True
            print(f"Successfully connected to Arduino on {self.port}")
        except serial.SerialException:
            self.connected = False
            print(f"Arduino not found on {self.port}. Running in keyboard/mouse mode.")

    def read_input(self):
        """
        Reads and parses input from the Arduino.
        Returns a list of lane indices that have just been pressed.
        """
        if not self.connected:
            return []

        try:
            if self.ser.in_waiting > 0:
                line = self.ser.readline().decode('utf-8').strip()
                if len(line) == 4 and all(c in '01' for c in line):
                    current_state = [c == '1' for c in line]
                    pressed_lanes = [i for i, (prev, curr) in enumerate(zip(self.last_state, current_state)) if
                                     not prev and curr]
                    self.last_state = current_state
                    return pressed_lanes
        except (serial.SerialException, OSError):
            print("Arduino disconnected. Reverting to keyboard/mouse mode.")
            self.connected = False
            if self.ser:
                self.ser.close()
            self.ser = None
        except Exception as e:
            print(f"An error occurred while reading from Arduino: {e}")

        return []

    def get_held_lanes(self):
        """Returns a list of lanes currently being held down."""
        if not self.connected:
            return []
        return [i for i, state in enumerate(self.last_state) if state]

    def close(self):
        """Closes the serial connection if it's open."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Arduino connection closed.")


if __name__ == '__main__':
    print("--- Arduino Handler Test ---")
    print(f"Attempting to connect to Arduino on {config.SERIAL_PORT}...")

    arduino = ArduinoHandler()

    if not arduino.connected:
        print("Test finished: Could not connect to Arduino.")
    else:
        print("\nConnection successful. Listening for sensor input.")
        print("Trigger your IR sensors to see the output. Press Ctrl+C to exit.")
        try:
            while True:
                newly_pressed = arduino.read_input()
                if newly_pressed:
                    print(f"Newly Pressed: {newly_pressed}")

                held = arduino.get_held_lanes()
                # To avoid spamming the console, we'll only print held state changes
                # This is a simplified representation for the test
                # print(f"Currently Held: {held}") # Uncomment to see continuous held state

                time.sleep(0.02)
        except KeyboardInterrupt:
            print("\nStopping test.")
        finally:
            arduino.close()