
import http.server
import socketserver
import os
import sys

# Get port from command line or use default
if len(sys.argv) > 1:
    try:
        PORT = int(sys.argv[1])
    except ValueError:
        PORT = 8000
else:
    PORT = 8000

class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Enable CORS to allow cross-origin requests
        self.send_header('Access-Control-Allow-Origin', '*')
        http.server.SimpleHTTPRequestHandler.end_headers(self)
        
    def do_GET(self):
        # Special case for root URL
        if self.path == '/' or self.path == '':
            self.path = '/index.html'
            
        # Remove any query parameters
        self.path = self.path.split('?')[0]
        
        # Try to serve the file
        return http.server.SimpleHTTPRequestHandler.do_GET(self)

# Change to the directory of this script
os.chdir(os.path.dirname(os.path.abspath(__file__)))

Handler = MyHttpRequestHandler
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving at http://localhost:{PORT}")
    print("Press Ctrl+C to stop the server")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        httpd.shutdown()
