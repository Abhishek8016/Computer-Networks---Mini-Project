# client.py — NTP-style clock-sync client (auto-connects to SERVER_IP)
# Sockets: socket() sendto() recvfrom()  |  SSL/TCP: create_connection() recv() sendall()
import argparse,json,os,socket,ssl,statistics,time
from protocol import Pkt,UDP_PORT,SSL_PORT,PKT_SIZE,REQ,RESP,PING,to_ntp

SERVER_IP="10.58.0.137"   # hardcoded host — change only this if IP changes
STEP=0.128; GAIN=0.125; MAX_PPM=500e-6
_freq=0.0; _step_off=0.0

def correct(off):
    global _freq,_step_off
    if abs(off)>STEP: _step_off+=off; return "step"
    _freq=max(-MAX_PPM,min(MAX_PPM,_freq+GAIN*off)); return "slew"

def run(server,count,interval):
    print(f"[*] Creating UDP socket...")
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)   # socket()
    sock.settimeout(2.0)
    print(f"[*] Sending PING to {server}:{UDP_PORT}...")
    p=Pkt(); p.mode=PING; p.seq=0; t0=time.time()
    try:
        sock.sendto(p.pack(),(server,UDP_PORT))             # sendto()
        sock.recvfrom(PKT_SIZE)                             # recvfrom()
        print(f"[UDP] PING OK  rtt~{(time.time()-t0)*1000:.1f}ms  server={server}")
    except socket.timeout:
        print(f"[!] PING timed out — {server}:{UDP_PORT} unreachable")
        print(f"    Check: 1) server is running  2) same Wi-Fi  3) firewall allows UDP {UDP_PORT}")
        sock.close(); return
    offsets=[]; rtts=[]; hist=[]; seq=0
    print(f"[*] Syncing  count={count}  interval={interval}s")
    print("-"*55)
    for i in range(count):
        seq+=1; t1=time.time()
        req=Pkt(); req.mode=REQ; req.seq=seq; req.t1s,req.t1f=to_ntp(t1)
        try:
            sock.sendto(req.pack(),(server,UDP_PORT))       # sendto()
            raw,addr=sock.recvfrom(PKT_SIZE)                # recvfrom()
        except socket.timeout: print(f"  seq={seq:4d}  TIMEOUT"); continue
        t4=time.time()
        try: rep=Pkt.unpack(raw)
        except Exception as e: print(f"  seq={seq:4d}  BAD PACKET: {e}"); continue
        if rep.mode!=RESP: continue
        off=rep.offset(t4); rtt=rep.rtt(t4)
        if len(hist)>=5 and rtt>3*statistics.median(hist):
            print(f"  seq={seq:4d}  OUTLIER rtt={rtt*1000:.2f}ms"); continue
        hist=(hist+[rtt])[-20:]; action=correct(off)
        offsets.append(off); rtts.append(rtt)
        print(f"  seq={seq:4d}  off={off*1000:+8.3f}ms  rtt={rtt*1000:7.3f}ms  [{action}]")
        if i<count-1: time.sleep(interval)
    sock.close()
    if not offsets: print("[!] No valid samples collected."); return
    o=[x*1000 for x in offsets]; d=[x*1000 for x in rtts]
    print("-"*55)
    print(f"[RESULTS]")
    print(f"  samples={len(o)}  mean_off={statistics.mean(o):+.3f}ms  mean_rtt={statistics.mean(d):.3f}ms")
    if len(o)>1: print(f"  jitter={statistics.stdev(o):.3f}ms  min_rtt={min(d):.3f}ms  max_rtt={max(d):.3f}ms")
    if len(o)>=3:
        diffs=[abs(o[i+1]-o[i]) for i in range(len(o)-1)]
        print(f"  allan_dev={(statistics.mean(x**2 for x in diffs)/2)**0.5:.3f}ms  pll_freq={_freq*1e6:+.2f}ppm")

def status(server,cert):
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(cert); ctx.check_hostname=False
    try: conn=ctx.wrap_socket(socket.create_connection((server,SSL_PORT),timeout=5))
    except Exception as e: print(f"[!] SSL connect failed: {e}"); return
    buf=b""
    while b"\n" not in buf: buf+=conn.recv(1024)            # recv()
    conn.sendall((json.dumps({"cmd":"status"})+"\n").encode())  # sendall()
    buf=b""
    while b"\n" not in buf: buf+=conn.recv(4096)            # recv()
    conn.close(); print(json.dumps(json.loads(buf.split(b"\n")[0]),indent=2))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--server",default=SERVER_IP)
    ap.add_argument("--count",type=int,default=20); ap.add_argument("--interval",type=float,default=1.0)
    ap.add_argument("--status",action="store_true"); args=ap.parse_args()
    base=os.path.dirname(os.path.abspath(__file__))
    cert=os.path.join(base,"certs","server.crt")
    print("="*55)
    print(f"  NCSP Client  →  server : {args.server}")
    print(f"  UDP sync port          : {UDP_PORT}")
    print(f"  SSL admin port         : {SSL_PORT}")
    print("="*55)
    if args.status:
        if not os.path.exists(cert): print(f"[!] cert not found: {cert}"); return
        status(args.server,cert)
    else: run(args.server,args.count,args.interval)

if __name__=="__main__": main()
