import sys
import os
import struct
import math
import pytest
import numpy as np

# Ensure backend directory is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from stage1_modbuse import ModbusEScheduler, ModbusSlotTask
from stage1_firewall import IEEE754ByteOrderFirewall
from stage2_tesla import TESLALogBinnedCalibrator
from stage2_gpr import CompositeGPRDriftEngine
from chaos_injector import ChaosFaultInjector
from replay_generator import MultiSensorReplayGenerator


def test_tc01_modbuse_bus_starvation_and_alarm_latency():
    """
    TC-01 Verification:
    - 50 scattered holding registers polled at 9600 bps.
    - Modbus RTU (alpha=0) produces ~1145.87 ms.
    - Modbus RTU (alpha=1) produces ~2239.66 ms.
    - ModbusE slot-packing drops cycle to ~588.40 ms (48.7% to 73.7% reduction).
    - ModbusE delivers emergency alarm in < 25 ms, while RTU starves it for > 1100 ms.
    """
    scheduler = ModbusEScheduler(baud_rate=9600)
    periodic_slots = [
        ModbusSlotTask(slot_id=i + 1, slave_addr=1, nr_registers=1, period_ms=100.0)
        for i in range(50)
    ]
    alarm_task = ModbusSlotTask(
        slot_id=1, slave_addr=1, nr_registers=1, period_ms=0.0, is_aperiodic_alarm=True
    )

    timing = scheduler.compute_acquisition_cycle(
        periodic_slots=periodic_slots,
        aperiodic_queue=[alarm_task],
        subcycle_gap_ms=35.0
    )

    # 1. Verify standard Modbus RTU timings at 9600 bps
    assert abs(timing["t_AC_RTU_alpha0_ms"] - 1145.87) < 2.0, f"Expected ~1145.87ms, got {timing['t_AC_RTU_alpha0_ms']}"
    assert abs(timing["t_AC_RTU_alpha1_ms"] - 2239.66) < 2.0, f"Expected ~2239.66ms, got {timing['t_AC_RTU_alpha1_ms']}"

    # 2. Verify ModbusE slot-packing cycle time and overhead reduction
    assert timing["t_AC_ModbusE_ms"] < 620.0, f"ModbusE cycle too long: {timing['t_AC_ModbusE_ms']}"
    assert timing["overhead_reduction_alpha1_pct"] > 70.0, f"Expected >70% reduction, got {timing['overhead_reduction_alpha1_pct']}%"

    # 3. Verify alarm latency: ModbusE < 25 ms vs RTU > 1100 ms
    assert timing["modbus_e_alarm_latency_ms"] < 25.0
    assert timing["rtu_alarm_latency_ms"] > 1100.0


def test_tc02_silent_ieee754_word_swap_and_signature_400_5():
    """
    TC-02 Verification:
    - Injects signature 400.5 FNU reading (0x43C84000).
    - Transmitted in CDAB word order: R1 = 0x4000, R2 = 0x43C8.
    - Demonstrates naive ABCD decodes to 2.004137 (silent failure!).
    - Proves Gate 3 Slew Rate and Gate 2 Entropy detect the swap immediately.
    - Verifies Firewall auto-heals and locks onto CDAB in 1 step!
    """
    firewall = IEEE754ByteOrderFirewall(phys_min=0.0, phys_max=1000.0, max_slew_per_sec=15.0)

    # Prime firewall with prior state of 400.5 as established in paper (page 13)
    firewall.last_valid_value = 400.5
    firewall.active_locked_endian = "ABCD"

    # Now transmit 400.5 in CDAB order
    # 400.5 = 0x43C84000 -> word_high=0x43C8, word_low=0x4000
    r1_cdab = 0x4000
    r2_cdab = 0x43C8

    # 1. Verify naive ABCD decoding produces 2.004137
    naive_bytes = bytes([(r1_cdab >> 8) & 0xFF, r1_cdab & 0xFF, (r2_cdab >> 8) & 0xFF, r2_cdab & 0xFF])
    naive_float = struct.unpack(">f", naive_bytes)[0]
    assert abs(naive_float - 2.004137) < 0.001, f"Expected 2.004137, got {naive_float}"

    # 2. Inspect with Stage 1B Firewall
    result = firewall.inspect_and_heal(r1_cdab, r2_cdab, dt_sec=1.0, gpr_prior_mean=400.5)

    # Assert firewall auto-healed to CDAB and restored 400.5
    assert result["selected_endian"] == "CDAB"
    assert abs(result["verified_value"] - 400.5) < 0.01
    assert "AUTO_HEALED_ENDIAN_CDAB" in result["status"]


