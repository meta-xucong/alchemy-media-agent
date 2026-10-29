"""Input limits shared by Alchemy's Bridge transport and V3 admission layer."""

MAX_REFERENCE_INPUT_BYTES = 16 * 1024 * 1024
MAX_REFERENCE_INPUT_PIXELS = 16 * 1024 * 1024

# Keep Alchemy's bounded fallback aligned when a Bridge omits input limits.
LEGACY_REFERENCE_INPUT_BYTES = MAX_REFERENCE_INPUT_BYTES
LEGACY_REFERENCE_INPUT_PIXELS = MAX_REFERENCE_INPUT_PIXELS
