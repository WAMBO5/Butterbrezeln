"""The tests run offline on the golden files, not on whatever pipeline runs this machine has."""

import os

os.environ["BACKEND_MODE"] = "mock"  # read once when api.config is imported
