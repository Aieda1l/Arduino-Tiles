// arduino_tiles.ino

// Arduino Sketch for 4 Momentary Push Buttons
// Sends a 4-character string like "0100\n" representing the state of the buttons.
// 1 = pressed, 0 = not pressed.

// Define the pins for the four buttons
const int buttonPin1 = 2; // Lane 1
const int buttonPin2 = 3; // Lane 2
const int buttonPin3 = 4; // Lane 3
const int buttonPin4 = 5; // Lane 4

void setup() {
  // Start serial communication at the same baud rate as your Python config
  Serial.begin(9600);

  // Initialize the button pins as inputs with the internal pull-up resistor enabled.
  // This means the pin will be HIGH when the button is not pressed, and LOW when pressed.
  pinMode(buttonPin1, INPUT_PULLUP);
  pinMode(buttonPin2, INPUT_PULLUP);
  pinMode(buttonPin3, INPUT_PULLUP);
  pinMode(buttonPin4, INPUT_PULLUP);
}

void loop() {
  // Read the state of each button.
  // digitalRead() will be LOW (0) when pressed and HIGH (1) when not.
  // We invert the logic with '!' so that a pressed button is '1' (true).
  int state1 = !digitalRead(buttonPin1);
  int state2 = !digitalRead(buttonPin2);
  int state3 = !digitalRead(buttonPin3);
  int state4 = !digitalRead(buttonPin4);

  // Print the states as a single string followed by a newline character.
  // The newline is crucial for readline() in Python.
  Serial.print(state1);
  Serial.print(state2);
  Serial.print(state3);
  Serial.println(state4);

  // A small delay to prevent flooding the serial port, but fast enough for a rhythm game.
  // 10ms means we send an update 100 times per second.
  delay(10);
}