#!/usr/bin/env python3
from monitor import Monitor
import sys
import queue
import time
import math
# import datetime

# Config File
import configparser

def print_queue(q):
    print("QUEUE START")
    for i in range(len(q.queue)):
        print(q.queue[i][1])
    print("QUEUE END")

# Header format: 32 bit sequence number (indiciating the number assigned to first byte in packet)
if __name__ == '__main__':
    # print("Sender starting up!")
    # with open("../../temp.txt", "a") as f:
    #     f.write(f"Appending to temp.txt as a test for grader. Date: {str(datetime.datetime.now())}")
    config_path = sys.argv[1]

    # Initialize sender monitor
    send_monitor = Monitor(config_path, 'sender')
    send_monitor.socketfd.settimeout(0.5)
    
    # Parse config file
    cfg = configparser.RawConfigParser(allow_no_value=True)
    cfg.read(config_path)
    receiver_id = int(cfg.get('receiver', 'id'))
    file_to_send = cfg.get('nodes', 'file_to_send')
    max_packet_size = int(cfg.get('network', 'MAX_PACKET_SIZE'))
    delay = float(cfg.get('network', 'PROP_DELAY'))
    # The header size including what monitor.py tacks on (it tacks on 4 bytes)
    HEADER_SIZE = 9
    bw = int(cfg.get('network', 'LINK_BANDWIDTH'))
    # Update max packet size depending on BW. This handles situations where we have low bandwidth.
    max_packet_size = max(min(max_packet_size, int(bw/4)), HEADER_SIZE+1)
    # window_size = math.ceil(delay * bw * 2)
    # Set the window size to the BDP
    window_size_packets = math.ceil(delay * bw * 2.0 / max_packet_size)
    # window_size_packets = round(80000/max_packet_size)
    print(f"MAX PACKET SIZE IS: {max_packet_size}")
    print(f"WINDOW SIZE (PACKETS) IS: {window_size_packets}")
    # Smoothed RTT Estimator (initially 3*prop delay):
    R = delay*3
    # Smoothing factor
    alpha = 0.9
    # Delay variance factor
    beta = 1.5
    TIMEOUT = R * beta
    # The actual selected timeout is TIMEOUT above (RTO on webpage)

    with open(file_to_send, "rb") as f:
        f.seek(0, 2)
        file_size = f.tell()
        f.seek(0, 0)
        # print("Start sending file...")
        seq_no_b = (0).to_bytes(4, 'big')
        fin_b = (0).to_bytes(1, 'big')
        lbs = 0
        lba = 0
        time_queue = queue.Queue()
        all_packets_sent = False
        all_acks_received = False
        packets_in_flight = 0
        acked_seq_nos = set()
        # Note the 0 below is intentional. This has to do with acks coming back as NBE, not the first byte of the ack'd packet
        sent_seq_nos = [0]
        sent_seq_nos_index = 0

        # The actual monitor send function has 4 bytes of overhead itself.
        # With 9 bytes of overhead, we can only send 13 bytes of data less than the maximum
        while (payload := f.read(max_packet_size-HEADER_SIZE)):
            if file_size - f.tell() == 0:
                # print("Hit end of file, setting fin to 1")
                fin_b = (1).to_bytes(1, 'big')
                all_packets_sent = True
            seq_no_b = lbs.to_bytes(4, 'big')
            packet = seq_no_b + fin_b + payload
            # print(f"First attempt to send packet with seq no {lbs} SEE")
            send_monitor.send(receiver_id, packet)
            packets_in_flight += 1
            # Time queue entries: (Time at which packet is considered timed out, seq no, the packet itself, the TIMEOUT it was given, retransmitted)
            time_queue.put((time.time() + TIMEOUT, lbs, packet, TIMEOUT, False))
            lbs = lbs + len(packet)
            sent_seq_nos.append(lbs)
            while (window_size_packets <= packets_in_flight) or packets_in_flight >= 50 or (all_packets_sent and not all_acks_received):
                # print(f"Packets in flight: {packets_in_flight} SEE")
                # Read the details about the first packet in the queue (not popping it here)
                timeout, seq_no_temp, packet_temp, _, _ = time_queue.queue[0]
                timeout -= time.time()
                # Sanity check that timeout is positive
                if timeout > 0:
                    send_monitor.socketfd.settimeout(timeout)
                    try:
                        # Try to receive a packet
                        addr, data = send_monitor.recv(max_packet_size)
                        # If we get here, we received an ack. Update lba.
                        lba_received = int.from_bytes(data[0:4], 'big')
                        lba = lba_received if lba_received > lba else lba
                        # Check if the message contains a selective ack
                        if len(data) > 4:
                            selective_seq_no = int.from_bytes(data[4:8], 'big')
                            # print(f"Received SELECTIVE ack with ack no {lba_received}, selective ack no {selective_seq_no} SEE")
                            # If we haven't received this ack before, add it to acked seq nos and allow another packet to be sent
                            if selective_seq_no not in acked_seq_nos:
                                acked_seq_nos.add(selective_seq_no)
                                packets_in_flight -= 1
                        # else:
                        #     print(f"Received CUMULATIVE ack with ack no {lba_received}")
                        # Update acked seq nos and packets in flight
                        while lba > sent_seq_nos[sent_seq_nos_index]:
                            if sent_seq_nos[sent_seq_nos_index] not in acked_seq_nos:
                                packets_in_flight -= 1
                                acked_seq_nos.add(sent_seq_nos[sent_seq_nos_index])
                            sent_seq_nos_index += 1
                        while sent_seq_nos[sent_seq_nos_index] in acked_seq_nos:
                            sent_seq_nos_index += 1
                        # print(f"lba before adjustment: {lba}", "SEE")
                        lba = sent_seq_nos[sent_seq_nos_index]
                        # print(f"lba after adjustment: {lba}", "SEE")

                        # Pop values until either queue is empty or we find lba
                        while not time_queue.empty() and time_queue.queue[0][1] < lba:
                            # Try to measure the RTT if this is not a retransmission
                            if not time_queue.queue[0][4]:
                                m = time.time() - (time_queue.queue[0][0] - time_queue.queue[0][3])
                                R = alpha*R + (1-alpha)*m
                                old_timeout = TIMEOUT
                                TIMEOUT = R * beta
                                # print(f"Measured RTT of {m} secs, old timeout = {old_timeout}, new timeout = {TIMEOUT} SEE")
                            # print(f"1Popping buffered packet with seq no {time_queue.get(False)[1]} SEE")
                            time_queue.get(False)
                        # If we have sent all the packets and gotten the last ack -> all acks received
                        if all_packets_sent and lba == lbs:
                            # print("Received all acks")
                            all_acks_received = True
                    except:
                        # If we timeout, see if we have the ack, otherwise resend
                        if seq_no_temp in acked_seq_nos:
                            # Pop it if we already have the ack, and continue on
                            # print(f"2Popping buffered packet with seq no {time_queue.get(False)[1]} SEE")
                            time_queue.get(False)
                            continue
                        # print(f"TIMEOUT, resending seq_no: {seq_no_temp}")
                        # Pop the value out, it will be readded to the back of the queue
                        # print(f"3Popping buffered packet with seq no {time_queue.get(False)[1]} SEE")
                        time_queue.get(False)
                        send_monitor.send(receiver_id, packet_temp)
                        # Readd it to the queue
                        time_queue.put((time.time() + TIMEOUT, seq_no_temp, packet_temp, TIMEOUT, True))
                # If it wasn't positive, it has already timed out. Resend it.
                else:
                    # If we timeout, see if we have the ack, otherwise resend
                    if seq_no_temp in acked_seq_nos:
                        # Pop it if we already have the ack, and continue on
                        # print(f"4Popping buffered packet with seq no {time_queue.get(False)[1]} SEE")
                        time_queue.get(False)
                        continue
                    # print(f"Unusual timeout, resending seq_no: {seq_no_temp}")
                    # Pop the value out, it will be readded to the back of the queue
                    # print(f"5Popping buffered packet with seq no {time_queue.get(False)[1]} SEE")
                    time_queue.get(False)
                    send_monitor.send(receiver_id, packet_temp)
                    # Readd it to the queue
                    time_queue.put((time.time() + TIMEOUT, seq_no_temp, packet_temp, TIMEOUT, True))

    # Done sending the file, tell the receiver we are done
    print("Done sending file...")
    send_monitor.send_end(receiver_id)
