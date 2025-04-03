from functools import partial

import uvicorn
from fastapi import FastAPI

from server.api.common.monitor import background_monitor, lifespan
from server.api.endpoints.ds18b20 import router
from server.sensors.ds18b20.tools import read_temp, store_temperature

# Initialize FastAPI app with lifespan
# app = FastAPI(lifespan=lifespan)

app = FastAPI(
    lifespan=partial(
        lifespan,
        background_tasks=[
            background_monitor(read_temp, store_temperature, "temperature")
        ],
    )
)

# Mount the imported router directly to the app
app.include_router(router=router)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
