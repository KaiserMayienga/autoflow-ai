"""Data access interface. In-memory seed now; a PostgresRepo (Neon) in Phase 2."""
from typing import Protocol


class VehicleRepo(Protocol):
    def history(self, vehicle: dict) -> list[dict]: ...


class InMemoryRepo:
    def history(self, vehicle: dict) -> list[dict]:
        if (vehicle.get("make"), vehicle.get("model"), vehicle.get("year")) == ("Toyota", "Corolla", 2018):
            return [
                {"date": "2025-03-12", "work": "Oil and filter change"},
                {"date": "2025-09-02", "work": "Tyre rotation and alignment check"},
            ]
        return []
