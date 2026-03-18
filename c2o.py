import argparse
import configparser
from convert import convert

import logging
logger = logging.getLogger(__name__)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("-c", help="Config file", default="c2o.ini")
    p.add_argument("-d", help="Debugging on", default=False, action='store_true')

    args = p.parse_args()
    config = configparser.ConfigParser()
    config.read(args.c)
    convert(config)

    if args.d or config.get_boolean("general","debug",fallback=False):
        logger.setLevel(logging.DEBUG)


if __name__ == '__main__':
    main()
