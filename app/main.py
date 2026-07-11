import os
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, APIRouter, HTTPException
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend-service")

app = FastAPI(title="acme-cloud backend-service")

# All routes live under /api — this matches the Ingress path in
# k8s/ingress.yaml. The ALB forwards the full request path (including /api)
# to the pod rather than stripping it, so the app's routes must include the
# same prefix or every request 404s.
router = APIRouter(prefix="/api")


def get_db_connection():
    """
    Reads DB connection details from environment variables — these are
    injected from the 'rds-credentials' Kubernetes Secret (see k8s/deployment.yaml),
    which itself was synced from AWS Secrets Manager by External Secrets
    Operator in Phase 7. This app never talks to AWS APIs directly.
    """
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USERNAME"],
        password=os.environ["DB_PASSWORD"],
        connect_timeout=5,
    )


class OrderRequest(BaseModel):
    item: str
    quantity: int = 1


@app.on_event("startup")
def startup_check_db():
    """Create the orders table if it doesn't exist yet, and fail loudly if RDS is unreachable."""
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS orders (
                    id SERIAL PRIMARY KEY,
                    item TEXT NOT NULL,
                    quantity INT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
        conn.commit()
        conn.close()
        logger.info("Connected to RDS and ensured orders table exists.")
    except Exception as e:
        logger.error(f"Startup DB check failed: {e}")
        # Intentionally don't crash the pod — /healthz still reports DB status
        # separately, so k8s doesn't loop-restart on a transient DB hiccup.


@router.get("/healthz")
def healthz():
    """Liveness/readiness probe target — checked by Kubernetes, see k8s/deployment.yaml."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz():
    """Deeper check: confirms the pod can actually reach RDS, not just that the process is alive."""
    try:
        conn = get_db_connection()
        conn.close()
        return {"status": "ready", "db": "reachable"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB unreachable: {e}")


@router.post("/order")
def create_order(order: OrderRequest):
    try:
        conn = get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "INSERT INTO orders (item, quantity, created_at) VALUES (%s, %s, %s) RETURNING id, item, quantity, created_at",
                (order.item, order.quantity, datetime.now(timezone.utc)),
            )
            row = cur.fetchone()
        conn.commit()
        conn.close()
        logger.info(f"Order created: {row}")
        return row
    except Exception as e:
        logger.error(f"Order creation failed: {e}")
        raise HTTPException(status_code=500, detail="Could not create order")


@router.get("/orders")
def list_orders():
    conn = get_db_connection()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, item, quantity, created_at FROM orders ORDER BY id DESC LIMIT 50")
        rows = cur.fetchall()
    conn.close()
    return rows


app.include_router(router)
