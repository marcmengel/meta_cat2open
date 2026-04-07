import argparse
import configparser
from convert import convert, AmSCClient

import logging
logger = logging.getLogger(__name__)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("-c", help="Config file", default="c2o.ini")
    p.add_argument("-d", help="Debugging on", default=False, action='store_true')
    p.add_argument("-q", help="Query instead" )

    args = p.parse_args()
    if args.d:
        logger.setLevel(logging.DEBUG)

        

    config = configparser.ConfigParser()
    config.read(args.c)
    if config.get("general","debug",fallback=False):
        logger.setLevel(logging.DEBUG)

    if args.q:
        c = AmSCClient(config, None)
        res = c.query(args.q)
        print(f"Query Result: {repr(res)}")
        exit(0)
    convert(config)



if __name__ == '__main__':
    main()
