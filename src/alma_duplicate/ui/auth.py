"""Explicit OIDC mode, default-deny routes and server-side workspace authorization."""
from datetime import datetime, timezone
from secrets import compare_digest, token_urlsafe
from urllib.parse import urlsplit
import weakref

from flask import abort, g, redirect, render_template, request, session, url_for
from authlib.integrations.flask_client import OAuth
from authlib.integrations.base_client.errors import OAuthError
from joserfc.errors import JoseError
from requests.exceptions import RequestException
from alma_duplicate.artifacts.local import LocalArtifactStore
from alma_duplicate.persistence.db import database_engine
from alma_duplicate.persistence.reports import SavedReport
from alma_duplicate.persistence.repositories import RecordUnavailable
from alma_duplicate.ui.workspaces import create_login, resolve_login, revoke_login


def _https(value, name):
    if not isinstance(value, str):
        raise ValueError(f'{name} must be an HTTPS URL')
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError(f'{name} must be an HTTPS URL')
    return value


def register_auth(app):
    issuer = _https(app.config.get('OIDC_ISSUER'), 'OIDC_ISSUER')
    if urlsplit(issuer).query:
        raise ValueError('OIDC_ISSUER must not contain a query')
    metadata_url = _https(app.config.get('OIDC_METADATA_URL') or issuer.rstrip('/') + '/.well-known/openid-configuration',
                          'OIDC_METADATA_URL')
    callback = _https(app.config.get('OIDC_REDIRECT_URI'), 'OIDC_REDIRECT_URI')
    if urlsplit(callback).path != '/auth/callback' or urlsplit(callback).query:
        raise ValueError('OIDC_REDIRECT_URI must point to /auth/callback without query parameters')
    for key in ['OIDC_CLIENT_ID', 'OIDC_CLIENT_SECRET', 'AUTH_SESSION_SECRET', 'ARTIFACT_ROOT']:
        if not isinstance(app.config.get(key), str) or not app.config[key].strip():
            raise ValueError(f'{key} is required in OIDC mode')
    if len(app.config['AUTH_SESSION_SECRET']) < 32:
        raise ValueError('AUTH_SESSION_SECRET must contain at least 32 characters')
    app.config.update(SECRET_KEY=app.config['AUTH_SESSION_SECRET'], SESSION_COOKIE_SECURE=True,
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax',
                      SESSION_COOKIE_NAME='alma_authenticated', SESSION_COOKIE_PATH='/', SESSION_COOKIE_DOMAIN=None,
                      TRUSTED_HOSTS=[urlsplit(callback).hostname])
    engine = app.config.get('AUTH_TEST_ENGINE') if app.testing else None
    if engine is None:
        if not isinstance(app.config.get('DATABASE_URL'), str) or not app.config['DATABASE_URL']:
            raise ValueError('DATABASE_URL is required in OIDC mode')
        engine = database_engine(app.config['DATABASE_URL'])
        weakref.finalize(app, engine.dispose)
    store = LocalArtifactStore(app.config['ARTIFACT_ROOT'])
    oauth = OAuth(app)
    client = oauth.register('identity', client_id=app.config['OIDC_CLIENT_ID'],
        client_secret=app.config['OIDC_CLIENT_SECRET'], server_metadata_url=metadata_url,
        client_kwargs={'scope': 'openid', 'code_challenge_method': 'S256', 'default_timeout': 10},
        authorize_params={'response_type': 'code'})
    app.extensions['oidc_client'] = client
    app.extensions['identity_engine'] = engine

    def saved(report_id):
        identity = getattr(g, 'identity', None)
        if identity is None:
            raise RecordUnavailable('Report unavailable')
        return SavedReport(engine, store, identity['workspace_id'], report_id)
    app.extensions['persistent_report_resolver'] = saved

    @app.before_request
    def authorize_request():
        if not request.is_secure:
            abort(400, description='HTTPS is required in authenticated mode')
        # No trusting arbitrary forwarded headers or caller-supplied workspace IDs.
        if request.endpoint in {'static', 'auth_login', 'auth_callback', 'auth_signed_out', 'healthz'}:
            return None
        g.identity = resolve_login(engine, session.get('login_secret'))
        if g.identity is None:
            session.clear()
            if request.method == 'GET':
                return redirect(url_for('auth_login'))
            abort(401)
        if request.endpoint in {'auth_workspace', 'auth_logout'}:
            return None
        if request.endpoint == 'index':
            return redirect(url_for('auth_workspace'))
        if request.endpoint in {'run_view', 'run_queue_view', 'run_visualization', 'mosaic_visualization', 'run_download'}:
            try:
                saved(request.view_args['report_id'])
            except RecordUnavailable:
                abort(404)
            return None
        # Submission/Batch/progress/static report routes are still process-local.
        # They will be enabled only after authenticated persistent Web integration.
        abort(403, description='This workflow is not enabled for authenticated workspaces yet')

    def verified_provider_metadata():
        metadata = client.load_server_metadata()
        if metadata.get('issuer') != issuer:
            raise ValueError('Identity provider configuration mismatch')
        for key in ['authorization_endpoint', 'token_endpoint', 'jwks_uri']:
            _https(metadata.get(key), key)

    @app.get('/auth/login')
    def auth_login():
        try:
            verified_provider_metadata()
            return client.authorize_redirect(callback)
        except (RequestException, ValueError):
            abort(502, description='Identity provider unavailable or misconfigured')

    @app.get('/auth/callback')
    def auth_callback():
        try:
            verified_provider_metadata()
            token = client.authorize_access_token(claims_options={
                'iss': {'essential': True, 'value': issuer},
                'sub': {'essential': True}, 'exp': {'essential': True}}, leeway=0)
            claims = token.get('userinfo')
            if not token.get('id_token') or not claims or claims.get('iss') != issuer:
                raise ValueError('Verified identity required')
            expiration = datetime.fromtimestamp(claims['exp'], timezone.utc)
            secret = create_login(engine, issuer, claims['sub'], token_expires_at=expiration)
        except RequestException:
            abort(502, description='Identity provider unavailable')
        except (OAuthError, JoseError, ValueError, KeyError, TypeError, OverflowError):
            # Provider errors may contain credentials or token data; do not echo them.
            abort(400, description='Sign-in could not be verified')
        revoke_login(engine, session.get('login_secret'))
        session.clear()
        session.update(login_secret=secret, auth_csrf=token_urlsafe(32))
        return redirect(url_for('auth_workspace'))

    @app.get('/workspace')
    def auth_workspace():
        return render_template('workspace.html', workspace=g.identity, csrf=session['auth_csrf'])

    @app.post('/auth/logout')
    def auth_logout():
        csrf = session.get('auth_csrf')
        if not isinstance(csrf, str) or not compare_digest(request.form.get('csrf', '').encode('utf-8'), csrf.encode('utf-8')):
            abort(400)
        revoke_login(engine, session.get('login_secret'))
        session.clear()
        return redirect(url_for('auth_signed_out'))

    @app.get('/auth/signed-out')
    def auth_signed_out():
        return render_template('signed_out.html')
