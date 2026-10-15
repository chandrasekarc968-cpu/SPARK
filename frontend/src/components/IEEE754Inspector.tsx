import React from 'react';
import { TelemetryPacket } from '../types';
import { Binary, ShieldAlert, CheckCircle2, AlertTriangle } from 'lucide-react';

interface IEEE754InspectorProps {
  telemetry: TelemetryPacket | null;
}

export const IEEE754Inspector: React.FC<IEEE754InspectorProps> = ({ telemetry }) => {
  const wire = telemetry?.wire_registers;
  const firewall = telemetry?.firewall;
  const candidates = firewall?.candidates ?? {};
  const selectedEndian = firewall?.selected_endian ?? 'ABCD';
  const status = firewall?.status ?? 'ONLINE';

  const modes = ['ABCD', 'CDAB', 'BADC', 'DCBA'];

  return (
    <div className="scada-panel p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between border-b border-scada-border pb-2">
        <div className="flex items-center gap-2">
          <Binary className="w-5 h-5 text-purple-400" />
          <h2 className="text-sm font-bold font-mono tracking-wider text-white uppercase">
            Stage 1B: IEEE-754 Endian & Entropy Firewall
          </h2>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-slate-400">
            Wire Registers:
          </span>
          <span className="px-2 py-0.5 rounded bg-slate-800 text-purple-300 font-mono text-xs font-bold border border-slate-700">
            R1={wire?.r1_hex ?? '0x4000'} R2={wire?.r2_hex ?? '0x43C8'}
          </span>
          <span className={`px-2 py-0.5 rounded text-xs font-mono font-bold ${
            status.includes('HEALED') 
              ? 'bg-amber-950 text-amber-300 border border-amber-800'
              : status.includes('QUARANTINED')
              ? 'bg-rose-950 text-rose-300 border border-rose-800'
              : 'bg-emerald-950 text-emerald-300 border border-emerald-800'
          }`}>
            {status}
          </span>
        </div>
      </div>

      {/* 4-Way Candidate Permutation Comparison Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left font-mono text-xs">
          <thead>
            <tr className="border-b border-scada-border text-slate-400 uppercase text-[10px]">
              <th className="pb-2">Permutation</th>
              <th className="pb-2">Reconstructed Hex</th>
              <th className="pb-2">Decoded Float</th>
              <th className="pb-2">Exponent Entropy H_W</th>
              <th className="pb-2">Slew Ratio</th>
              <th className="pb-2">Gate Status</th>
              <th className="pb-2">Firewall Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-scada-border/60">
            {modes.map((mode) => {
              const cand = candidates[mode];
              const isSelected = mode === selectedEndian;
              const val = cand?.value ?? 0;
              const entropy = cand?.entropy_bits ?? 0;
              const slew = cand?.slew_ratio ?? 0;
              const isSubnormal = cand?.is_subnormal ?? false;
              const isNan = cand?.is_nan_inf ?? false;
              const isOutOfRange = cand?.out_of_range ?? false;

              // Operational significance explanation
              let note = 'Rejected';
              let badgeColor = 'text-slate-400 bg-slate-900';

              if (isSelected) {
                note = '✓ Active Verified Lock';
                badgeColor = 'text-emerald-300 bg-emerald-950 border border-emerald-700 font-bold';
              } else if (mode === 'ABCD' && Math.abs(val - 2.0041) < 0.05) {
                note = '⚠ Silent Lie (Masks Hazard!)';
                badgeColor = 'text-rose-400 bg-rose-950/80 border border-rose-800 font-bold';
              } else if (isSubnormal) {
                note = 'Subnormal Underflow';
                badgeColor = 'text-slate-500 bg-slate-900';
              } else if (val < 0) {
                note = 'Negative Overflow';
                badgeColor = 'text-slate-500 bg-slate-900';
              }

              return (
                <tr
                  key={mode}
                  className={`transition-colors ${
                    isSelected ? 'bg-cyan-950/20 font-semibold' : 'hover:bg-slate-800/30'
                  }`}
                >
                  <td className="py-2.5 flex items-center gap-1.5">
                    {isSelected ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <div className="w-4 h-4 rounded-full border border-slate-700 flex items-center justify-center text-[10px] text-slate-500">
                        •
                      </div>
                    )}
                    <span className={isSelected ? 'text-cyan-300 font-bold' : 'text-slate-300'}>
                      {mode}
                    </span>
                  </td>
                  <td className="py-2.5 text-slate-400">
                    {cand?.raw_hex ?? '00000000'}
                  </td>
                  <td className="py-2.5">
                    <span
                      className={`px-1.5 py-0.5 rounded ${
                        isSelected
                          ? 'text-white bg-cyan-900/40 border border-cyan-700'
                          : mode === 'ABCD' && Math.abs(val - 2.0041) < 0.05
                          ? 'text-rose-300 bg-rose-950/60 border border-rose-800'
                          : 'text-slate-300'
                      }`}
                    >
                      {val.toFixed(4)}
                    </span>
                  </td>
                  <td className="py-2.5">
                    <div className="flex items-center gap-2">
                      <div className="w-16 bg-slate-800 h-1.5 rounded-full overflow-hidden">
                        <div
                          className={`h-full ${
                            entropy > 1.2 ? 'bg-rose-500' : 'bg-emerald-400'
                          }`}
                          style={{ width: `${Math.min(100, (entropy / 5.5) * 100)}%` }}
                        />
                      </div>
                      <span className={entropy > 1.2 ? 'text-rose-400 font-bold' : 'text-slate-400'}>
                        {entropy.toFixed(2)} b
                      </span>
                    </div>
                  </td>
                  <td className="py-2.5">
                    <span className={slew > 1.0 ? 'text-amber-400' : 'text-slate-400'}>
                      {slew.toFixed(2)}
                    </span>
                  </td>
                  <td className="py-2.5">
                    {isSubnormal ? (
                      <span className="text-amber-400">Subnormal (E=0)</span>
                    ) : isNan ? (
                      <span className="text-rose-400">NaN/Inf (E=255)</span>
                    ) : isOutOfRange ? (
                      <span className="text-rose-400">Out-of-Bounds</span>
                    ) : (
                      <span className="text-emerald-400">Gate 1 Pass</span>
                    )}
                  </td>
                  <td className="py-2.5">
                    <span className={`px-2 py-0.5 rounded text-[11px] ${badgeColor}`}>
                      {note}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