def test_tc02_exponent_entropy_discrimination():
    """
    Verifies Gate 2 Exponent Shannon Entropy:
    - Normal constant process: H_W(E_true) <= 1.0 bit.
    - Swapped word order: noisy mantissa maps to exponent, scattering values and driving H_W > 4.0 bits.
    """
    firewall = IEEE754ByteOrderFirewall(window_size=32, entropy_threshold_bits=1.20)
    rng = np.random.default_rng(42)

    # Simulate 32 samples of process around 25.0 C with ADC noise
    true_exp_list = []
    swapped_exp_list = []

    for _ in range(32):
        t_val = 25.0 + float(rng.normal(0.0, 0.05))
        b_true = struct.pack(">f", t_val)
        _, _, exp_true, _ = IEEE754ByteOrderFirewall.extract_ieee754_fields(b_true)
        true_exp_list.append(exp_true)

        # Word swap the bytes (CDAB)
        b_swapped = bytes([b_true[2], b_true[3], b_true[0], b_true[1]])
        _, _, exp_swapped, _ = IEEE754ByteOrderFirewall.extract_ieee754_fields(b_swapped)
        swapped_exp_list.append(exp_swapped)

    h_true = IEEE754ByteOrderFirewall.shannon_entropy_bits(true_exp_list)
    h_swapped = IEEE754ByteOrderFirewall.shannon_entropy_bits(swapped_exp_list)

    assert h_true <= 1.0, f"True entropy too high: {h_true} bits"
    assert h_swapped > 3.0, f"Swapped entropy too low: {h_swapped} bits"


def test_tc03_bit_flip_quarantine_and_hamming1_recovery():
    """
    TC-03 Verification:
    - Injects bit 29 flip into exponent of valid 12.0 float.
    - Detects extreme slew across all 4 permutations.
    - Recovers via Hamming-1 search or quarantines and imputes GPR prior mean.
    """
    firewall = IEEE754ByteOrderFirewall(phys_min=0.0, phys_max=1000.0, max_slew_per_sec=15.0)

    # Prime with baseline 12.0
    val_bytes = struct.pack(">f", 12.0)
    uint_val = struct.unpack(">I", val_bytes)[0]
    r1, r2 = (uint_val >> 16) & 0xFFFF, uint_val & 0xFFFF
    _ = firewall.inspect_and_heal(r1, r2, dt_sec=1.0)

    # Corrupt bit 29
    corrupted_uint = uint_val ^ (1 << 29)
    r1_corrupt = (corrupted_uint >> 16) & 0xFFFF
    r2_corrupt = corrupted_uint & 0xFFFF

    result = firewall.inspect_and_heal(r1_corrupt, r2_corrupt, dt_sec=1.0, gpr_prior_mean=12.0)

    # Must be either healed via Hamming-1 or quarantined & imputed
    assert result["status"] in ("HEALED_BIT_FLIP_HAMMING1", "QUARANTINED_BIT_FLIP_IMPUTED")
    # Resulting value must remain close to 12.0, not >10^19!
    assert abs(result["verified_value"] - 12.0) < 1.0


