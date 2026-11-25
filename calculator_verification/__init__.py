"""Standalone Scientific Calculator Verification Module.
Independent of Book, Answer Sheet, Mobile, Smartwatch, and Risk Engine systems.
"""
from calculator_verification.candidate import CalculatorCandidateDetector
from calculator_verification.config import CalculatorConfig
from calculator_verification.gemini_verifier import CalculatorGeminiVerifier
from calculator_verification.models import (
    CalculatorCandidate,
    CalculatorClassification,
    CalculatorObjectType,
    CalculatorVerificationResult,
)

__all__ = [
    "CalculatorCandidateDetector",
    "CalculatorConfig",
    "CalculatorGeminiVerifier",
    "CalculatorCandidate",
    "CalculatorClassification",
    "CalculatorObjectType",
    "CalculatorVerificationResult",
]
