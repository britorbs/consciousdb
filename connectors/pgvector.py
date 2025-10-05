from __future__ import annotations
from typing import List, Tuple, Optional
import numpy as np
try:
    import psycopg2
except Exception:
    psycopg2 = None

from .base import BaseConnector

class PgVectorConnector(BaseConnector):
    def __init__(self, dsn: str, table: str = "items", id_col: str = "id", vec_col: str = "embedding"):
        if psycopg2 is None:
            raise RuntimeError("psycopg2 not installed")
        self.dsn = dsn; self.table = table; self.id_col=id_col; self.vec_col=vec_col

    def top_m(self, query_vec: np.ndarray, m: int) -> List[Tuple[str, float, Optional[np.ndarray]]]:
        q = query_vec.astype(np.float32).tolist()
        sql = f"""
            SELECT {self.id_col} AS id, 1.0 - ({self.vec_col} <-> %s::vector) AS sim
            FROM {self.table}
            ORDER BY {self.vec_col} <-> %s::vector
            LIMIT %s
        """
        with psycopg2.connect(self.dsn) as conn, conn.cursor() as cur:
            cur.execute(sql, (q, q, m))
            rows = cur.fetchall()
        return [(str(r[0]), float(r[1]), None) for r in rows]

    def fetch_vectors(self, ids: List[str]) -> np.ndarray:
        # You can implement a fetch; many pgvector schemas store vectors in a separate table.
        raise NotImplementedError("Implement fetch_vectors or return vectors in top_m")
