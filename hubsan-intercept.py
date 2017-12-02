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

def generate_cf32_pulse(numSamps, scaleFactor=0.8):
    return np.array([scaleFactor]*numSamps, np.complex64)

def measure_delay(
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
    numTxSamps=1900,
    numRxSamps=10000,
    dumpDir=None,
):
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
    txPulse = generate_cf32_pulse(numTxSamps)
    txFlags = SOAPY_SDR_HAS_TIME | SOAPY_SDR_END_BURST

    retune = 0
    while True:
        if sdr.getHardwareTime() > (txTime + long(1e6)):
            txTime += long(10e6)
            sr = sdr.writeStream(txStream, [txPulse], len(txPulse), txFlags, txTime, timeoutUs=1000000)
            if sr.ret != len(txPulse): raise Exception('transmit failed %s'%str(sr))
#            time.sleep(0.001)
#            if retune > 3:
#                sdr.setFrequency(SOAPY_SDR_TX, txChan, 1e9 + 1e6)
#                retune = 0
#            elif retune == 0:
#                sdr.setFrequency(SOAPY_SDR_TX, txChan, 1e9);
#                retune += 1
#            else:
#                retune += 1

    #cleanup streams
    print("Cleanup streams")
    sdr.deactivateStream(txStream)
    sdr.closeStream(rxStream)
    sdr.closeStream(txStream)


def main():
    parser = OptionParser()
    parser.add_option("--args", type="string", dest="args", help="device factor arguments", default="")
    parser.add_option("--rate", type="float", dest="rate", help="Tx and Rx sample rate", default=1e6)
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
    (options, args) = parser.parse_args()
    measure_delay(
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
    )

if __name__ == '__main__': main()
