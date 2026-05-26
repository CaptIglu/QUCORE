# -*- coding: utf-8 -*-
import sys
import os
import unittest

# Ensure the tests folder is in sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
tests_dir = os.path.join(root_dir, "tests")
if tests_dir not in sys.path:
    sys.path.append(tests_dir)

# Import the test suite from tests/test_suite.py
from test_suite import TestBufferCalculatorSuite

if __name__ == "__main__":
    unittest.main()
