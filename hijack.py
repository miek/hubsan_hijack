########################################################################
## Intercept control of Hubsan quadcopter
########################################################################

import SoapySDR
from SoapySDR import * #SOAPY_SDR_ constants
import numpy as np
from scipy import signal
from optparse import OptionParser
import time
import os

import gamepad
import hubsan

# The following three one-liners come from 
#   https://oshearesearch.com/index.php/2015/05/31/building-a-burst-fsk-modem-in-gnu-radio-with-message-lambda-blocks-and-eventstream/
def bits2symbols(bits):
    return np.array(bits, dtype=np.float32)*2 - 1

def interp(symbols, sps):
    return np.tile(symbols, [sps, 1]).T.reshape([1, len(symbols)*sps])[0]

def fskmod(x, deviation, samp_rate):
    return np.array(np.exp(1j*2*np.pi*((deviation*x*np.arange(len(x)))/samp_rate)), dtype="complex64")

def generate_packet(gamepad_state, sync, txid, deviation, data_rate, samp_rate):
    throttle = gamepad_state["ABS_Z"]
    rudder = (gamepad_state["ABS_X"] / 512) + 128
    elevator = (gamepad_state["ABS_RY"] / 512) + 128
    aileron = (gamepad_state["ABS_RX"] / -512) + 128
    bits = hubsan.build_packet(sync, throttle, rudder, elevator, aileron, txid)
    syms = bits2symbols(bits)
    # TODO: warn/error on non-integer samp_rate/data_rate
    isyms = interp(syms, int(samp_rate / data_rate))
    return fskmod(isyms, deviation, samp_rate)

def hijack(
    args,
    rate,
    freq=None,
    rxBw=None,
    txBw=None,
    rxChan=0,
    txChan=0,
    rxAnt=None,
    txAnt=None,
    rxGain=None,
    txGain=None,
    clockRate=None,
    numRxSamps=10000,
    dumpDir=None,
    a7105ID=None,
    txID=None,
):
    gp = gamepad.Gamepad()

    sdr = SoapySDR.Device(args)
    if not sdr.hasHardwareTime():
        raise Exception('this device does not support timed streaming')

    #set clock rate first
    if clockRate is not None: sdr.setMasterClockRate(clockRate)

    #set sample rate
    sdr.setSampleRate(SOAPY_SDR_RX, rxChan, rate)
    sdr.setSampleRate(SOAPY_SDR_TX, txChan, rate)
    print("Actual Rx Rate %f Msps"%(sdr.getSampleRate(SOAPY_SDR_RX, rxChan)/1e6))
    print("Actual Tx Rate %f Msps"%(sdr.getSampleRate(SOAPY_SDR_TX, txChan)/1e6))

    #set antenna
    if rxAnt is not None: sdr.setAntenna(SOAPY_SDR_RX, rxChan, rxAnt)
    if txAnt is not None: sdr.setAntenna(SOAPY_SDR_TX, txChan, txAnt)

    #set overall gain
    if rxGain is not None: sdr.setGain(SOAPY_SDR_RX, rxChan, rxGain)
    if txGain is not None: sdr.setGain(SOAPY_SDR_TX, txChan, txGain)

    #tune frontends
    if freq is not None: sdr.setFrequency(SOAPY_SDR_RX, rxChan, freq)
    if freq is not None: sdr.setFrequency(SOAPY_SDR_TX, txChan, freq)

    #set bandwidth
    if rxBw is not None: sdr.setBandwidth(SOAPY_SDR_RX, rxChan, rxBw)
    if txBw is not None: sdr.setBandwidth(SOAPY_SDR_TX, txChan, txBw)

    #create rx and tx streams
    print("Create Rx and Tx streams")
    rxStream = sdr.setupStream(SOAPY_SDR_RX, "CF32", [rxChan])
    txStream = sdr.setupStream(SOAPY_SDR_TX, "CF32", [txChan])

    #let things settle
    time.sleep(1)

    #setup rx buff so we get hardware time updates
    sdr.activateStream(rxStream)

    # transmit pulses
    sdr.activateStream(txStream)
    txTime = sdr.getHardwareTime() + long(0.1e9)
    txFlags = SOAPY_SDR_HAS_TIME | SOAPY_SDR_END_BURST

    retune = 0
    while True:
        try:
            ss = sdr.readStreamStatus(txStream, timeoutUs=int(200))
            if ss.ret != SOAPY_SDR_TIMEOUT:
                print "Status: %s" % str(ss)

            # wait 2ms for the previous packet to finish sending
            if sdr.getHardwareTime() > (txTime + long(2e6)):
                # send packets every 10ms
                txTime += long(10e6)
                packet = generate_packet(gamepad_state=gp.get_state(), sync=a7105ID, txid=txID, deviation=186e3, data_rate=100e3, samp_rate=rate)
                sr = sdr.writeStream(txStream, [packet], len(packet), txFlags, txTime, timeoutUs=1000)
                if sr.ret != len(packet):
                    raise Exception('transmit failed %s'%str(sr))
        except KeyboardInterrupt:
            break

    #cleanup streams
    print("Cleanup streams")
    sdr.deactivateStream(txStream)
    sdr.closeStream(rxStream)
    sdr.closeStream(txStream)


def main():
    parser = OptionParser()
    parser.add_option("--args", type="string", dest="args", help="device factor arguments", default="")
    parser.add_option("--rate", type="float", dest="rate", help="Tx and Rx sample rate", default=4e6)
    parser.add_option("--rxAnt", type="string", dest="rxAnt", help="Optional Rx antenna", default=None)
    parser.add_option("--txAnt", type="string", dest="txAnt", help="Optional Tx antenna", default=None)
    parser.add_option("--rxGain", type="float", dest="rxGain", help="Optional Rx gain (dB)", default=None)
    parser.add_option("--txGain", type="float", dest="txGain", help="Optional Tx gain (dB)", default=None)
    parser.add_option("--rxBw", type="float", dest="rxBw", help="Optional Rx filter bw (Hz)", default=None)
    parser.add_option("--txBw", type="float", dest="txBw", help="Optional Tx filter bw (Hz)", default=None)
    parser.add_option("--rxChan", type="int", dest="rxChan", help="Receiver channel (def=0)", default=0)
    parser.add_option("--txChan", type="int", dest="txChan", help="Transmitter channel (def=0)", default=0)
    parser.add_option("--freq", type="float", dest="freq", help="Optional Tx and Rx freq (Hz)", default=None)
    parser.add_option("--clockRate", type="float", dest="clockRate", help="Optional clock rate (Hz)", default=None)
    parser.add_option("--dumpDir", type="string", dest="dumpDir", help="Optional directory to dump debug samples", default=None)
    parser.add_option("--a7105ID", type="int", dest="a7105ID", help="Optional sync word", default=1)
    parser.add_option("--txID", type="int", dest="txID", help="Optional TX ID", default=1)
    (options, args) = parser.parse_args()
    hijack(
        args=options.args,
        rate=options.rate,
        freq=options.freq,
        rxBw=options.rxBw,
        txBw=options.txBw,
        rxAnt=options.rxAnt,
        txAnt=options.txAnt,
        rxGain=options.rxGain,
        txGain=options.txGain,
        rxChan=options.rxChan,
        txChan=options.txChan,
        clockRate=options.clockRate,
        dumpDir=options.dumpDir,
        a7105ID=options.a7105ID,
        txID=options.txID,
    )

if __name__ == '__main__':
    main()
