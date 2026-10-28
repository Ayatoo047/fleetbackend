from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class Invalid(APIException):
    """A 422 with `{ "errors": { "<field>": "<code>" } }`, the shape the frontend reads."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY

    def __init__(self, errors):
        super().__init__("Some fields are invalid.")
        self.errors = errors


def exception_handler(exc, context):
    if isinstance(exc, Invalid):
        return Response({"errors": exc.errors}, status=exc.status_code)
    return drf_exception_handler(exc, context)
