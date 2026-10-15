import time
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class ChaosState:
    tc01_bus_starvation: bool = False
    tc02_cdab_word_swap: bool = False
    tc03_bit_flip: bool = False
    tc04_biofouling_drift: bool = False
    tc05_chemical_hazard_spike: bool = False
    inject_signature_400_5: bool = False

    # Timers and progress tracking
    drift_elapsed_sec: float = 0.0
    hazard_elapsed_sec: float = 0.0
    auto_sequencer_active: bool = False
    auto_step_index: int = 0
    auto_step_timer: float = 0.0


class ChaosFaultInjector:
    """
    Real-Time Chaos Engineering Fault and Corruption Injector.
    Injects wire-level and physical transducer failure modes (TC-01 through TC-05)
    to test deterministic recovery, self-healing endianness, and event disentanglement.
    """
    def __init__(self):
        self.state = ChaosState()
        self.start_time = time.time()
        self.last_update_time = time.time()

    def toggle(self, fault_id: str, enabled: Optional[bool] = None) -> Dict[str, object]:
        """Toggles or sets the specific fault injection flag."""
        if fault_id == "tc01":
            self.state.tc01_bus_starvation = not self.state.tc01_bus_starvation if enabled is None else enabled
        elif fault_id == "tc02":
            self.state.tc02_cdab_word_swap = not self.state.tc02_cdab_word_swap if enabled is None else enabled
            if not self.state.tc02_cdab_word_swap:
                self.state.inject_signature_400_5 = False
        elif fault_id == "tc02_sig400":
            self.state.inject_signature_400_5 = True
            self.state.tc02_cdab_word_swap = True
        elif fault_id == "tc03":
            self.state.tc03_bit_flip = not self.state.tc03_bit_flip if enabled is None else enabled
        elif fault_id == "tc04":
            self.state.tc04_biofouling_drift = not self.state.tc04_biofouling_drift if enabled is None else enabled
            if self.state.tc04_biofouling_drift:
                self.state.drift_elapsed_sec = 0.0
        elif fault_id == "tc05":
            self.state.tc05_chemical_hazard_spike = not self.state.tc05_chemical_hazard_spike if enabled is None else enabled
            if self.state.tc05_chemical_hazard_spike:
                self.state.hazard_elapsed_sec = 0.0
        elif fault_id == "auto_sequencer":
            self.state.auto_sequencer_active = not self.state.auto_sequencer_active if enabled is None else enabled
            self.state.auto_step_index = 0
            self.state.auto_step_timer = 0.0
        elif fault_id == "reset":
            self.reset_all()

        return self.get_status()

    def reset_all(self):
        """Resets all chaos fault switches to normal clean operation."""
        self.state = ChaosState()

    def get_status(self) -> Dict[str, object]:
        """Returns the current state dictionary of the chaos injector."""
        return {
            "tc01_bus_starvation": self.state.tc01_bus_starvation,
            "tc02_cdab_word_swap": self.state.tc02_cdab_word_swap,
            "tc02_inject_signature_400_5": self.state.inject_signature_400_5,
            "tc03_bit_flip": self.state.tc03_bit_flip,
            "tc04_biofouling_drift": self.state.tc04_biofouling_drift,
            "tc05_chemical_hazard_spike": self.state.tc05_chemical_hazard_spike,
            "auto_sequencer_active": self.state.auto_sequencer_active,
            "auto_step_index": self.state.auto_step_index,
            "drift_elapsed_sec": round(self.state.drift_elapsed_sec, 2),
            "hazard_elapsed_sec": round(self.state.hazard_elapsed_sec, 2),
        }

    def update_timers(self, dt: float):
        """Advances internal chaos progression clocks."""
        if self.state.tc04_biofouling_drift:
            self.state.drift_elapsed_sec += dt
        else:
            self.state.drift_elapsed_sec = 0.0

        if self.state.tc05_chemical_hazard_spike:
            self.state.hazard_elapsed_sec += dt
        else:
            self.state.hazard_elapsed_sec = 0.0

        # Handle automated demo sequencer
        if self.state.auto_sequencer_active:
            self.state.auto_step_timer += dt
            step_duration = 10.0  # 10 seconds per chaos scenario

            step = int(self.state.auto_step_timer // step_duration)
            if step != self.state.auto_step_index:
                self.state.auto_step_index = step
                self._apply_auto_step(step)

    def _apply_auto_step(self, step: int):
        """Advances through the 5 chaos test cases automatically for demonstrations."""
        if step == 0:
            # Baseline normal
            self.reset_all()
            self.state.auto_sequencer_active = True
        elif step == 1:
            # TC-01: Bus starvation
            self.reset_all()
            self.state.auto_sequencer_active = True
            self.state.tc01_bus_starvation = True
        elif step == 2:
            # TC-02: Silent word swap (400.5 test vector)
            self.reset_all()
            self.state.auto_sequencer_active = True
            self.state.tc02_cdab_word_swap = True
            self.state.inject_signature_400_5 = True
        elif step == 3:
            # TC-03: Exponent bit-flip
            self.reset_all()
            self.state.auto_sequencer_active = True
            self.state.tc03_bit_flip = True
        elif step == 4:
            # TC-04: Biofouling drift
            self.reset_all()
            self.state.auto_sequencer_active = True
            self.state.tc04_biofouling_drift = True
        elif step == 5:
            # TC-05: Real chemical spike during drift
            self.state.tc04_biofouling_drift = True
            self.state.tc05_chemical_hazard_spike = True
        else:
            # Cycle complete, return to baseline
            self.reset_all()
            self.state.auto_sequencer_active = False
