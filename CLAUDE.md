# ADKDEPLOY Project Memory

## Current objective

Deploy the ADK research assistant to Google Cloud Run in GCP project
`projectbea`, using either the ADK CLI or lower-level `gcloud` commands.

## Current project state

- Primary prototype: `test_app/`
- Agent entry point: `test_app/agent.py`
- Local ADK session data: `test_app/.adk/session.db`
- Local configuration: `test_app/.env`
- Container definition: `test_app/Dockerfile`
- A separate, more complete project also exists under `currency-agent/`; do not
  confuse it with the tagged `test_app` deployment target.

## Agent behavior

`test_app/agent.py` defines `root_agent` using:

- Google ADK `Agent`
- Model: `gemini-2.5-flash`
- Tool: `google_search`
- Agent name: `research_assistant`
- Purpose: answer questions with current web research and cite sources

## Local environment configuration

The current `test_app/.env` contains:

```env
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=projectbea
GOOGLE_CLOUD_LOCATION=us-east1
```

Do not commit API keys, credentials, or other secrets. Prefer Secret Manager
for production secrets.

## Tools confirmed available

- `agents-cli` is installed and available on PATH.
- `adk` is installed and available on PATH.
- `gcloud` is installed and available on PATH.
- The installed ADK CLI supports:
  `adk deploy cloud_run [OPTIONS] AGENT`.
- The installed ADK CLI supports passing additional Cloud Run/gcloud flags
  after `--`, for example `--allow-unauthenticated`.

## Recommended deployment workflow

From the repository root:

```powershell
cd C:\Users\marlon.v.barcelon\CLAUDEDIR\ADKDEPLOY
gcloud auth login
gcloud auth application-default login
gcloud config set project projectbea
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com --project=projectbea
adk deploy cloud_run --project=projectbea --region=us-east1 --service_name=test-app test_app
```

Use `--allow-unauthenticated` only when a public service is intentionally
needed:

```powershell
adk deploy cloud_run --project=projectbea --region=us-east1 --service_name=test-app test_app -- --allow-unauthenticated
```

The safer default is authenticated Cloud Run ingress.

## Alternative agents-cli workflow

`agents-cli` can add deployment scaffolding to a project:

```powershell
cd C:\Users\marlon.v.barcelon\CLAUDEDIR\ADKDEPLOY\test_app
agents-cli scaffold enhance . --deployment-target cloud_run
agents-cli deploy --deployment-target cloud_run --project projectbea --region us-east1 --dry-run
agents-cli deploy --deployment-target cloud_run --project projectbea --region us-east1
```

Review generated files before deploying. Do not run a deployment without
explicit approval.

## Manual gcloud workflow

The lower-level path requires:

1. A correct Dockerfile and startup command.
2. An Artifact Registry Docker repository.
3. A Cloud Build image build and push.
4. `gcloud run deploy` with the image, region, port, scaling, ingress, and
   runtime service account.
5. Vertex AI IAM permissions for the runtime service account.

Typical commands:

```powershell
gcloud artifacts repositories create adk-images --repository-format=docker --location=us-east1 --project=projectbea
gcloud builds submit . --tag us-east1-docker.pkg.dev/projectbea/adk-images/test-app:latest --project=projectbea
gcloud run deploy test-app --image us-east1-docker.pkg.dev/projectbea/adk-images/test-app:latest --region us-east1 --project projectbea --port 8080 --no-allow-unauthenticated
```

## Important Dockerfile caveat

The current `test_app/Dockerfile` contains:

```dockerfile
COPY . /app
CMD ["adk", "api_server", "--host", "0.0.0.0", "--port", "8080", "/app/test_app"]
```

This assumes the Docker build context is the repository root, where
`test_app/` is copied to `/app/test_app`. If the build context is
`test_app/` itself, the copied files land directly under `/app`, and the
startup path must be adjusted. Verify the build context and container startup
before using the manual `gcloud` path.

## Runtime and operations

- Cloud Run port: `8080`
- Suggested initial region: `us-east1`, matching `GOOGLE_CLOUD_LOCATION`
- Suggested initial sizing: 1 CPU, 4 GiB memory, concurrency 8
- Start with minimum instances 0 for cost efficiency unless cold-start
  avoidance is required.
- Test authenticated services with an identity token:

```powershell
$token = gcloud auth print-identity-token
agents-cli run --url https://YOUR-CLOUD-RUN-URL --mode adk -H "Authorization: Bearer $token" "What can you do?"
```

- Read logs with:

```powershell
gcloud run services logs read test-app --region us-east1 --project projectbea --limit 50
```

- Grant the Cloud Run runtime service account `roles/aiplatform.user` for
  Vertex AI access when required.
- Use Secret Manager rather than embedding credentials in `.env` or Docker
  build arguments.
- Roll back by shifting traffic to a previous Cloud Run revision.

## Working rules

- Treat `test_app` as the current deployment target unless explicitly changed.
- Prefer `adk deploy cloud_run` for the straightforward ADK deployment.
- Use `agents-cli` when deployment scaffolding, Terraform, or CI/CD support is
  desired.
- Use raw `gcloud` for custom container, networking, IAM, or advanced Cloud Run
  configuration.
- Preview commands and validate locally before mutating GCP resources.
