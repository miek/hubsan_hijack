import bitarray
import struct

def gen_checksum(payload):
    s = sum(ord(c) for c in payload)
    cs = 256 - (s % 256)
    return cs if cs < 256 else 0

def build_packet(addr, throttle, rudder, elevator, aileron, tx_id):
    pkt = bitarray.bitarray()
    pkt.frombytes(struct.pack('>II', 0xAAAAAAAA, addr))

    payload = bitarray.bitarray()
    payload.frombytes(struct.pack('>B4HBBI', 0x20, throttle, rudder, elevator, aileron, 0x02, 0x61, tx_id))

    checksum = gen_checksum(payload.tobytes())
    pkt += payload
    pkt.frombytes(struct.pack('>B', checksum))
    return [int(b) for b in pkt]
