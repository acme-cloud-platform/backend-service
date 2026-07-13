# backend-service
# Testing
FastAPI backend for the Acme Cloud POC — owns order creation, talks to RDS Postgres.

## What this repo owns
Source code, `Dockerfile`, K8s manifests (`k8s/`), and its own CI/CD workflow. No Terraform, no infrastructure — that all lives in `platform-infrastructure`.

See `platform-infrastructure/README.md` for the full architecture and how every piece connects.

## Endpoints
- `GET /healthz` — liveness probe target
- `GET /readyz` — readiness probe target, actually checks DB connectivity
- `POST /order` — create an order (`{"item": "widget", "quantity": 2}`)
- `GET /orders` — list last 50 orders

## Local development
```bash
pip install -r requirements.txt
export DB_HOST=localhost DB_PORT=5432 DB_NAME=acmecloud DB_USERNAME=... DB_PASSWORD=...
uvicorn app.main:app --reload
```

## Deployment
Every push to `main` triggers `.github/workflows/deploy.yml`:
1. Authenticates to AWS via OIDC (no static keys — see `platform-infrastructure` Phase 5)
2. Builds the Docker image, pushes to ECR (`acme-cloud-poc-backend` repo — Phase 4)
3. Applies `k8s/*.yaml` to the EKS cluster (Phase 3), with the image tag substituted in
4. DB credentials come from the `rds-credentials` K8s Secret, synced by External Secrets Operator (Phase 7) — this app never touches AWS Secrets Manager directly
5. The `Ingress` resource gets picked up by AWS Load Balancer Controller (Phase 6), which provisions a real ALB automatically

