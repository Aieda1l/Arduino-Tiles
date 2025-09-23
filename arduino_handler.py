# arduino_handler.py
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
        # Buffer to hold incomplete data between reads
        self._read_buffer = ""
        self.connect()

    def connect(self):
        """Attempts to establish a serial connection with the Arduino."""
        try:
            self.ser = serial.Serial(self.port, self.baud_rate, timeout=0.01)  # Use a small timeout
            time.sleep(2)  # Wait for connection to stabilize
            self.ser.reset_input_buffer()  # Clear any initial garbage on connect
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

        pressed_lanes = []
        try:
            # Read all available data and process the last complete line
            if self.ser.in_waiting > 0:
                # Read all data and append to our internal buffer
                data = self.ser.read(self.ser.in_waiting).decode('utf-8', errors='ignore')
                self._read_buffer += data

                # Process all complete lines in the buffer
                # The `\n` at the end is important
                while '\n' in self._read_buffer:
                    line, self._read_buffer = self._read_buffer.split('\n', 1)
                    line = line.strip()

                    # Only process valid lines
                    if len(line) == 4 and all(c in '01' for c in line):
                        # This line represents the most recent state from the Arduino
                        current_state = [c == '1' for c in line]
                        # Check for newly pressed lanes (transition from False to True)
                        newly_pressed = [i for i, (prev, curr) in enumerate(zip(self.last_state, current_state)) if
                                         not prev and curr]

                        if newly_pressed:
                            # Add any newly pressed lanes to our return list
                            pressed_lanes.extend(newly_pressed)

                        # Update the last state for the next iteration
                        self.last_state = current_state

        except (serial.SerialException, OSError):
            print("Arduino disconnected. Reverting to keyboard/mouse mode.")
            self.connected = False
            if self.ser:
                self.ser.close()
            self.ser = None
        except Exception as e:
            print(f"An error occurred while reading from Arduino: {e}")

        # Return a unique list of lanes pressed during this frame
        return list(set(pressed_lanes))

    def get_held_lanes(self):
        """Returns a list of lanes currently being held down."""
        if not self.connected:
            return []
        # No change needed here, it relies on self.last_state which is now correctly updated
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
        print("\nConnection successful. Listening for button input.")
        print("Press your buttons to see the output. Press Ctrl+C to exit.")
        try:
            while True:
                # This loop simulates the game loop
                newly_pressed = arduino.read_input()
                if newly_pressed:
                    print(f"Newly Pressed: {newly_pressed}")

                # We don't need to check held lanes in the test, but this shows how it works
                # held = arduino.get_held_lanes()
                # print(f"Currently Held: {held}") # Uncomment to see held states

                time.sleep(0.016)  # Simulate a ~60 FPS game loop
        except KeyboardInterrupt:
            print("\nStopping test.")
        finally:
            arduino.close()