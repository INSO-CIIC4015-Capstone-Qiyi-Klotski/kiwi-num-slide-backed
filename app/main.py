from fastapi import FastAPI

app = FastAPI(title="three-tier BE")

@app.get("/")
def root():
    return {"message": "Hello from FastAPI on EB via ECR (port 80)! crear un commit"}

@app.get("/health")
def health():
    return {"ok": True}

