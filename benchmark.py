# benchmark.py — Performance evaluation: stress tests the NCSP server
# Supports preset tests AND custom user-entered parameters
import socket,statistics,threading,time
from protocol import Pkt,UDP_PORT,PKT_SIZE,REQ,RESP,PING,to_ntp

SERVER_IP="127.0.0.1"
W=64
def ln(c="─"): print(c*W)
def row(l,r): print(f"  {l:<32}{r}")

def single_client(server,count,interval,result_store,client_id):
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    sock.settimeout(2.0); offsets=[]; rtts=[]; timeouts=0; seq=0
    t_start=time.time()
    for _ in range(count):
        seq+=1; t1=time.time()
        req=Pkt(); req.mode=REQ; req.seq=seq; req.t1s,req.t1f=to_ntp(t1)
        try:
            sock.sendto(req.pack(),(server,UDP_PORT))
            raw,_=sock.recvfrom(PKT_SIZE)
        except socket.timeout: timeouts+=1; continue
        t4=time.time()
        try: rep=Pkt.unpack(raw)
        except: continue
        if rep.mode!=RESP: continue
        offsets.append(rep.offset(t4)); rtts.append(rep.rtt(t4))
    elapsed=time.time()-t_start; sock.close()
    result_store[client_id]={"offsets":offsets,"rtts":rtts,
                              "timeouts":timeouts,"elapsed":elapsed,"count":count}

def run_test(label,server,num_clients,count,interval):
    ln("═"); print(f"  {label}"); ln("═")
    row("Concurrent clients",str(num_clients))
    row("Packets per client",str(count))
    row("Interval between packets",f"{interval} s")
    row("Total packets to send",str(num_clients*count))
    row("Expected duration",f"~{count*interval:.1f} s")
    ln()
    print("  Running... please wait.")
    results={}
    threads=[threading.Thread(target=single_client,
             args=(server,count,interval,results,i)) for i in range(num_clients)]
    t0=time.time()
    for t in threads: t.start()
    for t in threads: t.join()
    elapsed=time.time()-t0
    all_off=[x*1000 for r in results.values() for x in r["offsets"]]
    all_rtt=[x*1000 for r in results.values() for x in r["rtts"]]
    total_sent=num_clients*count; total_ok=len(all_off)
    total_to=sum(r["timeouts"] for r in results.values())
    tput=total_ok/elapsed if elapsed>0 else 0
    print(f"\n  {'Metric':<32} {'Value':>15}"); ln()
    row("Test duration",f"{elapsed:.2f} s")
    row("Packets sent",str(total_sent))
    row("Responses received",str(total_ok))
    row("Timeouts / lost packets",str(total_to))
    row("Packet success rate",f"{total_ok/total_sent*100:.1f}%")
    row("Throughput",f"{tput:.2f} pkts/sec")
    if all_rtt:
        row("Mean RTT  (response time)",f"{statistics.mean(all_rtt):.3f} ms")
        row("Min RTT   (best latency)",f"{min(all_rtt):.3f} ms")
        row("Max RTT   (worst latency)",f"{max(all_rtt):.3f} ms")
        if len(all_rtt)>1: row("Jitter  (RTT std dev)",f"{statistics.stdev(all_rtt):.3f} ms")
    if all_off:
        row("Mean clock offset",f"{statistics.mean(all_off):+.3f} ms")
        if len(all_off)>1: row("Offset jitter",f"{statistics.stdev(all_off):.3f} ms")
    ln()
    return {"tput":tput,"mean_rtt":statistics.mean(all_rtt) if all_rtt else 0,
            "success":total_ok/total_sent*100,"label":label}

def ping_check(server):
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); sock.settimeout(2.0)
    p=Pkt(); p.mode=PING; p.seq=0; t0=time.time()
    try:
        sock.sendto(p.pack(),(server,UDP_PORT)); sock.recvfrom(PKT_SIZE)
        rtt=(time.time()-t0)*1000; sock.close(); return rtt
    except socket.timeout: sock.close(); return None

