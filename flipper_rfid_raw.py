import sys
import struct
import io
from enum import Enum

class ManchesterState(Enum):
    ManchesterStateStart1 = 0
    ManchesterStateMid1 = 1
    ManchesterStateMid0 = 2
    ManchesterStateStart0 = 3

class ManchesterEvent(Enum):
    ManchesterEventShortLow = 0
    ManchesterEventShortHigh = 2
    ManchesterEventLongLow = 4
    ManchesterEventLongHigh = 6
    ManchesterEventReset = 8

transitions = [0b00000001, 0b10010001, 0b10011011, 0b11111011]
EM_READ_SHORT_TIME = 256
EM_READ_LONG_TIME = 512
EM_READ_JITTER_TIME = 100

EM_READ_SHORT_TIME_LOW = EM_READ_SHORT_TIME - EM_READ_JITTER_TIME
EM_READ_SHORT_TIME_HIGH = EM_READ_SHORT_TIME + EM_READ_JITTER_TIME
EM_READ_LONG_TIME_LOW = EM_READ_LONG_TIME - EM_READ_JITTER_TIME
EM_READ_LONG_TIME_HIGH = EM_READ_LONG_TIME + EM_READ_JITTER_TIME

EM_HEADER_POS = 55
EM_STOP_POS = 0
EM_STOP_MASK = 0x1 << EM_STOP_POS
EM_HEADER_MASK = 0x1FF << EM_HEADER_POS
EM_HEADER_AND_STOP_MASK = EM_HEADER_MASK | EM_STOP_MASK
EM_HEADER_AND_STOP_DATA = EM_HEADER_MASK

def varint(f):
    shift = 0
    result = 0
    while True:
        i = f.read(1)[0]
        result |= (i & 0x7f) << shift
        shift += 7
        if not (i & 0x80):
            break

    return result


def r32(f):
    return struct.unpack('I', f.read(4))[0]

def rf(f):
    return struct.unpack('f', f.read(4))[0]


def manchester_advance(state, event):
    result = False
    data = None
    if event == ManchesterEvent.ManchesterEventReset:
        new_state = ManchesterState(ManchesterState.ManchesterStateMid1)
    else:
        new_state = ManchesterState(transitions[state.value] >> event.value & 0x3)
        if new_state == state:
            new_state = ManchesterState.ManchesterStateMid1
        else:
            if new_state == ManchesterState.ManchesterStateMid0:
                data = False
                result = True
            elif new_state == ManchesterState.ManchesterStateMid1:
                data = True
                result = True
    return new_state, result, data


def pd2bit(pulse, duration, level, state):
    event = ManchesterEvent.ManchesterEventReset
    if not level:
        pulse = duration - pulse
    if pulse > EM_READ_SHORT_TIME_LOW and pulse < EM_READ_SHORT_TIME_HIGH:
        if level:
            event = ManchesterEvent.ManchesterEventShortLow
        else:
            event = ManchesterEvent.ManchesterEventShortHigh
    elif pulse > EM_READ_LONG_TIME_LOW and pulse < EM_READ_LONG_TIME_HIGH:
        if level:
            event = ManchesterEvent.ManchesterEventLongLow
        else:
            event = ManchesterEvent.ManchesterEventLongHigh
    if event != ManchesterEvent.ManchesterEventReset:
        (state, data_ok, data) = manchester_advance(state, event)
        if data_ok:
            return (state, '1' if data else '0')
    return (state, None)


with open(sys.argv[1], 'rb') as f:
    assert(f.read(4) == b'RIFL') #magic
    assert(r32(f) == 1) #version

    frequency = rf(f)
    duty_cycle = rf(f)
    max_buffer_size = r32(f)
    #print("frequencey", frequency)
    #print("duty_cycle", duty_cycle)
    #print("max_buffer_size", max_buffer_size)
    smp = 0
    decoded = ''
    (state, data_ok, data) = manchester_advance(ManchesterState.ManchesterStateMid1, ManchesterEvent.ManchesterEventReset)
    level = True
    while True:
        a = f.read(4)
        if len(a) != 4:
            print(decoded)
            break
        bufferlength = struct.unpack('I', a)[0]
        buffer = f.read(bufferlength)

        bio = io.BytesIO(buffer)
        while bio.tell() < len(buffer):
            pulse = varint(bio)
            duration = varint(bio)
            state, result = pd2bit(pulse, duration, True, state)  
            if result != None:
                decoded = decoded + result
            state, result = pd2bit(pulse, duration, False, state)
            if result != None:
                decoded = decoded + result
        
            #print("[%d %d]\t[%d %d]" % (pulse, duration, pulse, duration-pulse))
            #print("0"*pulse + "1"*(duration-pulse), end='')
            #i


    print(bin(EM_HEADER_AND_STOP_DATA))