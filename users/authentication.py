import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import authentication, exceptions

class ClerkAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            raise exceptions.AuthenticationFailed('Invalid authorization header format. Expected "Bearer <token>".')

        token = parts[1]

        public_key = getattr(settings, 'CLERK_JWT_PEM_PUBLIC_KEY', None)
        if not public_key:
            raise exceptions.AuthenticationFailed('Clerk public key is not configured.')

        try:
            # Decode the token using RS256 algorithm.
            # We disable audience verification since it may not be configured.
            payload = jwt.decode(
                token,
                public_key,
                algorithms=['RS256'],
                options={'verify_aud': False}
            )
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired.')
        except jwt.InvalidTokenError as e:
            raise exceptions.AuthenticationFailed(f'Invalid token: {str(e)}')

        sub = payload.get('sub')
        if not sub:
            raise exceptions.AuthenticationFailed('Token is missing "sub" claim.')

        # Extract standard claims
        email = payload.get('email') or payload.get('email_address') or ''
        
        # Concat first/last name if full name is not directly available
        first_name = payload.get('first_name', '')
        last_name = payload.get('last_name', '')
        full_name = payload.get('name') or payload.get('full_name') or f"{first_name} {last_name}".strip()
        
        avatar_url = payload.get('picture') or payload.get('image_url') or payload.get('avatar_url') or ''

        User = get_user_model()
        try:
            user, created = User.objects.get_or_create(
                clerk_id=sub,
                defaults={
                    'email': email,
                    'full_name': full_name,
                    'avatar_url': avatar_url,
                }
            )
            if not created:
                user.email = email
                user.full_name = full_name
                user.avatar_url = avatar_url
                user.save()
        except Exception as e:
            raise exceptions.AuthenticationFailed(f'Error syncing user: {str(e)}')

        if not user.status_active:
            raise exceptions.AuthenticationFailed('User account is deactivated.')

        return (user, None)

    def authenticate_header(self, request):
        return 'Bearer'
