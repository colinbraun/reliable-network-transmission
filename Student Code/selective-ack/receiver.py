#!/usr/bin/env python3
from monitor import Monitor
import sys

# Config File
import configparser

def insert_packet(packet_list, packet):
    """
    Insert packet into the packet_list using a binary search
    """

if __name__ == '__main__':
    print("Receivier starting up!")
    config_path = sys.argv[1]

    # Initialize sender monitor
    recv_monitor = Monitor(config_path, 'receiver')
    
    # Parse config file
    cfg = configparser.RawConfigParser(allow_no_value=True)
    cfg.read(config_path)
    sender_id = int(cfg.get('sender', 'id'))
    file_to_send = cfg.get('nodes', 'file_to_send')
    max_packet_size = int(cfg.get('network', 'MAX_PACKET_SIZE'))
    write_location = cfg.get('receiver', 'write_location')

    # with open(write_location, "wb") as f:
    #     print("Start receiving file...")
    #     fin = 0
    #     # bytes_written = 0
    #     while not fin:
    #         addr, packet = recv_monitor.recv(max_packet_size)
    #         # print('--------------')
    #         # print(type(packet))
    #         # print(type(packet[8]))
    #         # print(packet)
    #         # print('--------------')
    #         seq_no = int.from_bytes(packet[:4])
    #         payload_size = int.from_bytes(packet[4:8])
    #         # fin = int.from_bytes(packet[8])
    #         # This is dumb. If you get a slice, you get bytes. If you get a single item, you get an int
    #         fin = packet[8]
    #         # TODO: Consider situation where payload_size = 0
    #         if seq_no == bytes_written:
    #             f.write(packet[9:payload_size+9])
    #             bytes_written += payload_size
    #         # Send back an ACK
    #         print(f"Sending ACK with ack no {bytes_written}")
    #         recv_monitor.send(sender_id, (bytes_written).to_bytes(4))
    nbe = 0
    lbg = 0
    fin = 0
    seq_no = 0
    seq_to_pack_map = {}
    final_nbe = -1
    # while fin == 0 or seq_no != nbe:
    while True:
        # Wait for a packet
        addr, packet = recv_monitor.recv(max_packet_size)
        seq_no = int.from_bytes(packet[0:4], 'big')
        print(f"Received packet with seq no {seq_no}, expecting nbe = {nbe} SEE")
        packet_size = int.from_bytes(packet[4:8], 'big')
        # fin = int.from_bytes(packet[8]) 
        fin = packet[8]
        if fin:
            final_nbe = seq_no + packet_size
        seq_to_pack_map[seq_no] = packet
        if seq_no == nbe:
            nbe += packet_size
            try:
                # Increment NBE until we find what our cummulative ack should be
                while int.from_bytes(seq_to_pack_map[nbe][0:4], 'big') == nbe:
                    packet_size = int.from_bytes(seq_to_pack_map[nbe][4:8], 'big')
                    nbe += packet_size
            except:
                # This happens when the while loop trys a key that does not work
                pass
            # nbe is now updated, send the ack
            print(f"Sending ack with ack no {nbe}")
            recv_monitor.send(sender_id, nbe.to_bytes(4, 'big'))
        else:
            # We received a packet out of order, send an ack containing NBE
            print(f"Out of order packet, sending ack with ack no {nbe}")
            recv_monitor.send(sender_id, nbe.to_bytes(4, 'big') + seq_no.to_bytes(4, 'big'))
        if nbe == final_nbe:
            break

    # Once we are out of the while loop, we are done.
    print("Done receiving file")
    # Now write the file out
    keys_sorted = sorted(seq_to_pack_map.keys())
    with open(write_location, "wb") as f:
        for seq_no in keys_sorted:
            packet = seq_to_pack_map[seq_no]
            # data_size = int.from_bytes(packet[0:4]) - 9
            f.write(packet[9:])
        print("Done writing file")


    # After we are done receiving, it is fine to call recv_end, but keep sending acks back for the last packet.
    recv_monitor.recv_end(write_location, sender_id)
    # Keep sending acks back for last packet if any requests come in
    print("Waiting for any additional packets from sender")
    recv_monitor.socketfd.settimeout(2.5)
    while True:
        try:
            recv_monitor.recv(max_packet_size)
            print("Received additional packet, sending an ack")
            recv_monitor.send(sender_id, nbe.to_bytes(4, 'big'))
        except Exception as e:
            print(e)
            print("BROKE OUT due to timeout")
            break
    print("Done waiting for sender packets")


    # # Exchange messages!
    # addr, data = recv_monitor.recv(max_packet_size)
    # print(f'Receiver: Got message from id {addr}: {data}')
    # print('Receiver: Responding with "Hello, Sender!".')
    # recv_monitor.send(sender_id, b'Hello, Sender!')

    # # Exit! Make sure the receiver ends before the sender. send_end will stop the emulator.
    # recv_monitor.recv_end('received_file', sender_id)
