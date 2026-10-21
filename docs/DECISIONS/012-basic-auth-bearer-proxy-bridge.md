# 012: Keep proxy Basic Auth separate from application bearer transport

Status: Accepted for the BA3073 deployment
Date: 2026-10-21

The assignment requires an independent reverse-proxy login in addition to BNBU
application login. Both HTTP Basic Auth and the existing application client use
`Authorization`. Sending a bearer token in that header prevents Nginx Basic Auth
from authenticating the same request. Exempting API routes would expose the paid
model and artifact APIs, so it does not meet the deployment requirement.

Nginx injects an opt-in meta tag only into `/ui/` HTML. In that deployment the
frontend sends its opaque bearer token as `X-App-Authorization`, leaving the
browser's `Authorization` header available for its cached Basic Auth credentials.
After checking Basic Auth on every UI and API request, Nginx replaces the
upstream `Authorization` header with the application bearer header. It does not
forward its own Basic Auth credentials to FastAPI.

The backend's `Authorization: Bearer` API, token validation, user roles, password
storage and local/Electron clients are unchanged. Direct UI access has no meta
tag and continues to use the original header. The frontend accepts only the
fixed optional header name, rather than arbitrary names from page content.

Validation covers local and proxy header selection and authenticated artifact
downloads. Deployment acceptance must additionally check that a valid app token
without Basic Auth is rejected, that invalid app tokens remain rejected after
Basic Auth, and that both valid credentials permit generation and downloads.
