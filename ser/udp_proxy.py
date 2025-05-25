#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# UDP Port Forwarding Proxy
# Memungkinkan akses ke berbagai port di server melalui satu koneksi WireGuard

import socket
import threading
import time
import logging
import argparse
import sys
import json
import signal
import os

# Konfigurasi logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('udp_proxy')

# Class utama untuk UDP Proxy
class UDPProxy:
    def __init__(self, config_file=None, wireguard_endpoint=None):
        self.running = True
        self.forwarders = {}
        self.threads = []
        
        # Muat konfigurasi
        if config_file:
            self.load_config(config_file)
        elif wireguard_endpoint:
            self.wireguard_endpoint = wireguard_endpoint
            self.port_mappings = {}
        else:
            logger.error("Dibutuhkan file konfigurasi atau endpoint WireGuard")
            sys.exit(1)
            
        # Setup signal handler untuk menangani Ctrl+C
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def load_config(self, config_file):
        """Muat konfigurasi dari file JSON"""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                
            self.wireguard_endpoint = config.get('wireguard_endpoint', '')
            if not self.wireguard_endpoint:
                logger.error("Konfigurasi harus berisi wireguard_endpoint")
                sys.exit(1)
                
            self.port_mappings = config.get('port_mappings', {})
            
            # Konversi string port ke integer
            converted_mappings = {}
            for local_port, remote_port in self.port_mappings.items():
                converted_mappings[int(local_port)] = int(remote_port)
            self.port_mappings = converted_mappings
            
            logger.info(f"Konfigurasi dimuat: {len(self.port_mappings)} port mappings")
            
        except Exception as e:
            logger.error(f"Gagal memuat konfigurasi: {str(e)}")
            sys.exit(1)
    
    def save_config(self, config_file):
        """Simpan konfigurasi ke file JSON"""
        config = {
            'wireguard_endpoint': self.wireguard_endpoint,
            'port_mappings': self.port_mappings
        }
        
        try:
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=4)
            logger.info(f"Konfigurasi disimpan ke {config_file}")
        except Exception as e:
            logger.error(f"Gagal menyimpan konfigurasi: {str(e)}")
    
    def add_port_mapping(self, local_port, remote_port):
        """Tambahkan pemetaan port baru"""
        local_port, remote_port = int(local_port), int(remote_port)
        self.port_mappings[local_port] = remote_port
        logger.info(f"Ditambahkan mapping: {local_port} -> {remote_port}")
        
        # Mulai forwarder untuk mapping baru jika proxy sedang berjalan
        if self.running and local_port not in self.forwarders:
            self.start_forwarder(local_port, remote_port)
    
    def remove_port_mapping(self, local_port):
        """Hapus pemetaan port"""
        local_port = int(local_port)
        if local_port in self.port_mappings:
            del self.port_mappings[local_port]
            logger.info(f"Dihapus mapping untuk port {local_port}")
            
            # Hentikan forwarder jika sedang berjalan
            if local_port in self.forwarders:
                self.forwarders[local_port] = False
                # Tidak ada cara untuk memaksa socket keluar dari recvfrom
                # Forwarder akan berhenti pada iterasi berikutnya
    
    def start_forwarder(self, local_port, remote_port):
        """Mulai thread untuk forwarding port tertentu"""
        if local_port in self.forwarders:
            logger.warning(f"Forwarder untuk port {local_port} sudah berjalan")
            return
            
        self.forwarders[local_port] = True
        thread = threading.Thread(
            target=self.port_forwarder,
            args=(local_port, remote_port),
            daemon=True
        )
        thread.start()
        self.threads.append(thread)
        logger.info(f"Dimulai forwarder: {local_port} -> {remote_port}")
    
    def port_forwarder(self, local_port, remote_port):
        """Thread forwarding untuk port tertentu"""
        # Parse wireguard endpoint
        try:
            wg_host, wg_port = self.wireguard_endpoint.split(':')
            wg_port = int(wg_port)
            wg_addr = (wg_host, wg_port)
        except Exception as e:
            logger.error(f"Format endpoint tidak valid: {str(e)}")
            return
            
        # Buat socket untuk menerima koneksi lokal
        try:
            local_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            local_socket.bind(('0.0.0.0', local_port))
            local_socket.settimeout(1.0)  # Timeout untuk pengecekan running flag
        except Exception as e:
            logger.error(f"Gagal membuat socket lokal pada port {local_port}: {str(e)}")
            return
            
        # Buat socket untuk meneruskan data ke server WireGuard
        remote_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # Client tracking untuk membedakan koneksi berbeda ke port yang sama
        clients = {}
        
        logger.info(f"Forwarder aktif: 0.0.0.0:{local_port} -> {wg_host}:{remote_port}")
        
        try:
            while self.forwarders.get(local_port, False):
                try:
                    # Terima data dari klien lokal
                    data, client_addr = local_socket.recvfrom(4096)
                    
                    # Teruskan ke server WireGuard
                    remote_socket.sendto(data, (wg_host, remote_port))
                    
                    # Catat client untuk routing balik
                    clients[client_addr] = time.time()
                    
                    # Proses respons
                    remote_socket.settimeout(0.5)
                    try:
                        response, _ = remote_socket.recvfrom(4096)
                        local_socket.sendto(response, client_addr)
                    except socket.timeout:
                        # Tidak ada respons, lanjutkan
                        pass
                        
                except socket.timeout:
                    # Timeout normal, lanjutkan loop
                    continue
                    
                # Bersihkan clients yang sudah lama tidak aktif (5 menit)
                now = time.time()
                expired = [addr for addr, timestamp in clients.items() if now - timestamp > 300]
                for addr in expired:
                    del clients[addr]
                    
        except Exception as e:
            if self.forwarders.get(local_port, False):  # Hanya log error jika bukan shutdown normal
                logger.error(f"Error pada forwarder {local_port}: {str(e)}")
        finally:
            local_socket.close()
            remote_socket.close()
            if local_port in self.forwarders:
                del self.forwarders[local_port]
            logger.info(f"Forwarder berhenti: port {local_port}")
    
    def start(self):
        """Mulai semua forwarder"""
        logger.info("Memulai UDP Proxy...")
        self.running = True
        
        for local_port, remote_port in self.port_mappings.items():
            self.start_forwarder(local_port, remote_port)
        
        logger.info(f"UDP Proxy berjalan dengan {len(self.port_mappings)} port mappings")
        
        # Tunggu semua thread berhenti
        while self.running:
            time.sleep(1)
    
    def stop(self):
        """Hentikan semua forwarder"""
        logger.info("Menghentikan UDP Proxy...")
        self.running = False
        
        # Tandai semua forwarder untuk berhenti
        for port in list(self.forwarders.keys()):
            self.forwarders[port] = False
        
        # Tunggu semua thread berhenti
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=2)
        
        logger.info("UDP Proxy berhenti")
    
    def signal_handler(self, sig, frame):
        """Handler untuk menangkap sinyal interrupt"""
        logger.info("Menangkap sinyal, menghentikan...")
        self.stop()

