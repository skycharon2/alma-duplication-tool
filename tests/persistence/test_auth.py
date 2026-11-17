"""Offline signed OIDC tokens plus database-backed session and route isolation."""
from datetime import datetime, timedelta, timezone
import base64
import hashlib
from urllib.parse import parse_qs, urlsplit
import time

import pytest
pytest.importorskip('authlib')
pytest.importorskip('sqlalchemy')
pytest.importorskip('alembic')
from joserfc import jwk, jwt
from sqlalchemy import select, func
from alma_duplicate.persistence import models as m
from alma_duplicate.persistence.db import transaction
from alma_duplicate.ui import create_app
from alma_duplicate.ui.workspaces import create_login, resolve_login, revoke_login
from tests.persistence.test_foundation import connection as connection_fixture
from tests.ui.test_runs import config

from tests.ui.test_run_store import assessment as assessment_fixture

connection = connection_fixture
assessment = assessment_fixture
ISSUER = 'https://identity.example.test'
ORIGIN = 'https://alma.example.test'


def auth_config(conn, root):
    return config(AUTH_MODE='oidc', OIDC_ISSUER=ISSUER, OIDC_CLIENT_ID='alma-client',
        OIDC_CLIENT_SECRET='test-provider-secret', OIDC_REDIRECT_URI=ORIGIN+'/auth/callback',
        AUTH_SESSION_SECRET='a'*48, ARTIFACT_ROOT=str(root), AUTH_TEST_ENGINE=conn)


def close_app(app):
    for key in ['assessment_runs', 'source_uploads', 'mosaic_uploads']:
        app.extensions[key].close()


@pytest.fixture
def login_app(connection, tmp_path, monkeypatch):
    app = create_app(auth_config(connection, tmp_path / 'artifacts'))
    oidc = app.extensions['oidc_client']
    key = jwk.RSAKey.generate_key(parameters={'kid': 'test-key'})
    metadata = dict(issuer=ISSUER, authorization_endpoint=ISSUER+'/authorize',
                    token_endpoint=ISSUER+'/token', jwks_uri=ISSUER+'/jwks',
                    id_token_signing_alg_values_supported=['RS256'])
    monkeypatch.setattr(oidc, 'load_server_metadata', lambda: metadata)
    monkeypatch.setattr(oidc, 'fetch_jwk_set', lambda **kwargs: {'keys': [key.as_dict(private=False)]})
    def sign_in(client, changes=None, signing_key=None, state_override=None):
        response = client.get('/auth/login', base_url=ORIGIN)
        assert response.status_code == 302
        params = parse_qs(urlsplit(response.location).query)
        assert params['code_challenge_method'] == ['S256']
        assert params['redirect_uri'] == [ORIGIN+'/auth/callback']
        now = int(time.time())
        claims = dict(iss=ISSUER, sub='subject-a', aud='alma-client', iat=now, exp=now+600,
                      nonce=params['nonce'][0]) | (changes or {})
        signed = jwt.encode({'alg': 'RS256', 'kid': 'test-key'}, claims, signing_key or key)
        def fetch(**kwargs):
            assert base64.urlsafe_b64encode(hashlib.sha256(
                kwargs['code_verifier'].encode()).digest()).rstrip(b'=').decode() == params['code_challenge'][0]
            return dict(access_token='test-access', token_type='Bearer', id_token=signed)
        monkeypatch.setattr(oidc, 'fetch_access_token', fetch)
        return client.get('/auth/callback', query_string={
            'state': state_override or params['state'][0], 'code': 'test-code'}, base_url=ORIGIN)
    yield app, sign_in
    close_app(app)


def test_signed_login_workspace_logout_and_cookie_replay(login_app):
    app, sign_in = login_app
    client = app.test_client()
    assert client.get('/workspace', base_url=ORIGIN).status_code == 302
    assert sign_in(client).status_code == 302
    page = client.get('/workspace', base_url=ORIGIN)
    assert page.status_code == 200 and b'Personal workspace' in page.data
    cookie = client.get_cookie('alma_authenticated', domain='alma.example.test')
    assert cookie.secure and cookie.http_only and cookie.same_site == 'Lax'
    with client.session_transaction(base_url=ORIGIN) as state:
        csrf, secret = state['auth_csrf'], state['login_secret']
        assert 'access_token' not in state and 'id_token' not in state
    assert client.post('/auth/logout', base_url=ORIGIN, data={'csrf': 'wrong'}).status_code == 400
    assert client.post('/auth/logout', base_url=ORIGIN, data={'csrf': csrf}).status_code == 302
    assert resolve_login(app.extensions['identity_engine'], secret) is None
    client.set_cookie('alma_authenticated', cookie.value, domain='alma.example.test')
    assert client.get('/workspace', base_url=ORIGIN).status_code == 302


@pytest.mark.parametrize('changes', [dict(iss='https://wrong.test'), dict(aud='other-client'),
                                     dict(nonce='wrong'), dict(exp=1)])
def test_signed_invalid_claims_are_rejected(login_app, changes):
    app, sign_in = login_app
    client = app.test_client()
    assert sign_in(client, changes=changes).status_code == 400
    assert client.get('/workspace', base_url=ORIGIN).status_code == 302


def test_bad_signature_and_state_are_rejected(login_app):
    app, sign_in = login_app
    client = app.test_client()
    wrong = jwk.RSAKey.generate_key(parameters={'kid': 'test-key'})
    assert sign_in(client, signing_key=wrong).status_code == 400
    assert sign_in(client, state_override='forged-state').status_code == 400


