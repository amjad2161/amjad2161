from brainiac.core.cyber_shield import CyberShield


def test_detect_gps_spoofing_indicators():
    shield = CyberShield()
    low = shield.detect_gps_spoofing(position_jump_m=1, speed_mps=1, snr_drop_db=0, clock_bias_ms=0)
    high_jump = shield.detect_gps_spoofing(position_jump_m=1000)
    high_speed = shield.detect_gps_spoofing(speed_mps=200)
    high_snr = shield.detect_gps_spoofing(snr_drop_db=30)
    high_clock = shield.detect_gps_spoofing(clock_bias_ms=500)
    assert low["spoofing_detected"] is False
    assert high_jump["risk_score"] > 0
    assert high_speed["risk_score"] > 0
    assert high_snr["risk_score"] > 0
    assert high_clock["risk_score"] > 0