def main():
    """Fungsi utama"""
    parser = argparse.ArgumentParser(description='UDP Port Forwarding Proxy untuk WireGuard')
    parser.add_argument('-c', '--config', help='File konfigurasi JSON')
    parser.add_argument('-e', '--endpoint', help='WireGuard endpoint (host:port)')
    parser.add_argument('-a', '--add', help='Tambahkan mapping port (local_port:remote_port)')
    parser.add_argument('-r', '--remove', help='Hapus mapping port (local_port)')
    parser.add_argument('-s', '--save', help='Simpan konfigurasi ke file')
    parser.add_argument('-l', '--list', action='store_true', help='Tampilkan daftar port mappings')
    parser.add_argument('-v', '--verbose', action='store_true', help='Output verbose')
    
    args = parser.parse_args()
    
    # Set level logging
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Inisialisasi proxy
    proxy = UDPProxy(config_file=args.config, wireguard_endpoint=args.endpoint)
    
    # Tambahkan port mapping jika diminta
    if args.add:
        try:
            local_port, remote_port = args.add.split(':')
            proxy.add_port_mapping(int(local_port), int(remote_port))
        except Exception as e:
            logger.error(f"Format mapping port tidak valid: {str(e)}")
            sys.exit(1)
    
    # Hapus port mapping jika diminta
    if args.remove:
        try:
            proxy.remove_port_mapping(int(args.remove))
        except Exception as e:
            logger.error(f"Format port tidak valid: {str(e)}")
            sys.exit(1)
    
    # Tampilkan daftar port mappings jika diminta
    if args.list:
        print("Port Mappings:")
        for local_port, remote_port in proxy.port_mappings.items():
            print(f"  {local_port} -> {remote_port}")
    
    # Simpan konfigurasi jika diminta
    if args.save:
        proxy.save_config(args.save)
    
    # Mulai proxy jika tidak ada opsi manajemen yang diminta
    if not (args.add or args.remove or args.list or args.save):
        try:
            proxy.start()
        except KeyboardInterrupt:
            proxy.stop()

if __name__ == "__main__":
    main()