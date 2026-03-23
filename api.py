from fastapi import FastAPI
import psycopg2

app = FastAPI()


def get_connection():
    return psycopg2.connect(
        "postgresql://postgres.xxx:XQ%3fCge9gJaP9NE@aws-1-eu-west-1.pooler.supabase.com:5432/postgres",
        sslmode="require"
    )


@app.get("/top5")
def get_top5(amount: int, age: int, duration: int):
    conn = get_connection()
    cur = conn.cursor()

    # Alle verified records ophalen
    cur.execute(
        """
        select
            p.provider_name,
            np.product_name,
            np.product_variant,
            nr.monthly_payout,
            nr.rate_value
        from normalized_rates nr
        join normalized_products np
            on np.id = nr.normalized_product_id
        join providers p
            on p.id = nr.provider_id
        where nr.scenario_amount = %s
          and nr.scenario_age = %s
          and nr.scenario_duration = %s
          and nr.is_verified = true
        order by nr.monthly_payout desc
        """,
        (amount, age, duration)
    )
    verified_rows = cur.fetchall()

    # Indicatieve records ophalen
    cur.execute(
        """
        select
            p.provider_name,
            np.product_name,
            np.product_variant,
            nr.monthly_payout,
            nr.rate_value
        from normalized_rates nr
        join normalized_products np
            on np.id = nr.normalized_product_id
        join providers p
            on p.id = nr.provider_id
        where nr.scenario_amount = %s
          and nr.scenario_age = %s
          and nr.scenario_duration = %s
          and nr.is_verified = false
        order by nr.monthly_payout desc
        """,
        (amount, age, duration)
    )
    indicative_rows = cur.fetchall()

    cur.close()
    conn.close()

    # Dedupe: per provider alleen hoogste verified record behouden
    seen_providers = set()
    official_rows = []

    for row in verified_rows:
        provider_name = row[0]
        if provider_name not in seen_providers:
            official_rows.append(row)
            seen_providers.add(provider_name)

    official_rows = official_rows[:5]

    # Geen officiële data
    if not official_rows:
        return {
            "best_choice": None,
            "alternatives": [],
            "indicative": [
                {
                    "provider": row[0],
                    "product_name": row[1],
                    "product_variant": row[2],
                    "monthly": float(row[3]),
                    "rate": float(row[4]),
                    "label": "indicatief"
                }
                for row in indicative_rows
            ]
        }

    # Beste keuze
    best = official_rows[0]
    best_choice = {
        "provider": best[0],
        "product_name": best[1],
        "product_variant": best[2],
        "monthly": float(best[3]),
        "rate": float(best[4])
    }

    # Alternatieven
    alternatives = []
    for row in official_rows[1:]:
        alternatives.append(
            {
                "provider": row[0],
                "product_name": row[1],
                "product_variant": row[2],
                "monthly": float(row[3]),
                "rate": float(row[4])
            }
        )

    # Indicatieve aanbieders
    indicative = []
    for row in indicative_rows:
        indicative.append(
            {
                "provider": row[0],
                "product_name": row[1],
                "product_variant": row[2],
                "monthly": float(row[3]),
                "rate": float(row[4]),
                "label": "indicatief"
            }
        )

    return {
        "best_choice": best_choice,
        "alternatives": alternatives,
        "indicative": indicative
    }
