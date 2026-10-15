export interface PermutationCandidate {
  value: number;
  raw_hex: string;
  sign: number;
  exponent: number;
  mantissa: number;
  entropy_bits: number;
  slew_ratio: number;
  loss: number;
  is_subnormal: boolean;
  is_nan_inf: boolean;
  out_of_range: boolean;
}

export interface TelemetryPacket {
  tick: number;
  time_sec: number;
  signals: {
    turb_true: number;
    turb_wire_raw: number;
    ph_wire_raw: number;
    cond_wire_raw: number;
    temp_c: number;
    rh_pct: number;
    spark_calibrated: number;
    gpr_drift_estimate: number;
    uncertainty_95ci: number;
    epa_threshold: number;
  };
  wire_registers: {
    r1: number;
    r2: number;
    r1_hex: string;
    r2_hex: string;
    transmitted_endian: string;
  };
  firewall: {
    status: string;
    selected_endian: string;
    active_locked_endian: string;
    abcd_naive_value: number;
    selected_entropy_bits: number;
    abcd_entropy_bits: number;
    slew_ratio: number;
    candidates: Record<string, PermutationCandidate>;
  };
  modbuse: {
    bus_starvation_active: boolean;
    active_cycle_time_ms: number;
    rtu_cycle_time_ms: number;
    modbuse_cycle_time_ms: number;
    overhead_reduction_pct: number;
    alarm_latency_ms: number;
  };
  tesla: {
    gamma_tesla: number;
    z_bins: number;
    bin_sizes: number[];
    inference_time_ms: number;
    sram_footprint_kb: number;
  };
  disentanglement: {
    regime: string;
    z_innov: number;
    stci: number;
    T_PM_horizon_hours: number;
    is_hazard_event: boolean;
    false_alarm_averted: boolean;
  };
  chaos: {
    tc01_bus_starvation: boolean;
    tc02_cdab_word_swap: boolean;
    tc02_inject_signature_400_5: boolean;
    tc03_bit_flip: boolean;
    tc04_biofouling_drift: boolean;
    tc05_chemical_hazard_spike: boolean;
    auto_sequencer_active: boolean;
    auto_step_index: number;
    drift_elapsed_sec: number;
    hazard_elapsed_sec: number;
  };
  roi: {
    downtime_saved_dollars: number;
    truck_rolls_avoided: number;
    false_alarm_seconds_suppressed: number;
  };
}
