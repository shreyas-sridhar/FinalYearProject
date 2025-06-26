# 🚨 Emergency Traffic Prioritization System (ETPS)

A smart traffic signal system that detects emergency vehicles using RFID and dynamically alters traffic lights to prioritize their passage. Built with **Raspberry Pi**, **Arduino Nano**, **Python**, **SQLite**, and **Flask**, this system integrates **dual RFID readers**, a **web dashboard**, and **GPIO-based light controls**.

---

## 🧠 Project Highlights

- 🟢 Dynamic traffic light control using severity-based RFID input  
- 💾 Emergency cases logged to local SQLite DB  
- 🧑‍⚕️ Dashboard for drivers to view nearby hospitals & case history  
- 🔄 Dual RFID integration (Pi and Arduino)  
- ⚡ Real-time GPIO-based signal switching  

---

## 🧰 Hardware Used

| Device         | Quantity | Notes                              |
|----------------|----------|------------------------------------|
| Raspberry Pi   | 1        | Any model with GPIO and SPI        |
| Arduino Nano   | 1        | Connected via USB to Pi            |
| MFRC522 RFID   | 2        | One via SPI to Pi, one via Arduino |
| Breadboard     | 1        | For LED connections                |
| LEDs (Red/Yellow/Green/White) | 8 | 4 for each signal set          |
| Resistors      | 8        | 220Ω or 330Ω for each LED          |
| Jumper Wires   | —        | Male-to-female and male-to-male    |

---

## 🔌 Hardware Connections

### 🔴 Signal 1 (Connected to Raspberry Pi)

| LED Color | GPIO Pin (BOARD) |
|-----------|------------------|
| Red       | 5                |
| Yellow    | 12               |
| Green     | 3                |
| White (Emergency) | 40       |

### 🟡 Signal 2 (Connected to Raspberry Pi)

| LED Color | GPIO Pin (BOARD) |
|-----------|------------------|
| Red       | 13               |
| Yellow    | 38               |
| Green     | 15               |
| White (Emergency) | 16       |

### 📡 RFID Connections

#### 1. **RFID1** via Arduino Nano (USB)
- Arduino reads RFID and sends UID + name via serial (`/dev/ttyUSB0`)
- Acts as emergency case entry

#### 2. **RFID2** via MFRC522 to Raspberry Pi SPI

| MFRC522 Pin | Raspberry Pi Pin (BOARD) |
|-------------|--------------------------|
| SDA         | 24 (CE1)                 |
| SCK         | 23                       |
| MOSI        | 19                       |
| MISO        | 21                       |
| GND         | 6                        |
| RST         | 22                       |
| 3.3V        | 1                        |

---

## ⚙️ Software Setup

### 1. Clone the Repository

```bash
git clone https://github.com/shreyas-sridhar/The-Emergency-Traffic-Prioritization-System.git
cd The-Emergency-Traffic-Prioritization-System
````

### 2. Install Dependencies

```bash
sudo apt update
sudo apt install python3-pip
pip3 install flask RPi.GPIO spidev sqlite3
```

For MFRC522:

```bash
git clone https://github.com/pimylifeup/MFRC522-python.git
cd MFRC522-python
sudo python3 setup.py install
```

### 3. Enable SPI on Raspberry Pi

```bash
sudo raspi-config
# Navigate to: Interface Options > SPI > Enable
```

### 4. Run the App

```bash
cd The-Emergency-Traffic-Prioritization-System
python3 app.py
```

---

## 🧪 How It Works

1. **Driver scans RFID card** → RFID UID is read by Arduino and sent to Raspberry Pi via Serial.
2. **Severity is determined** → System uses UID mapping to assign severity (stored in DB).
3. **If severity ≥ 3**, signal turns **white** (emergency priority) and overrides normal cycles.
4. **Web dashboard** displays case info and nearby hospitals.

---

## 🗃️ Database Schema (SQLite)

### Table: `emergency_cases`

| Column Name | Type    | Description         |
| ----------- | ------- | ------------------- |
| id          | INTEGER | Primary Key         |
| name        | TEXT    | Patient name        |
| rfid\_uid   | TEXT    | UID of scanned card |
| severity    | INTEGER | 1 to 5              |
| timestamp   | TEXT    | Auto-filled         |

---

## 📷 Project Snapshot

*(Add your images here for better visualization)*

```
📸 Dashboard Screenshot  
📸 Signal LED Setup  
📸 Arduino + RFID  
```

---

## 🙌 Team

* Shreyas H Reddy
* Sanju John
* Shrinikethan S

Special thanks to **Dr. Sasikala Nagarajan** for mentorship and guidance.

---
---

## 🌐 Acknowledgments

Presented at **IEEE CONIT 2025**
---

## 🔗 Useful Commands

```bash
# Kill app if stuck
sudo fuser -k 5000/tcp

# Check GPIO status
gpio readall
```

---

*Made with ❤️ in Bengaluru*

```

---

Let me know once you've uploaded it to GitHub — I can also help you set up a `LICENSE`, `.gitignore`, or even convert this into a GitHub Pages site if you'd like.
```
