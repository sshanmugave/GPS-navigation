# GPS Waypoint Navigation & Pixhawk Orientation (Emlid Reach M2 + Cube/Pixhawk)

An autonomous rover navigation prototype that fuses real-time RTK/GNSS positioning from an **Emlid Reach M2** receiver with live orientation and compass heading from a **Cube / Pixhawk autopilot** over MAVLink. The project features a real-time 2D live map visualizer with breadcrumb trail tracking, arrival threshold detection, and waypoint management.

---

## Live Visualizer Preview

![Live GPS & Pixhawk Navigator Visualization](piwhawk%20orienation/output.png)

*The live 2D navigation map displaying real-time rover position (blue dot), heading arrow (blue vector), breadcrumb path history, destination waypoint (red star), arrival threshold radius (dashed green circle), and status telemetry.*

---

## Features

- **Multi-Sensor Fusion:**
  - **Emlid Reach M2 GNSS:** Streams high-precision NMEA GGA sentences over TCP (default port `9001`).
  - **Cube / Pixhawk Autopilot:** Streams live `ATTITUDE` messages (yaw, heading, pitch, roll) over USB MAVLink.
- **Real-Time 2D Map Visualization (`navigator.py`):**
  - Live breadcrumb trail showing previous positions.
  - Active rover position dot with dynamic heading vector arrow.
  - Target waypoint marked with a red star and arrival radius circle (default 2.0 m).
  - Cardinal compass display (North, East, South, West) and bearing calculations.
- **Standalone Orientation Utility (`piwhawk orienation/orientation.py`):**
  - Dedicated script for auto-detecting Pixhawk/Cube COM ports and streaming yaw, pitch, roll, and cardinal directions.
- **One-Key Waypoint Management:**
  - Press <kbd>S</kbd> to save the current coordinates as the target destination to `destination.json`.
  - Press <kbd>C</kbd> to clear the current destination.
  - Press <kbd>Q</kbd> to cleanly quit.
- **Accurate Geodesic Math:**
  - Real-time great-circle Haversine distance calculations in meters.
  - Exact compass bearing angles from current position to destination.
  - Local tangent plane conversion (`to_local`) for accurate metric 2D plotting.
- **GNSS Fix Quality Tracking:**
  - Real-time identification of fix modes: `SINGLE`, `DGPS`, `RTK FLOAT`, and `RTK FIXED`.
- **Fault-Tolerant Multi-Threading:**
  - Dedicated background daemon threads for Reach M2 TCP streaming and Pixhawk MAVLink communication with automatic reconnect logic.

---

## Hardware & System Requirements

- **Operating System:** Windows 10 or 11 (Linux compatible with appropriate COM/serial device permissions).
- **Python:** Python 3.9 or newer.
- **Hardware:**
  - **GNSS Receiver:** Emlid Reach M2 with a GNSS antenna (placed outdoors with clear sky view).
  - **Autopilot / IMU:** Pixhawk or Cube autopilot connected via USB (MAVLink telemetry).
- **Python Dependencies:**
  ```text
  pyserial>=3.5
  pymavlink>=2.4.40
  matplotlib>=3.5.0
  ```

---

## System Architecture

```text
+-----------------------+       NMEA (GGA Sentences)       +-----------------------+
|    Emlid Reach M2     | -------------------------------> |                       |
|    (GNSS Receiver)    |         TCP Port 9001            |                       |
+-----------------------+                                  |     navigator.py      |
                                                           |   (Multi-threaded)    | ===> Live 2D Matplotlib
+-----------------------+   MAVLink ATTITUDE (Heading/Yaw) |                       |      Visualizer & Watchdog
|    Cube / Pixhawk     | -------------------------------> |  - GPS TCP Thread     |
|  (Autopilot / IMU)    |       Auto-detect USB COM        |  - Cube MAVLink Thread|
+-----------------------+                                  +-----------------------+
```

---

## Installation & Setup

### 1. Clone the Repository

```powershell
git clone https://github.com/sshanmugave/GPS-navigation.git
cd GPS-navigation
```

### 2. Install Dependencies

```powershell
py -m pip install -r requirements.txt
```

---

