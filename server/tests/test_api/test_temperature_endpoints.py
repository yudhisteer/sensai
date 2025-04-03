# main.py
from fastapi import FastAPI
from server.api.endpoints.ds18b20 import router

app = FastAPI()
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)