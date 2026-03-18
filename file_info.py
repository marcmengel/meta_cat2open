import configparser
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
    def __init__(self):
        self.s = requests.Session()
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

    def get_files( self, basedir, do_checksums = False ):
        logger.debug(f"get_files: {basedir=}")

        req = requests.Request('PROPFIND', basedir, headers=self.token_header)
        #req = requests.Request('PROPFIND', basedir)
        resp = self.s.send(req.prepare(), verify=False )

        logger.debug(f"{resp.status_code=} {resp.text=}")

        file_list = []
        curname = None
        filename = None
        size = None
        def start_element(name, attrs):
            nonlocal curname, filename, size
            curname = name
        def char_data(text):
            nonlocal curname, filename, size
            if curname == 'd:displayname':
                filename = text
            if curname == 'd:getcontentlength':
                size = int(text)
        def end_element(name):
            nonlocal curname, filename, size
            if name == 'd:response':
               file_list.append((filename, size))

        xp = xml.parsers.expat.ParserCreate()
        xp.StartElementHandler = start_element
        xp.CharacterDataHandler = char_data
        xp.EndElementHandler = end_element
        xp.Parse(resp.text)

        # first displayname is the directory itself, so skip it
        file_list = file_list[1:]


        spos = basedir.find("/", 9)
        apibase = f"{basedir[0:spos]}/api/v1/namespace{basedir[spos:]}"
        apibase = apibase.replace(":2880/",":3880/")

        for filename, size in file_list:
            url=f"{apibase}/{filename}?checksum=true"
            logger.debug(f"{url=}")
            resp = self.s.get(url, headers=self.token_header, verify=False)
            logger.debug(f"{resp.status_code=} {resp.text=}")
            if resp.status_code == 200:
                data = resp.json()
                csvalue = data["checksums"][0]["value"]
                cstype = data["checksums"][0]["type"].lower()
                checksums = f'{{ "{cstype}": "{csvalue}" }}'
            else:
                checksums = "{}"
            self.file_checksum_list.append( (filename, size, checksums, basedir))

    def get_file_list(self):
        return self.file_checksum_list


def get_suffix(fname):
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

def get_mimetype(suffix):
     if not suffix:
         mimetype = f"unknown"
     elif suffix == "txt":
         mimetype = "text/plain"
     elif suffix.find("json") > 0:
         mimetype = "text/javascript"
     elif suffix in iana_applications :
         mimetype = f"application/{suffix}"
     else:
         mimetype = f"application/X-{suffix}"
     return mimetype
 
def main():
    level = logging.INFO
    if len(sys.argv) == 1 or sys.argv[1] == "-h":
        print("file_info.py -- make metadata upload file from dcache directories")
        print("usage: python file_info.py [-h] [-d]  directory_url1 url2 ... > out.json")
        print("  options:")
        print("  -h: print this help message")
        print("  -d: enable debug logging")
        exit(1)

    if sys.argv[1] == "-d":
        level = logging.DEBUG
        sys.argv = sys.argv[1:]
    logging.basicConfig(level=level)

    ig = InfoGetter()
    for basedir in sys.argv[1:]:
        ig.get_files(basedir.strip("/"), do_checksums=True)

    sep="["
    for finfo in ig.get_file_list():
        gz, suffix = get_suffix(finfo[0])
        mimetype = get_mimetype(suffix)
            
        print(f"""{sep}
    {{
        "name": "{finfo[0]}",
        "namespace": "amsc",
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
    }}""", end="")

        sep=","

    print("\n]")

if __name__ == "__main__":
    main()
