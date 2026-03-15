"""
WebSocket-based PTY terminal for product workspaces.

Architecture:
  Browser (xterm.js) <--WebSocket--> FastAPI (PTY handler) <--pty--> bash

Protocol:
  - Binary WS frames: terminal I/O (stdin/stdout)
  - Text WS frames: JSON control messages
    - {"type":"resize","cols":80,"rows":24}
    - {"type":"ping"}
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

# Limits
MAX_TERMINALS_PER_PRODUCT = 3
IDLE_TIMEOUT_SEC = 30 * 60  # 30 minutes
READ_SIZE = 4096

# Track active terminals per product
_active_terminals: dict[str, int] = {}


def _resize_pty(fd: int, rows: int, cols: int) -> None:
    """Send TIOCSWINSZ to resize the PTY."""
    winsize = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)


async def _get_product_env(db: AsyncSession, product_id: uuid.UUID) -> dict[str, str]:
    """Build env dict with product secrets injected."""
    env = os.environ.copy()
    env["TERM"] = "xterm-256color"
    env["LANG"] = "en_US.UTF-8"

    # Load product secrets
    try:
        from app.models.product_secret import ProductSecret
        result = await db.execute(
            select(ProductSecret).where(ProductSecret.product_id == product_id)
        )
        for secret in result.scalars().all():
            env[secret.key] = secret.value
    except Exception as exc:
        logger.warning("Failed to load product secrets: %s", exc)

    return env


@router.websocket("/products/{product_id}/terminal")
async def websocket_terminal(
    websocket: WebSocket,
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    await websocket.accept()

    # Validate product exists and get workspace path
    from app.services.product_service import get_product
    try:
        product = await get_product(db, product_id)
    except Exception:
        await websocket.send_json({"type": "error", "error": "Product not found"})
        await websocket.close(code=4004)
        return

    workspace = product.workspace_path
    if not workspace or not os.path.isdir(workspace):
        await websocket.send_json({"type": "error", "error": "Workspace not found"})
        await websocket.close(code=4004)
        return

    # Check terminal limit
    pid_key = str(product_id)
    count = _active_terminals.get(pid_key, 0)
    if count >= MAX_TERMINALS_PER_PRODUCT:
        await websocket.send_json({"type": "error", "error": f"Max {MAX_TERMINALS_PER_PRODUCT} terminals per product"})
        await websocket.close(code=4008)
        return

    _active_terminals[pid_key] = count + 1

    # Build environment with product secrets
    env = await _get_product_env(db, product_id)

    # Fork PTY
    master_fd, slave_fd = pty.openpty()

    # Set initial size
    _resize_pty(master_fd, 24, 80)

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
    except Exception as exc:
        os.close(master_fd)
        os.close(slave_fd)
        _active_terminals[pid_key] = max(0, _active_terminals.get(pid_key, 1) - 1)
        await websocket.send_json({"type": "error", "error": f"Failed to start shell: {exc}"})
        await websocket.close(code=4500)
        return

    # Close slave in parent — child has it
    os.close(slave_fd)

    # Make master_fd non-blocking for asyncio
    os.set_blocking(master_fd, False)

    loop = asyncio.get_event_loop()
    idle_timer = [asyncio.get_event_loop().time()]  # mutable for closure

    async def pty_to_ws():
        """Read PTY output and send to WebSocket as binary."""
        try:
            while True:
                try:
                    data = await loop.run_in_executor(
                        None, _blocking_read, master_fd
                    )
                    if not data:
                        break
                    if websocket.client_state != WebSocketState.CONNECTED:
                        break
                    await websocket.send_bytes(data)
                    idle_timer[0] = loop.time()
                except OSError:
                    break
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug("pty_to_ws error: %s", exc)

    async def ws_to_pty():
        """Read WebSocket input and write to PTY."""
        try:
            while True:
                msg = await websocket.receive()

                if msg.get("type") == "websocket.disconnect":
                    break

                idle_timer[0] = loop.time()

                if "bytes" in msg and msg["bytes"]:
                    os.write(master_fd, msg["bytes"])
                elif "text" in msg and msg["text"]:
                    import json
                    try:
                        ctrl = json.loads(msg["text"])
                        if ctrl.get("type") == "resize":
                            cols = ctrl.get("cols", 80)
                            rows = ctrl.get("rows", 24)
                            _resize_pty(master_fd, rows, cols)
                        elif ctrl.get("type") == "ping":
                            await websocket.send_json({"type": "pong"})
                    except (json.JSONDecodeError, ValueError):
                        # Plain text input — write as bytes
                        os.write(master_fd, msg["text"].encode())
        except WebSocketDisconnect:
            pass
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug("ws_to_pty error: %s", exc)

    async def idle_watchdog():
        """Kill terminal after IDLE_TIMEOUT_SEC of inactivity."""
        try:
            while True:
                await asyncio.sleep(60)
                elapsed = loop.time() - idle_timer[0]
                if elapsed > IDLE_TIMEOUT_SEC:
                    logger.info("Terminal idle timeout for product %s", product_id)
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
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    finally:
        # Cleanup PTY
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
        logger.info("Terminal closed for product %s", product_id)


def _blocking_read(fd: int) -> bytes:
    """Blocking read from PTY fd (runs in thread executor)."""
    import select as _select
    # Wait up to 1 second for data
    readable, _, _ = _select.select([fd], [], [], 1.0)
    if readable:
        try:
            return os.read(fd, READ_SIZE)
        except OSError:
            return b""
    return b""  # timeout, return empty to allow cancellation check
