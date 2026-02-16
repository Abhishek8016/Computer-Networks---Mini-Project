# protocol.py — 48-byte NTP-style packet, timestamps, offset/rtt math
import struct, time

UDP_PORT=12300; SSL_PORT=12301; PKT_SIZE=48
DELTA=2_208_988_800        # gap: NTP starts 1900, Unix starts 1970
FMT="!IIIIIIIIIIiI"       # 12 x 4-byte words = 48 bytes total

REQ=1; RESP=2; PING=3; PONG=4

def now():        t=time.time(); return int(t)+DELTA, int((t%1)*2**32)
def to_unix(s,f): return (s-DELTA)+f/2**32
def to_ntp(t):    return int(t)+DELTA, int((t%1)*2**32)

class Pkt:
    def __init__(self):
        self.mode=REQ; self.seq=0
        self.t1s=self.t1f=self.t2s=self.t2f=0
        self.t3s=self.t3f=self.t4s=self.t4f=0
        self.rd=self.disp=0

    def pack(self):
        h=(self.mode&0xFF)<<24
        return struct.pack(FMT,h,self.seq,
            self.t1s,self.t1f,self.t2s,self.t2f,
            self.t3s,self.t3f,self.t4s,self.t4f,self.rd,self.disp)

    @classmethod
    def unpack(cls,d):
        if len(d)!=PKT_SIZE: raise ValueError(f"bad size {len(d)}")
        h,seq,t1s,t1f,t2s,t2f,t3s,t3f,t4s,t4f,rd,di=struct.unpack(FMT,d)
        p=cls(); p.mode=(h>>24)&0xFF; p.seq=seq
        p.t1s,p.t1f=t1s,t1f; p.t2s,p.t2f=t2s,t2f
        p.t3s,p.t3f=t3s,t3f; p.t4s,p.t4f=t4s,t4f; p.rd=rd; p.disp=di
        return p

    def offset(self,t4):
        T1,T2,T3=to_unix(self.t1s,self.t1f),to_unix(self.t2s,self.t2f),to_unix(self.t3s,self.t3f)
        return ((T2-T1)+(T3-t4))/2   # θ = ((T2-T1)+(T3-T4))/2

    def rtt(self,t4):
        T1,T2,T3=to_unix(self.t1s,self.t1f),to_unix(self.t2s,self.t2f),to_unix(self.t3s,self.t3f)
        return (t4-T1)-(T3-T2)       # δ = (T4-T1)-(T3-T2)
