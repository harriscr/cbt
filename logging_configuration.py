import logging
import os
import yaml

has_a_tty = os.isatty(1)  # test stdout

# Unified log formats used by both cbt and post_processing
SCREEN_FORMAT = "%(levelname)-8s - %(name)s: %(message)s"
FILE_FORMAT = "%(asctime)s - %(levelname)-8s - %(name)-12s - %(module)s.%(funcName)s:%(lineno)d - %(message)s"
FILE_DATEFMT = "%Y-%m-%d %H:%M:%S"


def load_run_params(run_params_file):
    with open(run_params_file) as fd:
        dt = yaml.load(fd)

    return dict(run_uuid=dt["run_uuid"], comment=dt.get("comment"))


def color_me(color):
    RESET_SEQ = "\033[0m"
    COLOR_SEQ = "\033[1;%dm"

    color_seq = COLOR_SEQ % (30 + color)

    def closure(msg):
        return color_seq + msg + RESET_SEQ

    return closure


class ColoredFormatter(logging.Formatter):
    BLACK, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = list(range(8))

    colors = {
        "WARNING": color_me(YELLOW),
        "DEBUG": color_me(BLUE),
        "CRITICAL": color_me(RED),
        "ERROR": color_me(RED),
        "INFO": color_me(GREEN),
    }

    def __init__(self, msg, use_color=True, datefmt=None):
        logging.Formatter.__init__(self, msg, datefmt=datefmt)
        self.use_color = use_color

    def format(self, record):
        orig = record.__dict__
        record.__dict__ = record.__dict__.copy()
        levelname = record.levelname

        prn_name = levelname + " " * (8 - len(levelname))
        if (levelname in self.colors) and has_a_tty:
            record.levelname = self.colors[levelname](prn_name)
        else:
            record.levelname = prn_name

        # super doesn't work here in 2.6 O_o
        res = logging.Formatter.format(self, record)
        # res = super(ColoredFormatter, self).format(record)

        # restore record, as it will be used by other formatters
        record.__dict__ = orig
        return res


def setup_loggers(log_fname=None, log_file_mode="w"):
    """Configure the 'cbt' logger.

    Sets up a screen handler (INFO+, coloured on TTY) and, when log_fname is
    provided, a file handler (DEBUG+) writing to that path.

    Call once at startup without log_fname for early console output, then call
    again with log_fname=<archive_dir>/cbt.log once the archive directory is
    known.  The second call adds the file handler without duplicating the
    screen handler.
    """
    logger = logging.getLogger("cbt")
    logger.setLevel(logging.DEBUG)

    # Only add a stream handler if one is not already present
    if not any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in logger.handlers
    ):
        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.setFormatter(ColoredFormatter(SCREEN_FORMAT))
        logger.addHandler(sh)

    if log_fname is not None:
        os.makedirs(os.path.dirname(log_fname), exist_ok=True)
        fh = logging.FileHandler(log_fname, mode=log_file_mode)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(FILE_FORMAT, datefmt=FILE_DATEFMT))
        logger.addHandler(fh)
