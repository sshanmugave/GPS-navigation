# GPS Waypoint Navigation (Emlid Reach M2)

A beginner-friendly Python prototype for GPS waypoint navigation designed as Stage 1 of an autonomous rover project. It connects to an Emlid Reach M2 multi-band GNSS receiver over TCP or serial, streams live NMEA data, and lets the user save the current coordinates as a destination at the press of a key. The program calculates real-time Haversine distance in meters to the saved waypoint and triggers a visual "DESTINATION REACHED!" alert once within a configurable proximity threshold (default 2 meters). Destinations are persisted locally in `destination.json` so they survive restarts without requiring ROS 2 or motor drivers at this stage.

*Screenshots coming soon*

---

## Features

- **Live Coordinates & Status:** Real-time latitude, longitude, and GNSS fix-type tracking.
- **One-Key Waypoint Save:** Save the active position as your navigation target with a single key press (`S`).
- **Live Distance Calculation:** Continuous distance estimation in meters to the saved target using the Haversine formula.
- **Configurable Arrival Threshold:** Visual alert (`DESTINATION REACHED!`) when distance falls within threshold (defaults to 2.0 m, adjustable on-the-fly or via CLI).
- **Persistent Storage:** Waypoints are saved to `destination.json` across sessions.
- **Fix-Type Identification:** Real-time visibility into satellite fix quality: Single, DGPS, RTK Float, and RTK Fixed.
- **Robust Error Handling:** Rejects invalid/zero coordinates, handles temporary GPS signal loss, filters noisy measurements, and automatically reconnects upon stream interruptions.

---

## Requirements

- **Operating System:** Windows 10 or 11 (the interactive keyboard handling relies on the Windows-native `msvcrt` standard library module).
  > **Note on Linux Porting:** To run this project on Linux, replace `msvcrt` with a cross-platform keyboard input library (such as `pynput` or `curses` / non-blocking `termios`).
