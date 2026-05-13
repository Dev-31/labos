from fastapi import FastAPI

from labos import __version__
from labos.core.models import HealthResponse

app = FastAPI(title="LabOS", version=__version__)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()
