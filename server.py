# server.py — UDP time server + SSL/TCP admin (cert only)
# Sockets: socket() bind() listen() accept() recvfrom() sendto() sendall() recv()
import json,os,socket,ssl,statistics,threading,time
from protocol import Pkt,UDP_PORT,SSL_PORT,PKT_SIZE,REQ,RESP,PING,PONG,now,to_ntp

clients={};total=0;dropped=0;lock=threading.Lock();start=time.time();udp=None
W=64
def ln(c="─"): print(c*W)
def row(l,r): print(f"  {l:<30}{r}")

def record(addr,off,rtt):
    global total
    k=f"{addr[0]}:{addr[1]}"
    with lock:
        if k not in clients:
            clients[k]={"n":0,"o":[],"r":[],"first":time.strftime("%H:%M:%S")}
            ln("┄"); print(f"  + New client connected : {k}"); ln("┄")
        c=clients[k]; c["n"]+=1
        c["o"]=(c["o"]+[off])[-50:]; c["r"]=(c["r"]+[rtt])[-50:]; total+=1

def handle_udp(data,addr,t2):
    global dropped
    # Edge case: invalid/partial packet
    try: req=Pkt.unpack(data)
    except Exception:
        with lock: dropped+=1
        return
    # PING reachability check
    if req.mode==PING:
        try:
            p=Pkt(); p.mode=PONG; p.seq=req.seq; udp.sendto(p.pack(),addr)  # sendto()
        except OSError: pass
        return
    if req.mode!=REQ: return
    # Build and send RESP
    t3=time.time()
    rep=Pkt(); rep.mode=RESP; rep.seq=req.seq
    rep.t1s,rep.t1f=req.t1s,req.t1f
    rep.t2s,rep.t2f=to_ntp(t2); rep.t3s,rep.t3f=to_ntp(t3); rep.t4s,rep.t4f=now()
    try: udp.sendto(rep.pack(),addr)                         # sendto()
    except OSError: return
    t4=time.time(); off=rep.offset(t4); rtt=rep.rtt(t4)
    record(addr,off,rtt)
    print(f"  {time.strftime('%H:%M:%S')}  {addr[0]:<15}  #{req.seq:<5}  {off*1000:>+9.3f} ms  {rtt*1000:>8.3f} ms")

def udp_loop():
    while True:
        try:
            data,addr=udp.recvfrom(PKT_SIZE)                # recvfrom()
            t2=time.time()
            threading.Thread(target=handle_udp,args=(data,addr,t2),daemon=True).start()
        except OSError: break

def print_perf_summary():
    """Print a performance summary table of all connected clients."""
    with lock:
        if not clients: return
        ln("═"); print(f"{'  PERFORMANCE SUMMARY':^{W}}"); ln("═")
        print(f"  {'Client':<22} {'Pkts':>5} {'Mean Offset':>13} {'Mean RTT':>10} {'Jitter':>9}")
        ln()
        for k,c in clients.items():
            mo=statistics.mean(c["o"])*1000 if c["o"] else 0
            mr=statistics.mean(c["r"])*1000 if c["r"] else 0
            jt=statistics.stdev(c["o"])*1000 if len(c["o"])>1 else 0
            print(f"  {k:<22} {c['n']:>5} {mo:>+12.3f}ms {mr:>9.3f}ms {jt:>8.3f}ms")
        ln()
        up=round(time.time()-start,1)
        tput=total/up if up>0 else 0
        row("Total packets served",str(total))
        row("Dropped / invalid packets",str(dropped))
        row("Throughput",f"{tput:.2f} pkts/sec")
        row("Uptime",f"{up} s")
        ln("═"); print()

def tcp_handler(conn):
    # TCP used ONLY for cert exchange (implicit in TLS handshake) + admin commands
    try:
        conn.settimeout(30)
        conn.sendall(b'{"msg":"NCSP"}\n')                   # sendall()
        buf=b""
        while True:
            chunk=conn.recv(1024)                           # recv()
            if not chunk: break                             # client disconnected cleanly
            buf+=chunk
            if b"\n" not in buf: continue
            line,buf=buf.split(b"\n",1)
            # Edge case: malformed JSON or missing "cmd" key
            try: cmd=json.loads(line)["cmd"]
            except (json.JSONDecodeError,KeyError):
                conn.sendall(b'{"err":"bad request"}\n'); continue
            if cmd=="status":
                with lock:
                    out=[{"addr":k,"packets":c["n"],
                          "avg_off_ms":round(statistics.mean(c["o"])*1000,3) if c["o"] else 0,
                          "avg_rtt_ms":round(statistics.mean(c["r"])*1000,3) if c["r"] else 0,
                          "jitter_ms":round(statistics.stdev(c["o"])*1000,3) if len(c["o"])>1 else 0}
                         for k,c in clients.items()]
                payload={"uptime_s":round(time.time()-start,1),"total_pkts":total,
                         "dropped":dropped,"clients":out}
                conn.sendall((json.dumps(payload)+"\n").encode())
            elif cmd=="ping": conn.sendall(b'{"reply":"pong"}\n')
            elif cmd=="quit": conn.sendall(b'{"msg":"bye"}\n'); break
            else: conn.sendall(b'{"err":"unknown command"}\n')
    except ssl.SSLError as e: print(f"  ! SSL error in handler : {e}")  # SSL handshake failure
    except OSError: pass                                    # abrupt client disconnection
    finally: conn.close()                                   # always close — edge case guard

def ssl_loop(cert,key):
    raw=socket.socket(socket.AF_INET,socket.SOCK_STREAM)   # socket()
    raw.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)# allow immediate restart
    raw.bind(("0.0.0.0",SSL_PORT)); raw.listen(10)         # bind() listen()
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert,key)
    ctx.minimum_version=ssl.TLSVersion.TLSv1_2             # reject TLS 1.0/1.1
    srv=ctx.wrap_socket(raw,server_side=True)
    while True:
        try:
            conn,addr=srv.accept()                         # accept()
            print(f"  + SSL admin connection : {addr[0]}")
            threading.Thread(target=tcp_handler,args=(conn,),daemon=True).start()
        except ssl.SSLError as e: print(f"  ! SSL handshake failed : {e}")  # bad cert/version
        except OSError: break

def main():
    global udp
    base=os.path.dirname(os.path.abspath(__file__))
    cert=os.path.join(base,"certs","server.crt")
    key=os.path.join(base,"certs","server.key")
    if not os.path.exists(cert) or not os.path.exists(key):
        print("  ! Cert/key missing. Run: openssl req -x509 -newkey rsa:2048 ..."); return
    udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)    # socket()
    udp.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    udp.bind(("0.0.0.0",UDP_PORT))                         # bind()
    threading.Thread(target=udp_loop,daemon=True).start()
    try: ip=socket.gethostbyname(socket.gethostname())
    except: ip="<LAN IP>"
    ln("═"); print(f"{'  NCSP  —  Network Clock Synchronization Protocol':^{W}}"); ln("═")
    row("Role","Server")
    row("LAN IP Address",ip)
    row("UDP Port  (time sync)",str(UDP_PORT))
    row("SSL/TCP Port  (admin/cert)",str(SSL_PORT))
    row("TLS Version","1.2 minimum")
    row("Started",time.strftime("%Y-%m-%d  %H:%M:%S"))
    ln()
    print(f"  {'Time':<10}  {'Client IP':<15}  {'Pkt':^6}  {'Offset':>12}  {'RTT':>11}")
    ln()
    try: ssl_loop(cert,key)
    except KeyboardInterrupt:
        print(); print_perf_summary(); print("  Server stopped.")

if __name__=="__main__": main()
