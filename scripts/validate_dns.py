"""Validate CoreDNS on a free loopback test port; never change host DNS."""
import ipaddress
from pathlib import Path
import re
import secrets
import socket
import struct
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
name='vmm-dns-validation-'+secrets.token_hex(3)

def docker(args):
    result=subprocess.run(['docker']+args,capture_output=True,text=True,timeout=180)
    if result.returncode:raise RuntimeError(result.stderr[-1500:])
    return result.stdout

def query(domain,qtype=1):
    ident=secrets.randbelow(65536)
    wire=b''.join(bytes([len(p)])+p.encode() for p in domain.split('.'))+b'\0'
    packet=struct.pack('!HHHHHH',ident,0x100,1,0,0,0)+wire+struct.pack('!HH',qtype,1)
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
        sock.settimeout(5);sock.sendto(packet,('127.0.0.1',11053));data,_=sock.recvfrom(4096)
    header=struct.unpack('!HHHHHH',data[:12])
    assert header[0]==ident and header[1]&15==0,'DNS response failed'
    return header,data

if __name__=='__main__':
    try:
        docker(['run','-d','--name',name,'-p','127.0.0.1:11053:53/udp','--mount','type=bind,source='+str(ROOT/'infra'/'Corefile')+',target=/etc/coredns/Corefile,readonly','coredns/coredns:1.12.0','-conf','/etc/coredns/Corefile'])
        time.sleep(2)
        ip=re.search(r'60 IN A ([0-9.]+)',(ROOT/'infra'/'Corefile').read_text()).group(1)
        for domain in ('vmm.test','demo.vmm.test','nested.demo.vmm.test'):
            header,data=query(domain)
            assert header[3]>0 and data[-4:]==ipaddress.IPv4Address(ip).packed
        header,_=query('demo.vmm.test',28)
        assert header[3]==0
        print('PASS CoreDNS: Basisdomain, Wildcard, verschachtelte Subdomain und AAAA-Antwort.',flush=True)
    finally:
        try:docker(['rm','-f',name])
        except Exception:pass
