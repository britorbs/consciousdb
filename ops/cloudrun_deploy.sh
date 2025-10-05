#!/usr/bin/env bash
set -euo pipefail

SERVICE=${1:-consciousdb-sidecar}
REGION=${2:-us-central1}

gcloud run deploy "$SERVICE"   --source .   --region "$REGION"   --allow-unauthenticated
