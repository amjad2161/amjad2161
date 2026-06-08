"""Tests for TELEMETRY-HUB module."""

from __future__ import annotations

import pytest

from brainiac.core.telemetry_hub import AnomalyType, SensorReading, TelemetryHub


@pytest.fixture
def hub():
    return TelemetryHub(window_size=20)


@pytest.mark.asyncio
async def test_ingest_normal(hub):
    reading = SensorReading(sensor_id="temp-01", value=22.5, unit="°C")
    anomaly = await hub.ingest(reading)
    assert anomaly is None


@pytest.mark.asyncio
async def test_anomaly_detection_spike(hub):
    for idx in range(15):
        await hub.ingest(SensorReading(sensor_id="s1", value=20.0 + idx * 0.01, unit="°C"))

    anomaly = await hub.ingest(SensorReading(sensor_id="s1", value=999.0, unit="°C"))
    assert anomaly is not None
    assert anomaly.anomaly_type == AnomalyType.SPIKE


@pytest.mark.asyncio
async def test_anomaly_detection_drop(hub):
    for _idx in range(15):
        await hub.ingest(SensorReading(sensor_id="s2", value=100.0, unit="Pa"))

    anomaly = await hub.ingest(SensorReading(sensor_id="s2", value=-999.0, unit="Pa"))
    assert anomaly is not None
    assert anomaly.anomaly_type == AnomalyType.DROP


@pytest.mark.asyncio
async def test_batch_ingest(hub):
    readings = [SensorReading(sensor_id=f"sensor-{i}", value=float(i), unit="V") for i in range(10)]
    anomalies = await hub.ingest_batch(readings)
    assert isinstance(anomalies, list)
    assert hub.diagnostics()["active_streams"] == 10


@pytest.mark.asyncio
async def test_anomaly_handler(hub):
    received = []
    hub.on_anomaly(lambda anomaly: received.append(anomaly))

    for _ in range(15):
        await hub.ingest(SensorReading(sensor_id="s3", value=50.0, unit="V"))

    await hub.ingest(SensorReading(sensor_id="s3", value=50000.0, unit="V"))
    assert len(received) == 1
    assert received[0].sensor_id == "s3"


def test_default_anomaly_handler_registered(hub):
    diagnostics = hub.diagnostics()
    assert diagnostics["handlers_registered"] >= 1


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
