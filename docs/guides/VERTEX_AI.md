# Vertex AI Deployment Guide

This guide covers configuring APME's Abbenay AI provider to use Google Cloud
Vertex AI for Claude model access via Application Default Credentials (ADC).

---

## Prerequisites

- A GCP project with the **Vertex AI API** enabled
- `gcloud` CLI installed and authenticated
- A Kubernetes or OpenShift cluster with the APME Helm chart installed
- `kubectl` (or `oc`) with access to the target namespace

---

## 1. Create a GCP service account

Create a dedicated service account for APME and grant it the `Vertex AI User`
role:

```bash
export GCP_PROJECT="your-gcp-project-id"
export SA_NAME="apme-vertex-ai"

gcloud iam service-accounts create "$SA_NAME" \
  --project="$GCP_PROJECT" \
  --display-name="APME Vertex AI"

gcloud projects add-iam-policy-binding "$GCP_PROJECT" \
  --member="serviceAccount:${SA_NAME}@${GCP_PROJECT}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

## 2. Generate a service account key

```bash
gcloud iam service-accounts keys create sa-key.json \
  --iam-account="${SA_NAME}@${GCP_PROJECT}.iam.gserviceaccount.com"
```

> **Security note:** Treat `sa-key.json` as a secret. Do not commit it to
> version control. Delete the local copy after creating the Kubernetes Secret.

## 3. Create the Kubernetes Secret

```bash
kubectl create secret generic apme-gcp-credentials \
  --from-file=service-account-key.json=./sa-key.json \
  -n apme
```

Verify:

```bash
kubectl get secret apme-gcp-credentials -n apme
```

## 4. Configure the Helm chart

Add the following to your `values.yaml` (or pass via `--set`):

```yaml
abbenay:
  enabled: true
  token: "generate-a-random-token-here"    # e.g. openssl rand -hex 16
  aiModel: "vertex-claude/claude-sonnet-4@20250514"

  providers:
    vertex-claude:
      engine: vertex-anthropic
      models:
        claude-sonnet-4@20250514: {}

  gcp:
    project: "your-gcp-project-id"
    location: us-east5                     # or your Vertex AI region
    existingSecret: apme-gcp-credentials   # the Secret from step 3
```

Install or upgrade:

```bash
helm upgrade --install apme deploy/helm/apme/ \
  -n apme --create-namespace \
  -f values.yaml
```

## 5. Verify

Check the Abbenay pod is running:

```bash
kubectl get pods -n apme -l app.kubernetes.io/component=abbenay
```

Check the logs for successful Vertex AI initialization:

```bash
kubectl logs -n apme -l app.kubernetes.io/component=abbenay --tail=50
```

You should see model registration output without `undefined` in any URLs.
A working Vertex AI URL looks like:

```
https://us-east5-aiplatform.googleapis.com/v1/projects/your-project/locations/us-east5/publishers/anthropic/models/claude-sonnet-4@20250514:streamRawPredict
```

---

## Alternative: inline service account key

For development or CI environments, you can embed the service account key
directly in values instead of pre-creating a Secret. **Not recommended for
production.**

```yaml
abbenay:
  enabled: true
  token: "your-token"

  providers:
    vertex-claude:
      engine: vertex-anthropic
      models:
        claude-sonnet-4@20250514: {}

  gcp:
    project: "your-gcp-project-id"
    location: us-east5
    serviceAccountKey: |
      {
        "type": "service_account",
        "project_id": "your-gcp-project-id",
        ...
      }
```

---

## Environment variables

The chart sets these environment variables automatically when a
`vertex-anthropic` provider is configured with GCP credentials:

| Variable | Source | Purpose |
|----------|--------|---------|
| `GOOGLE_APPLICATION_CREDENTIALS` | Volume mount path | Points to the mounted service account JSON |
| `GOOGLE_VERTEX_PROJECT` | `abbenay.gcp.project` | GCP project for Vertex AI API calls |
| `GOOGLE_VERTEX_LOCATION` | `abbenay.gcp.location` | Vertex AI region (e.g. `us-east5`) |

These are the env var names that Abbenay's Vercel AI SDK integration reads.
Do not use `ANTHROPIC_VERTEX_PROJECT_ID` or `CLOUD_ML_REGION` — those are
for different SDKs and will be ignored.

---

## Using a corporate Vertex proxy

If your organization routes Vertex AI traffic through an API proxy (e.g.
APIcast), use the `baseUrl` and `apiKeySecret` fields instead of GCP ADC:

```yaml
abbenay:
  enabled: true
  token: "your-token"

  providers:
    corp-vertex:
      engine: vertex-anthropic
      baseUrl: "https://your-proxy.example.com/models"
      apiKeySecret:
        name: vertex-proxy-credentials
        key: bearer-token
      models:
        claude-sonnet-4@20250514: {}

  # gcp section not needed — the proxy handles authentication
```

---

## Troubleshooting

**`undefined` in Vertex API URL:**
Check that `GOOGLE_VERTEX_PROJECT` and `GOOGLE_VERTEX_LOCATION` are set in the
pod environment:

```bash
kubectl exec -n apme deploy/apme-abbenay -- env | grep GOOGLE_VERTEX
```

**`PERMISSION_DENIED` errors:**
Verify the service account has `roles/aiplatform.user` on the project and that
the Vertex AI API is enabled:

```bash
gcloud services list --project="$GCP_PROJECT" --filter="aiplatform"
```

**Pod stuck in `ContainerCreating`:**
The GCP credentials Secret may not exist. Check:

```bash
kubectl get secret apme-gcp-credentials -n apme
```
