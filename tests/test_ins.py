import time

from brainiac.core.ins import GNSSHealth, IMUReading, INS, INSPoint


def test_ins_gnss_imu_gnss_fusion_path():
    ins = INS()
    p1 = ins.update_gnss(INSPoint(32.0, 34.0), GNSSHealth(True))
    assert p1.lat == 32.0
    imu_ts = time.time() + 0.1
    p2 = ins.update_imu(IMUReading(accel_x_mps2=0.5, accel_y_mps2=0.1, timestamp=imu_ts))
    assert p2 is not None
    p3 = ins.update_gnss(INSPoint(32.0001, 34.0001), GNSSHealth(True))
    assert p3.lat > 32.0


def test_ins_corridor_check():
    ins = INS()
    corridor = [INSPoint(32.0, 34.0), INSPoint(32.1, 34.1)]
    assert ins.corridor_check(INSPoint(32.05, 34.05), corridor, width_m=5000)
    assert not ins.corridor_check(INSPoint(33.0, 35.0), corridor, width_m=100)
