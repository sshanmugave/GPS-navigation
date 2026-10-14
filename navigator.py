"""
Rover navigator: Emlid Reach M2 GPS (TCP) + Cube orientation (USB MAVLink) + live map.

Run:   py navigator.py
Keys (click the map window first):
    S = save current GPS position as the destination
    C = clear the destination
    Q = quit

Install once:  py -m pip install pymavlink pyserial matplotlib
"""
import json
import math
import os
import socket
import threading
import time
from collections import deque

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle
from pymavlink import mavutil
from serial.tools import list_ports

# Turn off matplotlib's own shortcuts so S / Q / C only do what we want
for _k in ("keymap.save", "keymap.quit", "keymap.back"):
    plt.rcParams[_k] = []

# ---------------- settings ----------------
GPS_HOST, GPS_PORT = "192.168.42.1", 9001   # Reach M2 address and TCP port
CUBE_PORT = None            # None = auto-detect, or set "COM23"
THRESHOLD_M = 2.0           # "reached" distance in meters
SIGNAL_TIMEOUT_S = 3.0      # no valid GPS fix for this long = signal lost
HEADING_TIMEOUT_S = 2.0     # no compass data for this long = heading lost
HEADING_OFFSET_DEG = 0.0    # add this if the Cube arrow is not pointing to the rover front
STRAIGHT_TOL_DEG = 10.0     # within this angle = "Straight ahead"
TRAIL_POINTS = 500          # how many past positions to draw
DEST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "destination.json")

FIX_NAMES = {1: "SINGLE", 2: "DGPS", 4: "RTK FIXED", 5: "RTK FLOAT"}
DIRECTIONS = ["North", "North-East", "East", "South-East",
              "South", "South-West", "West", "North-West"]


# ---------------- NMEA parsing (from your working code) ----------------
def to_degrees(value, hemi):
    dot = value.index(".")
    degrees = float(value[:dot - 2])
    minutes = float(value[dot - 2:])
    result = degrees + minutes / 60
    return -result if hemi in ("S", "W") else result


def parse_gga(line):
    """Return (lat, lon, quality) from a GGA line, or None if unusable."""
    try:
        parts = line.lstrip("$").split("*")[0].split(",")
        if len(parts) < 10 or not parts[0].endswith("GGA"):
            return None
        if parts[2] == "" or parts[4] == "" or parts[6] in ("", "0"):
            return None
        lat = to_degrees(parts[2], parts[3])
        lon = to_degrees(parts[4], parts[5])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None
        return lat, lon, int(parts[6])
    except (ValueError, IndexError):
        return None


# ---------------- geometry ----------------
R_EARTH = 6371000.0


def distance_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH * math.asin(math.sqrt(a))


