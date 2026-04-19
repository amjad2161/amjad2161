"""Provider interfaces for weather, traffic and reverse geocoding."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class WeatherProvider(ABC):
    @abstractmethod
    def weather_factor(self, lat: float, lon: float) -> float:
        raise NotImplementedError


class SyntheticWeatherProvider(WeatherProvider):
    def weather_factor(self, lat: float, lon: float) -> float:
        return 1.15 if abs(lat) > 55 else 1.0


class TrafficProvider(ABC):
    @abstractmethod
    def predict_traffic_factor(self, hour: int) -> float:
        raise NotImplementedError


class TimeOfDayTrafficProvider(TrafficProvider):
    def predict_traffic_factor(self, hour: int) -> float:
        return 1.4 if hour in {7, 8, 9, 16, 17, 18} else 1.0


class ReverseGeocoder(ABC):
    @abstractmethod
    def reverse(self, lat: float, lon: float) -> str:
        raise NotImplementedError


class SyntheticReverseGeocoder(ReverseGeocoder):
    def reverse(self, lat: float, lon: float) -> str:
        hemi_ns = "N" if lat >= 0 else "S"
        hemi_ew = "E" if lon >= 0 else "W"
        return f"{abs(lat):.3f}{hemi_ns}, {abs(lon):.3f}{hemi_ew}"
