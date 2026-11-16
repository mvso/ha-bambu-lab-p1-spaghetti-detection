import hmac
import os
from functools import wraps

from flask import request, Response

# The value that used to be shipped as the default secret. It is public, so it
# protects nothing and is treated the same as having no secret at all.
PUBLIC_DEFAULT_TOKEN = "obico_api_secret"

ML_API_TOKEN = os.environ.get("ML_API_TOKEN", "").strip()
TOKEN_IS_USABLE = bool(ML_API_TOKEN) and ML_API_TOKEN != PUBLIC_DEFAULT_TOKEN

if not TOKEN_IS_USABLE:
    print(
        "ERROR: ML_API_TOKEN is missing or still set to the public default "
        f"'{PUBLIC_DEFAULT_TOKEN}'. All detection requests are rejected until "
        "a secret of your own is configured.",
        flush=True,
    )


def token_required(f):
    @wraps(f)
    def check_authorization(*args, **kwargs):
        if not TOKEN_IS_USABLE:
            return Response("ML API token is not configured on the server", status=503)

        expected = "Bearer {}".format(ML_API_TOKEN).encode()
        provided = request.headers.get("Authorization", "").encode()
        if hmac.compare_digest(provided, expected):
            return f(*args, **kwargs)
        return Response(status=401)

    return check_authorization
