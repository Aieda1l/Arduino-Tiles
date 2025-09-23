// Arduino Sketch for 4 IR Proximity Sensors
// Sends "abcd\n" where a,b,c,d are 0 or 1 for each sensor state

void setup() {
  Serial.begin(9600);  // Match baud rate in config.py
  pinMode(2, INPUT_PULLUP);  // Sensor 1 (Lane 1)
  pinMode(3, INPUT_PULLUP);  // Sensor 2 (Lane 2)
  pinMode(4, INPUT_PULLUP);  // Sensor 3 (Lane 3)
  pinMode(5, INPUT_PULLUP);  // Sensor 4 (Lane 4)
}

void loop() {
  int s1 = !digitalRead(2);  // Invert for active LOW (1 = detected)
  int s2 = !digitalRead(3);
  int s3 = !digitalRead(4);
  int s4 = !digitalRead(5);

  Serial.print(s1);
  Serial.print(s2);
  Serial.print(s3);
  Serial.println(s4);

  delay(10);  // Small delay to avoid flooding serial
}