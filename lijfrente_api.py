from fastapi import FastAPI, Query, HTTPException
import pandas as pd

app = FastAPI()

CSV_PATH = "scraped_rates.csv"


def laad_data() -> pd.DataFrame:
    try:
        df = pd.read_csv(CSV_PATH, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(CSV_PATH, encoding="latin-1")

    numerieke_kolommen = [
        "staffel_min",
        "staffel_max",
        "min_looptijd_maanden",
        "max_looptijd_maanden",
        "rente_percentage",
        "kosten_eenmalig",
        "kosten_periodiek",
    ]

    for kol in numerieke_kolommen:
        if kol in df.columns:
            df[kol] = pd.to_numeric(df[kol], errors="coerce")

    # Ontbrekende kolommen veilig aanvullen
    if "kosten_eenmalig" not in df.columns:
        df["kosten_eenmalig"] = 0.0
    if "kosten_periodiek" not in df.columns:
        df["kosten_periodiek"] = 0.0
    if "staffel_min" not in df.columns:
        df["staffel_min"] = 0.0
    if "staffel_max" not in df.columns:
        df["staffel_max"] = 999999999.0
    if "max_looptijd_maanden" not in df.columns:
        df["max_looptijd_maanden"] = df["min_looptijd_maanden"]

    df["kosten_eenmalig"] = df["kosten_eenmalig"].fillna(0.0)
    df["kosten_periodiek"] = df["kosten_periodiek"].fillna(0.0)
    df["staffel_min"] = df["staffel_min"].fillna(0.0)
    df["staffel_max"] = df["staffel_max"].fillna(999999999.0)
    df["max_looptijd_maanden"] = df["max_looptijd_maanden"].fillna(df["min_looptijd_maanden"])

    return df


def bereken_uitkering(kapitaal: float, rente: float, looptijd_maanden: int) -> float:
    r = rente / 100 / 12
    n = looptijd_maanden

    if n <= 0:
        raise ValueError("Looptijd moet groter zijn dan 0")

    if r == 0:
        return kapitaal / n

    return kapitaal * r / (1 - (1 + r) ** -n)


def filter_producten(df: pd.DataFrame, kapitaal: float, looptijd_maanden: int) -> pd.DataFrame:
    gefilterd = df[
        (df["min_looptijd_maanden"] <= looptijd_maanden)
        & (df["max_looptijd_maanden"] >= looptijd_maanden)
        & (df["staffel_min"] <= kapitaal)
        & (df["staffel_max"] >= kapitaal)
    ].copy()

    return gefilterd


def verrijk_resultaten(df: pd.DataFrame, kapitaal: float, looptijd_maanden: int) -> pd.DataFrame:
    if df.empty:
        return df

    df["netto_startkapitaal"] = kapitaal - df["kosten_eenmalig"]
    df = df[df["netto_startkapitaal"] > 0].copy()

    if df.empty:
        return df

    df["maand_bruto"] = df.apply(
        lambda row: bereken_uitkering(
            kapitaal=float(row["netto_startkapitaal"]),
            rente=float(row["rente_percentage"]),
            looptijd_maanden=looptijd_maanden,
        ),
        axis=1,
    )

    df["maand_netto"] = df["maand_bruto"] - df["kosten_periodiek"]

    # Labels voorbereiden
    df["label"] = ""

    # Beste keuze = hoogste netto uitkering
    idx_beste = df["maand_netto"].idxmax()
    df.loc[idx_beste, "label"] = "beste_keuze"

    # Hoogste rente
    idx_hoogste_rente = df["rente_percentage"].idxmax()
    if df.loc[idx_hoogste_rente, "label"] == "":
        df.loc[idx_hoogste_rente, "label"] = "hoogste_rente"

    # Laagste totale kosten
    df["totale_kosten_indicatie"] = df["kosten_eenmalig"] + (df["kosten_periodiek"] * looptijd_maanden)
    idx_laagste_kosten = df["totale_kosten_indicatie"].idxmin()
    if df.loc[idx_laagste_kosten, "label"] == "":
        df.loc[idx_laagste_kosten, "label"] = "laagste_kosten"

    return df.sort_values("maand_netto", ascending=False).reset_index(drop=True)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/looptijden")
def looptijden():
    df = laad_data()

    waarden = sorted(
        int(x) for x in df["min_looptijd_maanden"].dropna().unique().tolist()
    )

    return waarden

@app.get("/compare")
def compare(
    kapitaal: float = Query(..., gt=0),
    looptijd_maanden: int = Query(..., gt=0),
    top_n: int = Query(5, gt=0, le=20),
):
    df = laad_data()
    gefilterd = filter_producten(df, kapitaal, looptijd_maanden)

    if gefilterd.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Geen producten gevonden voor kapitaal {kapitaal} en looptijd {looptijd_maanden} maanden."
        )

    resultaat = verrijk_resultaten(gefilterd, kapitaal, looptijd_maanden)

    if resultaat.empty:
        raise HTTPException(
            status_code=404,
            detail="Na verwerking bleven geen bruikbare producten over."
        )

    top = resultaat.head(top_n).copy()

    winnaar = top.iloc[0]
    verschil_nummer_2 = None
    if len(top) > 1:
        verschil_nummer_2 = round(float(top.iloc[0]["maand_netto"] - top.iloc[1]["maand_netto"]), 2)

    output = []
    for _, row in top.iterrows():
        output.append({
            "provider_id": row.get("provider_id"),
            "provider_name": row.get("provider_name"),
            "product_id": row.get("product_id"),
            "gekozen_looptijd_maanden": looptijd_maanden,
            "rente_percentage": round(float(row.get("rente_percentage", 0)), 4),
            "kosten_eenmalig": round(float(row.get("kosten_eenmalig", 0)), 2),
            "kosten_periodiek": round(float(row.get("kosten_periodiek", 0)), 2),
            "netto_startkapitaal": round(float(row.get("netto_startkapitaal", 0)), 2),
            "maand_bruto": round(float(row.get("maand_bruto", 0)), 2),
            "maand_netto": round(float(row.get("maand_netto", 0)), 2),
            "staffel_min": round(float(row.get("staffel_min", 0)), 2),
            "staffel_max": round(float(row.get("staffel_max", 0)), 2),
            "min_looptijd_maanden": int(row.get("min_looptijd_maanden", looptijd_maanden)),
            "max_looptijd_maanden": int(row.get("max_looptijd_maanden", looptijd_maanden)),
            "geldig_vanaf": row.get("geldig_vanaf"),
            "bron_url": row.get("bron_url"),
            "bron_regel": row.get("bron_regel"),
            "label": row.get("label", ""),
        })

    return {
        "kapitaal": kapitaal,
        "looptijd_maanden": looptijd_maanden,
        "aantal_resultaten": len(output),
        "winnaar": winnaar.get("provider_name"),
        "winnaar_maand_netto": round(float(winnaar.get("maand_netto", 0)), 2),
        "verschil_met_nummer_2": verschil_nummer_2,
        "resultaten": output,
    }