from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from core.security import require_api_key
from core.websocket import manager

router = APIRouter(
    prefix="/progress",
    tags=["Progress"],
    dependencies=[Depends(require_api_key)],
)


@router.websocket("")
@router.websocket("/")
async def websocket_endpoint(websocket: WebSocket):

    await manager.connect(websocket)

    try:
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        manager.disconnect(websocket)
