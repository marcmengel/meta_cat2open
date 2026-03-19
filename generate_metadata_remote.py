import argparse
import requests
import xml.parsers.expat
import re
import os
import sys

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import logging
logger = logging.getLogger(__name__)

class InfoGetter:
    def __init__(self, namespace="amsc"):
        self.s = requests.Session()
        self.namespace = namespace
        self.token_header = {
             "Authorization": f"Bearer {self.get_bearer_token()}",
         }
        self.file_checksum_list = []
#
    def get_bearer_token(self):
        token = os.environ.get("BEARER_TOKEN")
        if not token:
            token_file = os.environ.get("BEARER_TOKEN_FILE")
            if not token_file:
                uid = os.environ.get("ID", str(os.geteuid()))
                token_dir = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
                token_file = token_dir + "/" + "bt_u" + uid
        logger.debug(f"reading token file: {token_file}")
        token = open(token_file, "r").read().strip()
        return token

    def get_files( self, basedir):
        logger.debug(f"get_files: {basedir=}")
        headers = self.token_header.copy()
        headers["Depth"] = "1"

        req = requests.Request('PROPFIND', basedir, headers=headers)
        #req = requests.Request('PROPFIND', basedir)
        resp = self.s.send(req.prepare(), verify=False )

        logger.debug(f"{resp.status_code=} {resp.text=}")

        file_list = []
        curname = None
        filename = None
        size = None

        def start_element(name, attrs):
            nonlocal curname, filename, size
            logger.debug(f"start: {name}")
            curname = name
        def char_data(text):
            nonlocal curname, filename, size
            logger.debug(f"text: {curname=} {text=}")
            if curname == 'd:displayname':
                filename = text
            if curname == 'd:getcontentlength':
                size = int(text)
        def end_element(name):
            nonlocal curname, filename, size
            logger.debug(f"end: {name=} {size=}")
            if name == 'd:response' and size != None:
               file_list.append((filename, size))
               size = None
               filename = None

        xp = xml.parsers.expat.ParserCreate()
        xp.StartElementHandler = start_element
        xp.CharacterDataHandler = char_data
        xp.EndElementHandler = end_element
        xp.Parse(resp.text)

        # first displayname is the directory itself, so skip it

        spos = basedir.find("/", 9)
        apibase = f"{basedir[0:spos]}/api/v1/namespace{basedir[spos:]}"
        apibase = apibase.replace(":2880/",":3880/")

        logger.debug(f"before checksums: {file_list=}")

        for filename, size in file_list:
            url=f"{apibase}/{filename}?checksum=true"
            logger.debug(f"{url=}")
            resp = self.s.get(url, headers=self.token_header, verify=False)
            logger.debug(f"{resp.status_code=} {resp.text=}")
            checksums = "{}"
            if resp.status_code == 200:
                data = resp.json()
                if data and "checksums" in data and data["checksums"]:
                    csvalue = data["checksums"][0]["value"]
                    cstype = data["checksums"][0]["type"].lower()
                    checksums = f'{{ "{cstype}": "{csvalue}" }}'

            self.file_checksum_list.append( (filename, size, checksums, basedir))
        logger.debug(f"after checksums: {self.file_checksum_list=}")

    def get_file_list(self):
        return self.file_checksum_list


    def get_suffix(self, fname):
         pos = fname.rfind(".")
         if pos > 0:
              suffix = fname[pos+1:]
              if suffix == "gz":
                  return True, get_suffix(fname[:pos])[1]
              return False, suffix
         return False, ""

    # subset of legal iana application types
    iana_images=set([
      "jpeg","gif","png","svg","tiff","fits"
    ])
    iana_applications=set([
     "iges", "mp4"
    ])

    def get_mimetype(self, suffix):
         if not suffix:
             mimetype = f"unknown"
         elif suffix == "txt":
             mimetype = "text/plain"
         elif suffix == "csv":
             mimetype = "text/csv"
         elif suffix.find("json") > 0:
             mimetype = "text/javascript"
         elif suffix in InfoGetter.iana_images:
             mimetype = f"image/{suffix}"
         elif suffix in InfoGetter.iana_applications:
             mimetype = f"application/{suffix}"
         else:
             mimetype = f"application/X-{suffix}"
         return mimetype

    def generate(self, outfile):
        ''' generate the metadata for the scanned directories '''

        sep="["
        for finfo in self.file_checksum_list:
            gz, suffix = self.get_suffix(finfo[0])
            mimetype = self.get_mimetype(suffix)
                
            print(f"""{sep}
        {{
            "name": "{finfo[0]}",
            "namespace": "{self.namespace}",
            "size": {finfo[1]},
            "checksums": {finfo[2]},
            "metadata": {{
                "AmSC.common.description": "Description of file {finfo[0]} in {finfo[3]}",
                "AmSC.common.display_name": "{finfo[0]}",
                "AmSC.common.location": "{finfo[3]}/{finfo[0]}",
                "AmSC.common.tags": "",
                "AmSC.common.version": "",
                "AmSC.artifact.format": "{mimetype}"
            }}
        }}""", end="", file=outfile)

            sep=","

        if self.file_checksum_list:
            print("\n]", file=outfile)

 
def main():
    level = logging.INFO
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", action="store_true", default=False)
    parser.add_argument("-n", "--namespace",  default="amsc")
    parser.add_argument("-o", "--outfile", default=None)
    parser.add_argument("directory_url", default=[], nargs="+")

    args = parser.parse_args()

    level = logging.INFO
    if args.debug:
        level = logging.DEBUG

    logging.basicConfig(level=level)

    if args.outfile:
        outfile = open(args.outfile, "w")
    else:
        outfile = sys.stdout

    ig = InfoGetter(namespace=args.namespace)

    for basedir in args.directory_url:
        ig.get_files(basedir.strip("/"))

    ig.generate(outfile)


if __name__ == "__main__":
    main()