- **Python:** Python 3.9 or newer.
- **Python Packages:** `pyserial>=3.5` (see [`requirements.txt`](file:///E:/rover%202027/GPS%20navigation/requirements.txt)).
- **Hardware:** Emlid Reach M2 GNSS receiver with a compatible GNSS antenna placed with an unobstructed view of the sky.

---

## How It Works

```text
+-----------------+      NMEA (GGA sentences)      +--------------------+
| Emlid Reach M2  | -----------------------------> | Parse & Validate   |
| (GNSS Receiver) |      over TCP or Serial        | (Checksum, Range)  |
+-----------------+                                +---------+----------+
                                                             |
                                                             v
+-----------------+      Haversine Distance        +--------------------+
| Display & Check | <----------------------------- | Filter & Smooth    |
| (Reached Alert) |       to Saved Waypoint        | (HDOP, Moving Avg) |
+-----------------+                                +--------------------+
```

1. The Emlid Reach M2 outputs NMEA-0183 sentences (primarily `$GNGGA` / `$GPGGA`) over a TCP socket or serial connection.
2. The script parses incoming GGA sentences and validates sentence integrity using NMEA checksums.
3. Field 6 of the GGA sentence indicates the GNSS fix quality (0 = invalid, 1 = Single, 2 = DGPS, 4 = RTK Fixed, 5 = RTK Float).
4. Raw coordinates undergo sanity checks (rejecting 0,0 and out-of-range bounds), HDOP filtering, and moving-average smoothing to eliminate noise and jumps.
5. Distance to the saved waypoint is computed using great-circle Haversine mathematics.
6. The interface refreshes in-place in the console and checks against the proximity threshold.

---

## Connecting the Reach M2

You can connect your Windows computer to the Reach M2 using one of three methods:

### Option A: Direct Wi-Fi Hotspot (Recommended for Field Tests)
1. Power the Reach M2.
2. On your laptop, search for Wi-Fi networks and connect to the M2's built-in access point (typically named `reach:xx:xx`).
3. Open your browser and navigate to the ReachView web interface at **`http://192.168.42.1`**.
4. *Note:* While connected to the M2 hotspot, your laptop will not have standard internet access. Refer to official Emlid documentation for the default hotspot password (never commit network passwords to source control).

### Option B: USB Cable (Virtual Ethernet / RDNIS)
1. Connect the Reach M2 to your PC using a micro-USB cable.
2. In Windows, the M2 creates a virtual network interface rather than a standard COM port. If Windows does not automatically install the driver, it may appear in **Device Manager** under **Other devices** as `ReachM2` with **Code 28** (no driver).
3. **Driver fix steps:**
   - Open **Device Manager** (`Win + X` -> Device Manager).
   - Right-click `ReachM2` -> **Update driver**.
   - Select **Browse my computer for drivers** -> **Let me pick from a list of available drivers on my computer**.
   - Select **Network adapters** -> Manufacturer: **Microsoft** -> Model: **Remote NDIS Compatible Device**.
   - Complete the wizard.
4. Once installed, the ReachView interface is typically accessible at **`http://192.168.2.15`**.

### Option C: Join Existing Wi-Fi or Mobile Hotspot
1. Connect to the M2 via Option A first, open ReachView, and navigate to the **Wi-Fi** settings.
2. Configure the Reach M2 to join your local Wi-Fi router or your smartphone hotspot.
3. Find the IP address assigned to the M2 by your router or hotspot and open ReachView using that IP.

---

## ReachView Configuration

To stream NMEA data to these scripts, configure ReachView as follows:

1. In ReachView, navigate to **Position streaming 1**.
2. Select **TCP server** as the channel.
3. Set the **Port** to `9001`.
4. Set the **Format** to `NMEA`.
5. Under NMEA settings:
   - **Talker ID:** Set to `GN`.
   - Enable **GGA** messages (a **5 Hz** update rate is ideal for pedestrian navigation and rovers).
   - **RMC** is optional.
   - *Note:* Ensure the NMEA output rate does not exceed your GNSS update rate configured in ReachView's GNSS settings.

### Verifying the Stream in PowerShell
Before launching the Python scripts, test that the stream is transmitting data:

```powershell
py -c "import socket; s=socket.create_connection(('192.168.42.1',9001),timeout=5); print(s.recv(600).decode())"
```

> **Sky View Note:** If the command returns an empty sentence such as:
> ```text
> $GNGGA,,,,,,0,00,99.99,,,,,,*48
> ```
> this means the network connection is functional, but the receiver does not yet have a satellite lock. The GNSS antenna must be placed outdoors with a clear, unobstructed view of the sky.

---

## Quick Start (PowerShell)

```powershell
# 1. Clone the repository
git clone https://github.com/sshanmugave/GPS-navigation.git
cd GPS-navigation

# 2. Install dependencies
py -m pip install -r requirements.txt

# 3. Run the beginner script
py gps_simple.py

# Or run the full version with TCP flags
py gps_waypoint.py --tcp 192.168.42.1:9001
```

---

## Usage & Controls

### Keyboard Controls

| Key | Script | Function |
| :--- | :--- | :--- |
| `S` | Both | Save current position as destination waypoint (saved to `destination.json`) |
| `Q` | Both | Cleanly exit the program |
| `C` | `gps_waypoint.py` | Clear active saved destination |
| `+` | `gps_waypoint.py` | Increase arrival distance threshold by 0.5 m |
| `-` | `gps_waypoint.py` | Decrease arrival distance threshold by 0.5 m (minimum 0.5 m) |

### Command-Line Arguments (`gps_waypoint.py`)

| Argument | Description | Default |
| :--- | :--- | :--- |
| `--tcp HOST:PORT` | Stream NMEA over TCP socket | None (e.g. `192.168.42.1:9001`) |
| `--port PORT` | Read NMEA from serial port (e.g. `COM5`) | None |
| `--baud RATE` | Serial port baud rate | `115200` |
| `--threshold METERS` | Initial arrival distance threshold in meters | `2.0` |
| `--list` | List available serial COM ports and exit | - |

### Example Walkthrough Session

1. Start `gps_simple.py` or `gps_waypoint.py` outdoors with sky visibility.
2. Wait until the display changes from `"Waiting for GPS fix..."` to showing coordinates and fix status (e.g. `[SINGLE]` or `[RTK FLOAT]`).
3. Press <kbd>S</kbd> to save your current position as the target waypoint.
4. Walk 10 to 20 meters away. Observe the live distance increasing on the console.
5. Turn around and walk back toward the starting point.
6. As you approach within 2 meters of the origin, the alert displays:
   ```text
   [SINGLE] Now: 11.0799598, 76.9862270 | Dest: 11.0799598, 76.9862270 |    1.42 m  DESTINATION REACHED!
   ```

---

## Configuration Settings

### Arrival Threshold
- **Live adjustment:** Press <kbd>+</kbd> or <kbd>-</kbd> while running `gps_waypoint.py`.
- **Command-line:** Pass `--threshold <value>` (e.g., `--threshold 3.5`).
- **Script defaults:**
  - In `gps_waypoint.py`: modify `DEFAULT_THRESHOLD_M`.
  - In `gps_simple.py`: edit `THRESHOLD_M` near the top of the file.

### Advanced Tuning (`gps_waypoint.py`)

Constants at the top of [`gps_waypoint.py`](file:///E:/rover%202027/GPS%20navigation/gps_waypoint.py) can be tailored to your operating environment:

| Constant | Description | Default |
| :--- | :--- | :--- |
| `MAX_HDOP` | Maximum allowable Horizontal Dilution of Precision; sentences with higher HDOP are discarded | `2.5` |
| `SIGNAL_TIMEOUT_S` | Duration in seconds without valid fixes before triggering "SIGNAL LOST" status | `3.0` |
| `SMOOTHING_POINTS` | Number of recent valid coordinates averaged for moving-average smoothing | `5` |
| `MAX_SPEED_MPS` | Maximum plausible speed in m/s; sudden jumps exceeding this are discarded | `10.0` |
| `REQUIRE_RTK_TO_SAVE` | When `True`, prevents saving a waypoint unless fix quality is RTK Float (5) or RTK Fixed (4) | `False` |

---

## GPS Fix Quality & Accuracies

Field 6 of the NMEA GGA sentence denotes the fix solution quality:

| Quality Code | Mode | Typical Accuracy | Recommended Threshold | Notes |
| :---: | :--- | :--- | :--- | :--- |
| **0** | No Fix | N/A | N/A | Insufficient satellites or searching |
| **1** | Single (Autonomous) | ~1.0 – 3.0 m | ~5.0 m | Standard standalone GNSS |
| **2** | DGPS (SBAS) | ~0.5 – 2.0 m | ~3.0 m | Satellite-based differential corrections |
| **5** | RTK Float | ~10 – 50 cm | ~1.0 m | Carrier-phase tracking without fixed ambiguities |
| **4** | RTK Fixed | ~1 – 2 cm | ~0.3 – 0.5 m | Full centimeter-level precision |

> [!IMPORTANT]
> A tight threshold of 2.0 m is unreliable in standalone `Single` mode due to natural atmospheric drift and multipath errors (~1–3 m). For standalone navigation, use a threshold of ~5 m. To achieve sub-meter waypoint accuracy, feed RTK corrections (via NTRIP or a local base station) into ReachView's **Correction input** tab.

---

## Reliability & Safety Features

- **NMEA Checksum Verification:** Validates the two-character XOR checksum at the end of every sentence, eliminating partially transferred lines.
- **Coordinate Boundary Validation:** Discards `(0, 0)`, empty string fields, and coordinates outside latitude [-90, +90] / longitude [-180, +180].
- **HDOP Filtering:** Rejects satellite readings during degraded constellation geometry.
- **Moving Average Smoothing:** Buffers recent valid fixes to smooth jitter.
- **Jump Rejection:** Detects and ignores unrealistic coordinate spikes exceeding `MAX_SPEED_MPS`.
- **Signal-Lost Watchdog:** Clears active coordinates and alerts the operator if no valid fix arrives within 3 seconds.
- **Automatic Socket Reconnect:** Restores TCP data stream if connection drops.

---

## Project Structure

```text
GPS-navigation/
│
├── .gitignore            # Excludes destination.json, pycache, venv, and IDE files
├── LICENSE               # MIT License
├── README.md             # Project documentation and setup guide
├── requirements.txt      # Python dependencies (pyserial>=3.5)
├── gps_simple.py         # Minimal ~80-line beginner implementation (TCP only)
└── gps_waypoint.py       # Full implementation (Serial/TCP, filtering, CLI flags)
```

---

## Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| COM port list only displays `"Standard Serial over Bluetooth link"` | Reach M2 is connected over USB/network, not USB serial | The M2 does not expose a standard USB COM port on Windows. Use TCP streaming over Wi-Fi or RDNIS instead. |
| Device Manager shows `ReachM2` under Other Devices with Code 28 | Windows lacks the default RDNIS network driver for the M2 | In Device Manager, right-click `ReachM2` -> Update Driver -> Browse -> Let me pick -> Network adapters -> Microsoft -> Remote NDIS Compatible Device. |
| `"Can't connect to this network"` when joining Reach hotspot | Typo in Wi-Fi password or adapter timeout | Check the default hotspot password in Emlid documentation, retry connection, or use the Emlid Flow mobile app to configure the unit. |
| Connection error or timeout on port `9001` | TCP server disabled or wrong IP address | Ensure **Position streaming 1** is toggled ON as a **TCP server** on port `9001` in ReachView. Verify you are using the correct IP (`192.168.42.1` for hotspot, `192.168.2.15` for RDNIS). |
| Console displays `NO DATA` or `SIGNAL LOST` | Inactive stream or obstructed antenna view | Verify ReachView is streaming GGA messages. Check that the antenna is outside with a clear, open view of the sky. |
| `'python'` or `'py'` is not recognized as a command | Python not added to Windows PATH | Use the `py` launcher, or rerun the Python installer, check **Add Python to PATH**, and choose Modify/Repair. |
| Garbled terminal output or misaligned lines | Small terminal width or outdated shell window | Use Windows Terminal or standard PowerShell, and widen the console window to at least 120 columns. |

---

## Roadmap

- [ ] Add compass heading / bearing calculation to destination
- [ ] Support sequential multiple waypoints and route loading
- [ ] Integrate live RTK correction feed via NTRIP client
- [ ] Add live 2D map plotting (e.g. Leaflet / Matplotlib)
- [ ] Implement mission data logging to CSV
- [ ] Autonomous rover actuation (ROS 2 navigation and motor controller drivers)

---

## License

This project is licensed under the MIT License - see the [`LICENSE`](file:///E:/rover%202027/GPS%20navigation/LICENSE) file for details.
