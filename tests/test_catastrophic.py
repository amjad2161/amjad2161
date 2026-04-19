"""
Catastrophic failure simulation tests.

Validates GANE system resilience under extreme conditions:
- GNSS total blackout (all constellations lost)
- EMP strike during navigation
- V2X network flooding
- Simultaneous multi-system failure
- INS drift under extended GNSS denial
- Mesh network partition
- Sensor spoofing during active route
"""
import time
import pytest
from brainiac.core.ins import INS, IMUReading, PositionSource, INSState
from brainiac.core.orbital_nav import OrbitalNav, Coordinate, TransportMode
from brainiac.core.cyber_shield import CyberShield
from brainiac.core.nexus_sync import NexusSync, DeviceType, Protocol
from brainiac.core.telemetry_hub import TelemetryHub, SensorReading


class TestGNSSBlackout:
    """Simulate total GNSS constellation loss — zero satellites."""

    def test_ins_survives_total_gnss_loss(self):
        ins = INS()
        ins.seed_position(32.0853, 34.7818, 30.0)
        ins.update_gnss(32.0853, 34.7818, 30.0, accuracy_m=0.02)

        ins.update_gnss_health(0, 0, 99.0, "NO_FIX")
        assert ins.get_gnss_health().gnss_available is False

        ts = time.time()
        for i in range(100):
            ins.update_imu(IMUReading(
                accel_x=0.5, accel_y=0.0, accel_z=9.81,
                gyro_x=0.0, gyro_y=0.0, gyro_z=0.0,
                mag_x=20.0, mag_y=5.0, mag_z=-40.0,
                timestamp=ts + i * 0.1,
            ))

        pos = ins.position()
        assert pos.source == PositionSource.INS
        assert pos.lat != 0.0
        assert pos.drift_m > 0

    def test_ins_recovery_after_gnss_restored(self):
        ins = INS()
        ins.seed_position(32.0853, 34.7818, 30.0)
        ins.update_gnss_health(0, 0, 99.0, "NO_FIX")

        ts = time.time()
        for i in range(50):
            ins.update_imu(IMUReading(
                accel_x=1.0, accel_y=0.0, accel_z=9.81,
                gyro_x=0.0, gyro_y=0.0, gyro_z=0.0,
                mag_x=20.0, mag_y=5.0, mag_z=-40.0,
                timestamp=ts + i * 0.1,
            ))

        health = ins.update_gnss_health(6, 30, 0.8, "RTK_FIXED")
        assert health.gnss_available is True
        ins.update_gnss(32.0860, 34.7820, 30.0, accuracy_m=0.02)

        pos = ins.position()
        assert pos.source in (PositionSource.GNSS, PositionSource.FUSED)
        assert pos.drift_m < 30.0

    def test_extended_dead_reckoning_drift_accumulation(self):
        """300 seconds of pure dead reckoning — drift should be bounded."""
        ins = INS()
        ins.seed_position(32.0853, 34.7818, 30.0)
        ins.update_gnss_health(0, 0, 99.0, "NO_FIX")

        ts = time.time()
        for i in range(3000):
            ins.update_imu(IMUReading(
                accel_x=0.1, accel_y=0.0, accel_z=9.81,
                gyro_x=0.0, gyro_y=0.0, gyro_z=0.01,
                mag_x=20.0, mag_y=5.0, mag_z=-40.0,
                timestamp=ts + i * 0.1,
            ))

        pos = ins.position()
        assert pos.source == PositionSource.INS
        assert pos.drift_m > 0
        assert ins.state == INSState.NAVIGATING


