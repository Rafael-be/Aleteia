"""Bounded public-document fetch. DNS is validated and the connection pins that IP.

No ambient proxies/cookies, no JavaScript, no compressed responses or file parsers.
Only provider-retrieved URLs enter this module; every redirect is checked again.
"""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import http.client
import ipaddress
import re
import socket
import ssl
from threading import BoundedSemaphore, Lock
from time import monotonic
from urllib.parse import urljoin, urlsplit, urlunsplit

MAX_BYTES = 512_000
MAX_TEXT = 12_000
_DNS = ThreadPoolExecutor(max_workers=2, thread_name_prefix='evidence-dns')
_DNS_SLOTS = BoundedSemaphore(2)
_FETCH_SLOTS = BoundedSemaphore(4)
_CACHE = OrderedDict()
_CACHE_LOCK = Lock()


def _public_address(value):
    ip = ipaddress.ip_address(value)
    if not ip.is_global or ip.is_multicast or ip.is_unspecified:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped or ip.sixtofour or ip.teredo:
            return False
        if any(ip in ipaddress.ip_network(prefix) for prefix in ('64:ff9b::/96', '64:ff9b:1::/48')):
            return False
    return True


def public_url(url):
    if not isinstance(url, str) or len(url) > 2048 or re.search(r'[\x00-\x20\\<>"`]', url):
        raise ValueError('Unsafe URL')
    p = urlsplit(url)
    if p.scheme not in {'https', 'http'} or not p.hostname or p.username or p.password:
        raise ValueError('Unsafe URL')
    if p.port not in {None, 80 if p.scheme == 'http' else 443}:
        raise ValueError('Unsafe port')
    hostname = p.hostname.encode('idna').decode('ascii').lower().rstrip('.')
    if hostname == 'localhost' or hostname.endswith(('.localhost', '.local', '.internal')):
        raise ValueError('Private hostname')
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        if '.' not in hostname:
            raise ValueError('Private hostname')
    else:
        if not _public_address(hostname):
            raise ValueError('Private IP')
    host = f'[{hostname}]' if ':' in hostname else hostname
    return urlunsplit((p.scheme, host, p.path or '/', p.query, ''))


def resolve_public(host, port, timeout):
    if not _DNS_SLOTS.acquire(blocking=False):
        raise ValueError('DNS busy')
    try:
        task = _DNS.submit(socket.getaddrinfo, host, port, 0, socket.SOCK_STREAM)
    except Exception:
        _DNS_SLOTS.release()
        raise
    task.add_done_callback(lambda _: _DNS_SLOTS.release())
    addresses = task.result(timeout=timeout)
    if not addresses:
        raise ValueError('No address')
    for _, _, _, _, sockaddr in addresses:
        if not _public_address(sockaddr[0]):
            raise ValueError('Private DNS answer')
    return addresses[0][4][0]


class PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, host, address, timeout, secure):
        super().__init__(host, port=443 if secure else 80, timeout=timeout)
        self.address, self.secure = address, secure

    def connect(self):
        self.sock = socket.create_connection((self.address, self.port), self.timeout)
        if self.secure:
            try:
                self.sock = ssl.create_default_context().wrap_socket(self.sock, server_hostname=self.host)
            except Exception:
                self.sock.close()
                raise


class TextHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip, self.parts, self.links = 0, [], []
        self.title, self.in_title = [], False

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript', 'svg', 'template', 'nav', 'footer', 'form', 'aside'}:
            self.skip += 1
        if self.skip:
            return
        if tag == 'title':
            self.in_title = True
        if tag == 'a':
            href = dict(attrs).get('href', '')
            if href:
                self.links.append(href)
        if tag in {'p', 'div', 'br', 'h1', 'h2', 'h3', 'li', 'tr'}:
            self.parts.append(' ')

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript', 'svg', 'template', 'nav', 'footer', 'form', 'aside'}:
            self.skip = max(0, self.skip-1)
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)
            if self.in_title:
                self.title.append(data)


