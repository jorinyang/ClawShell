#!/usr/bin/env python3
"""
MemOS Local Bridge — Python HTTP server on port 18800
桥接 MemPalace SQLite + Wukong MCP 记忆调用。

提供端点:
  GET  /health              — 健康检查
  GET  /api/search?q=...    — 搜索记忆
  POST /api/memories        — 写入记忆
  GET  /api/stats           — 统计信息
"""

import json
import sqlite3
import os
import time
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DB_PATH = Path(os.environ.get("MEMPALACE_PATH", os.path.expanduser("~/.mempalace"))) / "knowledge_graph.sqlite3"
PORT = int(os.environ.get("MEMOS_LOCAL_PORT", "18800"))


class MemOSHandler(BaseHTTPRequestHandler):
    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        if path == "/health":
            self._json({
                "status": "healthy",
                "service": "memos-local-bridge",
                "version": "1.12.0",
                "db_path": str(DB_PATH),
                "db_exists": DB_PATH.exists(),
                "uptime": round(time.time() - START_TIME, 1),
            })

        elif path == "/api/search":
            q = params.get("q", [""])[0]
            limit = int(params.get("limit", ["10"])[0])
            results = []
            if DB_PATH.exists() and q:
                try:
                    conn = sqlite3.connect(str(DB_PATH))
                    rows = conn.execute(
                        "SELECT name, type, properties, created_at FROM entities "
                        "WHERE name LIKE ? OR properties LIKE ? LIMIT ?",
                        (f"%{q}%", f"%{q}%", limit)
                    ).fetchall()
                    for name, etype, props, created_at in rows:
                        results.append({
                            "source": "mempalace",
                            "key": name,
                            "type": etype,
                            "content": props[:200],
                            "created_at": created_at,
                        })
                    conn.close()
                except Exception:
                    pass
            self._json({"query": q, "total": len(results), "results": results})

        elif path == "/api/stats":
            stats = {"mempalace": {"entries": 0}, "memos_local": "running"}
            if DB_PATH.exists():
                try:
                    conn = sqlite3.connect(str(DB_PATH))
                    stats["mempalace"]["entries"] = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
                    conn.close()
                except Exception:
                    pass
            self._json(stats)

        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self._read_body()

        if path == "/api/memories":
            content = body.get("content", "")
            category = body.get("category", "general")
            if not content:
                return self._json({"error": "content required"}, 400)

            stored = False
            if DB_PATH.exists():
                try:
                    conn = sqlite3.connect(str(DB_PATH))
                    conn.execute(
                        "INSERT INTO entities (name, type, properties, created_at) VALUES (?, ?, ?, datetime('now'))",
                        (f"memos_{category}", "memory", content),
                    )
                    conn.commit()
                    conn.close()
                    stored = True
                except Exception:
                    pass

            self._json({"stored": stored, "content_preview": content[:100]})

        else:
            self._json({"error": "not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def log_message(self, format, *args):
        pass  # Quiet


START_TIME = time.time()

if __name__ == "__main__":
    server = HTTPServer(("127.0.0.1", PORT), MemOSHandler)
    print(f"[memos-local] Started on http://127.0.0.1:{PORT}")
    print(f"[memos-local] DB: {DB_PATH} (exists={DB_PATH.exists()})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[memos-local] Shutting down")
        server.shutdown()
