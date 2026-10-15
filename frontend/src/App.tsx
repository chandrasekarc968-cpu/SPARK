import React, { useState, useEffect, useRef } from 'react';
import { TelemetryPacket } from './types';
import { TopMetricsBar } from './components/TopMetricsBar';
import { ChaosControlDeck } from './components/ChaosControlDeck';
import { TelemetryRibbonChart } from './components/TelemetryRibbonChart';
import { IEEE754Inspector } from './components/IEEE754Inspector';
import { DisentangleRadar } from './components/DisentangleRadar';
import { Activity, Wifi, WifiOff } from 'lucide-react';

export const App: React.FC = () => {
  const [telemetry, setTelemetry] = useState<TelemetryPacket | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [history, setHistory] = useState<Array<{
    time: string;
    raw: number;
    calibrated: number;
    ci_upper: number;
    ci_lower: number;
    true_val: number;
  }>>([]);

  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let ws: WebSocket;
    let reconnectTimeout: any;

    const connect = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsUrl = `${protocol}//${window.location.host}/ws/telemetry`;

      ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const packet: TelemetryPacket = JSON.parse(event.data);
          setTelemetry(packet);

          // Update rolling chart history (keep 45 samples)
          setHistory((prev) => {
            const timeStr = `${packet.time_sec.toFixed(1)}s`;
            const raw = packet.signals.turb_wire_raw;
            const calibrated = packet.signals.spark_calibrated;
            const ci = packet.signals.uncertainty_95ci;

            const newPoint = {
              time: timeStr,
              raw: Number(raw.toFixed(2)),
              calibrated: Number(calibrated.toFixed(2)),
              ci_upper: Number((calibrated + ci).toFixed(2)),
              ci_lower: Number(Math.max(0, calibrated - ci).toFixed(2)),
              true_val: Number(packet.signals.turb_true.toFixed(2)),
            };

            const updated = [...prev, newPoint];
            return updated.length > 45 ? updated.slice(updated.length - 45) : updated;
          });
        } catch (e) {
          console.error('Error parsing telemetry JSON:', e);
        }
      };

      ws.onclose = () => {
        setIsConnected(false);
        reconnectTimeout = setTimeout(connect, 1000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const handleToggleChaos = async (faultId: string) => {
    try {
      await fetch('/api/chaos/toggle', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fault_id: faultId }),
      });
    } catch (e) {
      console.error('Failed to toggle chaos:', e);
    }
  };

  const handleInjectSignature = async () => {
    try {
      await fetch('/api/chaos/signature_vector', {
        method: 'POST',
      });
    } catch (e) {
      console.error('Failed to inject signature vector:', e);
    }
  };

  const handleReset = async () => {
    try {
      await fetch('/api/chaos/reset', {
        method: 'POST',
      });
      setHistory([]);
    } catch (e) {
      console.error('Failed to reset chaos:', e);
    }
  };

  return (
    <div className="min-h-screen bg-scada-bg text-slate-100 flex flex-col font-sans">
      {/* Header */}
      <header className="h-14 border-b border-scada-border bg-scada-surface/90 px-4 flex items-center justify-between backdrop-blur-md">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-600 to-emerald-500 flex items-center justify-center font-mono font-black text-black text-base shadow-glow-cyan">
            ⚡
          </div>
          <div>
            <h1 className="text-base font-bold font-mono tracking-tight text-white flex items-center gap-2">
              S.P.A.R.K.
              <span className="text-xs font-normal text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-800">
                SCADA MISSION CONTROL v2.0
              </span>
            </h1>
            <p className="text-[10px] text-slate-400 font-mono tracking-wide">
              Self-healing Protocol And Recalibration Kernel • Industrial IoT Telemetry
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1 rounded bg-slate-900 border border-scada-border text-xs font-mono">
            {isConnected ? (
              <span className="flex items-center gap-1.5 text-emerald-400">
                <Wifi className="w-3.5 h-3.5" />
                10Hz WEBSOCKET CONNECTED
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-rose-400 animate-pulse">
                <WifiOff className="w-3.5 h-3.5" />
                CONNECTING ENGINE...
              </span>
            )}
          </div>
        </div>
      </header>

      {/* Top Metrics Ribbon */}
      <TopMetricsBar telemetry={telemetry} />

      {/* Main SCADA Workspace */}
      <main className="flex-1 p-4 flex flex-col gap-4 max-w-[1600px] w-full mx-auto">
        {/* Chaos Engineering Controller */}
        <ChaosControlDeck
          telemetry={telemetry}
          onToggle={handleToggleChaos}
          onInjectSignature={handleInjectSignature}
          onReset={handleReset}
        />

        {/* Primary Dual-Trace Telemetry Ribbon */}
        <TelemetryRibbonChart history={history} telemetry={telemetry} />

        {/* Lower Diagnostic Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <IEEE754Inspector telemetry={telemetry} />
          <DisentangleRadar telemetry={telemetry} />
        </div>
      </main>

      {/* Footer */}
      <footer className="h-8 border-t border-scada-border bg-scada-surface px-4 flex items-center justify-between text-[11px] font-mono text-slate-400">
        <div>
          Target: <span className="text-slate-300">ARM Cortex-M4/M7 (STM32F407IG)</span> | 
          Baud: <span className="text-slate-300">9600 bps RS-485</span> | 
          Standards: <span className="text-slate-300">ISO 7027 / USGS TM 1-D3 / EPA 180.1</span>
        </div>
        <div>
          Algorithm: <span className="text-cyan-400">TESLA (AAAI 2025)</span> + <span className="text-purple-400">Composite-Kernel GPR</span>
        </div>
      </footer>
    </div>
  );
};