def fetch_document(url, deadline):
    original = public_url(url)
    with _CACHE_LOCK:
        cached = _CACHE.get(original)
        if cached and cached[0] > monotonic():
            _CACHE.move_to_end(original)
            return {**cached[1], 'cache_hit': True}
    if not _FETCH_SLOTS.acquire(timeout=max(.01, min(2, deadline-monotonic()))):
        raise ValueError('Fetch busy')
    try:
        current = original
        for _ in range(4):
            current = public_url(current)
            remaining = min(6, deadline-monotonic())
            if remaining <= 0:
                raise TimeoutError('Fetch deadline')
            p = urlsplit(current)
            address = resolve_public(p.hostname, 443 if p.scheme == 'https' else 80, remaining)
            connection = PinnedHTTP(p.hostname, address, max(.01, min(6, deadline-monotonic())), p.scheme == 'https')
            try:
                connection.request('GET', urlunsplit(('', '', p.path, p.query, '')), headers={
                    'User-Agent': 'Aleteia-Evidence/2.0', 'Accept': 'text/html,text/plain',
                    'Accept-Encoding': 'identity', 'Connection': 'close'})
                response = connection.getresponse()
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.getheader('Location')
                    if not location:
                        raise ValueError('Missing redirect')
                    current = urljoin(current, location)
                    continue
                if response.status != 200:
                    raise ValueError('Source unavailable')
                content_type = response.getheader('Content-Type', '').lower()
                if not any(x in content_type for x in ('text/html', 'text/plain')):
                    raise ValueError('Unsupported source type')
                if response.getheader('Content-Encoding', 'identity').lower() != 'identity':
                    raise ValueError('Compressed content rejected')
                length = response.getheader('Content-Length')
                if length and (not length.isdigit() or int(length) > MAX_BYTES):
                    raise ValueError('Source too large')
                data = bytearray()
                while len(data) <= MAX_BYTES:
                    remaining = min(3, deadline-monotonic())
                    if remaining <= 0:
                        raise TimeoutError('Read deadline')
                    if connection.sock:
                        connection.sock.settimeout(remaining)
                    part = response.read1(min(16384, MAX_BYTES+1-len(data)))
                    if not part:
                        break
                    data.extend(part)
                if len(data) > MAX_BYTES:
                    raise ValueError('Source too large')
            finally:
                connection.close()
            charset = re.search(r'charset=["\']?([\w-]+)', content_type)
            encoding = charset.group(1) if charset else 'utf-8'
            if encoding.lower() not in {'utf-8', 'utf8', 'iso-8859-1', 'latin-1', 'windows-1252'}:
                encoding = 'utf-8'
            decoded = data.decode(encoding, errors='replace')
            parser = TextHTML()
            if 'text/html' in content_type:
                parser.feed(decoded)
                text = re.sub(r'\s+', ' ', ''.join(parser.parts)).strip()
            else:
                text = re.sub(r'\s+', ' ', decoded).strip()
            if len(text) < 80:
                raise ValueError('Insufficient document text')
            links = []
            for href in parser.links[:300]:
                try:
                    links.append(public_url(urljoin(current, href)))
                except ValueError:
                    pass
            document = {'url': original, 'final_url': current, 'title': ''.join(parser.title)[:200],
                        'text': text[:MAX_TEXT], 'truncated': len(text) > MAX_TEXT,
                        'hash': sha256(text[:MAX_TEXT].encode()).hexdigest(),
                        'raw_hash': sha256(data).hexdigest(), 'links': sorted(set(links)),
                        'retrieved_at': datetime.now(timezone.utc).isoformat(), 'cache_hit': False}
            with _CACHE_LOCK:
                _CACHE[original] = (monotonic()+300, document)
                _CACHE.move_to_end(original)
                while len(_CACHE) > 64:
                    _CACHE.popitem(last=False)
            return document
        raise ValueError('Too many redirects')
    finally:
        _FETCH_SLOTS.release()
