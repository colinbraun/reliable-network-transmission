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
    print("Sender starting up!")
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
    # window_size = int(cfg.get('sender', 'window_size'))
    delay = float(cfg.get('network', 'PROP_DELAY'))
    # Tests showed that 3.1 is very good
    # These tests were done with 200k BW.
    # Goodput Mean[std]: 107016.625[5857.757251444019]
    # Overheads Mean[std]: 0.3580145540969421[0.031529922431872484]
    TIMEOUT = delay * 3.1
    # The header size including what monitor.py tacks on (it tacks on 4 bytes)
    HEADER_SIZE = 13
    # TIMEOUT = delay * 4
    bw = int(cfg.get('network', 'LINK_BANDWIDTH'))
    # Update max packet size depending on BW. This handles situations where we have low bandwidth.
    max_packet_size = max(min(max_packet_size, int(bw/4)), HEADER_SIZE+1)
    # Set the window size to the BDP
    window_size = math.ceil(delay * bw * 2)
    # window_size = 80000
    print(f"MAX PACKET SIZE IS: {max_packet_size}")
    print(f"WINDOW SIZE IS: {window_size}")

    with open(file_to_send, "rb") as f:
        f.seek(0, 2)
        file_size = f.tell()
        f.seek(0, 0)
        print("Start sending file...")
        seq_no_b = (0).to_bytes(4, 'big')
        fin_b = (0).to_bytes(1, 'big')
        lbs = 0
        lba = 0
        time_queue = queue.Queue()
        all_packets_sent = False
        all_acks_received = False
        packets_in_flight = 0

        # The actual monitor send function has 4 bytes of overhead itself.
        # With 9 bytes of overhead, we can only send 13 bytes of data less than the maximum
        while (payload := f.read(max_packet_size-HEADER_SIZE)):
            if file_size - f.tell() == 0:
                print("Hit end of file, setting fin to 1")
                fin_b = (1).to_bytes(1, 'big')
                all_packets_sent = True
            packet_size_b = (len(payload) + 9).to_bytes(4, 'big')
            seq_no_b = lbs.to_bytes(4, 'big')
            packet = seq_no_b + packet_size_b + fin_b + payload
            print(f"First attempt to send packet with seq no {lbs}")
            send_monitor.send(receiver_id, packet)
            packets_in_flight += 1
            time_queue.put((time.time() + TIMEOUT, lbs, packet))
            lbs = lbs + int.from_bytes(packet_size_b, 'big')
            # While our effective window is <= 0, sit there receiving
            # while (window_size - (lbs - lba) <= 0 or (all_packets_sent and not all_acks_received)) and not time_queue.empty():
            while (window_size - (lbs - lba) <= 0) or packets_in_flight >= 50 or (all_packets_sent and not all_acks_received):
                print(f"lbs: {lbs}")
                print(f"lba: {lba}")
                print(f"lbs - lba: {lbs - lba}")
                # Get the next timeout. Do not block waiting for an item
                # print(time_queue.queue)
                # timeout, seq_no_temp, packet_temp = time_queue.get(False)
                timeout, seq_no_temp, packet_temp = time_queue.queue[0]
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
                        print(f"Received ack with ack no {lba}")
                        # if lba <= seq_no_temp:
                        # Pop values until either queue is empty or we find lba
                        # while not time_queue.empty() and time_queue.queue[0][1] != lba:
                        while not time_queue.empty() and time_queue.queue[0][1] < lba:
                            print(f"Popping buffered packet with seq no {time_queue.get(False)[1]}")
                            packets_in_flight -=1
                        # If we have sent all the packets and gotten the last ack -> all acks received
                        if all_packets_sent and lba == lbs:
                            print("Received all acks")
                            all_acks_received = True
                    except:
                        # If we timeout, resend it
                        print(f"TIMEOUT, resending seq_no: {seq_no_temp}")
                        # print_queue(time_queue)
                        # Pop the value out, it will be readded to the back of the queue
                        time_queue.get(False)
                        send_monitor.send(receiver_id, packet_temp)
                        # Readd it to the queue
                        time_queue.put((time.time() + TIMEOUT, seq_no_temp, packet_temp))
                # If it wasn't positive, it has already timed out. Resend it.
                else:
                        print(f"Unusual timeout, resending seq_no: {seq_no_temp}")
                        # Pop the value out, it will be readded to the back of the queue
                        time_queue.get(False)
                        send_monitor.send(receiver_id, packet_temp)
                        # Readd it to the queue
                        time_queue.put((time.time() + TIMEOUT, seq_no_temp, packet_temp))

    # Done sending the file, tell the receiver we are done
    print("Done sending file...")
    send_monitor.send_end(receiver_id)


    # Exchange messages!
    # print('Sender: Sending "Hello, World!" to receiver.')
    # send_monitor.send(receiver_id, b'Hello, World!')
    # addr, data = send_monitor.recv(max_packet_size)
    # print(f'Sender: Got response from id {addr}: {data}')

    # Exit! Make sure the receiver ends before the sender. send_end will stop the emulator.
    # send_monitor.send_end(receiver_id)
