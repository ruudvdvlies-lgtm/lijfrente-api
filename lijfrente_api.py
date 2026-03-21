from fastapi import FastAPI, Query
import pandas as pd

app = FastAPI()

# laad data
df = pd.read_csv("scraped_rates.csv")


def bereken_uitkering(kapitaal, rente, looptijd_maanden):
    r = rente / 100 / 12
    n = looptijd_maanden

    if r == 0:
        return kapitaal / n

    return kapitaal * r / (1 - (1 + r) ** -n)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/looptijden")
def looptijden():
    return sorted(df["min_looptijd_maanden"].unique().tolist())


@app.get("/compare")
def compare(
    kapitaal: float = Query(...),
    looptijd_maanden: int = Query(...)
):
    data = df[df["min_looptijd_maanden"] == looptijd_maanden].copy()

    data["maand_bruto"] = data.apply(
        lambda row: bereken_uitkering(
            kapitaal,
            row["rente_percentage"],
            row["min_looptijd_maanden"]
        ),
        axis=1
    )

    data["maand_netto"] = data["maand_bruto"] - data["kosten_periodiek"]

    beste = data.sort_values("maand_netto", ascending=False).head(5)

    return beste[
        [
            "provider_name",
            "rente_percentage",
            "kosten_eenmalig",
            "kosten_periodiek",
            "maand_netto"
        ]
    ].to_dict(orient="records")