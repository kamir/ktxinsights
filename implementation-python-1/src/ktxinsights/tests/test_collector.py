import unittest
from unittest.mock import MagicMock
from confluent_kafka import KafkaException
import io
from contextlib import redirect_stderr

from ktxinsights import collector

class TestCollector(unittest.TestCase):

    def test_fetch_handles_exception_and_increments_metric(self):
        """
        Tests that fetch_and_publish_transactions correctly handles an exception,
        increments the error metric, re-raises the exception, and logs the error.
        """
        # Arrange
        mock_admin_client = MagicMock()
        mock_producer = MagicMock()
        mock_admin_client.list_transactions.return_value.result.side_effect = KafkaException("Broker not available")

        mock_duration_metric = MagicMock()
        mock_error_metric = MagicMock()

        # Act & Assert
        # We expect an error message, so we redirect stderr to capture and silence it.
        captured_stderr = io.StringIO()
        with redirect_stderr(captured_stderr):
            with self.assertRaises(KafkaException) as context:
                collector.fetch_and_publish_transactions(
                    mock_admin_client,
                    mock_producer,
                    "test-topic",
                    duration_metric=mock_duration_metric,
                    error_metric=mock_error_metric,
                )
        
        # Assert that the correct exception was raised
        self.assertIn("Broker not available", str(context.exception))

        # Assert that the expected error message was printed to stderr
        self.assertIn("Error fetching transaction states: Broker not available", captured_stderr.getvalue())

        # Assert that the error metric was incremented
        mock_error_metric.labels.assert_called_once_with(error_type='KafkaException')
        mock_error_metric.labels.return_value.inc.assert_called_once()
        
        # Assert that the duration metric was NOT called
        mock_duration_metric.observe.assert_not_called()
