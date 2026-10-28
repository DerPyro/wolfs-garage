# Test helpers copied from tests/lubelogger/run.py; no import-time sandbox creation.
# Source SHA256: 67be3363808867db2e6c94542aa87ac1001e84e31d69a1929afe81923660e063
# Existing B01/B02 harness and evidence remain unchanged.
import http.cookiejar
import json
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class Client:
    def __init__(self, base, key=None):
        self.base = base
        self.key = key
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), NoRedirect())

    def call(self, path, method='GET', data=None, form=None, invariant=True, upload=None):
        headers = {}
        if invariant:
            headers['culture-invariant'] = ''
        if self.key:
            headers['x-api-key'] = self.key
        body = None
        if data is not None:
            body = json.dumps(data).encode()
            headers['Content-Type'] = 'application/json'
        if form is not None:
            body = urllib.parse.urlencode(form, doseq=True).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        if upload:
            field, name, content = upload
            boundary = 'wolfs-' + secrets.token_hex(12)
            body = (f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{name}"\r\n'
                    'Content-Type: application/octet-stream\r\n\r\n').encode() + content + f'\r\n--{boundary}--\r\n'.encode()
            headers['Content-Type'] = 'multipart/form-data; boundary=' + boundary
        req = urllib.request.Request(self.base+path, body, headers, method=method)
        try:
            response = self.opener.open(req, timeout=20)
        except urllib.error.HTTPError as e:
            response = e
        raw = response.read()
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            value = None
        return response.code, value, raw

    def ok(self, path, **kwargs):
        code, value, _ = self.call(path, **kwargs)
        assert code == 200 and isinstance(value, dict) and value.get('success') is True, (path, code, 'unexpected operation result; response omitted')
        return value

    def get(self, path, **kwargs):
        code, value, _ = self.call(path, **kwargs)
        assert code == 200, (path, code)
        return value

def login(base, username, password):
    c = Client(base)
    # Upstream reloads JSON configuration asynchronously after initial setup/restore.
    for _ in range(30):
        code, value, _ = c.call('/Login/Login', method='POST', form={'UserName': username, 'Password': password})
        if code == 200 and isinstance(value, dict) and value.get('success') is True:
            return c
        time.sleep(0.2)
    raise AssertionError('Login failed after bounded configuration reload wait')

def user(root, base, name):
    email = name.removeprefix('sandbox-')+'@example.invalid'
    root.ok('/Admin/GenerateNewToken', method='POST', form={'emailAddress': email, 'autoNotify': 'false'})
    rows = root.call('/Admin/GetTokenPartialView')[2].decode('utf-8-sig')
    token = None
    for row in re.findall(r'<tr.*?</tr>', rows, re.S):
        if email in row:
            token = re.search(r'copyToClipboard\(this\)">(.*?)</td>', row).group(1)
    assert token, 'Registration token missing'
    password = secrets.token_urlsafe(24)
    Client(base).ok('/Login/Register', method='POST', form={'UserName': name, 'Password': password,
                       'EmailAddress': email, 'Token': token})
    client = login(base, name, password)
    client.test_credentials = (name, password)
    return client

def key(session, base, name, permissions):
    result = session.ok('/Home/CreateAPIKeyForUser', method='POST',
                        form={'keyName': name, 'permissions': permissions})
    return Client(base, result['additionalData']['apiKey'])

def api_add(client, resource, vehicle, data):
    return client.ok('/api/vehicle/'+resource+'/add?vehicleId='+str(vehicle), method='POST', data=data)['additionalData']['recordId']

def items(client, resource, vehicle):
    return client.get('/api/vehicle/'+resource+'?vehicleId='+str(vehicle))

def denied(result):
    code, value, _ = result
    return code in (401,403) or (code == 200 and isinstance(value,dict) and value.get('success') is False)
