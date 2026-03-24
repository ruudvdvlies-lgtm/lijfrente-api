from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from pathlib import Path
import pandas as pd

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BANK_DURATIONS = [5, 10, 15, 20]
CSV_PATH = Path("scraped_rates.csv")

# Mapping van jouw API-producten naar echte product_id in scraped_rates.csv
PRODUCT_ID_MAP = {
    "nn_basis": "NATIONALE-NEDERLANDEN_NNLIJF",
    "nn_extra": "NATIONALE-NEDERLANDEN_NNLIJF",
}


def load_scraped_rates():
    if not CSV_PATH.exists():
        return None

    try:
        df = pd.read_csv(CSV_PATH)
    except Exception:
        return None

    required_columns = {
        "product_id",
        "min_looptijd_maanden",
        "max_looptijd_maanden",
        "rente_percentage",
    }

    if not required_columns.issubset(df.columns):
        return None

    return df


def find_best_rate_from_csv(mapped_product_id, duration_years, df_rates):
    if df_rates is None:
        return None

    months = duration_years * 12

    df_provider = df_rates[df_rates["product_id"].astype(str) == str(mapped_product_id)].copy()
    if df_provider.empty:
        return None

    df_provider["min_looptijd_maanden"] = pd.to_numeric(
        df_provider["min_looptijd_maanden"], errors="coerce"
    )
    df_provider["max_looptijd_maanden"] = pd.to_numeric(
        df_provider["max_looptijd_maanden"], errors="coerce"
    )
    df_provider["rente_percentage"] = pd.to_numeric(
        df_provider["rente_percentage"], errors="coerce"
    )

    df_provider = df_provider.dropna(
        subset=["min_looptijd_maanden", "max_looptijd_maanden", "rente_percentage"]
    )

    if df_provider.empty:
        return None

    # Eerst proberen op exacte match binnen range
    exact_match = df_provider[
        (df_provider["min_looptijd_maanden"] <= months) &
        (df_provider["max_looptijd_maanden"] >= months)
    ]

    if not exact_match.empty:
        try:
            return float(exact_match.iloc[0]["rente_percentage"])
        except Exception:
            pass

    # Anders dichtstbijzijnde min_looptijd pakken
    df_provider["distance"] = (df_provider["min_looptijd_maanden"] - months).abs()
    nearest = df_provider.sort_values(by=["distance", "min_looptijd_maanden"]).iloc[0]

    try:
        return float(nearest["rente_percentage"])
    except Exception:
        return None


def get_rate_from_csv_or_fallback(product_key, duration, fallback_rate, df_rates):
    mapped_product_id = PRODUCT_ID_MAP.get(product_key)

    if mapped_product_id:
        csv_rate = find_best_rate_from_csv(mapped_product_id, duration, df_rates)
        if csv_rate is not None:
            return csv_rate

    # fallback testdata als CSV niets bruikbaars geeft
    fallback_scraped_rates = {
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

    return fallback_scraped_rates.get(product_key, {}).get(duration, fallback_rate)


def calculate_monthly_payout(amount, annual_rate_percent, duration_years):
    months = duration_years * 12
    monthly_rate = annual_rate_percent / 100 / 12

    if monthly_rate > 0:
        payout = amount * (monthly_rate / (1 - (1 + monthly_rate) ** -months))
    else:
        payout = amount / months

    return round(payout, 2)


def fetch_single_duration(product, duration, df_rates):
    provider = product["external_product_key"]

    rate = get_rate_from_csv_or_fallback(
        product_key=provider,
        duration=duration,
        fallback_rate=product["rate"],
        df_rates=df_rates
    )

    payout = calculate_monthly_payout(
        amount=product["scenario_amount"],
        annual_rate_percent=rate,
        duration_years=duration
    )

    return {
        "external_product_key": product["external_product_key"],
        "product_name": product["product_name"],
        "product_variant": product["product_variant"],
        "scenario_amount": product["scenario_amount"],
        "scenario_age": product["scenario_age"],
        "scenario_duration": duration,
        "monthly_payout": payout,
        "rate": rate,
        "product_type": "bank",
        "life_is_real": False,
        "derived_from": None,
        "scrape_date": datetime.now().strftime("%Y-%m-%d")
    }


def build_multi_duration_product(product, df_rates):
    results = []

    for duration in BANK_DURATIONS:
        row = fetch_single_duration(product, duration, df_rates)
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
    csv_loaded = CSV_PATH.exists()
    return {
        "status": "api werkt",
        "version": "TEST-MULTI-005",
        "csv_found": csv_loaded
    }


@app.get("/debug")
def debug():
    df_rates = load_scraped_rates()

    all_results = []
    for product in get_base_data():
        all_results.extend(build_multi_duration_product(product, df_rates))

    return {
        "version": "TEST-MULTI-005",
        "csv_found": CSV_PATH.exists(),
        "csv_loaded": df_rates is not None,
        "product_id_map": PRODUCT_ID_MAP,
        "count": len(all_results),
        "data": all_results
    }


@app.get("/top5")
def get_top5(
    amount: float = Query(...),
    age: int = Query(...),
    duration: str = Query(...)
):
    df_rates = load_scraped_rates()

    all_results = []
    for product in get_base_data():
        all_results.extend(build_multi_duration_product(product, df_rates))

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
        "version": "TEST-MULTI-005",
        "csv_found": CSV_PATH.exists(),
        "csv_loaded": df_rates is not None,
        "requested": {
            "amount": amount,
            "age": age,
            "duration": requested_duration
        },
        "available_durations": sorted(list(set(str(r["scenario_duration"]) for r in all_results))),
        "filtered_count": len(filtered),
        "data": filtered
    }
