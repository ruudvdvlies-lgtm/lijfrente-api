# (alle imports en functies blijven gelijk hierboven)

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

        net_amount = max(amount - once_cost, 0)
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

    # sorteren
    results = sorted(results, key=lambda x: x["monthly_payout"], reverse=True)

    # 🥇 BESTE KEUZE + verschil
    if len(results) > 1:
        best = results[0]
        second = results[1]

        difference = round(best["monthly_payout"] - second["monthly_payout"], 2)

        best["label"] = "Beste keuze"
        best["advantage_vs_next"] = difference

        best["explanation"] = (
            f"Deze optie levert €{difference} per maand meer op dan de volgende optie, "
            f"na aftrek van kosten."
        )

    return {
        "version": VERSION,
        "requested": {
            "amount": amount,
            "age": age,
            "duration": duration
        },
        "results": results[:5]
    }
