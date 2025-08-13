"""
Standardized throttling utilities for Thingpress vendor providers.

This module provides consistent throttling mechanisms across all vendor providers
to ensure optimal performance and avoid API rate limiting.
"""

import logging
import os
import time
from typing import Optional

from boto3 import Session

from .aws_utils import calculate_optimal_delay, get_queue_depth, send_sqs_message_batch_with_retry

logger = logging.getLogger(__name__)

class ThrottlingConfig:
    """Configuration class for throttling parameters."""

    def __init__(self):
        self.auto_throttling_enabled = os.environ.get(
            "AUTO_THROTTLING_ENABLED", "true").lower() == "true"
        self.throttling_base_delay = int(os.environ.get("THROTTLING_BASE_DELAY", 30))
        self.throttling_batch_interval = int(os.environ.get("THROTTLING_BATCH_INTERVAL", 3))
        self.max_queue_depth = int(os.environ.get("MAX_QUEUE_DEPTH", 1000))
        self.use_adaptive_throttling = os.environ.get(
            "USE_ADAPTIVE_THROTTLING", "false").lower() == "true"

class StandardizedThrottler:
    """Standardized throttling implementation for all vendor providers."""

    def __init__(self, config: ThrottlingConfig|None = None):
        self.config = config or ThrottlingConfig()
        self.batch_count = 0

    def should_throttle(self) -> bool:
        """Determine if throttling should be applied based on batch count."""
        if not self.config.auto_throttling_enabled:
            return False
        return self.batch_count % self.config.throttling_batch_interval == 0

    def apply_batch_throttling(self, batch_number: Optional[int] = None) -> None:
        """Apply standard batch-based throttling delay."""
        if not self.should_throttle():
            return

        display_batch = batch_number or self.batch_count

        logger.info({
            "message": "Applying throttling delay",
            "batch_number": display_batch,
            "delay_seconds": self.config.throttling_base_delay,
            "throttling_interval": self.config.throttling_batch_interval,
            "throttling_type": "batch_based"
        })

        time.sleep(self.config.throttling_base_delay)

    def apply_adaptive_throttling(self, queue_url: str, session: Session) -> None:
        """Apply adaptive throttling based on queue depth."""
        if not self.config.auto_throttling_enabled or not self.config.use_adaptive_throttling:
            return

        try:
            queue_metrics = get_queue_depth(queue_url, session)
            delay = calculate_optimal_delay(
                queue_metrics['total'], self.config.throttling_base_delay)

            logger.info({
                "message": "Adaptive throttling check",
                "batch_number": self.batch_count,
                "queue_depth": queue_metrics['total'],
                "calculated_delay": delay,
                "throttling_type": "adaptive"
            })

            if delay > 0:
                logger.info({
                    "message": "Applying adaptive throttling delay",
                    "batch_number": self.batch_count,
                    "delay_seconds": delay,
                    "queue_depth": queue_metrics['total']
                })
                time.sleep(delay)

        except Exception as e:
            logger.warning({
                "message": "Adaptive throttling check failed, falling back to batch throttling",
                "batch_number": self.batch_count,
                "error": str(e)
            })
            # Fallback to batch-based throttling
            self.apply_batch_throttling()

    def send_batch_with_throttling(self, batch_messages: list, queue_url: str,
                                 session: Session, is_final_batch: bool = False) -> list:
        """Send a batch of messages with appropriate throttling applied."""
        self.batch_count += 1

        # Choose throttling strategy
        if self.config.use_adaptive_throttling:
            self.apply_adaptive_throttling(queue_url, session)
        else:
            self.apply_batch_throttling()

        # Log batch sending
        batch_type = "final batch" if is_final_batch else "batch"
        logger.info({
            "message": f"Sending {batch_type} with standardized throttling",
            "batch_number": self.batch_count,
            "batch_size": len(batch_messages),
            "throttling_enabled": self.config.auto_throttling_enabled,
            "throttling_type": "adaptive" if self.config.use_adaptive_throttling else "batch_based"
        })

        # Send the batch
        return send_sqs_message_batch_with_retry(batch_messages, queue_url, session)

    def get_throttling_stats(self) -> dict[str, str|int]:
        """Get current throttling statistics."""
        return {
            "total_batches_processed": self.batch_count,
            "throttling_enabled": self.config.auto_throttling_enabled,
            "throttling_type": "adaptive" if self.config.use_adaptive_throttling else "batch_based",
            "base_delay": self.config.throttling_base_delay,
            "batch_interval": self.config.throttling_batch_interval,
            "max_queue_depth": self.config.max_queue_depth
        }

def create_standardized_throttler() -> StandardizedThrottler:
    """Factory function to create a standardized throttler with environment configuration."""
    return StandardizedThrottler()
