"""Compatibility import for Colab tools; canonical helper is in the wheel."""

from vtuber_pipeline.common.model_log_output import (
    is_weight_progress,
    quiet_model_environment,
)

__all__ = ["is_weight_progress", "quiet_model_environment"]
