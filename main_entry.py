from fastapi import FastAPI
from fastapi.responses import JSONResponse
import os
import psycopg2
import json

app = FastAPI()

@app.get("/")
def root():
    return {"status": "api werkt"}

def get_connection():
    return psycopg2.connect(
        os.environ["DATABASE_URL"],
        sslmode="require"
    )

@app.get("/top5")
def get_top5(amount: int, age: int, duration: int):
    try:
        conn = get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            select results
            from rankings
            where scenario_amount = %s
              and scenario_age = %s
              and scenario_duration = %s
            order by created_at desc
            limit 1
            """,
            (amount, age, duration)
        )

        row = cur.fetchone()

        cur.close()
        conn.close()

        if not row:
            return {"error": "geen data"}

        results = row[0]

        if isinstance(results, str):
            results = json.loads(results)

        if isinstance(results, dict):
            if "best_choice" in results:
                return results
            return {
                "error": "onverwachte dict-structuur in results",
                "debug_type": str(type(results)),
                "debug_preview": str(results)[:500]
            }

        if not isinstance(results, list):
            return {
                "error": "results is geen lijst",
                "debug_type": str(type(results)),
                "debug_preview": str(results)[:500]
            }

        if len(results) == 0:
            return {"error": "lege results-lijst"}

        best = results[0]

        if not isinstance(best, dict):
            return {
                "error": "eerste item in results is geen dict",
                "debug_type": str(type(best)),
                "debug_preview": str(best)[:500]
            }

        alternatives = []
        for r in results[1:]:
            if isinstance(r, dict):
                alternatives.append(
                    {
                        "provider": r.get("provider_name"),
                        "monthly": r.get("monthly_payout"),
                        "rate": r.get("rate_value"),
                    }
                )

        return {
            "best_choice": {
                "provider": best.get("provider_name"),
                "monthly": best.get("monthly_payout"),
                "rate": best.get("rate_value"),
            },
            "alternatives": alternatives,
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": "serverfout in /top5",
                "details": str(e)
            }
        )