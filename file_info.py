import configparser
import requests
import xml.parsers.expat
import re
import os
import sys

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class InfoGetter:
    def __init__(self):
        self.s = requests.Session()
        self.token_header = {
             "Authorization": f"Bearer {self.get_bearer_token()}",
         }
        #print(f"{self.s.headers=}")
#
    def get_bearer_token(self):
        token = os.environ.get("BEARER_TOKEN")
        if not token:
            token_file = os.environ.get("BEARER_TOKEN_FILE")
            if not token_file:
                uid = os.environ.get("ID", str(os.geteuid()))
                token_dir = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
                token_file = token_dir + "/" + "bt_u" + uid
        token = open(token_file, "r").read().strip()
        return token

    def get_files( self, basedir, do_checksums = False ):
        #print(f"get_files: {basedir=}")
        req = requests.Request('PROPFIND', basedir, headers=self.token_header)
        resp = self.s.send(req.prepare(), verify=False )

        #print(f"{resp.status_code=} {resp.text=}")

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


        if do_checksums:
            spos = basedir.find("/", 9)
            apibase = f"{basedir[0:spos]}/api/v1/namespace{basedir[spos:]}"
            apibase = apibase.replace(":2880/",":3880/")

            file_checksum_list = []
            for filename, size in file_list:
                url=f"{apibase}/{filename}?checksum=true"
                #print(f"{url=}")
                resp = self.s.get(url, headers=self.token_header, verify=False)
                #print(f"{resp.status_code=} {resp.text=}")
                if resp.status_code == 200:
                    data = resp.json()
                    csvalue = data["checksums"][0]["value"]
                    cstype = data["checksums"][0]["type"].lower()
                    checksums = f'{{ "{cstype}": "{csvalue}" }}'
                else:
                    checksums = "{}"
                file_checksum_list.append( (filename, size, checksums))

            return file_checksum_list

        return file_list

ig = InfoGetter()
fl = ig.get_files(sys.argv[1], do_checksums=True)


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
 

sep="["
for finfo in fl:
    gz, suffix = get_suffix(finfo[0])
    mimetype = get_mimetype(suffix)
        
    print(f"""
{sep}
{{
    "name": "{finfo[0]}",
    "namespace": "amsc",
    "size": {finfo[1]},
    "checksums": {finfo[2]},
    "metadata": {{
        "AmSC.common.description": "Description of file {finfo[0]}",
        "AmSC.common.display_name": "{finfo[0]}",
        "AmSC.common.fqn": "fnal-amsc-storage.fnal-amsc-data-catalog.migration_test_1.testfile1",
        "AmSC.common.license": "GPL",
        "AmSC.common.persistent_identifier": "16de1858-1e4b-11f1-8f62-fc4dd4d6e7f4@bel-kwinith.fnal.gov",
        "AmSC.common.tags": "demo,test",
        "AmSC.common.type": "artifact",
        "AmSC.common.version": "v0.1",
        "AmSC.artifact.format": "{mimetype}"
    }}
}}""", end="")
    sep=","

print("\n]")
