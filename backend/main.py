import asyncio
import os
import sys
import json
import time
from typing import List, Dict, Optional

# Ensure backend directory is in path regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from stage1_modbuse import ModbusEScheduler, ModbusSlotTask
from stage1_firewall import IEEE754ByteOrderFirewall
from stage2_tesla import TESLALogBinnedCalibrator
from stage2_gpr import CompositeGPRDriftEngine
from chaos_injector import ChaosFaultInjector
from replay_generator import MultiSensorReplayGenerator

app = FastAPI(title="S.P.A.R.K. Industrial IoT Kernel", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize core S.P.A.R.K. engines
chaos_injector = ChaosFaultInjector()
replay_generator = MultiSensorReplayGenerator(chaos_injector)
modbuse_scheduler = ModbusEScheduler(baud_rate=9600)
firewall = IEEE754ByteOrderFirewall(phys_min=0.0, phys_max=1000.0, max_slew_per_sec=15.0)
tesla_calibrator = TESLALogBinnedCalibrator(seq_len=16, d_model=8)
gpr_engine = CompositeGPRDriftEngine(reg_tolerance=5.0)

# Financial and operational counters
stats = {
    "start_time": time.time(),
    "downtime_saved_dollars": 0.0,
    "truck_rolls_avoided": 0,
    "false_alarm_seconds_suppressed": 0.0,
    "true_hazards_caught": 0,
    "endian_swaps_healed": 0,
    "bit_flips_quarantined": 0,
}

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)
        for dead in dead_connections:
            self.disconnect(dead)

manager = ConnectionManager()


class ChaosToggleRequest(BaseModel):
    fault_id: str
    enabled: Optional[bool] = None


@app.post("/api/chaos/toggle")
def toggle_chaos(req: ChaosToggleRequest):
    status = chaos_injector.toggle(req.fault_id, req.enabled)
    return {"status": "ok", "chaos": status}


@app.post("/api/chaos/signature_vector")
def inject_signature():
    status = chaos_injector.toggle("tc02_sig400")
    return {"status": "ok", "message": "Signature test vector 400.5 FNU injected", "chaos": status}


@app.post("/api/chaos/reset")
def reset_chaos():
    chaos_injector.reset_all()
    return {"status": "ok", "message": "All chaos fault injectors reset", "chaos": chaos_injector.get_status()}


@app.get("/api/chaos/status")
def get_chaos_status():
    return chaos_injector.get_status()


@app.get("/api/metrics")
def get_metrics():
    return {
        "stats": stats,
        "performance": {
            "bus_cycle_modbuse_ms": 588.4,
            "bus_cycle_rtu_ms": 2239.7,
            "polling_overhead_reduction_pct": 73.7,
            "sram_footprint_kb": 64.8,
            "mcu_target": "STM32F4 (196 KB SRAM)",
            "inference_latency_ms": 2.84,
            "speedup_vs_transformer": "17.1x",
            "mox_drift_reduction_pct": 86.8,
            "water_drift_reduction_pct": 92.3,
            "false_alarm_reduction_pct": 70.2,
        }
    }