def bearing_deg(lat1, lon1, lat2, lon2):
    """Compass bearing from point 1 to point 2, 0..360, 0 = North."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def to_local(lat, lon, lat0, lon0):
    """Lat/lon -> (east_m, north_m) relative to a reference point."""
    east = R_EARTH * math.cos(math.radians(lat0)) * math.radians(lon - lon0)
    north = R_EARTH * math.radians(lat - lat0)
    return east, north


def wrap180(angle):
    return (angle + 180) % 360 - 180


def direction_name(deg):
    return DIRECTIONS[int((deg + 22.5) // 45) % 8]


# ---------------- shared state ----------------
class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.pos = None            # (lat, lon)
        self.quality = 0
        self.last_fix = 0.0
        self.heading = None        # degrees 0..360
        self.last_heading = 0.0
        self.gps_status = "starting"
        self.cube_status = "starting"
        self.running = True


S = State()


# ---------------- GPS thread (Reach M2 over TCP) ----------------
def gps_thread():
    while S.running:
        sock = None
        try:
            S.gps_status = f"connecting to {GPS_HOST}:{GPS_PORT}"
            sock = socket.create_connection((GPS_HOST, GPS_PORT), timeout=3)
            sock.settimeout(0.5)
            S.gps_status = "connected"
            buf = ""
            while S.running:
                try:
                    data = sock.recv(1024)
                except socket.timeout:
                    continue
                if not data:
                    S.gps_status = "connection closed by M2"
                    break
                buf += data.decode(errors="ignore")
                while "\n" in buf:
                    line, buf = buf.split("\n", 1)
                    result = parse_gga(line.strip())
                    if result:
                        with S.lock:
                            S.pos = (result[0], result[1])
                            S.quality = result[2]
                            S.last_fix = time.time()
        except OSError as e:
            S.gps_status = f"error: {e}"
        finally:
            if sock:
                try:
                    sock.close()
                except OSError:
                    pass
        time.sleep(2)


# ---------------- Cube thread (heading over USB MAVLink) ----------------
def find_cube():
    if CUBE_PORT:
        candidates = [CUBE_PORT]
    else:
        candidates = [p.device for p in list_ports.comports()
                      if "Bluetooth" not in (p.description or "")]
    for dev in candidates:
        if not S.running:
            return None
        S.cube_status = f"trying {dev}"
        try:
            m = mavutil.mavlink_connection(dev, baud=115200)
            if m.wait_heartbeat(timeout=4):
                S.cube_status = f"connected on {dev}"
                return m
            m.close()
        except Exception:
            pass
    return None


def cube_thread():
    while S.running:
        m = find_cube()
        if m is None:
            S.cube_status = "not found (check USB, close Mission Planner)"
            time.sleep(3)
            continue
        m.mav.command_long_send(
            m.target_system, m.target_component,
            mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
            mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE,
            100000, 0, 0, 0, 0, 0)       # 10 Hz
        try:
            while S.running:
                msg = m.recv_match(type="ATTITUDE", blocking=True, timeout=2)
                if msg is None:
                    S.cube_status = "no attitude data"
                    continue
                heading = (math.degrees(msg.yaw) + HEADING_OFFSET_DEG) % 360
                with S.lock:
                    S.heading = heading
                    S.last_heading = time.time()
        except Exception as e:
            S.cube_status = f"error: {e}"
        finally:
            try:
                m.close()
            except Exception:
                pass
        time.sleep(2)


# ---------------- destination file ----------------
def load_dest():
    if os.path.exists(DEST_FILE):
        try:
            with open(DEST_FILE) as f:
                d = json.load(f)
            return {"lat": float(d["lat"]), "lon": float(d["lon"])}
        except (ValueError, KeyError, TypeError, OSError):
            return None
    return None


def save_dest(dest):
    with open(DEST_FILE, "w") as f:
        json.dump(dest, f)


# ---------------- map + main loop ----------------
def main():
    D = {"dest": load_dest(), "pos": None, "start": None, "msg": "", "msg_until": 0.0}
    trail = deque(maxlen=TRAIL_POINTS)

    fig, ax = plt.subplots(figsize=(8, 9))
    fig.subplots_adjust(top=0.80, bottom=0.08)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.4)
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.text(0.97, 0.97, "N\n\u2191", transform=ax.transAxes, ha="center", va="top",
            fontsize=14, fontweight="bold")

    trail_line, = ax.plot([], [], "-", color="tab:blue", lw=1, alpha=0.6)
    link_line, = ax.plot([], [], "--", color="tab:red", lw=1)
    rover_dot, = ax.plot([], [], "o", color="tab:blue", ms=10)
    dest_dot, = ax.plot([], [], "*", color="tab:red", ms=20)
    reach_circle = Circle((0, 0), THRESHOLD_M, fill=False, color="green", ls=":", lw=2)
    ax.add_patch(reach_circle)
    arrow = ax.annotate("", xy=(0, 0), xytext=(0, 0),
                        arrowprops=dict(arrowstyle="-|>", color="tab:blue", lw=2.5,
                                        shrinkA=0, shrinkB=0))
    arrow.set_visible(False)

    info = fig.text(0.5, 0.98, "", ha="center", va="top", fontsize=12, family="monospace")
    status = fig.text(0.5, 0.02, "", ha="center", va="bottom", fontsize=9, color="gray")

    def flash(text):
        D["msg"] = text
        D["msg_until"] = time.time() + 3

    def on_key(event):
        key = (event.key or "").lower()
        if key == "q":
            S.running = False
            plt.close(fig)
        elif key == "s":
            if D["pos"]:
                D["dest"] = {"lat": D["pos"][0], "lon": D["pos"][1]}
                save_dest(D["dest"])
                flash("Destination saved")
            else:
                flash("Cannot save: no GPS fix")
        elif key == "c":
            D["dest"] = None
            if os.path.exists(DEST_FILE):
                os.remove(DEST_FILE)
            flash("Destination cleared")

    fig.canvas.mpl_connect("key_press_event", on_key)
    fig.canvas.mpl_connect("close_event", lambda e: setattr(S, "running", False))

    def update(_frame):
        now = time.time()
        with S.lock:
            pos, quality, last_fix = S.pos, S.quality, S.last_fix
            heading, last_hd = S.heading, S.last_heading
        if pos and now - last_fix > SIGNAL_TIMEOUT_S:
            pos = None
        if heading is not None and now - last_hd > HEADING_TIMEOUT_S:
            heading = None
        D["pos"] = pos

        if pos:
            if D["start"] is None:
                D["start"] = pos
            if not trail or trail[-1] != pos:
                trail.append(pos)

        dest = D["dest"]
        ref = (dest["lat"], dest["lon"]) if dest else D["start"]

        # ----- drawing -----
        rx = ry = None
        if ref is not None:
            pts = [to_local(la, lo, *ref) for la, lo in trail]
            trail_line.set_data([p[0] for p in pts], [p[1] for p in pts])
            allx = [p[0] for p in pts]
            ally = [p[1] for p in pts]

            if dest:
                dest_dot.set_data([0], [0])
                reach_circle.center = (0, 0)
                reach_circle.set_visible(True)
                allx.append(0)
                ally.append(0)
            else:
                dest_dot.set_data([], [])
                reach_circle.set_visible(False)

            if pos:
                rx, ry = to_local(pos[0], pos[1], *ref)
                rover_dot.set_data([rx], [ry])
            else:
                rover_dot.set_data([], [])

            if pos and dest:
                link_line.set_data([rx, 0], [ry, 0])
            else:
                link_line.set_data([], [])

            if not allx:
                allx, ally = [0], [0]
            cx = (min(allx) + max(allx)) / 2
            cy = (min(ally) + max(ally)) / 2
            half = max((max(allx) - min(allx)) / 2, (max(ally) - min(ally)) / 2) * 1.25 + 3
            half = max(half, 6)
            ax.set_xlim(cx - half, cx + half)
            ax.set_ylim(cy - half, cy + half)

            if pos and heading is not None:
                length = half * 0.18
                arrow.set_position((rx, ry))
                arrow.xy = (rx + length * math.sin(math.radians(heading)),
                            ry + length * math.cos(math.radians(heading)))
                arrow.set_visible(True)
            else:
                arrow.set_visible(False)

        # ----- text -----
        if pos is None:
            line1 = "Waiting for GPS fix (antenna needs sky view)..."
        else:
            line1 = f"[{FIX_NAMES.get(quality, quality)}]  {pos[0]:.7f}, {pos[1]:.7f}"

        if heading is None:
            line2 = "Facing: no compass data"
        else:
            line2 = f"Facing: {direction_name(heading)} ({heading:.0f}\u00b0)"

        color = "black"
        if dest is None:
            line3 = "Press S to save destination"
        elif pos is None:
            line3 = "Destination saved - waiting for GPS"
        else:
            d = distance_m(pos[0], pos[1], dest["lat"], dest["lon"])
            b = bearing_deg(pos[0], pos[1], dest["lat"], dest["lon"])
            if d <= THRESHOLD_M:
                line3 = f"DESTINATION REACHED!  ({d:.2f} m)"
                color = "green"
            else:
                line3 = f"Go {direction_name(b)} ({b:.0f}\u00b0)  |  {d:.1f} m to destination"
                if heading is not None:
                    err = wrap180(b - heading)
                    if abs(err) <= STRAIGHT_TOL_DEG:
                        line3 += "\nStraight ahead"
                    else:
                        side = "right" if err > 0 else "left"
                        line3 += f"\nTurn {side} {abs(err):.0f}\u00b0"

        info.set_text(f"{line1}\n{line2}\n{line3}")
        info.set_color(color)

        msg = D["msg"] if now < D["msg_until"] else ""
        status.set_text(f"GPS: {S.gps_status}  |  Cube: {S.cube_status}"
                        + (f"  |  {msg}" if msg else "")
                        + "\nKeys: S = save destination, C = clear, Q = quit")

    threading.Thread(target=gps_thread, daemon=True).start()
    threading.Thread(target=cube_thread, daemon=True).start()

    ani = FuncAnimation(fig, update, interval=200, cache_frame_data=False)
    plt.show()
    S.running = False
    return ani


if __name__ == "__main__":
    main()