#!/usr/bin/env python3
"""
Simple HTTP server for testing the F-Droid repo locally.
"""

import http.server
import socketserver
import os
from pathlib import Path

PORT = 8080
DIRECTORY = "repo"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def end_headers(self):
        # Add CORS headers for testing
        self.send_header('Access-Control-Allow-Origin', '*')
        super().end_headers()

if __name__ == "__main__":
    os.chdir(Path(__file__).parent)
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"Serving F-Droid repo at http://localhost:{PORT}")
        print(f"index-v2.json: http://localhost:{PORT}/index-v2.json")
        print(f"index-v1.json: http://localhost:{PORT}/index-v1.json")
        print("Press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")
