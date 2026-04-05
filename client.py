# client.py — NTP-style clock-sync client (auto-connects to SERVER_IP)
# Sockets: socket() sendto() recvfrom()  |  SSL/TCP: create_connection() recv() sendall()
import argparse,json,os,socket,ssl,statistics,time
from protocol import Pkt,UDP_PORT,SSL_PORT,PKT_SIZE,REQ,RESP,PING,to_ntp

SERVER_IP="127.0.0.1"   # hardcoded host — change ONLY this line if IP changes
STEP=0.128; GAIN=0.125; MAX_PPM=500e-6
_freq=0.0; _step_off=0.0
W=64
def ln(c="─"): print(c*W)
def row(l,r): print(f"  {l:<30}{r}")

def correct(off):
    global _freq,_step_off
    if abs(off)>STEP: _step_off+=off; return "STEP"        # large offset — step immediately
    _freq=max(-MAX_PPM,min(MAX_PPM,_freq+GAIN*off)); return "slew"  # small — gradual adjust

def to_ntp_skewed(t,skew_ms):
    t2=t+skew_ms/1000.0
    return int(t2)+2_208_988_800,int((t2%1)*2**32)

def run(server,count,interval,skew_ms=0):
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)   # socket()
    sock.settimeout(2.0)
    # Reachability check via PING before starting sync
    p=Pkt(); p.mode=PING; p.seq=0; t0=time.time()
    try:
        sock.sendto(p.pack(),(server,UDP_PORT))             # sendto()
        sock.recvfrom(PKT_SIZE)                             # recvfrom()
        ping_rtt=(time.time()-t0)*1000
    except socket.timeout:
        ln("═"); print(f"  ! UNREACHABLE : {server}:{UDP_PORT}")
        print(f"  Checks : 1) server.py is running")
        print(f"           2) all laptops on same Wi-Fi")
        print(f"           3) firewall allows UDP {UDP_PORT}")
        ln("═"); sock.close(); return

    ln("═"); print(f"{'  NCSP  —  Clock Synchronization':^{W}}"); ln("═")
    row("Server",server)
    row("Reachability",f"OK  (ping {ping_rtt:.1f} ms)")
    row("Samples requested",str(count))
    row("Interval",f"{interval} s")
    row("Total duration",f"~{count*interval:.0f} s")
    if skew_ms: row("Simulated clock skew",f"{skew_ms:+} ms  (demo mode)")
    ln()
    print(f"  {'Seq':>4}   {'Offset':>12}   {'RTT':>10}   {'Action':<6}   {'Drift Bar'}")
    ln()

    offsets=[]; rtts=[]; hist=[]; timeouts=0; outliers=0; seq=0
    t_start=time.time()
    for i in range(count):
        seq+=1; t1=time.time()
        req=Pkt(); req.mode=REQ; req.seq=seq
        req.t1s,req.t1f=to_ntp_skewed(t1,skew_ms)
        try:
            sock.sendto(req.pack(),(server,UDP_PORT))       # sendto()
            raw,_=sock.recvfrom(PKT_SIZE)                   # recvfrom()
        except socket.timeout:
            timeouts+=1; print(f"  {seq:>4}   {'---':>12}   {'---':>10}   {'':6}   TIMEOUT ({timeouts} total)"); continue
        t4=time.time()
        # Edge case: corrupted or wrong-size response
        try: rep=Pkt.unpack(raw)
        except Exception as e: print(f"  {seq:>4}   BAD PACKET : {e}"); continue
        if rep.mode!=RESP: continue
        off=rep.offset(t4); rtt=rep.rtt(t4)
        # Outlier rejection — RTT > 3x median of recent window
        if len(hist)>=5 and rtt>3*statistics.median(hist):
            outliers+=1
            print(f"  {seq:>4}   {off*1000:>+11.3f} ms  {rtt*1000:>9.3f} ms   {'':6}   OUTLIER — skipped"); continue
        hist=(hist+[rtt])[-20:]; action=correct(off)
        offsets.append(off); rtts.append(rtt)
        bar_len=min(18,int(abs(off*1000)*5))
        bar=("+" if off>=0 else "-")+"|"*bar_len if bar_len>0 else "~0.000"
        print(f"  {seq:>4}   {off*1000:>+11.3f} ms  {rtt*1000:>9.3f} ms   {action:<6}   {bar}")
        if i<count-1: time.sleep(interval)

    elapsed=time.time()-t_start
    sock.close()
    if not offsets: ln(); print("  ! No valid samples collected."); ln(); return

    o=[x*1000 for x in offsets]; d=[x*1000 for x in rtts]
    diffs=[abs(o[i+1]-o[i]) for i in range(len(o)-1)] if len(o)>=3 else []
    allan=(statistics.mean(x**2 for x in diffs)/2)**0.5 if diffs else 0

    # ── Results ──────────────────────────────────────────────────────────
    ln("═"); print(f"{'  SYNCHRONIZATION RESULTS':^{W}}"); ln("═")
    row("Samples collected",f"{len(o)}  /  {count}")
    row("Timeouts",str(timeouts))
    row("Outliers rejected",str(outliers))
    ln()
    print(f"  {'Metric':<30} {'Value':>15}"); ln()
    row("Mean offset",f"{statistics.mean(o):>+.4f} ms")
    row("Mean RTT (round-trip delay)",f"{statistics.mean(d):>.4f} ms")
    if len(o)>1:
        row("Jitter  (offset std dev)",f"{statistics.stdev(o):>.4f} ms")
        row("Min RTT",f"{min(d):>.4f} ms")
        row("Max RTT",f"{max(d):>.4f} ms")
        row("RTT range",f"{max(d)-min(d):>.4f} ms")
    if diffs: row("Allan Deviation",f"{allan:>.4f} ms")
    row("PLL Frequency Correction",f"{_freq*1e6:>+.2f} ppm")
    ln()
    # ── Performance metrics ───────────────────────────────────────────────
    print(f"  {'PERFORMANCE METRICS':<30}"); ln()
    tput=len(o)/elapsed if elapsed>0 else 0
    row("Throughput",f"{tput:.2f} pkts/sec")
    row("Total elapsed time",f"{elapsed:.2f} s")
    row("Response time  (mean RTT)",f"{statistics.mean(d):.4f} ms")
    row("Latency  (min RTT / 2)",f"{min(d)/2:.4f} ms  (one-way est.)")
    row("Packet success rate",f"{len(o)/count*100:.1f}%")
    ln("═"); print()

