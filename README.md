# Computer-Networks---Mini-Project
Topic - Distributed Clock Synchronization System
The project demonstrates core networking concepts including UDP socket programming, time-offset calculation, drift correction using low level socket programming. It synchronizes the clocks of multiple client machines to a central time server over a local area network. One laptop acts as the server and up to N clients connect to it automatically, exchange timestamped packets, calculate their clock offset relative to the server, and apply corrections to stay in sync. 
Features:
1. Time Request-Reply
  -> Client sends a REQ packet with its send timestamp (T1)
  -> Server records receive time (T2), stamps send time (T3), echoes all back
  -> Client records receive time (T4) and computes offset and RTT

2. Offset and Delay Calculation
  -> NTP-standard four-timestamp math for accurate offset calculation
  -> Symmetric network delay assumed; asymmetry shows up as residual offset
  -> Results displayed per-packet and summarized at the end

3. Drift Correction (PLL)
  -> Step correction — if offset exceeds 128ms, the clock is stepped immediately
  -> Slew correction — for smaller offsets, a proportional gain (GAIN=0.125) gradually adjusts the frequency
  -> Frequency correction capped at ±500 ppm to prevent overcorrection

4. Accuracy Evaluation
  -> Mean offset — average clock difference over all samples
  -> Min/Max RTT — network latency range
  -> PLL frequency adjustment — shows the drift rate in parts per million
  -> Outlier rejection — packets with RTT > 3× (the median are discarded)
