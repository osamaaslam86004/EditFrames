from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from core.websocket import manager
from core.security import require_api_key

router = APIRouter(
    prefix="/api/v1/progress",
    tags=["Progress"],
    dependencies=[Depends(require_api_key)],
)


@router.websocket("")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
