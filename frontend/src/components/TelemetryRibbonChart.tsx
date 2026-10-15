import React from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  CartesianGrid,
  Legend
} from 'recharts';
import { TelemetryPacket } from '../types';
import { ShieldCheck, AlertOctagon, Activity } from 'lucide-react';

interface TelemetryRibbonChartProps {
  history: Array<{
    time: string;
    raw: number;
    calibrated: number;
    ci_upper: number;
    ci_lower: number;
    true_val: number;
  }>;
  telemetry: TelemetryPacket | null;
}

export const TelemetryRibbonChart: React.FC<TelemetryRibbonChartProps> = ({
  history,
  telemetry,
}) => {
  const isFalseAlarmAverted = telemetry?.disentanglement.false_alarm_averted ?? false;
  const isHazard = telemetry?.disentanglement.is_hazard_event ?? false;
  const regime = telemetry?.disentanglement.regime ?? 'NORMAL_OPERATION';
  const rawWireVal = telemetry?.signals.turb_wire_raw ?? 12.0;
  const sparkVal = telemetry?.signals.spark_calibrated ?? 12.0;

  return (
    <div className="scada-panel p-4 flex flex-col gap-3 h-[380px]">
      <div className="flex items-center justify-between border-b border-scada-border pb-2">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-cyan-400" />
          <h2 className="text-sm font-bold font-mono tracking-wider text-white uppercase">
            Real-Time Dual-Trace Telemetry Ribbon
          </h2>
          <span className="text-xs text-slate-400 font-mono">
            (Primary Channel: USGS 63680 Turbidity)
          </span>
        </div>

        {/* Dynamic Alert Banner */}
        <div className="flex items-center gap-2">
          {isFalseAlarmAverted && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-emerald-950 border border-emerald-500 text-emerald-300 text-xs font-mono font-bold animate-pulse">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>FALSE COMPLIANCE ALARM SUPPRESSED (SAVING $260K/HR)</span>
            </div>
          )}

          {isHazard && (
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-rose-950 border border-rose-500 text-rose-300 text-xs font-mono font-bold animate-pulse">
              <AlertOctagon className="w-4 h-4 text-rose-400" />
              <span>CRITICAL HAZARD DISPATCH: REAL CHEMICAL EFFLUENT SPIKE</span>
            </div>
          )}

          <div className="px-2 py-1 rounded bg-slate-800 text-[11px] font-mono text-slate-300">
            Regime: <span className="text-cyan-400 font-semibold">{regime}</span>
          </div>
        </div>
      </div>

      {/* Main Chart */}
      <div className="flex-1 w-full min-h-0">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={history} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
            <defs>
              <linearGradient id="gprCiGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#06B6D4" stopOpacity={0.25} />
                <stop offset="100%" stopColor="#06B6D4" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1F2942" vertical={false} />
            <XAxis dataKey="time" stroke="#64748B" tick={{ fontSize: 10, fill: '#64748B' }} />
            <YAxis
              stroke="#64748B"
              tick={{ fontSize: 10, fill: '#64748B' }}
              domain={[0, (dataMax: number) => Math.max(120, Math.ceil(dataMax * 1.1))]}
              unit=" FNU"
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#0E1322',
                border: '1px solid #1F2942',
                borderRadius: '8px',
                fontSize: '11px',
                fontFamily: 'JetBrains Mono',
              }}
            />
            <Legend
              wrapperStyle={{ fontSize: '11px', paddingTop: '8px', fontFamily: 'JetBrains Mono' }}
            />

            {/* EPA Statutory Regulatory Threshold */}
            <ReferenceLine
              y={25.0}
              stroke="#F59E0B"
              strokeDasharray="4 4"
              strokeWidth={1.5}
              label={{
                value: 'EPA EXCEEDANCE LIMIT (25.0 FNU)',
                fill: '#F59E0B',
                fontSize: 10,
                position: 'insideTopLeft',
              }}
            />

            {/* 95% GPR Epistemic Uncertainty Tube */}
            <Area
              type="monotone"
              dataKey="ci_upper"
              stroke="transparent"
              fill="url(#gprCiGradient)"
              name="95% Bayesian GPR CI Envelope"
            />
            <Area
              type="monotone"
              dataKey="ci_lower"
              stroke="transparent"
              fill="#070A12"
              legendType="none"
            />

            {/* Raw Corrupted / Drifted Wire Telemetry */}
            <Line
              type="monotone"
              dataKey="raw"
              stroke="#EF4444"
              strokeDasharray="3 3"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              name="Raw Wire Telemetry (Corrupted/Drifted)"
            />

            {/* S.P.A.R.K. Self-Healed & Calibrated Output */}
            <Line
              type="monotone"
              dataKey="calibrated"
              stroke="#06B6D4"
              strokeWidth={2.5}
              dot={false}
              isAnimationActive={false}
              name="S.P.A.R.K. Calibrated Telemetry"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div className="flex items-center justify-between text-xs font-mono text-slate-400 bg-scada-surface px-3 py-1.5 rounded border border-scada-border">
        <div>
          Raw Wire Instantaneous: <span className="text-rose-400 font-bold">{rawWireVal.toFixed(2)} FNU</span>
        </div>
        <div>
          S.P.A.R.K. Calibrated: <span className="text-cyan-400 font-bold">{sparkVal.toFixed(2)} FNU</span>
        </div>
        <div>
          Estimated Physical Drift: <span className="text-amber-400 font-semibold">{telemetry?.signals.gpr_drift_estimate.toFixed(2) ?? '0.00'} FNU</span>
        </div>
        <div>
          95% CI Half-Width: <span className="text-purple-400">±{telemetry?.signals.uncertainty_95ci.toFixed(2) ?? '0.00'} FNU</span>
        </div>
      </div>
    </div>
  );
};
