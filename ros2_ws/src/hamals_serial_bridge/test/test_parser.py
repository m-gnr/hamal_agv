from hamals_serial_bridge.protocol import (
    compute_checksum,
    decode_line,
    encode_cmd,
    encode_fork_cmd,
)


def make_frame(payload: str) -> str:
    return f"${payload}*{compute_checksum(payload):02X}\n"


def test_encode_fork_cmd_uses_existing_frame_style():
    payload = "FORK,UP"
    expected = make_frame(payload)

    assert encode_fork_cmd("UP") == expected
    assert encode_fork_cmd(" up ") == expected


def test_decode_fork_state_frame():
    decoded = decode_line(make_frame("FORK_STATE,12345678,1,0,0,0"))

    assert decoded == {
        "type": "fork_state",
        "t_us": 12345678,
        "state": 1,
        "upper_limit": False,
        "lower_limit": False,
        "error_code": 0,
    }


def test_decode_fork_state_bad_checksum_returns_none():
    assert decode_line("$FORK_STATE,12345678,1,0,0,0*00\n") is None


def test_decode_physical_safety_inputs():
    assert decode_line(make_frame("SAFETY,42,1,0")) == {
        "type": "safety",
        "t_us": 42,
        "estop": True,
        "manual": False,
    }


def test_encode_cmd_regression():
    payload = "CMD,0.100,-0.200"
    assert encode_cmd(0.1, -0.2) == make_frame(payload)


def test_decode_enc_regression():
    decoded = decode_line(make_frame("ENC,123,10,-20"))

    assert decoded == {
        "type": "enc",
        "t_us": 123,
        "dl": 10,
        "dr": -20,
    }


def test_decode_imu_regression():
    decoded = decode_line(make_frame("IMU,123,0.1,1.0,2.0,3.0"))

    assert decoded == {
        "type": "imu",
        "t_us": 123,
        "gz": 0.1,
        "ax": 1.0,
        "ay": 2.0,
        "az": 3.0,
    }


def test_decode_legacy_odom_regression():
    decoded = decode_line(make_frame("ODOM,123,1.0,2.0,3.0,0.4,0.5"))

    assert decoded == {
        "type": "odom",
        "t_us": 123,
        "x": 1.0,
        "y": 2.0,
        "yaw": 3.0,
        "v": 0.4,
        "w": 0.5,
    }
