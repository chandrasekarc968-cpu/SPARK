import React from 'react';
import { TelemetryPacket } from '../types';
import { 
  Flame, 
  RotateCcw, 
  Play, 
  Square, 
  AlertTriangle, 
  Radio, 
  Binary, 
  Biohazard, 
  Waves,
  Zap
} from 'lucide-react';

interface ChaosControlDeckProps {
  telemetry: TelemetryPacket | null;
  onToggle: (faultId: string) => void;
  onInjectSignature: () => void;
  onReset: () => void;
}

export const ChaosControlDeck: React.FC<ChaosControlDeckProps> = ({
  telemetry,
  onToggle,
  onInjectSignature,
  onReset,
}) => {
  const chaos = telemetry?.chaos;
  const isAuto = chaos?.auto_sequencer_active ?? false;
  const stepIdx = chaos?.auto_step_index ?? 0;

  const testCases = [
    {
      id: 'tc01',
      title: 'TC-01: Bus Starvation',
      tag: 'Transport Layer',
      desc: 'Modbus RTU α=1.0 sequential polling vs ModbusE TDMA slot-packing',
      active: chaos?.tc01_bus_starvation ?? false,
      color: 'border-rose-500/40 text-rose-400 bg-rose-950/20',
      icon: Radio,
    },
    {
      id: 'tc02',
      title: 'TC-02: Silent Word-Swap',
      tag: 'OSI Layer 7',
      desc: 'Slave ABCD → CDAB mutation. Decodes 400.5 as 2.0041 silent lie',
      active: chaos?.tc02_cdab_word_swap ?? false,
      color: 'border-amber-500/40 text-amber-400 bg-amber-950/20',
      icon: Binary,
      hasExtraButton: true,
    },
    {
      id: 'tc03',
      title: 'TC-03: Exponent Bit-Flip',
      tag: 'RS-485 / UDP',
      desc: 'Single-bit inversion in biased exponent bit 29 scaling float by 2^64',
      active: chaos?.tc03_bit_flip ?? false,
      color: 'border-purple-500/40 text-purple-400 bg-purple-950/20',
      icon: Zap,
    },
    {
      id: 'tc04',
      title: 'TC-04: Biofilm Drift',
      tag: 'Physical Electrochemistry',
      desc: 'Optical biofouling ramp (+180% Turbidity only; STCI < 0.35)',
      active: chaos?.tc04_biofouling_drift ?? false,
      color: 'border-cyan-500/40 text-cyan-400 bg-cyan-950/20',
      icon: Waves,
    },
    {
      id: 'tc05',
      title: 'TC-05: Chemical Hazard',
      tag: 'Disentanglement',
      desc: 'Real multi-sensor effluent spike (+85 FNU, -1.85 pH, +420 μS/cm; STCI ≥ 0.65)',
      active: chaos?.tc05_chemical_hazard_spike ?? false,
      color: 'border-emerald-500/40 text-emerald-400 bg-emerald-950/20',
      icon: Biohazard,
    },
  ];

  return (
    <div className="scada-panel p-4 flex flex-col gap-4">
      <div className="flex items-center justify-between border-b border-scada-border pb-3">
        <div className="flex items-center gap-2">
          <Flame className="w-5 h-5 text-rose-500" />
          <h2 className="text-sm font-bold font-mono tracking-wider text-white uppercase">
            Chaos Engineering Fault Injection Deck
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onToggle('auto_sequencer')}
            className={`px-3 py-1.5 rounded text-xs font-mono font-semibold flex items-center gap-1.5 transition-all ${
              isAuto
                ? 'bg-cyan-500 text-black shadow-glow-cyan'
                : 'bg-scada-card text-cyan-400 border border-cyan-800 hover:bg-cyan-950'
            }`}
          >
            {isAuto ? <Square className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            {isAuto ? `AUTO DEMO (STEP ${stepIdx}/5)` : 'AUTO DEMO SEQUENCER'}
          </button>
          <button
            onClick={onReset}
            className="px-3 py-1.5 rounded text-xs font-mono text-slate-400 border border-slate-700 bg-scada-card hover:bg-slate-800 hover:text-white flex items-center gap-1.5 transition-all"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            RESET ALL
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-3">
        {testCases.map((tc) => {
          const Icon = tc.icon;
          return (
            <div
              key={tc.id}
              className={`p-3 rounded-lg border flex flex-col justify-between transition-all ${
                tc.active
                  ? `${tc.color} shadow-lg ring-1 ring-white/10`
                  : 'bg-scada-card/60 border-scada-border text-slate-400 hover:border-slate-600'
              }`}
            >
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                    {tc.tag}
                  </span>
                  <Icon className={`w-4 h-4 ${tc.active ? 'text-white' : 'text-slate-500'}`} />
                </div>
                <h3 className="text-xs font-bold font-mono text-white mb-1">
                  {tc.title}
                </h3>
                <p className="text-[11px] text-slate-400 leading-tight mb-3">
                  {tc.desc}
                </p>
              </div>

              <div className="flex flex-col gap-1.5 mt-2">
                <button
                  onClick={() => onToggle(tc.id)}
                  className={`w-full py-1.5 px-2 rounded text-xs font-mono font-semibold transition-all ${
                    tc.active
                      ? 'bg-rose-600 text-white shadow-glow-danger'
                      : 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
                  }`}
                >
                  {tc.active ? 'FAULT ACTIVE (TOGGLE OFF)' : 'INJECT FAULT'}
                </button>

                {tc.hasExtraButton && (
                  <button
                    onClick={onInjectSignature}
                    className="w-full py-1 px-2 rounded text-[10px] font-mono bg-amber-950/80 text-amber-300 border border-amber-800 hover:bg-amber-900 transition-all flex items-center justify-center gap-1"
                  >
                    <span>⚡ INJECT 400.5 FNU</span>
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
