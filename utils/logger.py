import logging
import os
from pathlib import Path
import inspect
from datetime import datetime


NOTICE = 25  # Value between WARNING (30) and INFO (20)


class PipelineLogger:
    """包含时间和 caller frame的 logger class"""

    def __init__(self, output_dir: str="logs", file_suffix: str = "log", verbose: bool = True):
        self.output_dir = Path(output_dir)
        self.log_file_suffix = file_suffix
        self.verbose = verbose

        self.output_dir.mkdir(parents=True, exist_ok=True)
        log_file = (
            self.output_dir
            / f"{self.log_file_suffix}_{datetime.now().strftime('%Y%m%d')}.log"
        )

        handlers = [logging.FileHandler(log_file, mode="a", encoding="utf-8")]
        if verbose:
            handlers.append(logging.StreamHandler())
            log_level = logging.DEBUG
        else:
            log_level = logging.INFO


        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=handlers,
        )
        self.logger = logging.getLogger(self.__class__.__name__)

        logging.addLevelName(NOTICE, "NOTICE")

    def log(self, log_level: str, message: str):
        level = getattr(logging, log_level.upper(), logging.INFO)

        # Get the caller function information
        caller_frame = inspect.currentframe().f_back
        caller_func_name = caller_frame.f_code.co_name
        caller_class_name = caller_frame.f_locals.get("self", None).__class__.__name__

        # Include the caller function name in the message
        full_message = f"{caller_class_name}.{caller_func_name}: {message}"
        self.logger.log(level, full_message)

    def notice(self, message: str):
        self.log("NOTICE", message)

    def warning(self, message: str):
        self.log("WARNING", message)

    def error(self, message: str):
        self.log("ERROR", message)

    def info(self, message: str):
        self.log("INFO", message)
