import struct
from conveyor_stop import stop_request
cfg={'mode':'live','host':'192.168.10.50','coil':42,'unit_id':1}
class FakeRelay:
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def settimeout(self,n):pass
    def sendall(self,data):
        tx,p,ln,u,fc,coil,value=struct.unpack('>HHHBBHH',data)
        assert (p,ln,u,fc,coil,value)==(0,6,1,5,42,0xff00)
        self.reply=data if not bad else data[:8]+bytes(4)
    def recv(self,n):
        n=min(n,2)
        part,self.reply=self.reply[:n],self.reply[n:]
        return part
def connect(endpoint,timeout):
    assert endpoint==('192.168.10.50',502)
    return FakeRelay()
def forbidden(*a,**k):raise AssertionError('Unexpected network request')
assert 'SIMULATION' in stop_request({'mode':'simulation'},forbidden)
assert 'OFF' in stop_request({'mode':'off'},forbidden)
bad=False
assert 'motion unverified' in stop_request(cfg,connect)
bad=True
try:stop_request(cfg,connect)
except OSError:pass
else:raise AssertionError('Mismatched reply accepted')
print('PASS: stop-only coil write, fragmented acknowledgement, invalid reply, off and simulation isolation')