def get_int(prompt,default,min_val,max_val):
    while True:
        try:
            val=input(f"  {prompt} (default={default}): ").strip()
            val=int(val) if val else default
            if min_val<=val<=max_val: return val
            print(f"  ! Enter a value between {min_val} and {max_val}")
        except ValueError: print("  ! Please enter a whole number")

def get_float(prompt,default,min_val,max_val):
    while True:
        try:
            val=input(f"  {prompt} (default={default}): ").strip()
            val=float(val) if val else default
            if min_val<=val<=max_val: return val
            print(f"  ! Enter a value between {min_val} and {max_val}")
        except ValueError: print("  ! Please enter a number")

def show_menu():
    ln("═"); print(f"{'  NCSP  —  Performance Benchmark':^{W}}"); ln("═")
    row("Server",SERVER_IP)
    row("Started",time.strftime("%Y-%m-%d  %H:%M:%S")); ln()
    print("  Select mode:")
    print("  [1]  Run all preset tests  (recommended for demo)")
    print("  [2]  Run custom test       (enter your own values)")
    print("  [3]  Run single quick test (10 pkts, 1 client)")
    print("  [0]  Exit")
    ln()
    while True:
        choice=input("  Enter choice (0-3): ").strip()
        if choice in ("0","1","2","3"): return choice
        print("  ! Enter 0, 1, 2 or 3")

def main():
    # Reachability check first
    ln("═"); print(f"{'  NCSP  —  Performance Benchmark':^{W}}"); ln("═")
    print("  Checking server reachability...")
    rtt=ping_check(SERVER_IP)
    if rtt is None:
        print(f"\n  ! Server {SERVER_IP}:{UDP_PORT} is unreachable.")
        print("  Make sure server.py is running on the server laptop."); ln(); return
    print(f"  Server reachable  —  ping RTT : {rtt:.1f} ms\n")

    choice=show_menu()
    if choice=="0": print("  Exiting."); return

    summaries=[]

    if choice=="1":
        # All 4 preset tests
        summaries.append(run_test("TEST 1 — Baseline  (1 client, 20 pkts, 1.0s)",SERVER_IP,1,20,1.0))
        summaries.append(run_test("TEST 2 — Two Concurrent Clients  (2 clients, 20 pkts, 1.0s)",SERVER_IP,2,20,1.0))
        summaries.append(run_test("TEST 3 — High Request Rate  (2 clients, 30 pkts, 0.2s)",SERVER_IP,2,30,0.2))
        summaries.append(run_test("TEST 4 — High Data Volume  (2 clients, 50 pkts, 0.1s)",SERVER_IP,2,50,0.1))

    elif choice=="2":
        # Custom test — user enters all parameters
        ln("═"); print(f"{'  CUSTOM TEST — Enter Parameters':^{W}}"); ln("═")
        num_clients = get_int("Number of concurrent clients",2,1,10)
        count       = get_int("Packets per client",20,1,200)
        interval    = get_float("Interval between packets (seconds)",1.0,0.05,10.0)
        ln()
        label=f"CUSTOM — {num_clients} client(s), {count} pkts, {interval}s interval"
        summaries.append(run_test(label,SERVER_IP,num_clients,count,interval))

    elif choice=="3":
        # Quick single test — no input needed
        summaries.append(run_test("QUICK TEST — 1 client, 10 pkts, 1.0s",SERVER_IP,1,10,1.0))

    # Summary table (only meaningful if more than 1 test ran)
    if len(summaries)>1:
        ln("═"); print(f"{'  BENCHMARK SUMMARY':^{W}}"); ln("═")
        print(f"  {'Test':<38} {'Throughput':>11} {'Mean RTT':>10} {'Success':>8}"); ln()
        for s in summaries:
            print(f"  {s['label'][:38]:<38} {s['tput']:>9.2f}/s {s['mean_rtt']:>9.3f}ms {s['success']:>7.1f}%")
        ln("═")

    print("\n  Benchmark complete.\n")

if __name__=="__main__": main()
