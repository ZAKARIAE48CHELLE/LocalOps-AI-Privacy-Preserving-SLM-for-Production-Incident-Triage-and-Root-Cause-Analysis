"""
Energy & Power Consumption Tracker for LocalOps AI Evaluation.
Integrates GPU power draw over time to compute cumulative energy (Wh / kWh),
average power, carbon footprint, and workload energy efficiency.
"""

import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENERGY_FILE = PROJECT_ROOT / "reports" / "evaluation" / "energy_telemetry.json"


class EnergyTracker:
    _instance: Optional["EnergyTracker"] = None
    _lock = threading.Lock()

    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.thread: Optional[threading.Thread] = None

        # Telemetry metrics
        self.current_power_w: float = 0.0
        self.power_limit_w: float = 85.0
        self.energy_wh: float = 0.0
        self.peak_power_w: float = 0.0
        self.min_power_w: float = 999.0
        self.total_power_sum: float = 0.0
        self.sample_count: int = 0
        self.total_active_seconds: float = 0.0
        self.last_sample_time: Optional[float] = None
        self.start_timestamp: float = time.time()

        # Load existing state if available
        self._load_state()

    @classmethod
    def get_instance(cls) -> "EnergyTracker":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
                cls._instance.start()
            return cls._instance

    def _query_power(self) -> float:
        """Queries instant power draw from nvidia-smi."""
        try:
            cmd = [
                "nvidia-smi",
                "--query-gpu=power.draw,power.limit",
                "--format=csv,noheader,nounits",
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
            if res.returncode == 0 and res.stdout.strip():
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                if parts and parts[0] != "[N/A]":
                    p_w = float(parts[0])
                    if len(parts) > 1 and parts[1] != "[N/A]":
                        try:
                            self.power_limit_w = float(parts[1])
                        except Exception:
                            pass
                    # Filter physically impossible sensor spikes exceeding hardware ceiling (85.0W for RTX 3070 Laptop)
                    ceiling = self.power_limit_w if self.power_limit_w > 0 else 85.0
                    if p_w > ceiling:
                        p_w = ceiling
                    return p_w
        except Exception:
            pass
        return 0.0

    def _load_state(self):
        """Loads accumulated energy state from persistent file."""
        if ENERGY_FILE.exists():
            try:
                with open(ENERGY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.energy_wh = float(data.get("energy_wh", 0.0))
                    self.total_active_seconds = float(data.get("total_active_seconds", 0.0))
                    self.peak_power_w = float(data.get("peak_power_w", 0.0))
                    self.sample_count = int(data.get("sample_count", 0))
                    self.total_power_sum = float(data.get("total_power_sum", 0.0))
            except Exception:
                pass

    def _save_state(self):
        """Persists energy telemetry state to JSON."""
        try:
            ENERGY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(ENERGY_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "energy_wh": round(self.energy_wh, 4),
                        "energy_kwh": round(self.energy_wh / 1000.0, 6),
                        "total_active_seconds": round(self.total_active_seconds, 2),
                        "average_power_w": round(self.get_average_power(), 2),
                        "peak_power_w": round(self.peak_power_w, 2),
                        "sample_count": self.sample_count,
                        "total_power_sum": round(self.total_power_sum, 2),
                        "last_updated": time.time(),
                    },
                    f,
                    indent=2,
                )
        except Exception:
            pass

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        self._save_state()

    def _monitor_loop(self):
        """Background sampling loop running every 1.5s."""
        last_save = time.time()
        while self.running:
            now = time.time()
            power = self._query_power()

            with self.lock:
                if power > 0:
                    if self.last_sample_time is not None:
                        dt = now - self.last_sample_time
                        # Trapezoidal integration of energy in Watt-hours: (P_prev + P_curr)/2 * dt / 3600
                        avg_p = (self.current_power_w + power) / 2.0
                        delta_wh = (avg_p * dt) / 3600.0
                        self.energy_wh += delta_wh
                        self.total_active_seconds += dt

                    self.current_power_w = power
                    self.total_power_sum += power
                    self.sample_count += 1
                    if power > self.peak_power_w:
                        self.peak_power_w = power
                    if power < self.min_power_w:
                        self.min_power_w = power
                self.last_sample_time = now

            if now - last_save >= 10.0:
                with self.lock:
                    self._save_state()
                last_save = now

            time.sleep(1.5)

    def get_average_power(self) -> float:
        if self.sample_count > 0:
            return self.total_power_sum / self.sample_count
        return self.current_power_w

    def get_telemetry(self, completed_records: int = 0, total_records: int = 4320) -> Dict[str, Any]:
        with self.lock:
            kwh = self.energy_wh / 1000.0
            avg_p = self.get_average_power()

            # Carbon footprint (grams CO2): 385g CO2 per kWh (global grid average)
            carbon_co2_g = kwh * 385.0

            # Cost estimation ($0.15 / kWh)
            cost_usd = kwh * 0.15

            # Energy efficiency: Wh per 100 samples
            wh_per_100_samples = 0.0
            if completed_records > 0:
                wh_per_100_samples = (self.energy_wh / completed_records) * 100.0

            # Projected total energy for the complete benchmark run
            projected_total_kwh = 0.0
            if completed_records > 0 and total_records > 0:
                projected_total_kwh = (kwh / completed_records) * total_records

            return {
                "current_power_w": round(self.current_power_w, 1),
                "power_limit_w": round(self.power_limit_w, 1),
                "power_pct": round((self.current_power_w / max(1.0, self.power_limit_w)) * 100, 1),
                "average_power_w": round(avg_p, 1),
                "peak_power_w": round(self.peak_power_w, 1),
                "energy_wh": round(self.energy_wh, 2),
                "energy_kwh": round(kwh, 4),
                "active_duration_formatted": self._format_duration(self.total_active_seconds),
                "active_duration_seconds": round(self.total_active_seconds, 1),
                "wh_per_100_samples": round(wh_per_100_samples, 2),
                "projected_total_kwh": round(projected_total_kwh, 3),
                "carbon_co2_g": round(carbon_co2_g, 2),
                "estimated_cost_usd": round(cost_usd, 3),
            }

    @staticmethod
    def _format_duration(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h}h {m}m {s}s"
        return f"{m}m {s}s"
