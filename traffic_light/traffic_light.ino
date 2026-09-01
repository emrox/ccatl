// USB-controlled traffic light. One byte per command: R, Y, G, O (off).
// D0/D1 are the USB serial lines and D13 toggles during the bootloader, so
// the LEDs live on D2-D4.

const int RED = 2;
const int YELLOW = 3;
const int GREEN = 4;
const int PINS[3] = {RED, YELLOW, GREEN};

void show(int pin) {
  for (int i = 0; i < 3; i++) {
    digitalWrite(PINS[i], PINS[i] == pin ? HIGH : LOW);
  }
}

void setup() {
  for (int i = 0; i < 3; i++) {
    pinMode(PINS[i], OUTPUT);
  }
  show(-1);
  Serial.begin(9600);
}

void loop() {
  if (!Serial.available()) return;
  char cmd = Serial.read();
  switch (cmd) {
    case 'R': show(RED); break;
    case 'Y': show(YELLOW); break;
    case 'G': show(GREEN); break;
    case 'O': show(-1); break;
    default: return;  // newlines and junk: no change, no ack
  }
  Serial.println(cmd);
}