def status(server,cert):
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(cert); ctx.check_hostname=False
    # Edge case: SSL handshake failure / wrong cert / connection refused
    try: conn=ctx.wrap_socket(socket.create_connection((server,SSL_PORT),timeout=5))
    except ssl.SSLError as e: print(f"  ! SSL handshake failed : {e}"); return
    except OSError as e: print(f"  ! Cannot connect to {server}:{SSL_PORT} : {e}"); return
    try:
        buf=b""
        while b"\n" not in buf: buf+=conn.recv(1024)       # recv()
        conn.sendall((json.dumps({"cmd":"status"})+"\n").encode())  # sendall()
        buf=b""
        while b"\n" not in buf: buf+=conn.recv(4096)       # recv()
        data=json.loads(buf.split(b"\n")[0])
        ln("═"); print(f"{'  SERVER STATUS':^{W}}"); ln("═")
        row("Uptime",f"{data['uptime_s']} s")
        row("Total packets served",str(data['total_pkts']))
        row("Dropped / invalid packets",str(data.get('dropped',0)))
        ln()
        print(f"  {'Client':<22} {'Pkts':>5} {'Avg Offset':>12} {'Avg RTT':>10} {'Jitter':>9}"); ln()
        for c in data['clients']:
            print(f"  {c['addr']:<22} {c['packets']:>5} {c['avg_off_ms']:>+11.3f}ms {c['avg_rtt_ms']:>9.3f}ms {c['jitter_ms']:>8.3f}ms")
        ln("═"); print()
    except (OSError,json.JSONDecodeError) as e: print(f"  ! Status query failed : {e}")
    finally: conn.close()

def main():
    ap=argparse.ArgumentParser(description="NCSP Clock Sync Client")
    ap.add_argument("--server",default=SERVER_IP,help="Server IP address")
    ap.add_argument("--count",type=int,default=20,help="Number of sync packets")
    ap.add_argument("--interval",type=float,default=1.0,help="Seconds between packets")
    ap.add_argument("--status",action="store_true",help="Query server status via SSL/TCP")
    ap.add_argument("--skew",type=float,default=0,
                    help="Simulate clock offset in ms for demo (e.g. --skew 50)")
    args=ap.parse_args()
    base=os.path.dirname(os.path.abspath(__file__))
    cert=os.path.join(base,"certs","server.crt")
    if args.status:
        if not os.path.exists(cert): print(f"  ! Cert not found : {cert}"); return
        status(args.server,cert)
    else: run(args.server,args.count,args.interval,args.skew)

if __name__=="__main__": main()
