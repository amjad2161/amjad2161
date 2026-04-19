"""Tests for TELEMETRY-HUB module."""
import pytest
from brainiac.core.telemetry_hub import TelemetryHub, SensorReading, AnomalyType


@pytest.fixture
def hub():
    return TelemetryHub(window_size=20)


@pytest.mark.asyncio
async def test_ingest_normal(hub):
    reading = SensorReading(sensor_id="temp-01", value=22.5, unit="°C")
    anomaly = await hub.ingest(reading)
    assert anomaly is None   # single reading cannot trigger anomaly


@pytest.mark.asyncio
async def test_anomaly_detection_spike(hub):
    """Injecting a spike should be detected after enough baseline readings."""
    # Establish baseline
    for i in range(15):
        await hub.ingest(SensorReading(sensor_id="s1", value=20.0 + i * 0.01, unit="°C"))

    # Inject a huge spike
    anomaly = await hub.ingest(SensorReading(sensor_id="s1", value=999.0, unit="°C"))
    assert anomaly is not None
    assert anomaly.anomaly_type == AnomalyType.SPIKE
    assert anomaly.severity > 0


@pytest.mark.asyncio
async def test_anomaly_detection_drop(hub):
    for _i in range(15):
        await hub.ingest(SensorReading(sensor_id="s2", value=100.0, unit="Pa"))

    anomaly = await hub.ingest(SensorReading(sensor_id="s2", value=-999.0, unit="Pa"))
    assert anomaly is not None
    assert anomaly.anomaly_type == AnomalyType.DROP


@pytest.mark.asyncio
async def test_batch_ingest(hub):
    readings = [
        SensorReading(sensor_id=f"sensor-{i}", value=float(i), unit="V")
        for i in range(10)
    ]
    anomalies = await hub.ingest_batch(readings)
    assert isinstance(anomalies, list)
    assert hub.diagnostics()["active_streams"] == 10


@pytest.mark.asyncio
async def test_anomaly_handler(hub):
    received = []
    hub.on_anomaly(lambda a: received.append(a))

    for _ in range(15):
        await hub.ingest(SensorReading(sensor_id="s3", value=50.0, unit="V"))

    await hub.ingest(SensorReading(sensor_id="s3", value=50000.0, unit="V"))
    assert len(received) == 1
    assert received[0].sensor_id == "s3"


def test_prometheus_metrics(hub):
    metrics = hub.prometheus_metrics()
    assert "brainiac_telemetry_readings_total" in metrics
    assert "brainiac_telemetry_active_sensors" in metrics


def test_stream_summary_empty(hub):
    assert hub.stream_summary() == []


def test_diagnostics(hub):
    d = hub.diagnostics()
    assert d["status"] == "ONLINE"
    assert d["window_size"] == 20
