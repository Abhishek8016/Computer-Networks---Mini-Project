# tests/test_all.py — run: python3 tests/test_all.py
import os,sys,time,statistics
sys.path.insert(0,os.path.join(os.path.dirname(__file__),"..","src"))
from protocol import Pkt,PKT_SIZE,DELTA,REQ,RESP,PING,PONG,now,to_unix,to_ntp
from client import correct,STEP,MAX_PPM
import client as cl

ok=fail=0
def check(name,cond): 
    global ok,fail
    if cond: print(f"  pass  {name}"); ok+=1
    else:    print(f"  FAIL  {name}"); fail+=1

# Timestamps
print("-- timestamps")
ts=time.time(); s,f=to_ntp(ts)
check("unix->ntp->unix",    abs(to_unix(s,f)-ts)<1e-6)
check("ntp epoch = unix 0", abs(to_unix(DELTA,0))<1e-9)
_,fr=now(); check("fraction range", 0<=fr<2**32)

# Packet
print("-- packet")
p=Pkt(); p.mode=RESP; p.seq=99; p.t1s=3_900_000_000; p.rd=-7
r=Pkt.unpack(p.pack())
check("48 bytes",     len(p.pack())==PKT_SIZE)
check("mode",         r.mode==RESP)
check("seq",          r.seq==99)
check("t1s",          r.t1s==3_900_000_000)
check("signed rd",    r.rd==-7)
for m in (REQ,RESP,PING,PONG):
    q=Pkt(); q.mode=m; check(f"mode {m}", Pkt.unpack(q.pack()).mode==m)
try:    Pkt.unpack(b"\x00"*5); check("bad size raises",False)
except: check("bad size raises",True)

# Offset and RTT math
print("-- offset & rtt")
B=1000.0
def mkpkt(t1,t2,t3):
    p=Pkt(); p.mode=RESP
    p.t1s,p.t1f=to_ntp(t1); p.t2s,p.t2f=to_ntp(t2); p.t3s,p.t3f=to_ntp(t3); return p

sym=mkpkt(B,B+.01,B+.015)
check("symmetric offset=0",   abs(sym.offset(B+.025))<1e-5)
check("symmetric rtt=20ms",   abs(sym.rtt(B+.025)-.02)<1e-5)
asy=mkpkt(B,B+.02,B+.025)
check("asymmetric offset=7.5ms", abs(asy.offset(B+.03)-.0075)<1e-5)
for ms in [5,10,50]:
    p2=mkpkt(B,B+ms/2000,B+ms/2000+.001); check(f"rtt>=0 {ms}ms", p2.rtt(B+ms/1000)>=0)

# Clock correction
print("-- clock correction")
cl.step_off=cl.freq=0.0; cl.last_t=time.time()
check("large->step", correct(STEP+.01)=="step")
cl.step_off=cl.freq=0.0
check("small->slew", correct(STEP-.01)=="slew")
cl.step_off=cl.freq=0.0
correct(0.5); check("step stored", abs(cl.step_off-0.5)<1e-9)
cl.step_off=cl.freq=0.0
for _ in range(500): correct(1.0)
check("freq clamped", abs(cl.freq)<=MAX_PPM+1e-10)

print(f"\n{ok} passed  {fail} failed")
if fail: sys.exit(1)
