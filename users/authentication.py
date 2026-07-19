import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import authentication, exceptions
import logging
import requests

logger = logging.getLogger(__name__)

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
            user = User.objects.filter(clerk_id=sub).first()
            
            # If user not found and email is missing from JWT, attempt to fetch from Clerk API
            if not user and not email:
                clerk_secret = getattr(settings, 'CLERK_SECRET_KEY', None)
                if clerk_secret:
                    try:
                        response = requests.get(
                            f"https://api.clerk.com/v1/users/{sub}",
                            headers={"Authorization": f"Bearer {clerk_secret}"}
                        )
                        if response.status_code == 200:
                            clerk_user = response.json()
                            email_addresses = clerk_user.get('email_addresses', [])
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
                    except Exception as e:
                        logger.error(f"Failed to fetch user from Clerk API: {e}")

            if not user and email:
                user = User.objects.filter(email=email).first()
                if user:
                    user.clerk_id = sub
                    user.save()

            if not user:
                if not email:
                    raise exceptions.AuthenticationFailed('User not found and email could not be retrieved.')
                user = User.objects.create_user(
                    email=email,
                    clerk_id=sub,
                    full_name=full_name,
                    avatar_url=avatar_url,
                )
            else:
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
                    
        except Exception as e:
            raise exceptions.AuthenticationFailed(f'Error syncing user: {str(e)}')

        if not user.status_active:
            raise exceptions.AuthenticationFailed('User account is deactivated.')

        return (user, None)

    def authenticate_header(self, request):
        return 'Bearer'
