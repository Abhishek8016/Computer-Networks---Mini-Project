# server.py — UDP time server + SSL/TCP admin channel
# Socket calls: socket() bind() listen() accept() recvfrom() sendto() sendall() recv()
import json,os,socket,ssl,statistics,threading,time
from protocol import Pkt,UDP_PORT,SSL_PORT,PKT_SIZE,REQ,RESP,PING,PONG,now,to_ntp

clients={}; total=0; lock=threading.Lock(); start=time.time(); udp=None

def record(addr,off,rtt):
    global total
    k=f"{addr[0]}:{addr[1]}"
    with lock:
        if k not in clients: clients[k]={"n":0,"o":[],"r":[]}; print("new client",k)
        c=clients[k]; c["n"]+=1
        c["o"]=(c["o"]+[off])[-20:]; c["r"]=(c["r"]+[rtt])[-20:]; total+=1

def handle_udp(data,addr,t2):
    try: req=Pkt.unpack(data)
    except: return
    if req.mode==PING:
        p=Pkt(); p.mode=PONG; p.seq=req.seq; udp.sendto(p.pack(),addr); return
    if req.mode!=REQ: return
    t3=time.time()
    rep=Pkt(); rep.mode=RESP; rep.seq=req.seq
    rep.t1s,rep.t1f=req.t1s,req.t1f
    rep.t2s,rep.t2f=to_ntp(t2); rep.t3s,rep.t3f=to_ntp(t3); rep.t4s,rep.t4f=now()
    udp.sendto(rep.pack(),addr)                     # sendto()
    t4=time.time(); record(addr,rep.offset(t4),rep.rtt(t4))
    print(f"{addr[0]} seq={req.seq} off={rep.offset(t4)*1000:+.2f}ms rtt={rep.rtt(t4)*1000:.2f}ms")

def udp_loop():
    while True:
        data,addr=udp.recvfrom(PKT_SIZE)            # recvfrom()
        t2=time.time()
        threading.Thread(target=handle_udp,args=(data,addr,t2),daemon=True).start()

def tcp_handler(conn):
    try:
        conn.settimeout(30); conn.sendall(b'{"msg":"NCSP"}\n')   # sendall()
        buf=b""
        while True:
            chunk=conn.recv(1024)                   # recv()
            if not chunk: break
            buf+=chunk
            if b"\n" not in buf: continue
            try: cmd=json.loads(buf.split(b"\n")[0])["cmd"]
            except: conn.sendall(b'{"err":"bad"}\n'); buf=b""; continue
            buf=b""
            if cmd=="status":
                with lock:
                    out=[{"addr":k,"n":c["n"],"avg_off_ms":round(statistics.mean(c["o"])*1000,2) if c["o"] else 0}
                         for k,c in clients.items()]
                conn.sendall((json.dumps({"uptime":round(time.time()-start,1),"total":total,"clients":out})+"\n").encode())
            elif cmd=="ping": conn.sendall(b'{"reply":"pong"}\n')
            elif cmd=="quit": conn.sendall(b'{"msg":"bye"}\n'); break
            else: conn.sendall(b'{"err":"unknown"}\n')
    except: pass
    finally: conn.close()

def ssl_loop(cert,key):
    raw=socket.socket(socket.AF_INET,socket.SOCK_STREAM)  # socket()
    raw.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    raw.bind(("0.0.0.0",SSL_PORT)); raw.listen(10)        # bind() listen()
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cert,key); ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    s=ctx.wrap_socket(raw,server_side=True)
    print(f"SSL ready :{SSL_PORT}")
    while True:
        try:
            conn,_=s.accept()                             # accept()
            threading.Thread(target=tcp_handler,args=(conn,),daemon=True).start()
        except ssl.SSLError as e: print("SSL err:",e)

def main():
    global udp
    base=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cert=os.path.join(base,"certs","server.crt"); key=os.path.join(base,"certs","server.key")
    if not os.path.exists(cert): print("Run: bash generate_certs.sh"); return
    udp=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)   # socket()
    udp.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    udp.bind(("0.0.0.0",UDP_PORT))                        # bind()
    print(f"UDP ready :{UDP_PORT}")
    threading.Thread(target=udp_loop,daemon=True).start()
    print("Server running — Ctrl+C to stop")
    try: ssl_loop(cert,key)
    except KeyboardInterrupt: print("stopped")

if __name__=="__main__": main()
