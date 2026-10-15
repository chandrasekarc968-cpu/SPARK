import struct
import math
import random
from typing import Dict, Tuple, List
from chaos_injector import ChaosFaultInjector


class MultiSensorReplayGenerator:
    """
    Multi-Sensor Telemetry Replay & Wire Encoder.
    Simulates a 4-channel co-located industrial water quality sonde modeled on USGS NWIS / CA-DWR Bay-Delta:
    - Primary: Nephelometric Turbidity (USGS 63680, baseline 12.0 FNU, EPA limit 25.0 FNU)
    - Channel 2: pH (USGS 00400, baseline 7.20 pH)
    - Channel 3: Specific Conductance (USGS 00095, baseline 450.0 uS/cm)
    - Channel 4: Temperature (USGS 00010, diurnal 20-28 C) & Relative Humidity (35-65%)
    Encodes floats into IEEE-754 binary32 and splits them across 16-bit Modbus registers (R1, R2).
    """
    def __init__(self, chaos_injector: ChaosFaultInjector, seed: int = 100):
        self.chaos = chaos_injector
        self.tick_count = 0
        self.time_sec = 0.0
        self.rng = random.Random(seed)

        # Baseline physical parameters
        self.turb_base = 12.0
        self.ph_base = 7.20
        self.cond_base = 450.0
        self.temp_base = 24.0

    def step(self, dt: float = 0.1) -> Dict[str, object]:
        """
        Advances physical time series by dt (100 ms demo tick representing accelerated 15-min field samples).
        Applies chaos vectors if active and encodes primary Turbidity into wire registers R1, R2.
        """
        self.tick_count += 1
        self.time_sec += dt
        self.chaos.update_timers(dt)
        c_state = self.chaos.state

        # Diurnal temperature and humidity cycle
        diurnal_phase = (self.time_sec * 0.05) % (2.0 * math.pi)
        temp_c = self.temp_base + 4.0 * math.sin(diurnal_phase) + self.rng.gauss(0.0, 0.05)
        rh_pct = 50.0 - 15.0 * math.sin(diurnal_phase) + self.rng.gauss(0.0, 0.2)

        # Baseline clean signals with realistic analog/sensor noise
        turb_true = self.turb_base + self.rng.gauss(0.0, 0.15)
        ph_true = self.ph_base + self.rng.gauss(0.0, 0.015)
        cond_true = self.cond_base + self.rng.gauss(0.0, 1.5)

        # --- APPLY CHAOS FAULT MODES ---
        turb_wire_val = turb_true
        ph_wire_val = ph_true
        cond_wire_val = cond_true

        # TC-04: Non-linear optical biofouling exponential drift (TURBIDITY ONLY)
        drift_delta = 0.0
        if c_state.tc04_biofouling_drift:
            # d(t) = 22.0 * (1 - exp(-t / 40.0))
            drift_delta = 22.0 * (1.0 - math.exp(-c_state.drift_elapsed_sec / 40.0))
            turb_wire_val += drift_delta

        # TC-05: Sudden chemical hazard spike (MULTI-SENSOR CO-INTEGRATED EVENT)
        hazard_active = False
        if c_state.tc05_chemical_hazard_spike:
            hazard_active = True
            # Sharp chemical effluent discharge: +85 FNU, -1.85 pH, +420 uS/cm
            # Rise smoothly over first 2 seconds then sustain
            ramp = min(1.0, c_state.hazard_elapsed_sec / 2.0)
            turb_wire_val += 85.0 * ramp
            ph_wire_val -= 1.85 * ramp
            cond_wire_val += 420.0 * ramp

        # TC-02 Signature Vector: Explicit 400.5 FNU reading
        if c_state.inject_signature_400_5:
            turb_wire_val = 400.5

        # Compute standardized co-sensor innovation residuals for STCI calculation
        # Normalized by standard noise deviations
        r_turb = (turb_wire_val - (self.turb_base + (drift_delta if not hazard_active else 0.0))) / 0.5
        r_ph = (ph_wire_val - self.ph_base) / 0.05
        r_cond = (cond_wire_val - self.cond_base) / 5.0
        r_temp = (temp_c - self.temp_base) / 0.5
        co_sensor_residuals = [r_turb, r_ph, r_cond, r_temp]

        # --- WIRE ENCODING: IEEE-754 binary32 -> R1, R2 ---
        raw_float = float(turb_wire_val)
        raw_float_bytes = struct.pack(">f", raw_float)
        raw_uint = struct.unpack(">I", raw_float_bytes)[0]

        # TC-03: Bit-flip fault injection on RS-485/UDP wire
        if c_state.tc03_bit_flip:
            # Flip bit 29 (exponent bit, scaling float by 2^64)
            raw_uint = raw_uint ^ (1 << 29)
            raw_float_bytes = struct.pack(">I", raw_uint)

        # Standard Big-Endian ABCD splitting:
        word_high = (raw_uint >> 16) & 0xFFFF
        word_low = raw_uint & 0xFFFF

        # TC-02: Byte-order mutation (ABCD -> Word-Swapped CDAB)
        if c_state.tc02_cdab_word_swap:
            r1 = word_low
            r2 = word_high
            wire_endian_transmitted = "CDAB"
        else:
            r1 = word_high
            r2 = word_low
            wire_endian_transmitted = "ABCD"

        # Generate 50 scattered holding registers for bus evaluation
        scattered_regs: List[Tuple[int, int]] = []
        for i in range(50):
            addr = 40001 + (i * 3)  # scattered non-consecutive addresses
            if i == 0:
                scattered_regs.append((addr, r1))
            elif i == 1:
                scattered_regs.append((addr, r2))
            else:
                # Other sensor dummy registers
                scattered_regs.append((addr, (addr * 17) % 65535))

        return {
            "tick": self.tick_count,
            "time_sec": round(self.time_sec, 2),
            "turb_true": round(turb_true, 3),
            "turb_wire_val": round(turb_wire_val, 3),
            "ph_wire_val": round(ph_wire_val, 3),
            "cond_wire_val": round(cond_wire_val, 1),
            "temp_c": round(temp_c, 2),
            "rh_pct": round(rh_pct, 1),
            "drift_delta": round(drift_delta, 3),
            "hazard_active": hazard_active,
            "wire_r1": r1,
            "wire_r2": r2,
            "wire_r1_hex": f"0x{r1:04X}",
            "wire_r2_hex": f"0x{r2:04X}",
            "wire_endian_transmitted": wire_endian_transmitted,
            "co_sensor_residuals": co_sensor_residuals,
            "scattered_regs_count": len(scattered_regs),
        }
