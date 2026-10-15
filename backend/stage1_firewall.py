import struct
import math
from typing import Dict, List, Tuple, Optional
import numpy as np


class IEEE754ByteOrderFirewall:
    """
    Stage 1B: Automated Schema and Physics-Informed Word-Order Anomaly Detection Firewall.
    Decodes incoming 16-bit register pairs across four permutations (ABCD, CDAB, BADC, DCBA),
    evaluates IEEE-754 structural validity, sliding-window Exponent Shannon Entropy H_W(E_pi),
    and kinematic slew-rate bounds to auto-heal word-swaps and quarantine/impute bit-flips.
    """
    PERMUTATIONS = ("ABCD", "CDAB", "BADC", "DCBA")

    def __init__(
        self,
        phys_min: float = 0.0,
        phys_max: float = 1000.0,
        max_slew_per_sec: float = 15.0,
        window_size: int = 32,
        entropy_threshold_bits: float = 1.20
    ):
        self.phys_min = phys_min
        self.phys_max = phys_max
        self.max_slew_per_sec = max_slew_per_sec
        self.window_size = window_size
        self.entropy_threshold_bits = entropy_threshold_bits
        self.exp_history: Dict[str, List[int]] = {p: [] for p in self.PERMUTATIONS}
        self.last_valid_value: Optional[float] = None
        self.active_locked_endian: str = "ABCD"

    @staticmethod
    def permute_registers_to_bytes(r1: int, r2: int, mode: str) -> bytes:
        """Splits two 16-bit registers into 4 bytes [A, B, C, D] and permutes them."""
        a = (r1 >> 8) & 0xFF
        b = r1 & 0xFF
        c = (r2 >> 8) & 0xFF
        d = r2 & 0xFF

        if mode == "ABCD":
            return bytes([a, b, c, d])
        if mode == "CDAB":
            return bytes([c, d, a, b])
        if mode == "BADC":
            return bytes([b, a, d, c])
        if mode == "DCBA":
            return bytes([d, c, b, a])
        raise ValueError(f"Unknown endianness permutation: {mode}")

    @staticmethod
    def extract_ieee754_fields(raw_bytes: bytes) -> Tuple[float, int, int, int]:
        """Extracts IEEE-754 binary32 fields: decoded float, sign bit, exponent, mantissa."""
        val = struct.unpack(">f", raw_bytes)[0]
        uint_val = struct.unpack(">I", raw_bytes)[0]
        sign = (uint_val >> 31) & 0x1
        exponent = (uint_val >> 23) & 0xFF
        mantissa = uint_val & 0x7FFFFF
        return val, sign, exponent, mantissa

    @staticmethod
    def shannon_entropy_bits(exponents: List[int]) -> float:
        """Computes exact Shannon Entropy in bits over sliding exponent window."""
        if len(exponents) <= 1:
            return 0.0
        _, counts = np.unique(exponents, return_counts=True)
        probs = counts / float(len(exponents))
        return float(-np.sum(probs * np.log2(probs)))

    def inspect_and_heal(
        self,
        r1: int,
        r2: int,
        dt_sec: float = 1.0,
        gpr_prior_mean: Optional[float] = None
    ) -> Dict[str, object]:
        """
        Executes the three-gate firewall across all four endian candidate permutations.
        Returns detailed diagnostics including Shannon entropy, slew ratios, and healed value.
        """
        ref_val = self.last_valid_value if self.last_valid_value is not None else gpr_prior_mean

        # --- STEP 1: Check if active locked mode suffered a single-bit flip on RS-485/UDP ---
        # If active mode was valid previously, test Hamming-distance-1 on its exponent
        b_active = self.permute_registers_to_bytes(r1, r2, self.active_locked_endian)
        val_act, sign_act, exp_act, mant_act = self.extract_ieee754_fields(b_active)
        act_invalid = (
            (exp_act == 255)
            or (exp_act == 0 and mant_act != 0)
            or not (self.phys_min <= val_act <= self.phys_max)
            or (ref_val is not None and abs(val_act - ref_val) / (self.max_slew_per_sec * max(dt_sec, 1e-3) + 0.5) > 3.0)
        )

        if act_invalid and ref_val is not None:
            uint_act = struct.unpack(">I", b_active)[0]
            # Try 1-bit flip search across the 8 exponent bits [23..30]
            for bit_pos in range(23, 31):
                flipped_uint = uint_act ^ (1 << bit_pos)
                cand_bytes = struct.pack(">I", flipped_uint)
                cand_float = struct.unpack(">f", cand_bytes)[0]
                slew_cand = abs(cand_float - ref_val) / (self.max_slew_per_sec * max(dt_sec, 1e-3) + 0.5)
                if self.phys_min <= cand_float <= self.phys_max and slew_cand <= 1.0:
                    # Successfully healed bit flip!
                    self.last_valid_value = cand_float
                    return {
                        "status": "HEALED_BIT_FLIP_HAMMING1",
                        "selected_endian": self.active_locked_endian,
                        "verified_value": round(float(cand_float), 5),
                        "abcd_naive_value": round(float(val_act if self.active_locked_endian == "ABCD" else 0.0), 5),
                        "selected_entropy_bits": 0.0,
                        "abcd_entropy_bits": 0.0,
                        "slew_ratio": round(slew_cand, 4),
                        "all_candidates": {},
                        "best_loss": 0.0,
                        "active_locked_endian": self.active_locked_endian,
                    }

        # --- STEP 2: Evaluate all 4 permutations across the 3 gates ---
        candidates: Dict[str, Dict[str, object]] = {}
        best_mode: str = self.active_locked_endian
        best_loss: float = float("inf")

        for mode in self.PERMUTATIONS:
            b_arr = self.permute_registers_to_bytes(r1, r2, mode)
            val, sign, exp, mant = self.extract_ieee754_fields(b_arr)

            # Update sliding exponent history for this permutation
            hist = self.exp_history[mode]
            hist.append(exp)
            if len(hist) > self.window_size:
                hist.pop(0)

            h_exp = self.shannon_entropy_bits(hist)

            # Gate 1: IEEE-754 Subnormal, NaN/Inf, or physical range breach
            is_subnormal_or_nan = (
                (exp == 255)
                or (exp == 0 and mant != 0)
                or math.isnan(val)
                or math.isinf(val)
            )
            out_of_range = not (self.phys_min <= val <= self.phys_max) if not is_subnormal_or_nan else True
            p_ieee = 1e6 if (is_subnormal_or_nan or out_of_range) else 0.0

            # Gate 2: Exponent Shannon Entropy Penalty
            p_entropy = max(0.0, h_exp - self.entropy_threshold_bits) * 25.0

            # Gate 3: Physics-Informed First-Difference Slew Rate Penalty
            if ref_val is not None and not is_subnormal_or_nan and not out_of_range:
                d_slew = abs(val - ref_val) / (self.max_slew_per_sec * max(dt_sec, 1e-3) + 0.5)
            else:
                d_slew = 100.0 if (is_subnormal_or_nan or out_of_range) else 0.0

            slew_penalty = (10.0 * d_slew) if d_slew > 1.0 else d_slew
            total_loss = p_ieee + p_entropy + slew_penalty

            candidates[mode] = {
                "value": val if not (math.isnan(val) or math.isinf(val)) else 0.0,
                "raw_hex": b_arr.hex().upper(),
                "sign": sign,
                "exponent": exp,
                "mantissa": mant,
                "entropy_bits": round(h_exp, 4),
                "slew_ratio": round(d_slew, 4),
                "loss": round(total_loss, 4),
                "is_subnormal": (exp == 0 and mant != 0),
                "is_nan_inf": (exp == 255),
                "out_of_range": out_of_range,
            }

            if total_loss < best_loss:
                best_loss = total_loss
                best_mode = mode

        chosen = candidates[best_mode]
        all_slew_violated = all(c["slew_ratio"] > 3.0 or c["out_of_range"] for c in candidates.values())

        if all_slew_violated or best_loss >= 1e5:
            # Quarantine corrupted sample and impute from GPR prior
            healed_val = gpr_prior_mean if gpr_prior_mean is not None else (ref_val if ref_val is not None else 12.0)
            status = "QUARANTINED_BIT_FLIP_IMPUTED"
        else:
            healed_val = float(chosen["value"])
            self.last_valid_value = healed_val
            self.active_locked_endian = best_mode
            status = "VALID_ABCD" if best_mode == "ABCD" else f"AUTO_HEALED_ENDIAN_{best_mode}"

        return {
            "status": status,
            "selected_endian": best_mode,
            "verified_value": round(float(healed_val), 5),
            "abcd_naive_value": round(float(candidates["ABCD"]["value"]), 5),
            "selected_entropy_bits": chosen["entropy_bits"],
            "abcd_entropy_bits": candidates["ABCD"]["entropy_bits"],
            "slew_ratio": chosen["slew_ratio"],
            "all_candidates": candidates,
            "best_loss": round(best_loss, 2),
            "active_locked_endian": self.active_locked_endian,
        }
