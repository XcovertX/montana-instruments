import asyncio
import argparse
import json
import os
import time
import random
from pathlib import Path
from typing import Dict, Any

class Node:
    def _init_(self, node_id: str, host: str, port: int, workdir: Path):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.workdir = workdir