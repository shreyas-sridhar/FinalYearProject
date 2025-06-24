#include <SPI.h>
#include <MFRC522.h>

#define SS_PIN 10
#define RST_PIN 9

MFRC522 rfid(SS_PIN, RST_PIN);

void setup() {
  Serial.begin(9600);
  SPI.begin();
  rfid.PCD_Init();
  Serial.println("Place your RFID tag near the reader...");
}

void loop() {
  // Check for a new card
  if (!rfid.PICC_IsNewCardPresent()) return;
  if (!rfid.PICC_ReadCardSerial()) return;

  // Build the UID string
  String tag = "";
  for (byte i = 0; i < rfid.uid.size; i++) {
    byte b = rfid.uid.uidByte[i];
    if (b < 0x10) tag += "0";  // Leading zero for bytes < 0x10
    tag += String(b, HEX);     // Convert byte to hex string
  }

  tag.toUpperCase();  // Optional
  Serial.println(tag);

  // Clear RFID session
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}
