# protocol.py — 48-byte NTP-style packet, timestamps, offset/rtt math
import struct, time

UDP_PORT  = 12300   # used for ALL time-sync traffic (REQ/RESP/PING/PONG)
SSL_PORT  = 12301   # used ONLY for SSL/TLS certificate exchange + status admin
PKT_SIZE  = 48

DELTA = 2_208_988_800          # seconds between 1900-01-01 and 1970-01-01
FMT   = "!IIIIIIIIIIiI"        # 12 × 4-byte words = 48 bytes

REQ = 1; RESP = 2; PING = 3; PONG = 4

def now():
    """Return current time as (NTP-seconds, NTP-fraction)."""
    t = time.time()
    return int(t) + DELTA, int((t % 1) * 2**32)

def to_ntp(t):
    """Convert a Unix float timestamp to (NTP-seconds, NTP-fraction)."""
    return int(t) + DELTA, int((t % 1) * 2**32)

def to_unix(s, f):
    """Convert NTP (seconds, fraction) back to a Unix float timestamp."""
    return (s - DELTA) + f / 2**32


class Pkt:
    """48-byte NTP-style packet carrying four timestamps."""

    def __init__(self):
        self.mode = REQ
        self.seq  = 0
        self.t1s = self.t1f = 0   # T1: client send time
        self.t2s = self.t2f = 0   # T2: server receive time
        self.t3s = self.t3f = 0   # T3: server send time
        self.t4s = self.t4f = 0   # T4: client receive time (informational)
        self.rd   = 0
        self.disp = 0

    # ------------------------------------------------------------------
    def pack(self) -> bytes:
        h = (self.mode & 0xFF) << 24
        return struct.pack(
            FMT, h, self.seq,
            self.t1s, self.t1f,
            self.t2s, self.t2f,
            self.t3s, self.t3f,
            self.t4s, self.t4f,
            self.rd,  self.disp,
        )

    @classmethod
    def unpack(cls, d: bytes) -> "Pkt":
        if len(d) != PKT_SIZE:
            raise ValueError(f"bad packet size {len(d)} (expected {PKT_SIZE})")
        h, seq, t1s, t1f, t2s, t2f, t3s, t3f, t4s, t4f, rd, di = struct.unpack(FMT, d)
        p = cls()
        p.mode = (h >> 24) & 0xFF
        p.seq  = seq
        p.t1s, p.t1f = t1s, t1f
        p.t2s, p.t2f = t2s, t2f
        p.t3s, p.t3f = t3s, t3f
        p.t4s, p.t4f = t4s, t4f
        p.rd  = rd
        p.disp = di
        return p

    # ------------------------------------------------------------------
    # NTP clock-offset  θ = ((T2-T1) + (T3-T4)) / 2
    def offset(self, t4: float) -> float:
        T1 = to_unix(self.t1s, self.t1f)
        T2 = to_unix(self.t2s, self.t2f)
        T3 = to_unix(self.t3s, self.t3f)
        return ((T2 - T1) + (T3 - t4)) / 2

    # Round-trip delay  δ = (T4-T1) - (T3-T2)
    def rtt(self, t4: float) -> float:
        T1 = to_unix(self.t1s, self.t1f)
        T2 = to_unix(self.t2s, self.t2f)
        T3 = to_unix(self.t3s, self.t3f)
        return (t4 - T1) - (T3 - T2)
