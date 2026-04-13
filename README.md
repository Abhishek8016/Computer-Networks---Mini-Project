# Team members:\
Abhishek M PES1UG24AM012\
Anarghyaa Kashyap PES1UG24AM039\
Aaditya Vijaywargi PES1UG24AM003\

# Computer-Networks---Mini-Project  (TEAM 14, PROJECT 10)

Topic - Distributed Clock Synchronization System

The Distributed Clock Synchronization System is a network-based project designed to demonstrate key concepts from computer networks, distributed systems, and low-level socket programming. The goal of the project is to synchronize the clocks of multiple client machines with a central server over a Local Area Network (LAN) using UDP communication and NTP-style timestamp calculations. In distributed systems, accurate time synchronization is essential for applications such as logging, transaction ordering, sensor coordination, distributed databases, multimedia streaming, and real-time systems. Since each computer maintains its own hardware clock, small differences in oscillator frequencies cause clocks to drift apart over time. This project implements a simplified version of the Network Time Protocol (NTP) to measure these differences and correct them dynamically. 

System Architecture --> 
The system follows a client–server architecture. One machine acts as the Time Server, providing the reference clock. Multiple machines act as Clients, which adjust their clocks based on the server’s time. Communication occurs using UDP socket programming, which provides low-latency transmission suitable for time-sensitive applications. Clients automatically discover or connect to the server and periodically exchange timestamped packets. The system supports multiple clients simultaneously, making it a distributed synchronization solution.

Core Concepts -->
The Distributed Clock Synchronization System is based on several core concepts from computer networks and distributed systems. UDP socket programming is used to enable fast, connectionless communication between a central server and multiple clients over a LAN with minimal delay. The system applies the four-timestamp synchronization method (T1, T2, T3, T4), where the client and server exchange timestamped packets to calculate Round Trip Time (RTT), defined as the total time taken for a message to travel from client to server and back, and clock offset, defined as the time difference between the client’s clock and the server’s reference clock. Because computer clocks naturally drift due to hardware frequency differences, the system uses drift correction through a Phase Locked Loop (PLL), a feedback control mechanism that adjusts clock time either by step correction (immediate adjustment for large errors) or slew correction (gradual frequency adjustment for small errors). To improve accuracy, the system performs statistical evaluation, including mean offset (average synchronization error), jitter (variation in packet delay), and outlier rejection (discarding unusually delayed packets), ensuring stable and precise synchronization similar to real-world protocols like Network Time Protocol (NTP).
