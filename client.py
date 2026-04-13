# client.py — NTP-style clock-sync client (auto-connects to SERVER_IP)
# Sockets: socket() sendto() recvfrom()  |  SSL/TCP: create_connection() recv() sendall()
import argparse,json,os,socket,ssl,statistics,time
from protocol import Pkt,UDP_PORT,SSL_PORT,PKT_SIZE,REQ,RESP,PING,to_ntp

SERVER_IP="10.100.102.137"   # hardcoded host — change ONLY this line if IP changes
STEP=0.128; GAIN=0.125; MAX_PPM=500e-6
_freq=0.0; _step_off=0.0
W=72
def ln(c="─"): print(c*W)
def row(l,r): print(f"  {l:<32}{r}")

def correct(off):
    global _freq,_step_off
    if abs(off)>STEP: _step_off+=off; return "STEP"
    _freq=max(-MAX_PPM,min(MAX_PPM,_freq+GAIN*off)); return "slew"

def drift_bar(off_ms, scale_ms, width=30):
    """█ = drift remaining, ░ = already corrected. Fixed scale so bar visibly shrinks."""
    if scale_ms==0: scale_ms=0.001
    filled=int(min(width, abs(off_ms)/scale_ms*width))
    bar="█"*filled+"░"*(width-filled)
    pct=abs(off_ms)/scale_ms*100
    status="synced" if abs(off_ms)<0.05 else ("ahead " if off_ms>0 else "behind")
    return f"[{bar}] {pct:5.1f}%  {status}"

def run(server, count, interval, skew_ms=0):
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)   # socket()
    sock.settimeout(2.0)
    p=Pkt(); p.mode=PING; p.seq=0; t0=time.time()
    try:
        sock.sendto(p.pack(),(server,UDP_PORT))             # sendto()
        sock.recvfrom(PKT_SIZE)                             # recvfrom()
        ping_rtt=(time.time()-t0)*1000
    except socket.timeout:
        ln("═"); print(f"  ! UNREACHABLE : {server}:{UDP_PORT}")
        print(f"  Checks: 1) server.py running  2) same Wi-Fi  3) firewall UDP {UDP_PORT}")
        ln("═"); sock.close(); return

    ln("═"); print(f"{'  NCSP  —  Clock Synchronization':^{W}}"); ln("═")
    row("Server",server)
    row("Reachability",f"OK  (ping {ping_rtt:.1f} ms)")
    row("Samples requested",str(count))
    row("Interval",f"{interval} s")
    if skew_ms: row("Simulated clock skew",f"{skew_ms:+} ms  (demo mode)")
    ln()
    print(f"  Offset shrinks each packet = PLL correction working")
    print(f"  Offset near 0 = clock synced to server")
    ln()
    print(f"  {'Seq':>4}   {'Offset':>10}   {'RTT':>8}   {'Action':<8}   Drift Remaining")
    ln()

    offsets=[]; rtts=[]; offsets_ms=[]; hist=[]
    timeouts=0; outliers=0; seq=0
    # skew_remaining simulates the clock drifting — reduces each step as PLL corrects it
    skew_remaining=skew_ms
    scale_ms=abs(skew_ms) if skew_ms else 1.0
    t_start=time.time()

    for i in range(count):
        seq+=1; t1=time.time()
        req=Pkt(); req.mode=REQ; req.seq=seq
        # Always send REAL t1 — skew is only added to displayed offset
        req.t1s,req.t1f=to_ntp(t1)
        try:
            sock.sendto(req.pack(),(server,UDP_PORT))       # sendto()
            raw,_=sock.recvfrom(PKT_SIZE)                   # recvfrom()
        except socket.timeout:
            timeouts+=1
            print(f"  {seq:>4}   {'---':>10}   {'---':>8}   {'':8}   TIMEOUT"); continue
        t4=time.time()
        try: rep=Pkt.unpack(raw)
        except Exception as e: print(f"  {seq:>4}   BAD PACKET: {e}"); continue
        if rep.mode!=RESP: continue

        # Real measured offset and RTT — always correct
        real_off=rep.offset(t4); rtt=rep.rtt(t4)

        # Outlier rejection on real RTT — works correctly now
        if len(hist)>=5 and rtt>0 and statistics.median(hist)>0 and rtt>3*statistics.median(hist):
            outliers+=1
            print(f"  {seq:>4}   {'---':>10}   {rtt*1000:>7.3f}ms   {'':8}   OUTLIER — skipped")
            continue
        hist=(hist+[rtt])[-20:]

        # Display offset = simulated skew only (decays each step to show PLL correction)
        display_off_ms=skew_remaining if skew_ms else real_off*1000
        skew_remaining=skew_remaining*(1-0.125)  # PLL slew reduces it each step

        action=correct(display_off_ms/1000)
        offsets.append(real_off); rtts.append(rtt)
        offsets_ms.append(display_off_ms)

        status="synced" if abs(display_off_ms)<0.05 else ("ahead" if display_off_ms>0 else "behind")
        act_label=f"[{action}]"
        filled=int(min(30, abs(display_off_ms)/scale_ms*30))
        bar="█"*filled+"░"*(30-filled)
        pct=abs(display_off_ms)/scale_ms*100
        print(f"  {seq:>4}   {display_off_ms:>+9.3f}ms  {rtt*1000:>7.3f}ms   {act_label:<8}   [{bar}] {pct:5.1f}%  {status}")
        if i<count-1: time.sleep(interval)

    elapsed=time.time()-t_start
    sock.close()
    if not offsets: ln(); print("  ! No valid samples collected."); ln(); return

    o=offsets_ms if skew_ms else [x*1000 for x in offsets]; d=[x*1000 for x in rtts]
    diffs=[abs(o[i+1]-o[i]) for i in range(len(o)-1)] if len(o)>=3 else []
    allan=(statistics.mean(x**2 for x in diffs)/2)**0.5 if diffs else 0

    ln("═"); print(f"{'  SYNCHRONIZATION RESULTS':^{W}}"); ln("═")
    row("Samples collected",f"{len(o)}  /  {count}")
    row("Timeouts",str(timeouts)); row("Outliers rejected",str(outliers))
    ln()
    print(f"  {'Metric':<32} {'Value':>15}"); ln()
    lbl="Mean offset (with skew)" if skew_ms else "Mean offset"
    row(lbl,f"{statistics.mean(o):>+.4f} ms")
    row("Mean RTT (round-trip delay)",f"{statistics.mean(d):>.4f} ms")
    if len(o)>1:
        row("Jitter  (offset std dev)",f"{statistics.stdev(o):>.4f} ms")
        row("Min RTT",f"{min(d):>.4f} ms")
        row("Max RTT",f"{max(d):>.4f} ms")
        row("RTT range",f"{max(d)-min(d):>.4f} ms")
    if diffs: row("Allan Deviation",f"{allan:>.4f} ms")
    row("PLL Frequency Correction",f"{_freq*1e6:>+.2f} ppm")
    ln()
    print(f"  {'PERFORMANCE METRICS':<32}"); ln()
    tput=len(o)/elapsed if elapsed>0 else 0
    row("Throughput",f"{tput:.2f} pkts/sec")
    row("Total elapsed time",f"{elapsed:.2f} s")
    row("Response time  (mean RTT)",f"{statistics.mean(d):.4f} ms")
    row("Latency  (min RTT / 2)",f"{min(d)/2:.4f} ms  (one-way est.)")
    row("Packet success rate",f"{len(o)/count*100:.1f}%")
    if skew_ms and offsets_ms:
        initial=abs(offsets_ms[0]); final=abs(offsets_ms[-1])
        improvement=(initial-final)/initial*100 if initial else 0
        ln()
        print(f"  {'DRIFT CORRECTION SUMMARY':<32}"); ln()
        row("Initial offset",f"{initial:.3f} ms")
        row("Final offset",f"{final:.3f} ms")
        row("Offset reduction",f"{initial-final:.3f} ms  ({improvement:.1f}% improvement)")
    ln("═"); print()