## Hardware Configuration

### Emlid Reach M2 (GNSS over TCP)
1. Power up the Reach M2 and connect your PC to its Wi-Fi hotspot (or shared local network).
2. Open ReachView in your browser at **`http://192.168.42.1`**.
3. Go to **Position streaming 1**:
   - Channel: **TCP server**
   - Port: **`9001`**
   - Format: **NMEA** (Ensure **GGA** message is enabled at 5 Hz or 10 Hz).

### Pixhawk / Cube (Heading over MAVLink)
1. Connect the Pixhawk / Cube to your PC using a USB cable.
2. Ensure Mission Planner or QGroundControl is **closed** so the COM port is not locked by another application.
3. The scripts automatically detect the active MAVLink COM port at 115200 baud. (You can also explicitly specify the port, e.g. `COM23`, in the script settings).

---

## Running the Applications

### 1. Integrated 2D Map Navigator (Recommended)

Combines live Reach M2 GPS coordinates with Cube/Pixhawk heading and renders a real-time matplotlib interface:

```powershell
py navigator.py
```

**Interactive Controls (click the map window first):**
| Key | Action |
| :---: | :--- |
| <kbd>S</kbd> | Save current GPS position as destination (persisted to `destination.json`) |
| <kbd>C</kbd> | Clear the current destination |
| <kbd>Q</kbd> | Cleanly quit the visualizer |

---

### 2. Standalone Pixhawk Orientation Utility

Reads raw MAVLink `ATTITUDE` messages and prints real-time heading, roll, pitch, and cardinal compass direction:

```powershell
py "piwhawk orienation/orientation.py"
```

Example terminal output:
```text
Trying ports: ['COM23']
Heartbeat OK on COM23
Reading orientation... Ctrl+C to stop

Facing: East        | heading  106.2° | roll    0.3  pitch   -1.1
```

---

### 3. Minimal GPS Console Prototype

For quick field testing of the Reach M2 TCP stream without graphical dependencies:

```powershell
py gps_simple.py
```

---

## GPS Fix Quality Reference

| Quality Code | Mode | Typical Accuracy | Recommended Proximity Threshold |
| :---: | :--- | :--- | :--- |
| **1** | Single (Autonomous) | ~1.0 – 3.0 m | ~3.0 – 5.0 m |
| **2** | DGPS (SBAS) | ~0.5 – 2.0 m | ~2.0 – 3.0 m |
| **5** | RTK Float | ~10 – 50 cm | ~1.0 m |
| **4** | RTK Fixed | ~1 – 2 cm | ~0.3 – 0.5 m |

> [!TIP]
> In standalone `SINGLE` mode, atmospheric drift and multipath jitter can cause small position jumps (~1–2 m). For centimeter precision, configure RTK corrections via NTRIP or a local base station in ReachView.

---

## Project Structure

```text
GPS-navigation/
│
├── .gitignore                       # Excludes destination.json, cache, venv, and IDE files
├── LICENSE                          # MIT License
├── README.md                        # Documentation and setup guide
├── requirements.txt                 # Dependencies: pyserial, pymavlink, matplotlib
├── destination.json                 # (Auto-generated) Active saved waypoint coordinates
├── gps_simple.py                    # Minimal beginner GPS terminal script (TCP)
├── navigator.py                     # Integrated GPS + Pixhawk heading + 2D map visualizer
└── piwhawk orienation/
    ├── orientation.py               # Standalone Pixhawk/Cube MAVLink heading reader
    └── output.png                   # Navigator visualization screenshot
```

---

## Roadmap

- [x] Multi-sensor fusion (Emlid Reach M2 GNSS + Pixhawk/Cube MAVLink)
- [x] Compass heading, yaw, and relative bearing calculations
- [x] Real-time 2D map plotting with breadcrumbs and heading arrow
- [ ] Support sequential multi-waypoint route loading
- [ ] Integrate NTRIP client for autonomous RTK corrections
- [ ] Autonomous rover actuation (motor controller & steering PID loops)
- [ ] ROS 2 Nav2 integration

---

## License

This project is licensed under the MIT License - see the [`LICENSE`](LICENSE) file for details.
