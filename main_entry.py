from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BANK_DURATIONS = [5, 10, 15, 20]


def fetch_single_duration(product, duration):
    """
    Koppeling met rente (voorbereid op echte scraping).
    """

    # 🔥 tijdelijke “scraped” rente (later vervangen door echte scraper)
    scraped_rates = {
        "nn_basis": {
            5: 3.2,
            10: 3.3,
            15: 3.4,
            20: 3.5
        },
        "nn_extra": {
            5: 3.3,
            10: 3.4,
            15: 3.5,
            20: 3.6
        }
    }

    provider = product["external_product_key"]

    # fallback naar bestaande rate als niet gevonden
    rate = scraped_rates.get(provider, {}).get(duration, product["rate"])

    amount = product["scenario_amount"]
    months = duration * 12
    monthly_rate = rate / 100 / 12

    # annuïteiten berekening
    if monthly_rate > 0:
        payout = amount * (monthly_rate / (1 - (1 + monthly_rate) ** -months))
    else:
        payout = amount / months

    return {
        "external_product_key": product["external_product_key"],
        "product_name": product["product_name"],
        "product_variant": product["product_variant"],
        "scenario_amount": product["scenario_amount"],
        "scenario_age": product["scenario_age"],
        "scenario_duration": duration,
        "monthly_payout": round(payout, 2),
        "rate": rate,
        "product_type": "bank",
        "life_is_real": False,
        "derived_from": None,
        "scrape_date": datetime.now().strftime("%Y-%m-%d")
    }


def build_multi_duration_product(product):
    results = []

    for duration in BANK_DURATIONS:
        row = fetch_single_duration(product, duration)
        results.append(row)

    # life = kopie van 20 jaar (bankproduct)
    row_20 = next((r for r in results if r["scenario_duration"] == 20), None)

    if row_20:
        life_row = row_20.copy()
        life_row["scenario_duration"] = "life"
        life_row["derived_from"] = 20
        life_row["life_is_real"] = False
        results.append(life_row)

    return results


def get_base_data():
    return [
        {
            "external_product_key": "nn_basis",
            "product_name": "NN Basis",
            "product_variant": "Standaard",
            "scenario_amount": 100000,
            "scenario_age": 67,
            "monthly_payout": 510.00,
            "rate": 3.10
        },
        {
            "external_product_key": "nn_extra",
            "product_name": "NN Extra",
            "product_variant": "Plus",
            "scenario_amount": 100000,
            "scenario_age": 67,
            "monthly_payout": 540.00,
            "rate": 3.45
        }
    ]


@app.get("/")
def root():
    return {"status": "api werkt", "version": "TEST-MULTI-003"}


@app.get("/debug")
def debug():
    all_results = []
    for product in get_base_data():
        all_results.extend(build_multi_duration_product(product))

    return {
        "version": "TEST-MULTI-003",
        "count": len(all_results),
        "data": all_results
    }


@app.get("/top5")
def get_top5(
    amount: float = Query(...),
    age: int = Query(...),
    duration: str = Query(...)
):
    all_results = []
    for product in get_base_data():
        all_results.extend(build_multi_duration_product(product))

    duration_input = duration.strip().lower()

    if duration_input == "life":
        requested_duration = "life"
    else:
        try:
            requested_duration = int(duration_input)
        except ValueError:
            return {"error": f"ongeldige duration: {duration}"}

    filtered = [
        row for row in all_results
        if row["scenario_amount"] == amount
        and row["scenario_age"] == age
        and row["scenario_duration"] == requested_duration
    ]

    filtered = sorted(filtered, key=lambda x: x["monthly_payout"], reverse=True)

    return {
        "version": "TEST-MULTI-003",
        "requested": {
            "amount": amount,
            "age": age,
            "duration": requested_duration
        },
        "available_durations": sorted(list(set(str(r["scenario_duration"]) for r in all_results))),
        "filtered_count": len(filtered),
        "data": filtered
    }
