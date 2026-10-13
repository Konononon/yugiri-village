import argparse
import json
import socket
import sys
from pathlib import Path


def call_blender(cmd_type: str, params: dict, host: str = "127.0.0.1", port: int = 9876) -> dict:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(180.0)
    try:
        sock.connect((host, port))
        payload = json.dumps({"type": cmd_type, "params": params}).encode("utf-8")
        sock.sendall(payload)
        chunks = []
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            try:
                data = b"".join(chunks)
                return json.loads(data.decode("utf-8"))
            except json.JSONDecodeError:
                continue
        if chunks:
            return json.loads(b"".join(chunks).decode("utf-8"))
        raise RuntimeError("No response from Blender MCP")
    finally:
        sock.close()


def call_unity(cmd_type: str, params: dict, host: str = "127.0.0.1", port: int = 9877) -> dict:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(180.0)
    try:
        sock.connect((host, port))
        payload = json.dumps({"type": cmd_type, "params": params}).encode("utf-8") + b"\n"
        sock.sendall(payload)
        chunks = []
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            if b"".join(chunks).endswith(b"\n"):
                break
        raw = b"".join(chunks).decode("utf-8", errors="replace").strip()
        return json.loads(raw)
    finally:
        sock.close()


def parse_val(v: str):
    if v.lower() == "true":
        return True
    if v.lower() == "false":
        return False
    if v.startswith("[") and v.endswith("]"):
        return [float(x.strip()) for x in v[1:-1].split(",") if x.strip()]
    try:
        if "." in v:
            return float(v)
        return int(v)
    except ValueError:
        return v


def main():
    parser = argparse.ArgumentParser(description="Direct MCP Socket Bridge CLI for Blender (9876) and Unity (9877)")
    parser.add_argument("target", choices=["blender", "unity"])
    parser.add_argument("command", help="Command type")
    parser.add_argument("--params", default="{}", help="JSON string of params")
    parser.add_argument("--kv", nargs="*", default=[], help="key=value pairs for params")
    parser.add_argument("--script", default="", help="Path to Python script for Blender execute_code")
    args = parser.parse_args()

    params = {}
    if args.params and args.params != "{}":
        params.update(json.loads(args.params))
    for item in args.kv:
        if "=" in item:
            k, v = item.split("=", 1)
            params[k] = parse_val(v)
    if args.script:
        params["code"] = Path(args.script).read_text(encoding="utf-8")

    if args.target == "blender":
        res = call_blender(args.command, params)
    else:
        res = call_unity(args.command, params)

    print(json.dumps(res, indent=2, ensure_ascii=False))
    if res.get("status") == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
