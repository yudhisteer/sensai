# logger.py
import logging
import colorlog

# Configure once at module level
handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s | %(name)s | %(levelname)s | %(filename)s:%(lineno)d | %(message)s',
    log_colors={
        'DEBUG':    'cyan',
        'INFO':     'green',
        'WARNING':  'yellow',
        'ERROR':    'red',
        'CRITICAL': 'red,bg_white',
    }
))
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.INFO)


def get_logger(name=None):
    return logging.getLogger(name or __name__)
