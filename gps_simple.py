"""
Simple GPS waypoint program (beginner version) - Emlid Reach M2 over TCP, Windows.

Run:   py gps_simple.py
Keys:  S = save current position as destination,  Q = quit
"""
import json
import math
import msvcrt          # Windows keyboard input
import os
import socket
import time

# ---------------- settings ----------------
HOST, PORT = "192.168.42.1", 9001     # the M2's address and TCP port
THRESHOLD_M = 2.0                     # "reached" distance in meters
DEST_FILE = "destination.json"        # saved destination lives here
SIGNAL_TIMEOUT_S = 3.0                # no valid fix for this long = signal lost


# ---------------- piece 2: NMEA text -> decimal degrees ----------------
def to_degrees(value, hemi):
    dot = value.index(".")
    degrees = float(value[:dot - 2])      # e.g. "12"
    minutes = float(value[dot - 2:])      # e.g. "58.12345"
    result = degrees + minutes / 60
    return -result if hemi in ("S", "W") else result


def parse_gga(line):
    """Return (lat, lon, quality) from a GGA line, or None if unusable."""
    try:
        parts = line.lstrip("$").split("*")[0].split(",")
        if len(parts) < 10 or not parts[0].endswith("GGA"):
            return None
        if parts[2] == "" or parts[4] == "" or parts[6] in ("", "0"):
            return None                              # empty fields / no fix
        lat = to_degrees(parts[2], parts[3])
        lon = to_degrees(parts[4], parts[5])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return None                              # impossible coordinates
        return lat, lon, int(parts[6])
    except (ValueError, IndexError):
        return None                                  # garbled line: ignore it


# ---------------- piece 3: distance in meters (haversine) ----------------
def distance_m(lat1, lon1, lat2, lon2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


FIX_NAMES = {1: "SINGLE", 2: "DGPS", 4: "RTK FIXED", 5: "RTK FLOAT"}


def main():
    # ---------------- piece 4: load saved destination ----------------
    dest = None
    if os.path.exists(DEST_FILE):
        try:
            dest = json.load(open(DEST_FILE))
        except ValueError:
            dest = None

    # ---------------- piece 1: connect to the M2 ----------------
    print(f"Connecting to {HOST}:{PORT} ...")
    sock = socket.create_connection((HOST, PORT), timeout=3)
    sock.settimeout(0.2)                  # recv waits at most 0.2 s, so the loop keeps running

    buffer = ""
    current = None                        # (lat, lon) or None when there is no fix
    quality = 0
    last_fix_time = 0.0

    # ---------------- piece 5: the loop ----------------
    while True:
        # 1) read new data
        try:
            data = sock.recv(1024)
            if not data:
                print("\nConnection closed by the M2.")
                break
            buffer += data.decode(errors="ignore")
        except socket.timeout:
            pass

        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            result = parse_gga(line.strip())
            if result:
                lat, lon, quality = result
                current = (lat, lon)
                last_fix_time = time.time()

        # signal lost? forget the old position
        if time.time() - last_fix_time > SIGNAL_TIMEOUT_S:
            current = None

        # 2) keys
        if msvcrt.kbhit():
            key = msvcrt.getwch().lower()
            if key == "q":
                break
            if key == "s":
                if current:
                    dest = {"lat": current[0], "lon": current[1]}
                    json.dump(dest, open(DEST_FILE, "w"))
                else:
                    print("\nCannot save: no GPS fix.")

        # 3) display
        if current is None:
            text = "Waiting for GPS fix (antenna needs sky view)..."
        else:
            text = f"[{FIX_NAMES.get(quality, quality)}] Now: {current[0]:.7f}, {current[1]:.7f}"
            if dest:
                d = distance_m(current[0], current[1], dest["lat"], dest["lon"])
                text += f" | Dest: {dest['lat']:.7f}, {dest['lon']:.7f} | {d:7.2f} m"
                if d <= THRESHOLD_M:
                    text += "  DESTINATION REACHED!"
            else:
                text += " | Press S to save destination"
        print("\r" + text.ljust(140), end="", flush=True)

    sock.close()
    print("\nBye.")


if __name__ == "__main__":
    main()