"""Demo测试路径配置。"""

import os
import sys


sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "..", "..", "src"),
)
