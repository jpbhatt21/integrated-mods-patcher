import os
from dotenv import load_dotenv
from sessions import get_session
from urllib.parse import quote

session = get_session()
load_dotenv()
NOCO_DB_API_URL = os.getenv('NOCO_DB_API_URL', '')
NOCO_DB_BASE = os.getenv('NOCO_DB_BASE', '')
NOCO_DB_TABLES = dict(item.split(":") for item in os.getenv('NOCO_DB_TABLES', '').split(",")) or {}
NOCO_DB_ENDPOINTS = dict(item.split(":") for item in os.getenv('NOCO_DB_ENDPOINTS', '').split(",")) or {}
HEADERS = {
    'Content-Type': 'application/json',
    'Authorization': "Bearer {}"
}

def get(ep, bearer=None, table="",record="",query_params=None):
    """Generic GET request to NocoDB API"""
    headers = HEADERS.copy()
    if bearer:
        headers['Authorization'] = headers['Authorization'].format(bearer)
    endpoint = NOCO_DB_ENDPOINTS.get(ep,False)
    # URL-encode the record parameter

    encoded_record = quote(str(record), safe='') if record else record
    url = NOCO_DB_API_URL.format(endpoint.format(NOCO_DB_BASE, NOCO_DB_TABLES[table], encoded_record)) if endpoint else ep
    print(f"GET URL: {url} with params: {query_params}")
    return session.get(
        url,
        headers=headers,
        params=query_params
    )

def patch(ep, bearer=None, table="",record="", data=None):
    """Generic PATCH request to NocoDB API"""
    headers = HEADERS.copy()
    if bearer:
        headers['Authorization'] = headers['Authorization'].format(bearer)
    endpoint = NOCO_DB_ENDPOINTS.get(ep,False)
    # URL-encode the record parameter
    encoded_record = quote(str(record), safe='') if record else record
    url = NOCO_DB_API_URL.format(endpoint.format(NOCO_DB_BASE, NOCO_DB_TABLES[table], encoded_record)) if endpoint else ep
    print(f"PATCH URL: {url} with data: {data}")
    return session.patch(
        url,
        headers=headers,
        json=data
    )



def post(endpoint, bearer=None, table="", data=None):
    """Generic POST request to NocoDB API"""
    headers = HEADERS.copy()
    if bearer:
        headers['Authorization'] = headers['Authorization'].format(bearer)
    endpoint = NOCO_DB_API_URL.format(NOCO_DB_ENDPOINTS.get(endpoint, endpoint))
    url = endpoint.format(NOCO_DB_BASE, NOCO_DB_TABLES[table])
    return session.post(
        url,
        headers=headers,
        json=data
    )