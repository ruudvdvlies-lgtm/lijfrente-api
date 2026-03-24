from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import csv
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VERSION = "TEST-MULTI-006"


# ===============================
# HELPER: duration → maanden
# ===============================
def duration_to_months(duration):
    if duration == "life":
        return 240  # fallback (20 jaar)
    return int(duration) * 12


# ===============================
# CSV laden
# ===============================
def load_data():
    data = []
    try:
        with open("scraped_rates.csv", newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                data.append(row)
        return data
    except:
        return []


# ===============================
# ROOT
# ===============================
@app.get("/")
def root():
    return {"status": "api werkt", "version": VERSION}


# ===============================
# DEBUG
# ===============================
@app.get("/debug")
def debug():
    data = load_data()
    return {
        "version": VERSION,
        "records": len(data),
        "sample": data[:5]
    }


# ===============================
# TOP5
# ===============================
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

    # ===============================
    # FILTER OP LOOPTJD
    # ===============================
    filtered = [
        row for row in data
        if int(row["min_looptijd_maanden"]) <= target_months <= int(row["max_looptijd_maanden"])
    ]

    # ===============================
    # BEREKEN UITKERING (SIMPEL)
    # ===============================
    results = []
    for row in filtered:
        rate = float(row["rente_percentage"])

        monthly = (amount * (1 + rate / 100)) / (target_months / 12)

        results.append({
            "provider": row["provider_name"],
            "product": row["product_id"],
            "duration_months": target_months,
            "monthly_payout": round(monthly, 2),
            "rate": rate
        })

    # ===============================
    # SORTEREN
    # ===============================
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