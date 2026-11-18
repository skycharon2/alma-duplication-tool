"""Explicit local HTTPS acceptance against a real Dex binary and PostgreSQL.

Run with --dex /path/to/dex and ALMA_TEST_DATABASE_URL. Uses disposable users,
private temporary artifacts and an isolated database schema; never a live IdP.
"""
from datetime import datetime, timedelta, timezone
import hashlib
from html.parser import HTMLParser
import ipaddress
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import urljoin, urlsplit, urlunsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]


class Form(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.action = ''
        self.fields = {}
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.action = attrs.get('action', '')
        if tag == 'input' and attrs.get('name'):
            self.fields[attrs['name']] = attrs.get('value', '')


def serve(config_path):
    from alma_duplicate.ui import create_app
    from alma_duplicate.ui.runs import BrowserAssessment
    from werkzeug.serving import make_server, WSGIRequestHandler
    config = json.loads(Path(config_path).read_text())
    port, cert, key = (config.pop(k) for k in ('port', 'cert', 'key'))

    def forbidden(*args, **kwargs):
        raise AssertionError('Saved reads must not execute an assessment')

    for name in ('assess', 'assess_mosaic', 'assess_queue_custom'):
        if hasattr(BrowserAssessment, name):
            setattr(BrowserAssessment, name, forbidden)
    app = create_app(config)

    @app.after_request
    def process_id(response):
        response.headers['X-Gate-Pid'] = str(os.getpid())
        return response

    class QuietHandler(WSGIRequestHandler):
        def log_request(self, *args, **kwargs):
            pass  # Callback URLs contain authorization codes.

    make_server('127.0.0.1', port, app, threaded=True,
                ssl_context=(cert, key), request_handler=QuietHandler).serve_forever()


def certificate(directory):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Disposable local acceptance')])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost'),
                x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]), critical=False)
            .sign(key, hashes.SHA256()))
    cert_path, key_path = directory / 'cert.pem', directory / 'key.pem'
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                         serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    key_path.chmod(0o600)
    return str(cert_path), str(key_path)


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def run(dex):
    import requests
    from sqlalchemy import text, select
    from sqlalchemy.engine import make_url
    from alembic import command
    from alembic.config import Config
    from alma_duplicate.persistence.db import database_engine, transaction
    from alma_duplicate.persistence import models as m
    from alma_duplicate.persistence.reports import publish_report
    from alma_duplicate.artifacts.local import LocalArtifactStore
    from alma_duplicate.ui.runs import BrowserAssessment
    from alma_duplicate.reporting import report_json_text

    url = os.environ['ALMA_TEST_DATABASE_URL']
    engine = database_engine(url)
    schema = 'test_alma_gate_' + uuid4().hex
    processes = []
    schema_created = False
    scoped = None
    checks = []
    try:
        with engine.begin() as conn:
            conn.execute(text(f'CREATE SCHEMA "{schema}"'))
            schema_created = True
        scoped_url = make_url(url).update_query_dict({'options': '-csearch_path=' + schema})
        scoped = database_engine(scoped_url.render_as_string(hide_password=False))
        with scoped.begin() as conn:
            cfg = Config(str(ROOT / 'alembic.ini'))
            cfg.set_main_option('script_location', str(ROOT / 'migrations'))
            cfg.attributes['connection'] = conn
            command.upgrade(cfg, 'head')
        with tempfile.TemporaryDirectory(prefix='alma-oidc-gate-') as temp:
            directory = Path(temp)
            cert, key = certificate(directory)
            ports = [free_port() for _ in range(3)]
            assert len(set(ports)) == 3
            issuer = f'https://localhost:{ports[0]}/dex'
            a, b = (f'https://localhost:{port}' for port in ports[1:])
            client_secret = secrets.token_urlsafe(32)
            dex_config = {'issuer': issuer, 'storage': {'type': 'memory'},
                'web': {'https': f'127.0.0.1:{ports[0]}', 'tlsCert': cert, 'tlsKey': key},
                'oauth2': {'skipApprovalScreen': True}, 'enablePasswordDB': True,
                'staticClients': [{'id': 'alma-gate', 'secret': client_secret,
                    'name': 'Local acceptance', 'redirectURIs': [a + '/auth/callback']}],
                'staticPasswords': [{'email': name + '@example.invalid', 'username': name,
                    'userID': str(uuid4()),
                    # Dex documentation fixture: password is "password".
                    'hash': '$2a$10$2b2cU8CPhOTaGrs1HRQuAueS7JTT5ZHsHSzYiFPm1leZck7Mc8T4W'}
                    for name in ('alice', 'bob')]}
            dex_path = directory / 'dex.json'
            dex_path.write_text(json.dumps(dex_config))
            env = dict(os.environ, REQUESTS_CA_BUNDLE=cert, NO_PROXY='localhost,127.0.0.1',
                       PYTHONPATH=str(ROOT / 'src'))

            def launch(args):
                process = subprocess.Popen(args, env=env, cwd=ROOT,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                processes.append(process)
                return process

            def client():
                session = requests.Session()
                session.trust_env = False
                session.verify = cert
                return session

            probe = client()

            def ready(address, process):
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        raise RuntimeError('Acceptance server exited during startup')
                    try:
                        if probe.get(address, timeout=1).status_code == 200:
                            return
                    except requests.RequestException:
                        pass
                    time.sleep(.1)
                raise RuntimeError('Acceptance server did not become ready')

            provider = launch([str(dex), 'serve', str(dex_path)])
            ready(issuer + '/.well-known/openid-configuration', provider)
            settings = {'AUTH_MODE': 'oidc', 'OIDC_ISSUER': issuer,
                'OIDC_CLIENT_ID': 'alma-gate', 'OIDC_CLIENT_SECRET': client_secret,
                'OIDC_REDIRECT_URI': a + '/auth/callback',
                'AUTH_SESSION_SECRET': secrets.token_urlsafe(48),
                'ARTIFACT_ROOT': str(directory / 'artifacts'),
                'DATABASE_URL': scoped_url.render_as_string(hide_password=False),
                'AUTO_QUEUE': False, 'cert': cert, 'key': key}
            config_paths = []
            servers = []
            for port, address in zip(ports[1:], (a, b)):
                path = directory / f'web-{port}.json'
                path.write_text(json.dumps(dict(settings, port=port)))
                config_paths.append(path)
                process = launch([sys.executable, __file__, '--serve', str(path)])
                ready(address + '/healthz', process)
                servers.append(process)

            def login(name, callback_server):
                session = client()
                response = session.get(a + '/auth/login', allow_redirects=False, timeout=10)
                # Keep callbacks under explicit control so state starts in A and ends in B.
                for _ in range(15):
                    if response.is_redirect:
                        destination = urljoin(response.url, response.headers['Location'])
                        if urlsplit(destination).path == '/auth/callback':
                            parsed = urlsplit(destination)
                            destination = urlunsplit((parsed.scheme, urlsplit(callback_server).netloc,
                                                       parsed.path, parsed.query, ''))
                            response = session.get(destination, allow_redirects=False, timeout=10)
                            assert response.status_code == 302, 'OIDC callback failed'
                            assert response.headers['Location'] == '/workspace'
                            return session
                        response = session.get(destination, allow_redirects=False, timeout=10)
                    else:
                        assert response.status_code == 200, 'IdP sign-in page failed'
                        form = Form(response.text)
                        assert 'login' in form.fields and 'password' in form.fields
                        form.fields.update(login=name + '@example.invalid', password='password')
                        response = session.post(urljoin(response.url, form.action), data=form.fields,
                                                allow_redirects=False, timeout=10)
                raise AssertionError('OIDC flow did not complete')

            alice = login('alice', b)
            checks.append('real discovery, authorization code, PKCE, JWKS, callback across processes')
            with scoped.connect() as conn:
                workspace = conn.scalar(select(m.workspaces.c.id))
            request = json.loads((ROOT / 'examples/confirmed_line/request.json').read_bytes())
            result = BrowserAssessment(archive_replay=ROOT / 'examples/confirmed_line/archive/manifest.json',
                                       report_detail='full').assess(request)
            now = datetime.now(timezone.utc)
            with transaction(scoped) as session:
                session.execute(m.submissions.insert().values(id='s', workspace_id=workspace,
                    kind='SINGLE', settings={}, input_sha256='a'*64))
                session.execute(m.sources.insert().values(id='src', workspace_id=workspace,
                    submission_id='s', ordinal=0, name='fixture', ra_deg=1, dec_deg=2, original_input={}))
                session.execute(m.jobs.insert().values(id='j', workspace_id=workspace, submission_id='s',
                    source_id='src', purpose='LINE', state='RUNNING', attempt=1, lease_token='gate',
                    heartbeat_at=now, lease_expires_at=now + timedelta(hours=1)))
            report = publish_report(scoped, LocalArtifactStore(settings['ARTIFACT_ROOT']), workspace, 'j',
                attempt=1, lease_token='gate', request_document=request, result=result, source_provenance={})
            expected = report_json_text(result.document).encode()
            bob = login('bob', a)
            pids = set()
            for address in (a, b):
                for suffix in ('', '/visualization', '/download/report'):
                    path = '/runs/' + report + suffix
                    response = alice.get(address + path, timeout=10, allow_redirects=False)
                    assert response.status_code == 200
                    pids.add(response.headers['X-Gate-Pid'])
                    if suffix == '/download/report':
                        assert response.content == expected
                    assert bob.get(address + path, timeout=10, allow_redirects=False).status_code == 404
                assert alice.get(address + '/proposed/batch', timeout=10).status_code == 403
            assert len(pids) == 2
            checks.append('two users, two processes, scoped report/visualization/download, legacy denial')
            servers[0].terminate()
            servers[0].wait(timeout=10)
            restarted = launch([sys.executable, __file__, '--serve', str(config_paths[0])])
            ready(a + '/healthz', restarted)
            response = alice.get(a + '/runs/' + report + '/download/report', timeout=10)
            assert response.status_code == 200 and response.content == expected
            assert response.headers['X-Gate-Pid'] not in pids
            checks.append('process restart preserves session and exact report bytes')
            old_cookies = alice.cookies.copy()
            form = Form(alice.get(b + '/workspace', timeout=10).text)
            assert alice.post(b + '/auth/logout', data=form.fields, timeout=10,
                              allow_redirects=False).status_code == 302
            replay = client()
            replay.cookies.update(old_cookies)
            response = replay.get(a + '/runs/' + report, timeout=10, allow_redirects=False)
            assert response.status_code == 302 and response.headers['Location'] == '/auth/login'
            checks.append('logout revocation is visible across processes; old cookie rejected')
            print(json.dumps({'checks': checks, 'report_sha256': hashlib.sha256(expected).hexdigest()}, indent=2))
            for process in processes:
                if process.poll() is None:
                    process.terminate()
            for process in processes:
                process.wait(timeout=10)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        if scoped is not None:
            scoped.dispose()
        if schema_created:
            with engine.begin() as conn:
                conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--serve')
    group.add_argument('--dex', type=Path)
    args = parser.parse_args()
    if args.serve:
        serve(args.serve)
    else:
        run(args.dex.resolve())
