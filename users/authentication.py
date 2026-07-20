import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import authentication, exceptions
import logging
import requests

logger = logging.getLogger(__name__)


class ClerkAuthentication(authentication.BaseAuthentication):
    _jwks_client = None

    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            raise exceptions.AuthenticationFailed('Invalid authorization header format. Expected "Bearer <token>".')

        token = parts[1]

        # Try to decode the token using JWKS (preferred) or PEM
        payload = self._decode_jwt(token)
        if payload is None:
            raise exceptions.AuthenticationFailed(
                'Unable to verify token. Check Clerk JWT configuration.'
            )

        sub = payload.get('sub')
        if not sub:
            raise exceptions.AuthenticationFailed('Token is missing "sub" claim.')

        # Extract user info from JWT claims (may be empty if Clerk JWT template not customized)
        email = payload.get('email') or payload.get('email_address') or ''
        first_name = payload.get('first_name', '')
        last_name = payload.get('last_name', '')
        full_name = payload.get('name') or payload.get('full_name') or f"{first_name} {last_name}".strip()
        avatar_url = payload.get('picture') or payload.get('image_url') or payload.get('avatar_url') or ''

        User = get_user_model()
        try:
            user = User.objects.filter(clerk_id=sub).first()

            # If user not found and email is missing from JWT, attempt to fetch from Clerk API
            if not user and not email:
                email, full_name, avatar_url = self._fetch_user_from_clerk_api(sub)

            # Lazy bind: existing user with this email but no clerk_id
            if not user and email:
                user = User.objects.filter(email=email).first()
                if user:
                    user.clerk_id = sub
                    user.save(update_fields=['clerk_id'])

            # Create new user if still not found
            if not user:
                if not email:
                    raise exceptions.AuthenticationFailed(
                        'User not found and email could not be retrieved from Clerk. '
                        'Configure a custom JWT template in Clerk Dashboard to include email, '
                        'or ensure CLERK_SECRET_KEY env var is set correctly.'
                    )
                user = User.objects.create_user(
                    email=email,
                    clerk_id=sub,
                    full_name=full_name,
                    avatar_url=avatar_url,
                )
            else:
                # Update existing user fields if needed
                update_fields = []
                if email and user.email != email:
                    if not User.objects.filter(email=email).exclude(id=user.id).exists():
                        user.email = email
                        update_fields.append('email')

                if full_name and user.full_name != full_name:
                    user.full_name = full_name
                    update_fields.append('full_name')

                if avatar_url and user.avatar_url != avatar_url:
                    user.avatar_url = avatar_url
                    update_fields.append('avatar_url')

                if update_fields:
                    user.save(update_fields=update_fields)

        except exceptions.AuthenticationFailed:
            raise
        except Exception as e:
            logger.exception(f"Error syncing user during authentication: {e}")
            raise exceptions.AuthenticationFailed(f'Error syncing user: {str(e)}')

        if not user.status_active:
            raise exceptions.AuthenticationFailed('User account is deactivated.')

        return (user, None)

    def authenticate_header(self, request):
        return 'Bearer'

    def _decode_jwt(self, token):
        """Decode and verify a Clerk JWT using JWKS (preferred) or PEM fallback."""
        # Strategy 1: JWKS URL (most robust)
        jwks_url = self._get_jwks_url()
        if jwks_url:
            try:
                if self._jwks_client is None:
                    self._jwks_client = jwt.PyJWKClient(jwks_url, cache_keys=True)
                signing_key = self._jwks_client.get_signing_key_from_jwt(token)
                payload = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=['RS256'],
                    options={'verify_aud': False}
                )
                return payload
            except Exception as e:
                logger.warning(f"JWKS verification failed, trying PEM fallback: {e}")

        # Strategy 2: PEM public key
        public_key = getattr(settings, 'CLERK_JWT_PEM_PUBLIC_KEY', None)
        if public_key:
            try:
                payload = jwt.decode(
                    token,
                    public_key,
                    algorithms=['RS256'],
                    options={'verify_aud': False}
                )
                return payload
            except jwt.ExpiredSignatureError:
                raise exceptions.AuthenticationFailed('Token has expired.')
            except jwt.InvalidTokenError as e:
                logger.warning(f"PEM verification failed: {e}")
                # Don't raise here — let caller decide final error

        return None

    def _get_jwks_url(self):
        """Derive the JWKS URL from settings or Clerk instance."""
        jwks_url = getattr(settings, 'CLERK_JWKS_URL', '')
        if jwks_url:
            return jwks_url

        # Derive from the Clerk publishable key (it contains the Clerk instance origin)
        publishable_key = getattr(settings, 'CLERK_PUBLISHABLE_KEY', '')
        if publishable_key:
            # Clerk publishable keys are prefixed with pk_test_ or pk_live_
            # The instance URL is embedded in the key's lookup
            # Use the well-known Clerk accounts URL pattern
            try:
                # Extract Clerk instance from the publishable key suffix
                # e.g., pk_test_Ym9sZC1seW54LTM3LmNsZXJrLmFjY291bnRzLmRldiQ
                # maps to https://bold-lynx-37.clerk.accounts.dev
                import base64
                key_data = publishable_key
                if key_data.startswith('pk_test_'):
                    key_data = key_data[8:]
                elif key_data.startswith('pk_live_'):
                    key_data = key_data[8:]
                try:
                    # Try to decode the base64-encoded instance URL
                    decoded = base64.b64decode(key_data).decode('utf-8')
                    return f"https://{decoded}/.well-known/jwks.json"
                except Exception:
                    pass
            except Exception:
                pass

        return ''

    def _fetch_user_from_clerk_api(self, clerk_user_id):
        """Fetch user details from Clerk API as fallback when JWT lacks user claims."""
        clerk_secret = getattr(settings, 'CLERK_SECRET_KEY', None)
        if not clerk_secret:
            logger.error("CLERK_SECRET_KEY not set — cannot fetch user from Clerk API")
            return '', '', ''

        try:
            response = requests.get(
                f"https://api.clerk.com/v1/users/{clerk_user_id}",
                headers={"Authorization": f"Bearer {clerk_secret}"},
                timeout=10,
            )
            if response.status_code == 200:
                clerk_user = response.json()
                email_addresses = clerk_user.get('email_addresses', [])
                email = ''
                if email_addresses:
                    primary_id = clerk_user.get('primary_email_address_id')
                    for ea in email_addresses:
                        if ea.get('id') == primary_id:
                            email = ea.get('email_address', '')
                            break
                    if not email:
                        email = email_addresses[0].get('email_address', '')

                first_name = clerk_user.get('first_name', '')
                last_name = clerk_user.get('last_name', '')
                full_name = f"{first_name} {last_name}".strip()
                avatar_url = clerk_user.get('profile_image_url', '')

                logger.info(f"Fetched user from Clerk API: {email}")
                return email, full_name, avatar_url
            else:
                logger.error(
                    f"Clerk API returned {response.status_code} for user {clerk_user_id}: "
                    f"{response.text[:200]}"
                )
        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching user {clerk_user_id} from Clerk API")
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error fetching user {clerk_user_id} from Clerk API")
        except Exception as e:
            logger.error(f"Failed to fetch user from Clerk API: {e}")

        return '', '', ''
