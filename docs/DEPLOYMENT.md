# BA3073 deployment and evidence guide

The assignment has three stages: local Docker, local-image delivery through ACR
to ECS, and a domain with HTTPS plus independent reverse-proxy authentication.
Run the stages in order and retain real evidence. A template is not a passed test.

## Local launch

1. Start Docker Desktop.
2. Configure the model using the in-app editor or the ignored file
   `data/model-secrets.env` containing `MODEL_API_KEY=...` (mode `600`).
3. Optional provider overrides go in ignored `.env`. For DeepSeek, use
   `MODEL_BASE_URL=https://api.deepseek.com`, `MODEL_NAME=deepseek-flash`, and
   `MODEL_CONTEXT_WINDOW=131072` (a conservative application budgeting limit).
   The provider and model are user configuration; tracked Qwen defaults remain.
4. Run:

   ```sh
   docker compose -p ai-learning-assistant up --build -d --wait
   curl -fsS http://127.0.0.1:14242/health
   bash scripts/check-local-ui.sh --open
   ```

5. Sign in with a BNBU account, generate an artifact, and capture the successful
   UI with the browser address bar visible. Save the screenshot outside the
   source archive. Check HTML/PDF preview and download, not just HTTP status.

Local port 14242 binds to loopback by default. Data and generated files are bind
mounted at `data/` and `workspace/`; replacing the container preserves them.

## Deliver a local image through ACR

Create a private ACR personal-edition namespace/repository in the Alibaba Cloud
console. Use the registry host shown by that console; new personal instances use
instance-specific hosts, so do not guess a legacy registry hostname. Complete
registry password setup yourself and enter the password only at the login prompt.

```sh
docker login --username YOUR_ACR_USERNAME YOUR_ACR_REGISTRY_HOST
docker buildx build --platform linux/amd64 --load \
  -t YOUR_ACR_REGISTRY_HOST/YOUR_NAMESPACE/ai-learning-assistant:ba3073 .
docker image inspect YOUR_ACR_REGISTRY_HOST/YOUR_NAMESPACE/ai-learning-assistant:ba3073 \
  --format '{{.Os}}/{{.Architecture}}'
docker push YOUR_ACR_REGISTRY_HOST/YOUR_NAMESPACE/ai-learning-assistant:ba3073
```

The example targets an x86-64 ECS. Use `linux/arm64` for an ARM ECS instead.
Record the push digest and image tag without recording registry credentials.
Test the locally built cloud image before uploading it.

## ECS deployment and Task 2 evidence

Use a new directory such as `/opt/ai-learning-assistant`; preserve existing
applications and Nginx sites. Copy `compose.ecs.yml` and the check scripts there.
On ECS, create a private `.env` with your actual values:

```text
AILA_IMAGE=YOUR_ACR_REGISTRY_HOST/YOUR_NAMESPACE/ai-learning-assistant:ba3073
AILA_BIND_ADDRESS=0.0.0.0
MODEL_BASE_URL=https://api.deepseek.com
MODEL_NAME=deepseek-flash
MODEL_CONTEXT_WINDOW=131072
```

Place the API key in ECS `data/model-secrets.env` with mode `600`. Do not commit,
paste into command history, or include it in screenshots. Login to ACR on ECS:

```sh
docker login --username YOUR_ACR_USERNAME YOUR_ACR_REGISTRY_HOST
docker compose -p ai-learning-assistant -f compose.ecs.yml pull
docker compose -p ai-learning-assistant -f compose.ecs.yml up -d --wait
```

Allow inbound TCP 14242 **only from your current public IP /32** in the ECS
security group. Visit `http://ECS_PUBLIC_IP:14242/ui/` from your own browser,
capture the working UI with its address bar, then run on the ECS itself:

```sh
bash scripts/check-ecs-public-ui.sh ECS_PUBLIC_IP
```

