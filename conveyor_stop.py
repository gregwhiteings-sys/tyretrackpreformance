"""Optional stop-only Modbus TCP client; no start or output-reset operation."""
import ipaddress
import json
import secrets
import socket
import struct

def load_config(path):
    if not path.exists():
        return {'mode':'off'}
    cfg=json.loads(path.read_text(encoding='utf-8'))
    mode=cfg.get('mode','off')
    if mode not in ('off','simulation','live'):
        raise ValueError('Invalid conveyor stop mode')
    if mode=='live':
        addr=ipaddress.IPv4Address(cfg['host'])
        if not addr.is_private or addr.is_loopback or addr.is_unspecified or addr.is_link_local or addr.is_multicast:
            raise ValueError('Relay requires a private site IPv4 address')
        for key,lo,hi in [('coil',0,65535),('unit_id',0,255)]:
            if type(cfg.get(key)) is not int or not lo<=cfg[key]<=hi:
                raise ValueError('Invalid Modbus '+key)
    return cfg

def stop_request(cfg, connect=socket.create_connection):
    if cfg['mode']=='simulation':
        return 'SIMULATION: stop request recorded; no relay contacted'
    if cfg['mode']!='live':
        return 'OFF: no stop request sent'
    tx=secrets.randbelow(65536)
    pdu=struct.pack('>BHH',5,cfg['coil'],0xff00)
    mbap=struct.pack('>HHHB',tx,0,len(pdu)+1,cfg['unit_id'])
    with connect((cfg['host'],502),timeout=1.0) as sock:
        sock.settimeout(1.0)
        def read(n):
            b=b''
            while len(b)<n:
                chunk=sock.recv(n-len(b))
                if not chunk:raise OSError('Relay closed the connection')
                b+=chunk
            return b
        sock.sendall(mbap+pdu)
        transaction,protocol,length,unit=struct.unpack('>HHHB',read(7))
        if (transaction,protocol,unit)!=(tx,0,cfg['unit_id']) or length not in (3,6):
            raise OSError('Invalid relay response header')
        reply=read(length-1)
        if reply!=pdu:
            raise OSError('Relay did not acknowledge stop output: '+reply.hex())
    return 'Stop output acknowledged by relay; belt motion unverified'
