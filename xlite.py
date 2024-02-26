import io
import platform
import tarfile
import zipfile
import asyncio
import psutil
import requests
import logging
import os
import subprocess
import time
import json
import copy

logging.basicConfig(level=logging.DEBUG)


class BlockdxUtility:
    def __init__(self):
        self.process_running = None
        self.blockdx_process = None
        self.blockdx_conf_local = None
        self.running = True  # flag for async funcs
        self.blockdx_pids = []
        self.parse_blockdx_conf()
        # self.start_async_tasks()