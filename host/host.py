import asyncio
import argparse
import random
import json
import time
from pathlib import Path
from common.protocol import send_json, read_json

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True, parents=True)

class ClientState:
    def __init__(self):
        self.high_ack = -1
        self.node_id = None

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter, args) -> None:
    peer = writer.get_extra_info("peername")
    state = ClientState()
    last_cfg_push = 0.0
    try:
        while True:
            # Fault injection: random close
            if args.faults and random.random() < args.drop_prob:
                writer.close()
                await writer.wait_closed()
                print(f"[HOST] Dropped connection {peer} (fault injection)")
                return

            msg = await read_json(reader)
            if msg is None:
                # Client closed
                print(f"[HOST] {peer} disconnected")
                return

            # Log delay if configured
            if args.ack_delay_ms > 0:
                await asyncio.sleep(args.ack_delay_ms / 1000.0)

            # Capture node id and logging path
            nid = msg.get("node_id", "UNKNOWN")
            if state.node_id is None and nid:
                state.node_id = nid
                print(f"[HOST] Client identified as {nid} from {peer}")

            # Persist message
            logfile = LOG_DIR / f"{nid}.jsonl"
            with logfile.open("a", encoding="utf-8") as f:
                f.write(json.dumps(msg, separators=(",", ":")) + "\n")

            # Maintain high-watermark ack (by seq)
            seq = msg.get("seq", -1)
            if seq is not None and seq > state.high_ack:
                state.high_ack = seq

            # Occasionally push a config update
            now = time.time()
            if args.push_config_every_s > 0 and now - last_cfg_push > args.push_config_every_s:
                last_cfg_push = now
                # tighten anomaly threshold randomly to demo runtime change
                new_z = random.choice([2.5, 3.0, 3.5])
                cfg = {
                    "type": "config_update",
                    "cfg_version": int(now),
                    "config": {"anomaly_z": new_z, "window": 120, "buffer_max": 5000}
                }
                await send_json(writer, cfg)

            # ACK
            ack = {"type": "ack", "ack_seq": state.high_ack}
            await send_json(writer, ack)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"[HOST] Error with {peer}: {e!r}")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
    
async def main():
    parser = argparse.ArgumentParser(description="MI Diagnostics Host")
    parser.add_argument("--port", type=int, default=9000)
    parser.add_argument("--bind", default="0.0.0.0")
    args = parser.parse_args()
    print(f"Starting server on {args.bind}:{args.port}")

    server = await asyncio.start_server(lambda r, w: handle_client(r, w, args), host=args.bind, port=args.port)
    addr = ", ".join(str(sock.getsockname()) for sock in server.sockets)
    print(f"[HOST] Listening on {addr}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())