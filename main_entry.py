from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import csv

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VERSION = "TEST-MULTI-008"


def duration_to_months(duration):
    if duration == "life":
        return 240
    return int(duration) * 12


def load_data():
    data = []
    try:
        with open("scraped_rates.csv", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                data.append(row)
        return data
    except Exception:
        return []


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(str(value).replace(",", "."))
    except Exception:
        return default


def calculate_monthly_payout(amount: float, annual_rate_percent: float, months: int) -> float:
    monthly_rate = annual_rate_percent / 100 / 12

    if months <= 0:
        return 0.0

    if monthly_rate == 0:
        return round(amount / months, 2)

    payout = amount * (monthly_rate / (1 - (1 + monthly_rate) ** (-months)))
    return round(payout, 2)


@app.get("/")
def root():
    return {"status": "api werkt", "version": VERSION}


@app.get("/debug")
def debug():
    data = load_data()
    return {
        "version": VERSION,
        "records": len(data),
        "sample": data[:5]
    }


@app.get("/top5")
def top5(
    amount: float = Query(...),
    age: int = Query(...),
    duration: str = Query(...)
):
    data = load_data()

    if not data:
        return {"error": "geen data"}

    target_months = duration_to_months(duration)

    filtered = [
        row for row in data
        if int(row["min_looptijd_maanden"]) <= target_months <= int(row["max_looptijd_maanden"])
    ]

    results = []
    for row in filtered:
        gross_rate = safe_float(row.get("rente_percentage"), 0.0)
        once_cost = safe_float(row.get("kosten_eenmalig"), 0.0)
        periodic_cost = safe_float(row.get("kosten_periodiek"), 0.0)

        # 1. eenmalige kosten gaan van het kapitaal af
        net_amount = max(amount - once_cost, 0)

        # 2. periodieke kosten verlagen het effectieve rendement
        net_rate = max(gross_rate - periodic_cost, 0)

        monthly = calculate_monthly_payout(
            amount=net_amount,
            annual_rate_percent=net_rate,
            months=target_months
        )

        results.append({
            "provider": row["provider_name"],
            "product": row["product_id"],
            "duration_months": target_months,
            "monthly_payout": monthly,
            "gross_rate": round(gross_rate, 4),
            "periodic_cost": round(periodic_cost, 4),
            "net_rate": round(net_rate, 4),
            "once_cost": round(once_cost, 2)
        })

    results = sorted(results, key=lambda x: x["monthly_payout"], reverse=True)

    return {
        "version": VERSION,
        "requested": {
            "amount": amount,
            "age": age,
            "duration": duration
        },
        "results": results[:5]
    }
