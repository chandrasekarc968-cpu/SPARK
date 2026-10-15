import React from 'react';
import { TelemetryPacket } from '../types';
import { Compass, Gauge, AlertTriangle, ShieldCheck, Clock, CheckCircle } from 'lucide-react';

interface DisentangleRadarProps {
  telemetry: TelemetryPacket | null;
}

export const DisentangleRadar: React.FC<DisentangleRadarProps> = ({ telemetry }) => {
  const disentangle = telemetry?.disentanglement;
  const tesla = telemetry?.tesla;
  const signals = telemetry?.signals;

  const stci = disentangle?.stci ?? 0.15;
  const zInnov = disentangle?.z_innov ?? 0.8;
  const gammaTesla = tesla?.gamma_tesla ?? 1.0;
  const tPmHours = disentangle?.T_PM_horizon_hours ?? 85.0;
  const isHazard = disentangle?.is_hazard_event ?? false;
  const regime = disentangle?.regime ?? 'NORMAL_OPERATION';

  // STCI threshold interpretation
  const isSingleSensorDrift = stci < 0.35 && zInnov <= 1.96;
  const isMultiSensorHazard = stci >= 0.65 && zInnov > 3.0;

  return (
    <div className="scada-panel p-4 flex flex-col gap-4">
      <div className="flex items-center justify-between border-b border-scada-border pb-2">
        <div className="flex items-center gap-2">
          <Compass className="w-5 h-5 text-cyan-400" />
          <h2 className="text-sm font-bold font-mono tracking-wider text-white uppercase">
            Event vs. Drift Disentanglement & T_PM Horizon
          </h2>
        </div>
        <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold ${
          isHazard
            ? 'bg-rose-950 text-rose-300 border border-rose-800 animate-pulse'
            : isSingleSensorDrift
            ? 'bg-amber-950 text-amber-300 border border-amber-800'
            : 'bg-emerald-950 text-emerald-300 border border-emerald-800'
        }`}>
          {regime}
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {/* Metric 1: STCI Gauge */}
        <div className="bg-scada-surface p-3 rounded-lg border border-scada-border flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span>STCI COHERENCE</span>
            <span className={stci >= 0.65 ? 'text-rose-400 font-bold' : 'text-cyan-400'}>
              {stci >= 0.65 ? 'CO-INTEGRATED' : 'UNCORRELATED'}
            </span>
          </div>

          <div className="my-3 flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-white">
              {stci.toFixed(3)}
            </span>
            <span className="text-xs font-mono text-slate-400">
              Range [0..1]
            </span>
          </div>

          <div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden flex">
              <div
                className={`h-full transition-all duration-300 ${
                  stci >= 0.65 ? 'bg-rose-500' : stci < 0.35 ? 'bg-amber-400' : 'bg-emerald-400'
                }`}
                style={{ width: `${Math.min(100, stci * 100)}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] font-mono text-slate-400 mt-1">
              <span>0.0 (Drift &lt; 0.35)</span>
              <span>0.65 (Hazard Spike)</span>
              <span>1.0</span>
            </div>
          </div>
        </div>

        {/* Metric 2: GPR Z_innov Z-Score */}
        <div className="bg-scada-surface p-3 rounded-lg border border-scada-border flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span>SLOW INNOVATION Z</span>
            <span className={zInnov > 3.0 ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
              {zInnov > 3.0 ? 'BREACH > 3.0σ' : 'INSIDE 95% CI'}
            </span>
          </div>

          <div className="my-3 flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-white">
              {zInnov.toFixed(2)} <span className="text-sm font-normal text-slate-400">σ</span>
            </span>
            <span className="text-xs font-mono text-slate-400">
              Threshold 3.0σ
            </span>
          </div>

          <div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-300 ${
                  zInnov > 3.0 ? 'bg-rose-500' : 'bg-emerald-400'
                }`}
                style={{ width: `${Math.min(100, (zInnov / 6.0) * 100)}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] font-mono text-slate-400 mt-1">
              <span>0σ (Normal)</span>
              <span>1.96σ (95% Tube)</span>
              <span>6.0σ</span>
            </div>
          </div>
        </div>

        {/* Metric 3: TESLA Bin Gradient Gamma */}
        <div className="bg-scada-surface p-3 rounded-lg border border-scada-border flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span>TESLA BIN GRADIENT Γ</span>
            <span className={gammaTesla > 3.5 ? 'text-rose-400 font-bold' : 'text-purple-400'}>
              {gammaTesla > 3.5 ? 'SHARP SURGE' : 'SLOW SLOPE'}
            </span>
          </div>

          <div className="my-3 flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-white">
              {gammaTesla.toFixed(2)}
            </span>
            <span className="text-xs font-mono text-slate-400">
              Fine / Coarse
            </span>
          </div>

          <div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all duration-300 ${
                  gammaTesla > 3.5 ? 'bg-rose-500' : 'bg-purple-400'
                }`}
                style={{ width: `${Math.min(100, (gammaTesla / 8.0) * 100)}%` }}
              />
            </div>
            <div className="flex justify-between text-[10px] font-mono text-slate-400 mt-1">
              <span>1.0 (Uniform)</span>
              <span>3.5 (Surge Boundary)</span>
              <span>8.0</span>
            </div>
          </div>
        </div>

        {/* Metric 4: Predictive Maintenance Countdown Clock */}
        <div className="bg-scada-surface p-3 rounded-lg border border-scada-border flex flex-col justify-between">
          <div className="flex items-center justify-between text-xs font-mono text-slate-400">
            <span className="flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-amber-400" />
              T_PM HORIZON
            </span>
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
              tPmHours < 40.0 ? 'bg-amber-950 text-amber-300' : 'bg-emerald-950 text-emerald-300'
            }`}>
              {tPmHours < 40.0 ? 'DISPATCH SOON' : 'HEALTHY'}
            </span>
          </div>

          <div className="my-3 flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-amber-300">
              {tPmHours.toFixed(1)} <span className="text-sm font-normal text-slate-400">hrs</span>
            </span>
            <span className="text-xs font-mono text-slate-400">
              EPA Tol. 5.0 FNU
            </span>
          </div>

          <div className="text-[11px] font-mono text-slate-400">
            {tPmHours < 100.0 ? (
              <span className="text-amber-300">Remaining calibration life countdown active</span>
            ) : (
              <span className="text-emerald-400">No scheduled truck roll required</span>
            )}
          </div>
        </div>
      </div>

      {/* Disentanglement Decision Ribbon */}
      <div className="bg-scada-surface/60 p-3 rounded-lg border border-scada-border flex items-center justify-between text-xs font-mono">
        <div className="flex items-center gap-3">
          <span className="text-slate-400">Active Action:</span>
          {isHazard ? (
            <span className="text-rose-400 font-bold flex items-center gap-1.5">
              <AlertTriangle className="w-4 h-4" />
              FREEZE GPR DRIFT UPDATE → TRANSMIT TRUE HAZARD SPIKE UNTOUCHED TO PLC / SCADA
            </span>
          ) : isSingleSensorDrift ? (
            <span className="text-amber-400 font-semibold flex items-center gap-1.5">
              <ShieldCheck className="w-4 h-4" />
              SINGLE-SENSOR DRIFT DETECTED → AUTOMATICALLY SUBTRACTING μ_d(t) & SUPPRESSING FALSE ALARM
            </span>
          ) : (
            <span className="text-emerald-400 font-semibold flex items-center gap-1.5">
              <CheckCircle className="w-4 h-4" />
              NORMAL MULTI-SENSOR EQUILIBRIUM → TESLA + COMPOSITE GPR NOMINAL TRACKING
            </span>
          )}
        </div>
        <div className="text-slate-400">
          pH: <span className="text-white font-semibold">{signals?.ph_wire_raw.toFixed(2) ?? '7.20'}</span> | 
          Cond: <span className="text-white font-semibold">{signals?.cond_wire_raw.toFixed(0) ?? '450'} μS/cm</span> | 
          Temp: <span className="text-white font-semibold">{signals?.temp_c.toFixed(1) ?? '24.0'} °C</span>
        </div>
      </div>
    </div>
  );
};
