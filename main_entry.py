from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import csv
from pathlib import Path

VERSION = "2026-03-25-bnd-fix"

app = FastAPI(title="Lijfrente API", version=VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = Path(__file__).resolve().parent / "scraped_rates.csv"


def load_data():
    if not DATA_FILE.exists():
        return []

    with open(DATA_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    cleaned = []
    for row in rows:
        if not row:
            continue
        if not row.get("provider_id"):
            continue
        cleaned.append(row)

    return cleaned


def duration_to_months(duration: str) -> int:
    d = str(duration).strip().lower()

    mapping = {
        "5": 60,
        "5 jaar": 60,
        "5j": 60,
        "60": 60,
        "60 maanden": 60,
        "10": 120,
        "10 jaar": 120,
        "10j": 120,
        "120": 120,
        "120 maanden": 120,
        "15": 180,
        "15 jaar": 180,
        "15j": 180,
        "180": 180,
        "180 maanden": 180,
        "20": 240,
        "20 jaar": 240,
        "20j": 240,
        "240": 240,
        "240 maanden": 240,
        "25": 300,
        "25 jaar": 300,
        "25j": 300,
        "300": 300,
        "300 maanden": 300,
        "30": 360,
        "30 jaar": 360,
        "30j": 360,
        "360": 360,
        "360 maanden": 360,
    }

    if d in mapping:
        return mapping[d]

    if d.isdigit():
        value = int(d)
        if value <= 40:
            return value * 12
        return value

    raise ValueError(f"Onbekende duration: {duration}")


def calculate_monthly_payout(amount: float, annual_rate_percent: float, months: int) -> float:
    if months <= 0:
        return 0.0

    monthly_rate = annual_rate_percent / 100.0 / 12.0

    if monthly_rate == 0:
        return amount / months

    return amount * (monthly_rate / (1 - (1 + monthly_rate) ** (-months)))


@app.get("/")
def root():
    data = load_data()
    return {
        "status": "ok",
        "version": VERSION,
        "records": len(data),
        "data_file": str(DATA_FILE),
        "sample": data[:5],
    }


@app.get("/health")
def health():
    data = load_data()
    return {
        "status": "healthy",
        "version": VERSION,
        "records": len(data),
    }


@app.get("/top5")
def top5(
    amount: float = Query(..., gt=0),
    age: int = Query(..., ge=0),
    duration: str = Query(...),
):
    data = load_data()

    if not data:
        return {
            "error": "geen data",
            "version": VERSION,
            "data_file": str(DATA_FILE),
        }

    target_months = duration_to_months(duration)

    filtered = [
        row for row in data
        if int(float(row["min_looptijd_maanden"])) <= target_months <= int(float(row["max_looptijd_maanden"]))
    ]

    results = []
    for row in filtered:
        rate = float(row["rente_percentage"])

        monthly = calculate_monthly_payout(
            amount=amount,
            annual_rate_percent=rate,
            months=target_months,
        )

        results.append({
            "provider": row["provider_name"],
            "provider_id": row["provider_id"],
            "product": row["product_id"],
            "duration_months": target_months,
            "monthly_payout": round(monthly, 2),
            "rate": rate,
            "kosten_eenmalig": float(row.get("kosten_eenmalig", 0) or 0),
            "kosten_periodiek": float(row.get("kosten_periodiek", 0) or 0),
            "bron_url": row.get("bron_url", ""),
        })

    results = sorted(results, key=lambda x: x["monthly_payout"], reverse=True)

    return {
        "version": VERSION,
        "requested": {
            "amount": amount,
            "age": age,
            "duration": duration,
            "target_months": target_months,
        },
        "count_filtered": len(results),
        "results": results[:5],
    }