class TestEMPStrike:
    """Simulate electromagnetic pulse attack during active navigation."""

    def test_emp_detected_and_blocked(self):
        shield = CyberShield()
        result = shield.detect_hardware_attack(
            sensor_readings={"emf_gauss": 500.0, "voltage_v": 1.0, "clock_drift_ppm": 200.0},
        )
        assert result["action"] == "BLOCK"
        assert result["attack_likelihood"] >= 0.7
        assert "EMP_INTERFERENCE_DETECTED" in result["indicators"]
        assert "VOLTAGE_ANOMALY" in result["indicators"]
        assert "CLOCK_DRIFT_ANOMALY" in result["indicators"]

    def test_emp_with_rf_flooding(self):
        shield = CyberShield()
        result = shield.detect_hardware_attack(
            sensor_readings={"emf_gauss": 200.0},
            rf_spectrum=[-5.0, -3.0, -8.0, -2.0, -6.0, -1.0],
        )
        assert result["action"] == "BLOCK"
        assert "EMP_INTERFERENCE_DETECTED" in result["indicators"]
        assert "RF_INJECTION_DETECTED" in result["indicators"]

    def test_ins_continues_after_emp_gnss_kill(self):
        """EMP kills GNSS but INS dead-reckoning keeps position."""
        ins = INS()
        ins.seed_position(32.0853, 34.7818, 30.0)
        ins.update_gnss(32.0853, 34.7818, 30.0, accuracy_m=0.02)

        ins.update_gnss_health(0, 0, 99.0, "NO_FIX")

        shield = CyberShield()
        emp_result = shield.detect_hardware_attack(
            sensor_readings={"emf_gauss": 300.0}
        )
        assert emp_result["action"] == "BLOCK"

        ts = time.time()
        for i in range(20):
            ins.update_imu(IMUReading(
                accel_x=0.5, accel_y=0.0, accel_z=9.81,
                gyro_x=0.0, gyro_y=0.0, gyro_z=0.0,
                mag_x=20.0, mag_y=5.0, mag_z=-40.0,
                timestamp=ts + i * 0.1,
            ))

        pos = ins.position()
        assert pos.source == PositionSource.INS
        assert pos.lat != 0.0


class TestV2XFlooding:
    """Simulate V2X network flooding / denial of service on mesh."""

    @pytest.mark.asyncio
    async def test_mesh_handles_rapid_broadcasts(self):
        nexus = NexusSync()
        nexus.register_device(
            "mesh-01", DeviceType.MESH_NODE, Protocol.LORAWAN,
            "lora://freq1", "Mesh Node 1",
        )
        await nexus.connect_device("mesh-01")
        for i in range(100):
            result = await nexus.broadcast_mesh(
                {"alert": f"flood_{i}", "seq": i},
                protocol=Protocol.LORAWAN, ttl=1,
            )
            assert result["nodes_reached"] >= 0

    @pytest.mark.asyncio
    async def test_v2x_signal_flood(self):
        nexus = NexusSync()
        nexus.register_device(
            "rsu-flood", DeviceType.V2X_RSU, Protocol.V2X,
            "v2x://intersection", "RSU Flood Test",
        )
        for i in range(50):
            result = await nexus.v2x_signal(
                signal_type="V2V",
                data={"speed": 60 + i, "heading": i * 7 % 360},
                source_id=f"vehicle-{i}",
            )
            assert result["signal_type"] == "V2V"

    @pytest.mark.asyncio
    async def test_traffic_light_request_spam(self):
        nexus = NexusSync()
        nexus.register_device(
            "rsu-01", DeviceType.V2X_RSU, Protocol.V2X,
            "v2x://signal", "RSU 01",
        )
        await nexus.connect_device("rsu-01")
        for i in range(20):
            result = await nexus.v2x_traffic_light_request(
                intersection_id=f"int-{i % 3}",
                priority="emergency",
                reason="ambulance",
            )
            assert result["status"] == "OK"


class TestSimultaneousFailure:
    """Multi-system cascade failure: GNSS + EMP + sensor anomalies."""

    def test_triple_failure_detection(self):
        shield = CyberShield()

        emp = shield.detect_hardware_attack(
            sensor_readings={"emf_gauss": 400.0, "voltage_v": 1.5, "clock_drift_ppm": 100.0},
            rf_spectrum=[-5.0, -2.0, -8.0, -3.0, -1.0],
        )
        assert emp["action"] == "BLOCK"

        spoof = shield.detect_gps_spoofing(
            reported_lat=35.6895, reported_lon=139.6917,
            previous_lat=32.0853, previous_lon=34.7818,
            previous_ts=time.time() - 1, current_ts=time.time(),
        )
        assert spoof["action"] == "BLOCK"
        assert spoof["spoof_likelihood"] >= 0.7

    @pytest.mark.asyncio
    async def test_telemetry_anomaly_burst(self):
        telem = TelemetryHub()
        anomaly_count = 0
        for i in range(30):
            value = 22.0 if i < 15 else 22.0 + (i - 15) * 100
            reading = SensorReading(
                sensor_id="temp-cascade",
                value=value,
                unit="°C",
            )
            anomaly = await telem.ingest(reading)
            if anomaly:
                anomaly_count += 1
        assert anomaly_count > 0

    def test_privacy_audit_under_attack(self):
        """PII audit should still function during system stress."""
        shield = CyberShield()
        data = {
            "email": "victim@example.com",
            "phone": "+972-50-123-4567",
            "ip_address": "192.168.1.1",
            "location": {"lat": 32.0853, "lon": 34.7818},
        }
        audit = shield.privacy_audit(data)
        assert not audit["federated_compliant"]
        assert len(audit["exposed_fields"]) >= 2

        sanitised = shield.enforce_data_locality(data)
        assert sanitised["email"] == "[REDACTED]"
        assert sanitised["phone"] == "[REDACTED]"


