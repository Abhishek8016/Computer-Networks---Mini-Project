# client.py — clock sync client: offset, delay, step/slew drift correction
import argparse,json,os,socket,ssl,statistics,time
from protocol import Pkt,UDP_PORT,SSL_PORT,PKT_SIZE,REQ,RESP,to_ntp

STEP=0.128; GAIN=0.125; MAX_PPM=500e-6
step_off=0.0; freq=0.0; last_t=time.time()   # PLL state

def correct(off):
    global step_off,freq,last_t
    if abs(off)>STEP: step_off+=off; action="step"
    else: freq=max(-MAX_PPM,min(MAX_PPM,freq+GAIN*off)); action="slew"
    last_t=time.time(); return action

def run(server,count,interval):
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)  # socket()
    sock.settimeout(2.0)
    offsets=[]; rtts=[]; hist=[]; seq=0
    print(f"Syncing {server}  count={count}  interval={interval}s")
    for _ in range(count):
        seq+=1; t1=time.time()
        req=Pkt(); req.mode=REQ; req.seq=seq; req.t1s,req.t1f=to_ntp(t1)
        try:
            sock.sendto(req.pack(),(server,UDP_PORT))      # sendto()
            data,_=sock.recvfrom(PKT_SIZE)                 # recvfrom()
        except socket.timeout: print(f"seq={seq} timeout"); continue
        t4=time.time(); rep=Pkt.unpack(data)
        if rep.mode!=RESP: continue
        off=rep.offset(t4); rtt=rep.rtt(t4)
        if len(hist)>=5 and rtt>3*statistics.median(hist):
            print(f"seq={seq} outlier skipped"); continue
        hist=(hist+[rtt])[-20:]
        action=correct(off); offsets.append(off); rtts.append(rtt)
        print(f"seq={seq}  offset={off*1000:+.2f}ms  rtt={rtt*1000:.2f}ms  action={action}")
        time.sleep(interval)
    sock.close()
    if not offsets: return
    o=[x*1000 for x in offsets]; d=[x*1000 for x in rtts]
    print(f"\nsamples={len(o)}  mean_offset={statistics.mean(o):+.3f}ms  mean_rtt={statistics.mean(d):.3f}ms")
    if len(o)>1: print(f"jitter={statistics.stdev(o):.3f}ms  min_rtt={min(d):.3f}ms  max_rtt={max(d):.3f}ms")
    if len(o)>=3:
        diffs=[abs(o[i+1]-o[i]) for i in range(len(o)-1)]
        print(f"allan_dev={(statistics.mean(x**2 for x in diffs)/2)**0.5:.3f}ms")

def status(server,cert):
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(cert); ctx.check_hostname=False
    conn=ctx.wrap_socket(socket.create_connection((server,SSL_PORT),timeout=5))
    buf=b""
    while b"\n" not in buf: buf+=conn.recv(1024)           # recv()
    conn.sendall((json.dumps({"cmd":"status"})+"\n").encode())  # sendall()
    buf=b""
    while b"\n" not in buf: buf+=conn.recv(4096)
    conn.close(); print(json.dumps(json.loads(buf.split(b"\n")[0]),indent=2))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--server",default="127.0.0.1")
    ap.add_argument("--count",type=int,default=20)
    ap.add_argument("--interval",type=float,default=1.0)
    ap.add_argument("--status",action="store_true")
    args=ap.parse_args()
    base=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cert=os.path.join(base,"certs","server.crt")
    if args.status: status(args.server,cert)
    else: run(args.server,args.count,args.interval)

if __name__=="__main__": main()
