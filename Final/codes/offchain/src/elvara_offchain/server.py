from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

from .service import IntentService, RunIntentOptions


class RebalanceRunRequest(BaseModel):
    strategy: str = Field(default="CVaR")
    epoch: int | None = None
    expiry_seconds: int | None = Field(default=None, alias="expirySeconds")
    submit_onchain: bool = Field(default=False, alias="submitOnchain")
    use_sample: bool = Field(default=False, alias="useSample")
    use_today: bool = Field(default=False, alias="useToday")
    weights_mode: Literal["last", "avg"] = Field(default="last", alias="weightsMode")


def create_app(service: IntentService | None = None) -> FastAPI:
    intent_service = service or IntentService()
    app = FastAPI(
        title="Elvara Intent Server",
        version="0.1.0",
        description="Single-chain intent collector, optimizer runner, and relayer for the Elvara PoC.",
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        return intent_service.health()

    @app.post("/rebalance/run")
    def run_rebalance(request: RebalanceRunRequest) -> dict[str, object]:
        try:
            return intent_service.run_rebalance(
                RunIntentOptions(
                    strategy=request.strategy,
                    epoch=request.epoch,
                    expiry_seconds=request.expiry_seconds,
                    submit_onchain=request.submit_onchain,
                    use_sample=request.use_sample,
                    use_today=request.use_today,
                    weights_mode=request.weights_mode,
                )
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get("/intents/latest")
    def latest_intent() -> dict[str, object]:
        payload = intent_service.get_latest_intent()
        if payload is None:
            raise HTTPException(status_code=404, detail="No intents have been created yet.")
        return payload

    @app.get("/intents/{epoch}")
    def get_intent(epoch: int) -> dict[str, object]:
        payload = intent_service.get_intent(epoch)
        if payload is None:
            raise HTTPException(status_code=404, detail=f"No intent found for epoch {epoch}.")
        return payload

    return app


app = create_app()


def main() -> None:
    uvicorn.run(
        "elvara_offchain.server:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
    )


if __name__ == "__main__":
    main()
