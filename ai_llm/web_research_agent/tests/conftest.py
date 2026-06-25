import sys
import os

# Add parent directory to path for imports
parent_dir = os.path.join(os.path.dirname(__file__), '..')
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
