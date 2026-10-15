import React from 'react';
import { TelemetryPacket } from '../types';
import { Cpu, Zap, Activity, ShieldCheck, DollarSign, Clock } from 'lucide-react';

interface TopMetricsBarProps {
  telemetry: TelemetryPacket | null;
}

export const TopMetricsBar: React.FC<TopMetricsBarProps> = ({ telemetry }) => {
  const busCycle = telemetry?.modbuse.active_cycle_time_ms ?? 588.4;
  const isStarved = telemetry?.modbuse.bus_starvation_active ?? false;
  const endianLock = telemetry?.firewall.active_locked_endian ?? 'ABCD';
  const endianStatus = telemetry?.firewall.status ?? 'ONLINE';
  const dollarsSaved = telemetry?.roi.downtime_saved_dollars ?? 0;
  const truckRollsSaved = telemetry?.roi.truck_rolls_avoided ?? 0;
  const latency = telemetry?.tesla.inference_time_ms ?? 2.84;
  const sram = telemetry?.tesla.sram_footprint_kb ?? 64.8;

  return (
    <div className="w-full grid grid-cols-2 lg:grid-cols-5 gap-3 p-3 bg-scada-surface/90 border-b border-scada-border backdrop-blur-md">
      {/* Metric 1: Bus Acquisition Cycle */}
      <div className="scada-panel p-3 flex flex-col justify-between">
        <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
          <span className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-cyan-400" />
            BUS ACQUISITION CYCLE
          </span>
          <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
            isStarved ? 'bg-rose-950 text-rose-400 border border-rose-800' : 'bg-emerald-950 text-emerald-400 border border-emerald-800'
          }`}>
            {isStarved ? 'RTU α=1.0' : 'ModbusE TDMA'}
          </span>
        </div>
        <div className="mt-2 flex items-baseline justify-between">
          <div className="text-xl font-bold font-mono text-white tracking-tight">
            {busCycle.toFixed(1)} <span className="text-xs text-slate-400 font-normal">ms</span>
          </div>
          <span className="text-xs font-mono text-emerald-400">
            {isStarved ? '+280% delay' : '-73.7% polling'}
          </span>
        </div>
        <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
          <div
            className={`h-full transition-all duration-300 ${isStarved ? 'bg-rose-500 w-[95%]' : 'bg-cyan-400 w-[26%]'}`}
          />
        </div>
      </div>

      {/* Metric 2: Edge SRAM Footprint */}
      <div className="scada-panel p-3 flex flex-col justify-between">
        <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
          <span className="flex items-center gap-1.5">
            <Cpu className="w-3.5 h-3.5 text-purple-400" />
            EDGE MEMORY FOOTPRINT
          </span>
          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-purple-950 text-purple-300 border border-purple-800">
            STM32F4 MCU
          </span>
        </div>
        <div className="mt-2 flex items-baseline justify-between">
          <div className="text-xl font-bold font-mono text-white tracking-tight">
            {sram.toFixed(1)} <span className="text-xs text-slate-400 font-normal">KB</span>
          </div>
          <span className="text-xs font-mono text-purple-400">
            33% of 196 KB
          </span>
        </div>
        <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
          <div className="bg-purple-500 h-full w-[33%]" />
        </div>
      </div>

      {/* Metric 3: Edge Inference Latency */}
      <div className="scada-panel p-3 flex flex-col justify-between">
        <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
          <span className="flex items-center gap-1.5">
            <Zap className="w-3.5 h-3.5 text-amber-400" />
            INFERENCE LATENCY
          </span>
          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-950 text-amber-400 border border-amber-800">
            17.1x Faster
          </span>
        </div>
        <div className="mt-2 flex items-baseline justify-between">
          <div className="text-xl font-bold font-mono text-white tracking-tight">
            {latency.toFixed(2)} <span className="text-xs text-slate-400 font-normal">ms</span>
          </div>
          <span className="text-xs font-mono text-slate-400">
            TESLA + GPR
          </span>
        </div>
        <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
          <div className="bg-amber-400 h-full w-[12%]" />
        </div>
      </div>

      {/* Metric 4: Endian Lock Status */}
      <div className="scada-panel p-3 flex flex-col justify-between">
        <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
          <span className="flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            IEEE-754 ENDIAN LOCK
          </span>
          <span className={`w-2 h-2 rounded-full animate-ping ${
            endianStatus.includes('HEALED') ? 'bg-amber-400' : 'bg-emerald-400'
          }`} />
        </div>
        <div className="mt-2 flex items-baseline justify-between">
          <div className="text-xl font-bold font-mono text-white tracking-tight flex items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-700 text-sm">
              {endianLock}
            </span>
            <span className="text-xs text-slate-400 font-normal">Order</span>
          </div>
          <span className="text-[11px] font-mono text-slate-300 truncate max-w-[90px]">
            {endianStatus.replace('AUTO_HEALED_', 'HEALED ')}
          </span>
        </div>
        <div className="text-[10px] font-mono text-slate-400 mt-2 truncate">
          H_W: {telemetry?.firewall.selected_entropy_bits.toFixed(2) ?? '0.00'} bits
        </div>
      </div>

      {/* Metric 5: Financial ROI Counter */}
      <div className="col-span-2 lg:col-span-1 scada-panel p-3 flex flex-col justify-between bg-gradient-to-br from-scada-card to-emerald-950/20 border-emerald-900/40">
        <div className="flex items-center justify-between text-xs text-emerald-400 font-mono">
          <span className="flex items-center gap-1.5">
            <DollarSign className="w-3.5 h-3.5" />
            CUMULATIVE SAVINGS
          </span>
          <span className="text-[10px] text-slate-400">
            $260K/hr baseline
          </span>
        </div>
        <div className="mt-2 flex items-baseline justify-between">
          <div className="text-xl font-bold font-mono text-emerald-300 tracking-tight">
            ${dollarsSaved.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
          </div>
          <span className="text-xs font-mono text-emerald-400">
            +{truckRollsSaved} rolls
          </span>
        </div>
        <div className="text-[10px] font-mono text-slate-400 mt-2 flex justify-between">
          <span>False Alarms Averted</span>
          <span className="text-emerald-400 font-semibold">{telemetry?.roi.false_alarm_seconds_suppressed.toFixed(0) ?? 0}s</span>
        </div>
      </div>
    </div>
  );
};
