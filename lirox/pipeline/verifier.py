"""
System Verifier
Checks actual system state, not LLM claims.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List

_logger = logging.getLogger("lirox.pipeline.verifier")


@dataclass
class VerificationResult:
    """Result of all verification checks."""
    all_passed: bool
    passed_steps: List[int]
    failed_steps: List[int]
    details: Dict[int, str]  # step-index → human-readable verdict


class SystemVerifier:
    """Verifies actual system state after execution."""

    def verify_all(self, steps, receipts) -> VerificationResult:
        """
        Run each step's verification callable against real system state.

        This checks DISK / PROCESS state — not LLM claims.
        """
        passed: List[int] = []
        failed: List[int] = []
        details: Dict[int, str] = {}

        for i, (step, receipt) in enumerate(zip(steps, receipts)):
            if not receipt.success:
                failed.append(i)
                details[i] = f"❌ Execution failed: {receipt.error}"
                continue

            try:
                if step.verify():
                    passed.append(i)
                    details[i] = f"✅ Verified: {step.description}"
                else:
                    failed.append(i)
                    details[i] = f"❌ Verification failed: {step.description}"
            except Exception as exc:
                failed.append(i)
                details[i] = f"❌ Verifier error: {exc}"

        return VerificationResult(
            all_passed=len(failed) == 0,
            passed_steps=passed,
            failed_steps=failed,
            details=details,
        )
