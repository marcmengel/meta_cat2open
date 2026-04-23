import os
import json
import requests
import urllib.parse
import logging
import traceback
logger = logging.getLogger(__name__)

class AmSCClient:
    def __init__(self, cf):
        self.amsc_url = cf.get("general","amsc_url") 
        self.catalog_name = cf.get("general","catalog_name") 
        self.sess = requests.Session()
        #self.sess.headers.update( {"Authorization": cf.get("openmetadata","jwt_token")})
        self.sess.headers.update( {"Authorization": f'Bearer {cf.get("openmetadata","jwt_token")}'})

    def query(self, querystring, limit=0, offset=0):
        url = f"{self.amsc_url}/search/catalog?q={urllib.parse.quote(querystring)}"
        if limit:
            url += f"&{limit=}"
        if offset:
            url += f"&{offset=}"
        resp = self.sess.get(url)
        return resp.json()

    def post_create(self, entity_dict):
        url = f"{self.amsc_url}/catalog/{self.catalog_name}/{entity_dict['type']}"
        logger.debug(f"posting {json.dumps(entity_dict, indent=4)} to {url}")
        logger.debug(f"..with headers {self.sess.headers}")
        resp = self.sess.post(url , json=entity_dict)
        if resp.status_code != 200: 
         
             if resp.text.find("already exists") > 0:
                 logger.info(f"Exists already: {entity_dict['name']}") 
             else:        
                 logger.error(f"got status {resp.status_code} for POST catalog entry: {resp.text}")
                 #raise RuntimeError(f"got status {resp.status_code} for POST catalog entry: {resp.text}")
        return resp.json()

    def get(self, fqn):
        url = f"{self.amsc_url}/catalog/{fqn}"
        resp = self.sess.get(url)
        if resp.status_code == 200:
            return resp.json()
        else:
            logger.error(f"get status: {resp.status_code} error {resp.text}")
            return None

    def put_update(self, entity_dict):
        url = f"{self.amsc_url}/catalog/{entity_dict['fqn']}"
        logger.debug(f"posting {json.dumps(entity_dict, indent=4)} to {url}")
        logger.debug(f"..with headers {self.sess.headers}")
        resp = self.sess.put(url, json=entity_dict)
        if resp.status_code != 200:
             logger.error(f"Error: got status {resp.status_code} for PUT catalog entry: {resp.text}")
             #raise RuntimeError(f"got status {resp.status_code} for PUT catalog entry: {resp.text}")
        return resp.json()

    def delete_item(self, entity_dict):
        url = f"{self.amsc_url}/catalog/{entity_dict['fqn']}"
        logger.debug(f"deleting {json.dumps(entity_dict, indent=4)} to {url}")
        logger.debug(f"..with headers {self.sess.headers}")
        resp = self.sess.delete(url, json=entity_dict)
        if resp.status_code != 200:
             logger.error(f"Error: got status {resp.status_code} for PUT catalog entry: {resp.text}")
             #raise RuntimeError(f"got status {resp.status_code} for PUT catalog entry: {resp.text}")
        return resp.json()