def test_personal_identity_reuse_and_expiry(connection):
    expiry = datetime.now(timezone.utc)+timedelta(hours=1)
    first = create_login(connection, ISSUER, 'a', token_expires_at=expiry)
    second = create_login(connection, ISSUER, 'a', token_expires_at=expiry)
    other = create_login(connection, ISSUER, 'b', token_expires_at=expiry)
    assert resolve_login(connection, first) == resolve_login(connection, second)
    assert resolve_login(connection, first)['workspace_id'] != resolve_login(connection, other)['workspace_id']
    with transaction(connection) as session:
        assert session.scalar(select(func.count()).select_from(m.users)) == 2
        assert session.scalar(select(func.count()).select_from(m.workspaces)) == 2
        session.execute(m.auth_sessions.update().values(expires_at=datetime.now(timezone.utc)-timedelta(hours=1)))
    assert resolve_login(connection, first) is None
    revoke_login(connection, first)


def test_private_routes_deny_legacy_workflows(login_app):
    app, sign_in = login_app
    client = app.test_client()
    assert sign_in(client).status_code == 302
    for path in ['/reports', '/reports/known', '/batches/known', '/assessment-progress/known', '/proposed']:
        assert client.get(path, base_url=ORIGIN).status_code == 403
    for path in ['/runs/unknown', '/runs/unknown/visualization', '/runs/unknown/download/report',
                 '/runs/unknown/queue', '/runs/unknown/mosaic-visualization']:
        assert client.get(path, base_url=ORIGIN).status_code == 404
    assert client.post('/proposed', base_url=ORIGIN).status_code == 403
    assert client.get('/workspace', base_url='http://alma.example.test').status_code == 400


def test_auth_config_does_not_fall_back_to_random_key(connection, tmp_path):
    settings = auth_config(connection, tmp_path / 'artifacts')
    with pytest.raises(ValueError, match='AUTH_SESSION_SECRET'):
        create_app(settings | {'AUTH_SESSION_SECRET': ''})
    with pytest.raises(ValueError, match='HTTPS'):
        create_app(settings | {'OIDC_ISSUER': 'http://identity.example.test'})


def test_two_signed_in_users_cannot_read_each_others_report(login_app, assessment):
    from alma_duplicate.persistence.repositories import WorkspaceRepository
    from alma_duplicate.persistence.reports import publish_report
    from alma_duplicate.artifacts.local import LocalArtifactStore
    app, sign_in = login_app
    first, second = app.test_client(), app.test_client()
    assert sign_in(first).status_code == 302
    assert sign_in(second, changes={'sub': 'subject-b'}).status_code == 302
    engine = app.extensions['identity_engine']
    with first.session_transaction(base_url=ORIGIN) as state:
        identity = resolve_login(engine, state['login_secret'])
    workspace = identity['workspace_id']
    now = datetime.now(timezone.utc)
    with transaction(engine) as db:
        repo = WorkspaceRepository(db, workspace)
        submission = repo.create_submission(kind='SINGLE', settings={}, input_sha256='a'*64,
            sources=[dict(name='test', ra_deg=201.365, dec_deg=-43.019, original_input={})], purposes=['LINE'])
        job = repo.jobs_for_submission(submission)[0]['id']
        db.execute(m.jobs.update().where(m.jobs.c.id == job).values(state='RUNNING', attempt=1,
            lease_token='token', heartbeat_at=now, lease_expires_at=now+timedelta(hours=1)))
    run_id = publish_report(engine, LocalArtifactStore(app.config['ARTIFACT_ROOT']), workspace, job,
        attempt=1, lease_token='token', request_document=assessment[0], result=assessment[1], source_provenance={})
    with second.session_transaction(base_url=ORIGIN) as state:
        state['workspace_id'] = workspace  # Client-side workspace selection is not authority.
    for suffix in ['', '/visualization', '/download/report', '/download/request', '/download/inspection']:
        owned = first.get('/runs/'+run_id+suffix, base_url=ORIGIN)
        assert owned.status_code == 200
        owned.close()
        assert second.get('/runs/'+run_id+suffix, base_url=ORIGIN).status_code == 404


def test_callback_state_is_single_use(login_app):
    app, sign_in = login_app
    client = app.test_client()
    response = sign_in(client)
    assert response.status_code == 302
    assert client.get(response.request.url, base_url=ORIGIN).status_code == 400


def test_signed_out_page_does_not_restart_oidc(login_app):
    app, sign_in = login_app
    client = app.test_client()
    assert sign_in(client).status_code == 302
    with client.session_transaction(base_url=ORIGIN) as state:
        csrf = state['auth_csrf']
    response = client.post('/auth/logout', data={'csrf': csrf}, base_url=ORIGIN, follow_redirects=True)
    assert response.status_code == 200 and b'<h1>Signed out</h1>' in response.data
    assert response.request.path == '/auth/signed-out'


def test_discovery_endpoint_validation_is_fail_closed(login_app, monkeypatch):
    app, _ = login_app
    client = app.test_client()
    monkeypatch.setattr(app.extensions['oidc_client'], 'load_server_metadata', lambda: {
        'issuer': ISSUER, 'authorization_endpoint': 'http://unsafe.test/authorize',
        'token_endpoint': ISSUER+'/token', 'jwks_uri': ISSUER+'/jwks'})
    assert client.get('/auth/login', base_url=ORIGIN).status_code == 502
    assert client.get('/auth/callback', base_url=ORIGIN).status_code == 400