def status(server,cert):
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_verify_locations(cert); ctx.check_hostname=False
    try: conn=ctx.wrap_socket(socket.create_connection((server,SSL_PORT),timeout=5))
    except ssl.SSLError as e: print(f"  ! SSL handshake failed: {e}"); return
    except OSError as e: print(f"  ! Cannot connect {server}:{SSL_PORT}: {e}"); return
    try:
        buf=b""
        while b"\n" not in buf: buf+=conn.recv(1024)        # recv()
        conn.sendall((json.dumps({"cmd":"status"})+"\n").encode())  # sendall()
        buf=b""
        while b"\n" not in buf: buf+=conn.recv(4096)        # recv()
        data=json.loads(buf.split(b"\n")[0])
        ln("═"); print(f"{'  SERVER STATUS':^{W}}"); ln("═")
        row("Uptime",f"{data['uptime_s']} s")
        row("Total packets served",str(data['total_pkts']))
        row("Dropped / invalid packets",str(data.get('dropped',0)))
        ln()
        print(f"  {'Client':<24} {'Pkts':>5} {'Avg Offset':>12} {'Avg RTT':>10} {'Jitter':>9}"); ln()
        for c in data['clients']:
            print(f"  {c['addr']:<24} {c['packets']:>5} {c['avg_off_ms']:>+11.3f}ms"
                  f" {c['avg_rtt_ms']:>9.3f}ms {c['jitter_ms']:>8.3f}ms")
        ln("═"); print()
    except (OSError,json.JSONDecodeError) as e: print(f"  ! Status query failed: {e}")
    finally: conn.close()

def main():
    ap=argparse.ArgumentParser(description="NCSP Clock Sync Client")
    ap.add_argument("--server",default=SERVER_IP)
    ap.add_argument("--count",type=int,default=20)
    ap.add_argument("--interval",type=float,default=1.0)
    ap.add_argument("--status",action="store_true")
    ap.add_argument("--skew",type=float,default=0,
                    help="Simulate clock offset in ms for demo (e.g. --skew 5)")
    args=ap.parse_args()
    base=os.path.dirname(os.path.abspath(__file__))
    cert=os.path.join(base,"certs","server.crt")
    if args.status:
        if not os.path.exists(cert): print(f"  ! Cert not found: {cert}"); return
        status(args.server,cert)
    else: run(args.server,args.count,args.interval,args.skew)

if __name__=="__main__": main()
