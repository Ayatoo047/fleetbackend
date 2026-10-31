from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core import validation as v
from core.exceptions import Invalid
from core.permissions import IsAdminRole
from core.throttling import LoginThrottle
from core.utils import iso

from .models import AuthToken, User


def user_to_json(user):
    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "createdAt": iso(user.created_at),
        "lastLoginAt": iso(user.last_login),
    }


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        email, password = data.get("email"), data.get("password")
        if not isinstance(email, str) or not isinstance(password, str) or not email or not password:
            return Response({"detail": "Email and password are required."}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, email=email.strip().lower(), password=password)
        if user is None:
            return Response({"detail": "Wrong email or password."}, status=status.HTTP_401_UNAUTHORIZED)

        token = AuthToken.issue(user)
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])
        return Response(
            {
                "token": token,
                "expiresIn": settings.AUTH_TOKEN_TTL_SECONDS,
                "user": {"id": str(user.id), "email": user.email, "name": user.name, "role": user.role},
            }
        )


def validate_user(data, instance=None):
    """Body of `POST /users` and `PATCH /users/:id`. On PATCH, missing fields keep their value."""
    check = v.Checker(data)

    def field(key, current):
        value = check.get(key)
        return current if value is v.MISSING and instance is not None else value

    cleaned = {
        "name": check.run("name", v.text, field("name", instance and instance.name), 100),
        "email": check.run("email", v.email, field("email", instance and instance.email)),
        "role": check.run("role", v.choice, field("role", instance and instance.role), User.Role.values),
    }
    password = check.get("password")
    if password in (v.MISSING, None, "") and instance is None:
        check.fail("password", "required")
    elif password not in (v.MISSING, None, ""):
        if not isinstance(password, str) or len(password) > 200:
            check.fail("password", "invalid")
        elif len(password) < 10:
            check.fail("password", "tooShort")
        else:
            cleaned["password"] = password

    if cleaned["email"]:
        cleaned["email"] = cleaned["email"].lower()
        taken = User.objects.filter(email__iexact=cleaned["email"])
        if instance is not None:
            taken = taken.exclude(pk=instance.pk)
        if taken.exists():
            check.fail("email", "taken")
    check.raise_if_invalid()
    return cleaned


class UserCollectionView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        return Response([user_to_json(user) for user in User.objects.all()])

    def post(self, request):
        cleaned = validate_user(request.data)
        user = User.objects.create_user(
            email=cleaned["email"], password=cleaned["password"], name=cleaned["name"], role=cleaned["role"]
        )
        return Response(user_to_json(user), status=status.HTTP_201_CREATED)


class UserDetailView(APIView):
    permission_classes = [IsAdminRole]

    def get_object(self, pk):
        user = User.objects.filter(pk=pk).first()
        if user is None:
            raise NotFound()
        return user

    def get(self, request, pk):
        return Response(user_to_json(self.get_object(pk)))

    def patch(self, request, pk):
        user = self.get_object(pk)
        cleaned = validate_user(request.data, instance=user)
        if user == request.user and cleaned["role"] != User.Role.ADMIN:
            raise Invalid({"role": "ownRole"})
        with transaction.atomic():
            user.name, user.email, user.role = cleaned["name"], cleaned["email"], cleaned["role"]
            if "password" in cleaned:
                user.set_password(cleaned["password"])
                # Sign the user out everywhere else, but keep the current admin session.
                user.auth_tokens.exclude(pk=getattr(request.auth, "pk", None)).delete()
            user.save()
        return Response(user_to_json(user))

    def delete(self, request, pk):
        user = self.get_object(pk)
        if user == request.user:
            raise Invalid({"id": "self"})
        user.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
