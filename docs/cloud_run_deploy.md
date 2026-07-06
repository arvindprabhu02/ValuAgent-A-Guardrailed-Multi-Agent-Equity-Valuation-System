# Google Cloud Run Deployment Guide

Follow these steps to deploy ValuAgent's web dashboard to Google Cloud Run, making it publicly accessible from any device.

## Prerequisites

1. **Google Cloud Account**: Ensure you have an active Google Cloud Platform project.
2. **Google Cloud SDK**: Install the `gcloud` CLI tool on your local machine.
3. **Billing Enabled**: Make sure billing is enabled for your Google Cloud project (required for Cloud Run).

---

## Deployment Steps

### 1. Authenticate with Google Cloud
Open your terminal and authenticate the CLI with your Google account:
```bash
gcloud auth login
```

### 2. Set your Google Cloud Project ID
Set your default project ID (replace `YOUR_PROJECT_ID` with your actual GCP project ID):
```bash
gcloud config set project YOUR_PROJECT_ID
```

### 3. Enable Required Services
Enable the Cloud Build and Cloud Run APIs for your project:
```bash
gcloud services enable run.googleapis.com builds.googleapis.com
```

### 4. Build and Deploy using a Single Command
Run the following command in the root of your project directory. This builds the container image using Google Cloud Build and deploys it directly to Cloud Run:

```bash
gcloud run deploy valuagent \
    --source . \
    --platform managed \
    --region us-central1 \
    --allow-unauthenticated \
    --set-env-vars GEMINI_API_KEY="your-gemini-api-key" \
    --set-env-vars VALUAGENT_MEMO_MODEL="gemini-2.5-flash"
```

> [!IMPORTANT]
> Replace `"your-gemini-api-key"` with your actual Google Gemini API key. Setting it as an environment variable ensures Cloud Run has access to the API key at runtime.

---

## After Deployment

Once the command completes, it will output a public service URL, for example:
`https://valuagent-xxxxxx-uc.a.run.app`

You can visit this URL from any device (phone, tablet, or external computer) to access the interactive valuation dashboard!
