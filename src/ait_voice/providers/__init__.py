"""Provider boundary.

Nothing outside this package imports a vendor SDK. See `base.py` for why —
constraint C-T1 requires per-region provider replaceability because no vendor
serves both US healthcare and India adequately.
"""

from ait_voice.providers.base import (
    LLMProvider,
    ProviderRegistry,
    ProviderSet,
    STTProvider,
    TelephonyProvider,
    TTSProvider,
    UnregisteredRegionError,
)

__all__ = [
    "LLMProvider",
    "ProviderRegistry",
    "ProviderSet",
    "STTProvider",
    "TTSProvider",
    "TelephonyProvider",
    "UnregisteredRegionError",
]
