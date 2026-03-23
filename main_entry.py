from fastapi import FastAPI
from fastapi.responses import JSONResponse
import os
import psycopg2
import json
from datetime import date

app = FastAPI()


@app.get("/")
def root():
    return {"status": "api werkt"}


def get_connection():
    return psycopg2.connect(
        os.environ["DATABASE_URL"],
        sslmode="require"
    )


def estimate_net_monthly(gross_monthly: float, tax_factor: float = 0.73) -> float:
    try:
        return round(float(gross_monthly) * tax_factor, 2)
    except Exception:
        return 0.0


def source_label(source_type: str) -> str:
    mapping = {
        "live_scraped": "Actueel tarief",
        "provider_feed": "Aanbiederdata",
        "modeled": "Indicatieve berekening",
        "hybrid": "Actuele data + berekening",
    }
    return mapping.get(source_type, "Indicatie")


def normalize_result_item(item: dict, fallback_duration: int) -> dict:
    gross = float(item.get("monthly_payout", 0) or 0)
    source_type = item.get("data_source_type", "live_scraped")

    why_this_option = item.get("why_this_option")
    if not isinstance(why_this_option, list) or len(why_this_option) == 0:
        why_this_option = [
            "Gebaseerd op uw gekozen looptijd en producttype",
            "Vergeleken op uitkering, kosten en productkenmerken",
            "Indicatie op basis van actuele beschikbare data",
        ]

    return {
        "provider": item.get("provider_name"),
        "product_name": item.get("product_name", item.get("provider_name")),
        "gross_monthly": gross,
        "net_monthly": estimate_net_monthly(gross),
        "rate": item.get("rate_value"),
        "duration_years": item.get("duration_years", fallback_duration),
        "one_off_costs": item.get("one_off_costs", 0),
        "periodic_costs": item.get("periodic_costs", 0),
        "fixed_costs_monthly": item.get("fixed_costs_monthly", 0),
        "score_total": item.get("score_total"),
        "score_breakdown": {
            "payout": item.get("score_payout"),
            "costs": item.get("score_costs"),
            "match": item.get("score_match"),
            "quality": item.get("score_quality"),
        },
        "data_source_type": source_type,
        "data_source_label": source_label(source_type),
        "data_last_updated": item.get("data_last_updated", str(date.today())),
        "why_this_option": why_this_option,
    }


@app.get("/top5")
def get_top5(
    amount: int,
    age: int,
    duration: int,
    start_date: str = "2026-06-01",
    frequency: str = "maandelijks",
    regime: str = "nieuw_regime"
):
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

        normalized = []
        for item in results:
            if isinstance(item, dict):
                normalized.append(normalize_result_item(item, duration))

        if len(normalized) == 0:
            return {"error": "geen bruikbare resultaten"}

        best = normalized[0]
        alternatives = normalized[1:]

        top_difference_monthly = 0
        if len(normalized) > 1:
            top_difference_monthly = round(
                abs(
                   float(best["gross_monthly"]) - float(normalized[1]["gross_monthly"])
                ),
                2
            )

        response = {
            "summary": {
                "amount": amount,
                "age": age,
                "duration_years": duration,
                "start_date": start_date,
                "frequency": frequency,
                "regime": regime,
                "providers_compared": len(normalized),
                "last_updated": best.get("data_last_updated"),
                "best_gross_monthly": best["gross_monthly"],
                "best_net_monthly": best["net_monthly"]
            },
            "best_choice": best,
            "alternatives": alternatives,
            "comparison_meta": {
                "gross_net_note": "Netto is een indicatieve berekening en geen persoonlijk belastingadvies.",
                "ranking_note": "De rangorde is gebaseerd op uitkering, kosten, productmatch en kwaliteit.",
                "advice_recommended": top_difference_monthly <= 25 if len(normalized) > 1 else False,
                "top_difference_monthly": top_difference_monthly
            }
        }

        return response

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": "serverfout in /top5",
                "details": str(e)
            }
        )