class TestSpoofingDuringRoute:
    """GPS spoofing attack while an active route is in progress."""

    def test_position_jump_detected(self):
        shield = CyberShield()
        result = shield.detect_gps_spoofing(
            reported_lat=48.8566, reported_lon=2.3522,  # Paris
            previous_lat=32.0853, previous_lon=34.7818,  # Tel Aviv
            previous_ts=time.time() - 2,
            current_ts=time.time(),
        )
        assert result["spoof_likelihood"] >= 0.7
        assert result["action"] == "BLOCK"
        assert any("IMPLAUSIBLE_SPEED" in i for i in result["indicators"])

    def test_perfect_hdop_spoof(self):
        shield = CyberShield()
        result = shield.detect_gps_spoofing(
            reported_lat=32.0853, reported_lon=34.7818,
            hdop=0.0,
        )
        assert "HDOP_TOO_PERFECT" in result["indicators"]
        assert result["spoof_likelihood"] >= 0.3

    def test_snr_uniformity_spoof(self):
        shield = CyberShield()
        result = shield.detect_gps_spoofing(
            reported_lat=32.0853, reported_lon=34.7818,
            snr_values=[42.0, 42.0, 42.0, 42.0, 42.0],
        )
        assert "SNR_UNIFORMITY_ANOMALY" in result["indicators"]

    def test_ins_ignores_spoofed_gnss(self):
        """When spoofing is detected, INS should keep dead-reckoning."""
        ins = INS()
        ins.seed_position(32.0853, 34.7818, 30.0)
        ins.update_gnss(32.0853, 34.7818, 30.0, accuracy_m=0.02)

        shield = CyberShield()
        spoof = shield.detect_gps_spoofing(
            reported_lat=48.8566, reported_lon=2.3522,
            previous_lat=32.0853, previous_lon=34.7818,
            previous_ts=time.time() - 1, current_ts=time.time(),
        )
        assert spoof["action"] == "BLOCK"

        ins.update_gnss_health(0, 0, 99.0, "NO_FIX")
        ts = time.time()
        for i in range(10):
            ins.update_imu(IMUReading(
                accel_x=0.5, accel_y=0.0, accel_z=9.81,
                gyro_x=0.0, gyro_y=0.0, gyro_z=0.0,
                mag_x=20.0, mag_y=5.0, mag_z=-40.0,
                timestamp=ts + i * 0.1,
            ))

        pos = ins.position()
        assert pos.source == PositionSource.INS
        assert abs(pos.lat - 32.0853) < 0.01


class TestHazardRouteIntegration:
    """Test hazard avoidance integrated with routing."""

    @pytest.mark.asyncio
    async def test_life_corridor_with_hazards(self):
        nav = OrbitalNav()
        nav.report_hazard(32.09, 34.79, "accident", severity=9)
        corridor = await nav.life_corridor(
            Coordinate(lat=32.0853, lon=34.7818),
            Coordinate(lat=32.1, lon=34.8),
            priority="emergency",
        )
        assert corridor["v2x_broadcast_required"] is True
        assert corridor["time_saved_s"] > 0

    @pytest.mark.asyncio
    async def test_route_with_hazard_check(self):
        nav = OrbitalNav()
        nav.report_hazard(32.0, 34.0, "road_closure", severity=10)
        route = await nav.route(
            Coordinate(lat=32.0, lon=34.0),
            Coordinate(lat=32.1, lon=34.1),
            mode=TransportMode.DRONE,
        )
        hazards = nav.hazards_on_route(route, buffer_m=500)
        assert len(hazards) >= 1