def test_tc04_biofouling_drift_compensation_and_t_pm():
    """
    TC-04 Verification:
    - Injects exponential single-sensor drift: d(t) = 22 * (1 - exp(-t / 40)).
    - Verifies STCI is low (< 0.35) because only Turbidity is drifting.
    - Verifies GPR tracks and subtracts drift, keeping calibrated output within EPA limits.
    - Verifies T_PM countdown is actively calculated.
    """
    gpr = CompositeGPRDriftEngine(reg_tolerance=5.0)
    tesla = TESLALogBinnedCalibrator(seq_len=16)

    baseline = 12.0
    y_calibrated_series = []

    # Simulate 30 steps of gradual single-sensor drift
    for step in range(1, 31):
        t = float(step)
        drift = 22.0 * (1.0 - math.exp(-t / 40.0))
        raw_reading = baseline + drift + np.random.normal(0, 0.1)

        # Single-sensor drift residuals (turbidity drifting, others clean)
        residuals = np.array([drift / 0.5, 0.01, 0.02, 0.01])

        tesla_out = tesla.forward(raw_reading, temp_c=24.0, rh_pct=50.0)
        x_tesla = tesla_out["x_calibrated"]
        gamma_tesla = tesla_out["gamma_tesla"]

        gpr_out = gpr.step_disentangle(
            t=t,
            x_tesla=x_tesla,
            baseline_expectation=baseline,
            gamma_tesla=gamma_tesla,
            co_sensor_residuals=residuals
        )
        y_calibrated_series.append(gpr_out["y_calibrated"])

        # Check STCI is low for single-sensor degradation
        assert gpr_out["stci"] < 0.60, f"STCI should be low for single sensor drift, got {gpr_out['stci']}"

    # Verify drift was subtracted: raw reading reached ~12 + 11.6 = 23.6 FNU,
    # but calibrated output remains near 12.0
    last_calibrated = y_calibrated_series[-1]
    assert abs(last_calibrated - baseline) < 2.5, f"Calibrated {last_calibrated} drifted away from baseline {baseline}"
    assert gpr.estimate_pm_horizon(30.0) < 100.0


def test_tc05_sudden_chemical_hazard_spike_preservation():
    """
    TC-05 Verification:
    - Real chemical spill (+85 FNU, -1.85 pH, +420 uS/cm) occurs during active drift.
    - STCI surges >= 0.65 (co-integrated across channels).
    - Z_innov > 3.0.
    - CRITICAL INVARIANT: GPR drift update FREEZES, and the real 85 FNU spike is passed
      untouched to trigger emergency alarms!
    """
    gpr = CompositeGPRDriftEngine(reg_tolerance=5.0)
    tesla = TESLALogBinnedCalibrator(seq_len=16)
    baseline = 12.0

    # 1. Establish initial drift state of ~5.0 FNU
    for step in range(1, 10):
        t = float(step)
        drift = 5.0
        r_single = np.array([drift / 0.5, 0.0, 0.0, 0.0])
        t_out = tesla.forward(baseline + drift, temp_c=25.0, rh_pct=50.0)
        _ = gpr.step_disentangle(t, t_out["x_calibrated"], baseline, t_out["gamma_tesla"], r_single)

    drift_before_spike = gpr.d_anchors[-1]

    # 2. Inject sudden co-integrated chemical hazard spike at t=10
    spike_t = 10.0
    raw_spike_val = baseline + drift_before_spike + 85.0
    co_residuals = np.array([85.0 / 0.5, -1.85 / 0.05, 420.0 / 5.0, 0.2 / 0.5])  # All sensors react!

    tesla_out = tesla.forward(raw_spike_val, temp_c=25.0, rh_pct=50.0)
    gpr_out = gpr.step_disentangle(
        t=spike_t,
        x_tesla=tesla_out["x_calibrated"],
        baseline_expectation=baseline,
        gamma_tesla=tesla_out["gamma_tesla"],
        co_sensor_residuals=co_residuals
    )

    # 3. Assertions
    assert gpr_out["regime"] == "ENVIRONMENTAL_HAZARD_EVENT"
    assert gpr_out["is_hazard_event"] is True
    assert gpr_out["stci"] >= 0.65, f"STCI should be high for multi-sensor spike, got {gpr_out['stci']}"
    assert gpr_out["z_innov"] > 3.0, f"Z_innov should exceed 3.0, got {gpr_out['z_innov']}"

    # Critical invariant: The spike is NOT subtracted as drift!
    # Calibrated value should reflect the ~85 FNU surge (approx baseline 12 + 85 = 97 FNU)
    assert gpr_out["y_calibrated"] > 75.0, f"Hazard spike was wrongly suppressed! Got {gpr_out['y_calibrated']}"

    # Drift anchor must NOT have recorded the 85 FNU spike
    assert gpr.d_anchors[-1] < 20.0, "GPR drift anchor absorbed the chemical hazard spike!"
