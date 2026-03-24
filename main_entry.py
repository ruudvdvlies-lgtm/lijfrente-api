from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"status": "WERKT_NU_ECHT"}
