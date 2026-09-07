# hamals_serial_bridge/protocol.py

# ======================================================
# CHECKSUM
# ======================================================

def compute_checksum(payload: str) -> int:
    """Compute XOR checksum of payload without frame delimiters."""
    cs = 0
    for c in payload:
        cs ^= ord(c)
    return cs


# ======================================================
# ROS → MCU
# ======================================================

def encode_cmd(v: float, w: float) -> str:
    """Encode cmd_vel to framed protocol."""
    payload = f"CMD,{v:.3f},{w:.3f}"
    cs = compute_checksum(payload)
    return f"${payload}*{cs:02X}\n"


def encode_fork_cmd(cmd: str) -> str:
    """Encode fork command to framed protocol."""
    cmd = cmd.strip().upper()
    payload = f"FORK,{cmd}"
    cs = compute_checksum(payload)
    return f"${payload}*{cs:02X}\n"


# ======================================================
# MCU → ROS
# ======================================================

def decode_line(line: str):
    """
    Decode framed protocol line.

    Expected:
      $ENC,t_us,dl,dr*CS
      $IMU,t_us,gz,ax,ay,az*CS
      $ODOM,t_us,x,y,yaw,v,w*CS
      $FORK_STATE,t_us,state,upper,lower,error*CS
      $SAFETY,t_us,estop,manual*CS
      $OBSTACLE,t_us,detected*CS
    """

    if not line:
        return None

    line = line.strip()

    # --------------------------------------------------
    # Frame start
    # --------------------------------------------------

    if not line.startswith("$"):
        return None

    # --------------------------------------------------
    # Checksum
    # --------------------------------------------------

    try:
        body, cs_part = line[1:].split("*", 1)
    except ValueError:
        return None

    try:
        received_cs = int(cs_part, 16)
    except ValueError:
        return None

    calc_cs = compute_checksum(body)

    if calc_cs != received_cs:
        return None

    # --------------------------------------------------
    # Payload
    # --------------------------------------------------

    parts = body.split(",")

    try:

        # ==================================================
        # ENCODER
        # ==================================================

        if parts[0] == "ENC" and len(parts) == 4:
            return {
                "type": "enc",
                "t_us": int(parts[1]),
                "dl": int(parts[2]),
                "dr": int(parts[3]),
            }

        # ==================================================
        # IMU
        # ==================================================

        elif parts[0] == "IMU" and len(parts) == 6:
            return {
                "type": "imu",
                "t_us": int(parts[1]),
                "gz": float(parts[2]),
                "ax": float(parts[3]),
                "ay": float(parts[4]),
                "az": float(parts[5]),
            }

        # ==================================================
        # ODOM
        # ==================================================

        elif parts[0] == "ODOM" and len(parts) == 7:
            return {
                "type": "odom",
                "t_us": int(parts[1]),
                "x": float(parts[2]),
                "y": float(parts[3]),
                "yaw": float(parts[4]),
                "v": float(parts[5]),
                "w": float(parts[6]),
            }

        # ==================================================
        # FORK STATE
        # ==================================================

        elif parts[0] == "FORK_STATE" and len(parts) == 6:
            return {
                "type": "fork_state",
                "t_us": int(parts[1]),
                "state": int(parts[2]),
                "upper_limit": bool(int(parts[3])),
                "lower_limit": bool(int(parts[4])),
                "error_code": int(parts[5]),
            }

        # ==================================================
        # SAFETY
        # ==================================================

        elif parts[0] == "SAFETY" and len(parts) == 4:
            return {
                "type": "safety",
                "t_us": int(parts[1]),
                "estop": bool(int(parts[2])),
                "manual": bool(int(parts[3])),
            }

        # ==================================================
        # E18-D80NK OBSTACLE SENSOR
        # ==================================================

        elif parts[0] == "OBSTACLE" and len(parts) == 3:
            return {
                "type": "obstacle",
                "t_us": int(parts[1]),
                "detected": bool(int(parts[2])),
            }

        # ==================================================
        # UNKNOWN
        # ==================================================

        else:
            return None

    except (ValueError, TypeError):
        return None