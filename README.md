# FleetFlow Service – backend API

Django REST API for the [FleetFlow Service website](https://github.com/TunarshBee/fleetflowservice) (Next.js). It implements the contract in the frontend's [`API.md`](https://github.com/TunarshBee/fleetflowservice/blob/main/API.md): bookings, contact messages, services, rental fleet, news articles, admin users and image uploads.

Built with Django 5.2 LTS and Django REST Framework. It uses PostgreSQL in production and SQLite for local development.

## Getting started

Requirements: Python 3.12+.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # DEBUG=true: SQLite, emails printed to the console
python manage.py migrate
python manage.py seed_content      # the site's starting services, rental cars and article
python manage.py createsuperuser   # your admin panel login (role "admin")
python manage.py runserver
```

The API is now at `http://localhost:8000/v1`. Point the frontend at it in the frontend's `.env`:

```bash
API_MOCK=false
API_BASE_URL=http://localhost:8000/v1
API_KEY=<the same value as FRONTEND_API_KEY here>
```

Then sign in at `http://localhost:3000/admin` with the account you created.

To run the API with PostgreSQL in Docker instead: `docker compose up`, then `docker compose exec api python manage.py seed_content` and `docker compose exec api python manage.py createsuperuser`.

## Tests

```bash
python manage.py test
```

The tests in `tests/test_api.py` call every endpoint and check the status codes, response shapes and error codes the frontend relies on.

## How it fits together

```
Browser ──► Next.js server (Vercel) ──► this API ──► PostgreSQL
                  │  Bearer token for admin calls
                  │  X-Api-Key + X-Visitor-Ip on public form posts
```

- Only the Next.js server calls the API, so there is no CORS configuration.
- **Admin sign-in**: `POST /v1/auth/login` returns a random token that is valid for 8 hours (`AUTH_TOKEN_TTL_SECONDS`). Only its SHA-256 hash is stored. The frontend keeps the token in an httpOnly cookie and sends it as `Authorization: Bearer …`.
- **Roles**: `staff` can manage bookings, messages and content; `admin` can also manage users. A staff token on `/users` gets `403`. Admins can't delete themselves or remove their own admin role.
- **Rate limits**: the booking form, the contact form and login are limited per visitor (`THROTTLE_*`). Because all requests come from the frontend server, the frontend forwards the visitor's IP in `X-Visitor-Ip`. The API only trusts it when the request also has the shared secret in `X-Api-Key` (`FRONTEND_API_KEY`). Requests with an admin token, such as phone bookings entered by staff, are never limited.
- **Validation** mirrors the frontend's Zod schemas and returns `422` with `{ "errors": { "pickup.city": "required", … } }`, using the codes listed in `API.md`. The website can't book a time in the past, but staff can, to log rides after the fact.
- **Emails**: a website booking sends a notification to `STAFF_NOTIFICATION_EMAILS` and a confirmation to the customer in the language they booked in (Polish or English). Contact-form messages notify staff. Bookings entered by staff send no emails. A failed email is logged, and the booking is still saved.
- **Rich text** (service descriptions, article bodies) is sanitised again on save, allowing only the tags the admin editor produces.
- **Uploads**: images (JPEG, PNG, WebP, AVIF, GIF, up to 3.5 MB) are checked by their content, not their file name, and stored under random names. They are saved on local disk and served at `/media/…`, or in S3-compatible storage if `S3_BUCKET` is set.
- **Django admin** at `/django-admin/` gives superusers direct access to all data. Day-to-day work happens in the website's own admin panel.

## Project layout

```
config/          settings, URLs (everything under /v1/), WSGI
core/            token authentication, permissions, rate limits, validation helpers, 422 errors
accounts/        admin users, sign-in tokens, /auth/login and /users
bookings/        bookings and contact messages, their validation and emails
content/         services, rental fleet, articles, uploads, seed_content command
seed/content.json  starting content, copied from the frontend's src/content/seed.ts
tests/           API contract tests
```

## Endpoints

All paths are under `/v1`. See the frontend's `API.md` for request and response bodies.

| Endpoint | Auth |
| --- | --- |
| `GET /health` | – |
| `POST /auth/login` | – |
| `POST /bookings` | – (or staff token: no rate limit, past dates allowed, no emails) |
| `GET /bookings`, `GET /bookings/stats`, `GET/PATCH/DELETE /bookings/:id` | staff |
| `POST /contact-messages` | – |
| `GET /contact-messages`, `PATCH/DELETE /contact-messages/:id` | staff |
| `GET /services`, `GET /fleet`, `GET /articles`, `GET /articles/by-slug/:slug` | – (published only) |
| the same lists with `?includeUnpublished=true`, `GET/PUT/DELETE /…/:id`, `POST` | staff |
| `POST /uploads` | staff |
| `GET/POST /users`, `GET/PATCH/DELETE /users/:id` | admin |

## Deployment

Any host that runs a Docker image or a Python web app works (Railway, Render, Fly.io, a VPS). The `Dockerfile` runs migrations on start and serves the app with Gunicorn.

1. Create a PostgreSQL database and set `DATABASE_URL`.
2. Set `SECRET_KEY` (a long random string), `ALLOWED_HOSTS` (e.g. `api.fleetflowservice.com`), `CSRF_TRUSTED_ORIGINS` (e.g. `https://api.fleetflowservice.com`) and `PUBLIC_BASE_URL`.
3. Set `FRONTEND_API_KEY`, and the same value as `API_KEY` in the frontend's Vercel settings.
4. Set the email settings and `STAFF_NOTIFICATION_EMAILS`.
5. For uploaded images, use S3-compatible storage (`S3_BUCKET`, plus `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`), or give the container a persistent volume at `/app/media`. Most platforms wipe the container's disk on each deploy.
6. With more than one Gunicorn worker, set `REDIS_URL` so rate limits are counted across workers.
7. After the first deploy, run `python manage.py seed_content` and `python manage.py createsuperuser`.
8. In the frontend's Vercel settings, set `API_BASE_URL=https://<your API host>/v1` and `API_MOCK=false`, then redeploy it.

`GET /v1/health` returns `{"status": "ok"}` for uptime checks.

All settings are listed in [`.env.example`](.env.example).
