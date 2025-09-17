import unittest
import sys
import os
import importlib

# Add the 'src' directory to the Python path to ensure correct module resolution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

# Import the module, then explicitly reload it to bypass any caching issues
from ktxinsights.tests import test_collector
importlib.reload(test_collector)

# --- DEBUG: Print the contents of the module's namespace ---
print("Attributes in test_collector module:", dir(test_collector))
# --- END DEBUG ---

# Now, access the class from the reloaded module
TestCollector = test_collector.TestCollector

if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestCollector)
    runner = unittest.TextTestRunner()
    result = runner.run(suite)
    # Exit with a non-zero status code if tests failed
    if not result.wasSuccessful():
        sys.exit(1)