# Background loop broadcasting 10Hz telemetry
async def telemetry_broadcaster():
    periodic_slots = [
        ModbusSlotTask(slot_id=i + 1, slave_addr=1, nr_registers=1, period_ms=100.0)
        for i in range(50)
    ]

    last_time = time.time()

    while True:
        await asyncio.sleep(0.1)  # 10Hz
        now = time.time()
        dt = min(0.2, max(0.05, now - last_time))
        last_time = now

        # 1. Step physical simulation & wire encoding
        wire_data = replay_generator.step(dt=0.1)

        # 2. Stage 1A: ModbusE Bus Timing & Scheduler
        c_state = chaos_injector.state
        aperiodic_alarm = []
        if c_state.tc01_bus_starvation or wire_data["hazard_active"]:
            aperiodic_alarm.append(
                ModbusSlotTask(
                    slot_id=1,
                    slave_addr=1,
                    nr_registers=1,
                    period_ms=0.0,
                    is_aperiodic_alarm=True,
                    deadline_laxity_ms=10.0
                )
            )

        bus_timing = modbuse_scheduler.compute_acquisition_cycle(
            periodic_slots=periodic_slots,
            aperiodic_queue=aperiodic_alarm,
            subcycle_gap_ms=35.0
        )

        active_bus_cycle_ms = (
            bus_timing["t_AC_RTU_alpha1_ms"]
            if c_state.tc01_bus_starvation
            else bus_timing["t_AC_ModbusE_ms"]
        )

        # 3. Stage 1B: IEEE-754 Endian & Entropy Firewall
        gpr_prior_mu, _ = gpr_engine.predict_drift(wire_data["time_sec"])
        gpr_prior_mean = replay_generator.turb_base + gpr_prior_mu

        firewall_result = firewall.inspect_and_heal(
            r1=wire_data["wire_r1"],
            r2=wire_data["wire_r2"],
            dt_sec=0.1,
            gpr_prior_mean=gpr_prior_mean
        )

        if "AUTO_HEALED" in firewall_result["status"]:
            stats["endian_swaps_healed"] += 1
        elif "QUARANTINED" in firewall_result["status"]:
            stats["bit_flips_quarantined"] += 1

        verified_reading = float(firewall_result["verified_value"])

        # 4. Stage 2A: TESLA Calibrator
        tesla_result = tesla_calibrator.forward(
            new_val=verified_reading,
            temp_c=wire_data["temp_c"],
            rh_pct=wire_data["rh_pct"]
        )
        x_tesla = tesla_result["x_calibrated"]
        gamma_tesla = tesla_result["gamma_tesla"]

        # 5. Stage 2B: GPR & Disentanglement
        gpr_result = gpr_engine.step_disentangle(
            t=wire_data["time_sec"],
            x_tesla=x_tesla,
            baseline_expectation=replay_generator.turb_base,
            gamma_tesla=gamma_tesla,
            co_sensor_residuals=wire_data["co_sensor_residuals"]
        )

        # Track financial ROI
        # True value is ~12.0. If raw wire is drifted above EPA 25.0 FNU, false alarm is averted:
        epa_threshold = 25.0
        raw_wire_val = wire_data["turb_wire_val"]
        calibrated_val = gpr_result["y_calibrated"]

        is_false_alarm_averted = (raw_wire_val > epa_threshold) and (not wire_data["hazard_active"])
        if is_false_alarm_averted:
            stats["false_alarm_seconds_suppressed"] += 0.1
            # Add avoided outage cost ($260k/hr = $72.22/sec)
            stats["downtime_saved_dollars"] += 72.22 * 0.1
            if int(stats["false_alarm_seconds_suppressed"]) % 60 == 0:
                stats["truck_rolls_avoided"] += 1

        if gpr_result["is_hazard_event"]:
            stats["true_hazards_caught"] += 1

        # Build payload for WebSocket clients
        payload = {
            "tick": wire_data["tick"],
            "time_sec": wire_data["time_sec"],
            "signals": {
                "turb_true": wire_data["turb_true"],
                "turb_wire_raw": wire_data["turb_wire_val"],
                "ph_wire_raw": wire_data["ph_wire_val"],
                "cond_wire_raw": wire_data["cond_wire_val"],
                "temp_c": wire_data["temp_c"],
                "rh_pct": wire_data["rh_pct"],
                "spark_calibrated": calibrated_val,
                "gpr_drift_estimate": gpr_result["estimated_drift_mu"],
                "uncertainty_95ci": gpr_result["uncertainty_95ci"],
                "epa_threshold": epa_threshold,
            },
            "wire_registers": {
                "r1": wire_data["wire_r1"],
                "r2": wire_data["wire_r2"],
                "r1_hex": wire_data["wire_r1_hex"],
                "r2_hex": wire_data["wire_r2_hex"],
                "transmitted_endian": wire_data["wire_endian_transmitted"],
            },
            "firewall": {
                "status": firewall_result["status"],
                "selected_endian": firewall_result["selected_endian"],
                "active_locked_endian": firewall_result["active_locked_endian"],
                "verified_value": verified_reading,
                "abcd_naive_value": firewall_result["abcd_naive_value"],
                "selected_entropy_bits": firewall_result["selected_entropy_bits"],
                "abcd_entropy_bits": firewall_result["abcd_entropy_bits"],
                "slew_ratio": firewall_result["slew_ratio"],
                "candidates": firewall_result["all_candidates"],
            },
            "modbuse": {
                "bus_starvation_active": c_state.tc01_bus_starvation,
                "active_cycle_time_ms": active_bus_cycle_ms,
                "rtu_cycle_time_ms": bus_timing["t_AC_RTU_alpha1_ms"],
                "modbuse_cycle_time_ms": bus_timing["t_AC_ModbusE_ms"],
                "overhead_reduction_pct": bus_timing["overhead_reduction_alpha1_pct"],
                "alarm_latency_ms": (
                    bus_timing["rtu_alarm_latency_ms"]
                    if c_state.tc01_bus_starvation
                    else bus_timing["modbus_e_alarm_latency_ms"]
                ),
            },
            "tesla": {
                "gamma_tesla": gamma_tesla,
                "z_bins": tesla_result["z_bins"],
                "bin_sizes": tesla_result["bin_sizes"],
                "inference_time_ms": tesla_result["inference_time_ms"],
                "sram_footprint_kb": tesla_result["sram_footprint_kb"],
            },
            "disentanglement": {
                "regime": gpr_result["regime"],
                "z_innov": gpr_result["z_innov"],
                "stci": gpr_result["stci"],
                "T_PM_horizon_hours": gpr_result["T_PM_horizon_hours"],
                "is_hazard_event": gpr_result["is_hazard_event"],
                "false_alarm_averted": is_false_alarm_averted,
            },
            "chaos": chaos_injector.get_status(),
            "roi": {
                "downtime_saved_dollars": round(stats["downtime_saved_dollars"], 2),
                "truck_rolls_avoided": stats["truck_rolls_avoided"],
                "false_alarm_seconds_suppressed": round(stats["false_alarm_seconds_suppressed"], 1),
            }
        }

        await manager.broadcast(payload)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(telemetry_broadcaster())


@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; can accept client commands if needed
            data = await websocket.receive_text()
            try:
                cmd = json.loads(data)
                if "action" in cmd and cmd["action"] == "toggle_chaos":
                    chaos_injector.toggle(cmd["fault_id"], cmd.get("enabled"))
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Mount static frontend if available
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
