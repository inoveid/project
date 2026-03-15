"""
WebSocket-based PTY terminal for product workspaces.
"""
from __future__ import annotations

import asyncio
import fcntl
import logging
import os
import pty
import signal
import struct
import termios
import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.websockets import WebSocketState

from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_TERMINALS_PER_PRODUCT = 3
IDLE_TIMEOUT_SEC = 30 * 60
READ_SIZE = 4096

_active_terminals: dict[str, int] = {}


def _resize_pty(fd: int, rows: int, cols: int) -> None:
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


async def _get_product_env(db: AsyncSession, product_id: uuid.UUID) -> dict[str, str]:
    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    env["LANG"] = "en_US.UTF-8"
    try:
        from app.models.product_secret import ProductSecret
        result = await db.execute(
            select(ProductSecret).where(ProductSecret.product_id == product_id)
        )
        for secret in result.scalars().all():
            env[secret.key] = secret.value
    except Exception as exc:
        logger.warning("[terminal] Failed to load product secrets: %s", exc)
    return env


@router.websocket("/products/{product_id}/terminal")
async def websocket_terminal(
    websocket: WebSocket,
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    logger.info("[terminal] WS connect request for product %s", product_id)
    await websocket.accept()
    logger.info("[terminal] WS accepted for product %s", product_id)

    from app.services.product_service import get_product
    try:
        product = await get_product(db, product_id)
    except Exception as exc:
        logger.error("[terminal] product not found: %s, error: %s", product_id, exc)
        await websocket.send_json({"type": "error", "error": "Product not found"})
        await websocket.close(code=4004)
        return

    workspace = product.workspace_path
    logger.info("[terminal] workspace: %s, exists: %s", workspace, os.path.isdir(workspace) if workspace else False)
    if not workspace or not os.path.isdir(workspace):
        await websocket.send_json({"type": "error", "error": "Workspace not found"})
        await websocket.close(code=4004)
        return

    pid_key = str(product_id)
    count = _active_terminals.get(pid_key, 0)
    logger.info("[terminal] active terminals for %s: %d", pid_key, count)
    if count >= MAX_TERMINALS_PER_PRODUCT:
        await websocket.send_json({"type": "error", "error": f"Max {MAX_TERMINALS_PER_PRODUCT} terminals"})
        await websocket.close(code=4008)
        return

    _active_terminals[pid_key] = count + 1

    env = await _get_product_env(db, product_id)

    master_fd, slave_fd = pty.openpty()
    _resize_pty(master_fd, 24, 80)
    logger.info("[terminal] PTY created, master_fd=%d, slave_fd=%d", master_fd, slave_fd)

    try:
        proc = await asyncio.create_subprocess_exec(
            "/bin/bash",
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            cwd=workspace,
            env=env,
            preexec_fn=os.setsid,
        )
        logger.info("[terminal] bash started, pid=%d", proc.pid)
    except Exception as exc:
        logger.error("[terminal] failed to start bash: %s", exc)
        os.close(master_fd)
        os.close(slave_fd)
        _active_terminals[pid_key] = max(0, _active_terminals.get(pid_key, 1) - 1)
        await websocket.send_json({"type": "error", "error": f"Failed to start shell: {exc}"})
        await websocket.close(code=4500)
        return

    os.close(slave_fd)
    os.set_blocking(master_fd, False)

    loop = asyncio.get_event_loop()
    idle_timer = [loop.time()]

    async def pty_to_ws():
        """Read PTY output → send to WS as binary."""
        read_count = 0
        try:
            while True:
                try:
                    data = await loop.run_in_executor(None, _blocking_read, master_fd)
                    if not data:
                        continue  # timeout, not EOF
                    if websocket.client_state != WebSocketState.CONNECTED:
                        logger.info("[terminal] pty_to_ws: WS no longer connected")
                        break
                    read_count += 1
                    if read_count <= 5:
                        logger.info("[terminal] pty→ws #%d, %d bytes: %s", read_count, len(data), repr(data[:100]))
                    await websocket.send_bytes(data)
                    idle_timer[0] = loop.time()
                except OSError as e:
                    logger.info("[terminal] pty_to_ws OSError: %s", e)
                    break
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("[terminal] pty_to_ws error: %s", exc)
        logger.info("[terminal] pty_to_ws ended after %d reads", read_count)

    async def ws_to_pty():
        """Read WS input → write to PTY."""
        write_count = 0
        try:
            while True:
                msg = await websocket.receive()
                msg_type = msg.get("type", "?")

                if msg_type == "websocket.disconnect":
                    logger.info("[terminal] ws_to_pty: disconnect received")
                    break

                idle_timer[0] = loop.time()

                if "bytes" in msg and msg["bytes"]:
                    write_count += 1
                    data = msg["bytes"]
                    logger.info("[terminal] ws→pty #%d, %d bytes: %s", write_count, len(data), repr(data[:50]))
                    os.write(master_fd, data)
                elif "text" in msg and msg["text"]:
                    import json
                    text = msg["text"]
                    logger.info("[terminal] ws→pty text: %s", text[:200])
                    try:
                        ctrl = json.loads(text)
                        if ctrl.get("type") == "resize":
                            cols = ctrl.get("cols", 80)
                            rows = ctrl.get("rows", 24)
                            logger.info("[terminal] resize: %dx%d", cols, rows)
                            _resize_pty(master_fd, rows, cols)
                        elif ctrl.get("type") == "ping":
                            await websocket.send_json({"type": "pong"})
                    except (json.JSONDecodeError, ValueError):
                        write_count += 1
                        logger.info("[terminal] ws→pty plain text #%d: %s", write_count, repr(text[:50]))
                        os.write(master_fd, text.encode())
                else:
                    logger.warning("[terminal] ws_to_pty: unknown msg type=%s, keys=%s", msg_type, list(msg.keys()))
        except WebSocketDisconnect:
            logger.info("[terminal] ws_to_pty: WebSocketDisconnect")
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("[terminal] ws_to_pty error: %s", exc)
        logger.info("[terminal] ws_to_pty ended after %d writes", write_count)

    async def idle_watchdog():
        try:
            while True:
                await asyncio.sleep(60)
                elapsed = loop.time() - idle_timer[0]
                if elapsed > IDLE_TIMEOUT_SEC:
                    logger.info("[terminal] idle timeout for %s", product_id)
                    try:
                        await websocket.send_json({"type": "idle_timeout"})
                    except Exception:
                        pass
                    break
        except asyncio.CancelledError:
            pass

    read_task = asyncio.create_task(pty_to_ws(), name=f"pty-read-{product_id}")
    write_task = asyncio.create_task(ws_to_pty(), name=f"pty-write-{product_id}")
    idle_task = asyncio.create_task(idle_watchdog(), name=f"pty-idle-{product_id}")

    try:
        done, pending = await asyncio.wait(
            [read_task, write_task, idle_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        logger.info("[terminal] first task completed: %s", [t.get_name() for t in done])
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    finally:
        try:
            os.kill(proc.pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            pass
        try:
            os.close(master_fd)
        except OSError:
            pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=3)
        except asyncio.TimeoutError:
            try:
                os.kill(proc.pid, signal.SIGKILL)
            except (OSError, ProcessLookupError):
                pass
        _active_terminals[pid_key] = max(0, _active_terminals.get(pid_key, 1) - 1)
        logger.info("[terminal] closed for product %s", product_id)


def _blocking_read(fd: int) -> bytes:
    import select as _select
    readable, _, _ = _select.select([fd], [], [], 1.0)
    if readable:
        try:
            return os.read(fd, READ_SIZE)
        except OSError:
            return b""
    return b""
