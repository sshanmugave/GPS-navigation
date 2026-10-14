import math
import sys
import time
from pymavlink import mavutil
from serial.tools import list_ports

PORT = None            # set "COM23" to skip auto-detect
BAUD = 115200          # ignored for USB
RATE_HZ = 10

DIRECTIONS = ["North", "North-East", "East", "South-East",
              "South", "South-West", "West", "North-West"]


def heading_to_direction(heading):
    """0-360 degrees -> compass name (N, NE, E, SE, S, SW, W, NW)."""
    idx = int((heading + 22.5) // 45) % 8
    return DIRECTIONS[idx]


def find_mavlink_port():
    if PORT:
        candidates = [PORT]
    else:
        candidates = [p.device for p in list_ports.comports()
                      if "Bluetooth" not in (p.description or "")]
    print("Trying ports:", candidates)

    for dev in candidates:
        try:
            m = mavutil.mavlink_connection(dev, baud=BAUD)
            if m.wait_heartbeat(timeout=4):
                print(f"Heartbeat OK on {dev}")
                return m
            print(f"{dev}: no heartbeat")
            m.close()
        except Exception as e:
            print(f"{dev}: error -> {e}")
    return None


def main():
    master = find_mavlink_port()
    if master is None:
        print("No MAVLink port found. Check cable, and close Mission Planner.")
        sys.exit(1)

    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL, 0,
        mavutil.mavlink.MAVLINK_MSG_ID_ATTITUDE,
        int(1e6 / RATE_HZ), 0, 0, 0, 0, 0)

    print("Reading orientation... Ctrl+C to stop\n")
    last = time.time()
    try:
        while True:
            msg = master.recv_match(type="ATTITUDE", blocking=True, timeout=2)
            if msg is None:
                print("No ATTITUDE data (2 s)...")
                continue

            roll = math.degrees(msg.roll)
            pitch = math.degrees(msg.pitch)
            heading = (math.degrees(msg.yaw) + 360) % 360
            direction = heading_to_direction(heading)

            now = time.time()
            if now - last >= 0.2:   # update 5 times per second
                print(f"\rFacing: {direction:<11} | heading {heading:6.1f}° | "
                      f"roll {roll:6.1f}  pitch {pitch:6.1f}   ",
                      end="", flush=True)
                last = now
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        master.close()


if __name__ == "__main__":
    main()