Keep the resulting `ecs-docker-check.txt` with the submission. A local container
check must not be represented as an ECS check. An ECS curl check does not replace
the external browser screenshot.

## Domain, HTTPS, and independent access control

Use a domain/subdomain you control and add an A record for the ECS public IPv4.
For mainland China hosting, resolve the applicable ICP filing requirements before
assuming a newly registered domain will work. DNS and hosting prerequisites can
take longer than the container deployment.

1. Permit TCP 80 and 443 in the security group. Keep existing application rules.
2. Create a separate Nginx site from `docs/deployment/nginx-site.conf.template`,
   replacing `__DOMAIN__`. Set the reverse proxy to `127.0.0.1:14242`.
3. Create the site's Basic Auth account interactively, keeping the password out
   of screenshots and source:

   ```sh
   sudo apt update
   sudo apt install nginx apache2-utils certbot python3-certbot-nginx
   sudo htpasswd -c /etc/nginx/ai-learning-assistant.htpasswd reportreader
   sudo chown root:www-data /etc/nginx/ai-learning-assistant.htpasswd
   sudo chmod 640 /etc/nginx/ai-learning-assistant.htpasswd
   ```

   Use `-c` only for this new dedicated file; never overwrite an existing
   password file. Enable the site, then run `nginx -t` before reloading.
4. Verify DNS and the initial HTTP site, then issue the certificate:

   ```sh
   sudo certbot --nginx -d YOUR_DOMAIN
   sudo certbot renew --dry-run
   ```

5. Change `AILA_BIND_ADDRESS` to `127.0.0.1`, recreate the ECS container, and
   remove the public security-group rule for 14242. Confirm the Nginx site still
   reaches the app and that public direct-port access no longer succeeds.
6. Check that HTTPS without Basic Auth returns `401`, with a valid certificate,
   and that access succeeds after Basic Auth and then the app's own BNBU login.
   Capture the successful page with the HTTPS domain visible in the address bar.
   Do not disable TLS verification to manufacture a successful result.

Basic Auth is separate from BNBU login. Preserve it on all proxied API and UI
routes; otherwise users could bypass the access-control screen through the API.

## Report and submission

Use a task that contains `BA3073` to activate the revised instructions in
`backend/pipelines/essay_html.py`. Supply actual commands/results, screenshot IDs,
URLs, image digest, deployment dates and source references. Missing evidence is
labelled `NOT VERIFIED`; do not substitute fabricated results or UI mockups.

Generate the final report through the deployed application's essay pipeline.
Verify the rendered PDF is at most 20 pages and that all evidence figures and
address bars are readable. Describe prompt improvements and distinguish completed
steps from proposed improvements. Retain the genuine generation run/manifest
locally; they are not part of the source repository.

Submit the report, your own complete source repository URL, `local-ui-check.txt`,
and `ecs-docker-check.txt`. Keep keys/passwords, `.env*`, `data/`, `workspace/`,
dependencies and runtime directories out of the source archive and repository.

## References checked 2026-10-21

- [Assignment README](https://github.com/bnbu-busa-projects/AI_Learning_Assistant)
- [DeepSeek API format and model names](https://api-docs.deepseek.com/)
- [Alibaba ACR personal-edition push/pull](https://help.aliyun.com/zh/acr/user-guide/use-a-container-registry-personal-edition-instance-to-push-and-pull-images)

The OpenAI Python dependency is bounded to major version 1, matching the supplied
SDK interface and the development HTTPX constraint. This avoids lengthy resolver
backtracking through incompatible later major versions during Docker builds.
The runtime installs Chromium's headless shell, which is the executable used by
the supplied Playwright PDF converter. The unused interactive Chromium download
is omitted. Optional non-secret build arguments `PIP_INDEX_URL` and
`PLAYWRIGHT_DOWNLOAD_HOST` allow an accessible package mirror or official
Playwright CDN to be selected on slow networks; defaults retain the upstream
package index and Playwright's own download selection.
