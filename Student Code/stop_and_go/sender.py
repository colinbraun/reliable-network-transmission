#!/usr/bin/env python3
from monitor import Monitor
import sys

# Config File
import configparser

# Header format: 32 bit sequence number (indiciating the number assigned to first byte in packet)
if __name__ == '__main__':
    print("Sender starting up!")
    config_path = sys.argv[1]

    # Initialize sender monitor
    send_monitor = Monitor(config_path, 'sender')
    
    # Parse config file
    cfg = configparser.RawConfigParser(allow_no_value=True)
    cfg.read(config_path)
    receiver_id = int(cfg.get('receiver', 'id'))
    file_to_send = cfg.get('nodes', 'file_to_send')
    max_packet_size = int(cfg.get('network', 'MAX_PACKET_SIZE'))
    bw = int(cfg.get('network', 'LINK_BANDWIDTH'))
    # Update max packet size depending on BW. This handles situations where we have low bandwidth.
    # max_packet_size = min(max_packet_size, int(bw*0.9))
    delay = float(cfg.get('network', 'PROP_DELAY'))
    TIMEOUT = delay * 10
    # send_monitor.socketfd.settimeout(0.3)
    send_monitor.socketfd.settimeout(TIMEOUT)

    with open(file_to_send, "rb") as f:
        f.seek(0, 2)
        file_size = f.tell()
        f.seek(0, 0)
        print("Start sending file...")
        seq_no_b = (0).to_bytes(4)
        fin_b = (0).to_bytes(1)
        # The actual monitor send function has 4 bytes of overhead itself.
        # With 9 bytes of overhead, we can only send 13 bytes of data less than the maximum
        while (payload := f.read(max_packet_size-13)):
            if file_size - f.tell() == 0:
                print("Hit end of file, setting fin to 1")
                fin_b = (1).to_bytes(1)
            payload_size_b = len(payload).to_bytes(4)
            packet = seq_no_b + payload_size_b + fin_b + payload
            timed_out = True
            while timed_out:
                # TODO: Possibly adjust the payload size to depend on max packet size
                # Send the packet
                send_monitor.send(receiver_id, packet)
                # Wait for ACK
                try:
                    addr, data = send_monitor.recv(max_packet_size)
                    timed_out = False
                except:
                    # This except happens when we timeout. Resend.
                    print(f"Timed out, resending packet with seq no {int.from_bytes(seq_no_b)}")
                    timed_out = True
                # Receiver only need respond with seq no.
            # We have finally received the ACK for that packet. We can send the next one.
            ack_no_b = data[:4]
            seq_no_b = ack_no_b
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