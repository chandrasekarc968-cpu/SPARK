import math
import time
from typing import List, Tuple, Dict, Optional
import numpy as np


class CompositeGPRDriftEngine:
    """
    Stage 2B: Composite-Kernel GPR (Linear + RBF + Matern-3/2 + WhiteNoise)
    with Event-vs-Drift Disentanglement (STCI + Z_innov) and Predictive Maintenance Horizon (T_PM) solver.
    """
    def __init__(
        self,
        sigma_lin: float = 0.08,
        sigma_rbf: float = 2.5,
        ell_rbf: float = 15.0,
        sigma_mat: float = 0.6,
        ell_mat: float = 2.0,
        sigma_noise: float = 0.25,
        reg_tolerance: float = 5.0
    ):
        self.sigma_lin = sigma_lin
        self.sigma_rbf = sigma_rbf
        self.ell_rbf = ell_rbf
        self.sigma_mat = sigma_mat
        self.ell_mat = ell_mat
        self.sigma_noise = sigma_noise
        self.reg_tolerance = reg_tolerance

        self.t_anchors: List[float] = [0.0, 1.0]
        self.d_anchors: List[float] = [0.0, 0.0]
        self.max_anchors: int = 48
        self.frozen_drift_mu: float = 0.0

    def kernel_slow(self, t1: np.ndarray, t2: np.ndarray) -> np.ndarray:
        """Slow manifold kernel: Linear (irreversible aging) + RBF (smooth biofilm colonization)."""
        dt = np.subtract.outer(t1, t2)
        k_lin = (self.sigma_lin ** 2) * np.outer(t1, t2)
        k_rbf = (self.sigma_rbf ** 2) * np.exp(-0.5 * (dt / self.ell_rbf) ** 2)
        return k_lin + k_rbf

    def kernel_full(self, t1: np.ndarray, t2: np.ndarray, add_noise: bool = False) -> np.ndarray:
        """Full 4-term composite kernel: k_slow + Matern-3/2 (transient weather shifts) + White Noise."""
        dt = np.abs(np.subtract.outer(t1, t2))
        k_s = self.kernel_slow(t1, t2)
        sqrt3_d = math.sqrt(3.0) * dt / self.ell_mat
        k_mat = (self.sigma_mat ** 2) * (1.0 + sqrt3_d) * np.exp(-sqrt3_d)
        K = k_s + k_mat
        if add_noise and K.shape[0] == K.shape[1]:
            K += (self.sigma_noise ** 2) * np.eye(K.shape[0])
        return K

    def predict_drift(self, t_query: float) -> Tuple[float, float]:
        """
        Computes exact GP posterior drift mean mu_d and epistemic variance sigma_d^2
        using rank-aware Cholesky factorization.
        """
        if len(self.t_anchors) < 2:
            return 0.0, self.sigma_noise

        t_arr = np.array(self.t_anchors, dtype=float)
        d_arr = np.array(self.d_anchors, dtype=float)

        try:
            K = self.kernel_full(t_arr, t_arr, add_noise=True)
            L = np.linalg.cholesky(K + 1e-6 * np.eye(len(t_arr)))
            alpha = np.linalg.solve(L.T, np.linalg.solve(L, d_arr))

            k_star = self.kernel_slow(t_arr, np.array([t_query])).flatten()
            mu_star = float(k_star @ alpha)

            v = np.linalg.solve(L, k_star)
            k_tt = float(self.kernel_slow(np.array([t_query]), np.array([t_query])).item())
            var_star = max(1e-5, k_tt - float(v @ v))
            return mu_star, math.sqrt(var_star)
        except Exception:
            # Fallback to mean anchor if numerical jitter occurs
            return float(np.mean(d_arr[-3:])), self.sigma_noise

    def estimate_pm_horizon(self, t_now: float, max_horizon: float = 100.0) -> float:
        """
        Solves for the exact Time-to-Recalibration (T_PM) in hours where
        the uncompensated drift or 95% uncertainty envelope crosses statutory tolerance.

        TIME-SCALE NOTE (demo acceleration):
        - GPR anchor time `t` is fed from `replay_generator.time_sec`, which advances
          by dt=0.1 demo-sec per 10 Hz tick. Each tick represents one accelerated
          15-min (900 s) field sample, i.e. DEMO_TO_FIELD_SEC = 9000.
        - Kernel lengthscales (ell_rbf=15.0, ell_mat=2.0) and the drift time
          constant (40 demo-sec ~= 100 field-hours) are therefore expressed in
          demo-seconds. The returned tau is numerically in demo-seconds but is
          SURFACED as field-hours (1 demo-sec ~= 2.5 field-hours) without rescaling,
          so treat displayed T_PM as an accelerated countdown for demo purposes.
          For field deployment, multiply tau by DEMO_TO_FIELD_SEC/3600 = 2.5 or
          retrain lengthscales in true hours.
        """
        for tau in np.linspace(0.5, max_horizon, 120):
            mu_f, std_f = self.predict_drift(t_now + float(tau))
            if abs(mu_f) + 1.96 * std_f >= self.reg_tolerance:
                return round(float(tau), 1)
        return float(max_horizon)

    @staticmethod
    def compute_stci(co_sensor_residuals: np.ndarray) -> float:
        """
        Computes Spatio-Temporal Coherence Index (STCI) in [0, 1].
        Projects residual vector onto the physical multi-sensor environmental coupling vector
        (Turbidity up [+], pH down [-], Conductivity up [+], Temp neutral [+0.1]).
        """
        r_vec = np.asarray(co_sensor_residuals, dtype=float)
        if len(r_vec) == 0:
            return 0.0
        
        # Environmental coupling eigenvector for industrial effluent / chemical dump
        if len(r_vec) == 4:
            u_env = np.array([1.0, -1.0, 1.0, 0.1], dtype=float)
        else:
            u_env = np.ones(len(r_vec), dtype=float)
        
        u_norm = u_env / (np.linalg.norm(u_env) + 1e-6)
        norm_sq = float(np.sum(r_vec ** 2)) + 1e-6
        proj_sq = float(np.dot(u_norm, r_vec) ** 2)
        return float(np.clip(proj_sq / norm_sq, 0.0, 1.0))

    def step_disentangle(
        self,
        t: float,
        x_tesla: float,
        baseline_expectation: float,
        gamma_tesla: float,
        co_sensor_residuals: np.ndarray
    ) -> Dict[str, object]:
        """
        Executes real-time Event vs. Drift Disentanglement using dual invariants:
        1. Temporal Innovation Scale Separation (Z_innov + Gamma_TESLA)
        2. Spatio-Temporal Cross-Sensor Co-Integration (STCI)
        """
        t_start = time.perf_counter()

        # Prior drift prediction before incorporating new point
        mu_d, std_d = self.predict_drift(t)
        predicted_reading = baseline_expectation + mu_d

        z_innov = abs(x_tesla - predicted_reading) / math.sqrt(std_d ** 2 + self.sigma_noise ** 2)
        stci = self.compute_stci(co_sensor_residuals)

        # Disentanglement Decision Logic
        is_hazard = (z_innov > 3.0 and stci >= 0.65) or (gamma_tesla > 3.5 and stci >= 0.65)

        if is_hazard:
            # Legitimate Multi-Sensor Environmental Spike:
            # FREEZE drift update: do NOT pollute GPR anchors with real hazard data!
            regime = "ENVIRONMENTAL_HAZARD_EVENT"
            y_corrected = x_tesla - mu_d
            self.frozen_drift_mu = mu_d
        else:
            # Normal baseline operation or single-sensor uncorrelated drift (e.g. biofouling)
            current_drift_est = x_tesla - baseline_expectation
            self.t_anchors.append(t)
            self.d_anchors.append(current_drift_est)

            if len(self.t_anchors) > self.max_anchors:
                self.t_anchors.pop(0)
                self.d_anchors.pop(0)

            # Updated posterior after observing drift anchor
            mu_d, std_d = self.predict_drift(t)
            y_corrected = x_tesla - mu_d

            if abs(mu_d) > 0.8:
                regime = "GRADUAL_DRIFT_COMPENSATED"
            else:
                regime = "NORMAL_OPERATION"

        t_pm = self.estimate_pm_horizon(t)
        compute_ms = (time.perf_counter() - t_start) * 1000.0

        return {
            "regime": regime,
            "y_calibrated": round(float(y_corrected), 3),
            "estimated_drift_mu": round(float(mu_d), 3),
            "uncertainty_95ci": round(float(1.96 * std_d), 3),
            "z_innov": round(float(z_innov), 2),
            "stci": round(float(stci), 3),
            "T_PM_horizon_hours": t_pm,
            "is_hazard_event": is_hazard,
            "gpr_compute_ms": round(compute_ms, 3),
        }
