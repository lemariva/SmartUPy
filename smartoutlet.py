import ESP32MicroPython.maes as maes
from ESP32MicroPython.md5hash import md5
from ESP32MicroPython.timeutils import RTC

import ubinascii
import json
import logging
import socket

log = logging.getLogger(__name__)
logging.basicConfig()
clock = RTC()

SET = 'set'
PROTOCOL_VERSION_BYTES = b'3.1'

# This is intended to match requests.json payload
# at https://github.com/codetheweb/tuyapi
payload_dict = {
  "device": {
    "status": {
      "hexByte": "0a",
      "command": {"gwId": "", "devId": ""}
    },
    "set": {
      "hexByte": "07",
      "command": {"devId": "", "uid": "", "t": ""}
    },
    "prefix": "000055aa00000000000000",    # Next byte is command byte ("hexByte") some zero padding, then length of remaining payload, i.e. command + suffix (unclear if multiple bytes used for length, zero padding implies could be more than one byte)
    "suffix": "000000000000aa55"
  }
}

def hex2bin(x):
    return ubinascii.unhexlify(x)

def bin2hex(x):
    space = ''
    result = ''.join('%02X%s' % (y, space) for y in x)
    return result


class AESCipher():
    def __init__(self, key):
        # self.bs = 32  # 32 work fines for ON, does not work for OFF.
        # Padding different compared to js version https://github.com/codetheweb/tuyapi/
        self.bs = 16
        self.key = key

    def encrypt(self, raw):
        raw = self._pad(raw)
        cipher = maes.new(self.key, maes.MODE_ECB)
        crypted_text = cipher.encrypt(raw)
        crypted_text_b64 = ubinascii.b2a_base64(crypted_text)
        return crypted_text_b64

    def decrypt(self, enc):
        enc = ubinascii.a2b_base64(enc)
        cipher = maes.new(self.key, maes.MODE_ECB)
        raw = cipher.decrypt(enc)
        return self._unpad(raw).decode('utf-8')

    def _pad(self, s):
        padnum = self.bs - len(s) % self.bs
        return s + padnum * chr(padnum).encode()

    @staticmethod
    def _unpad(dec):
        s = bytes(bytearray(dec))
        return s[:-ord(s[len(s)-1:])]

class TuyaDevice(object):
    def __init__(self, dev_id, address, local_key=None, dev_type=None, connection_timeout=10):
        """
        Represents a Tuya device.

        Args:
            dev_id (str): The device id.
            address (str): The network address.
            local_key (str, optional): The encryption key. Defaults to None.
            dev_type (str, optional): The device type.
                It will be used as key for lookups in payload_dict.
                Defaults to None.

        Attributes:
            port (int): The port to connect to.
        """
        self.id = dev_id
        self.address = address
        self.local_key = local_key
        self.local_key = local_key.encode('latin1')
        self.dev_type = dev_type
        self.connection_timeout = connection_timeout

        self.port = 6668  # default - do not expect caller to pass in

    def __repr__(self):
        return '%r' % ((self.id, self.address),)  # FIXME can do better than this

    def _send_receive(self, payload):
        """
        Send single buffer `payload` and receive a single buffer.

        Args:
            payload(bytes): Data to send.
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.connection_timeout)
        s.connect((self.address, self.port))
        s.send(payload)
        data = s.recv(1024)
        s.close()
        return data

    def generate_payload(self, command, data=None):
        """
        Generate the payload to send.

        Args:
            command(str): The type of command.
                This is one of the entries from payload_dict
            data(dict, optional): The data to be send.
                This is what will be passed via the 'dps' entry
        """
        json_data = payload_dict[self.dev_type][command]['command']
        clock.ntp_sync()

        if 'gwId' in json_data:
            json_data['gwId'] = self.id
        if 'devId' in json_data:
            json_data['devId'] = self.id
        if 'uid' in json_data:
            json_data['uid'] = self.id  # still use id, no seperate uid
        if 't' in json_data:
            json_data['t'] = str(clock.utcnow())

        if data is not None:
            json_data['dps'] = data

        # Create byte buffer from hex data
        json_payload = json.dumps(json_data)
        json_payload = json_payload.replace(' ', '')  # if spaces are not removed device does not respond!
        json_payload = json_payload.encode('utf-8')
        log.debug('json_payload=%r', json_payload)

        if command == SET:
            # need to encrypt
            self.cipher = AESCipher(self.local_key)  # expect to connect and then disconnect to set new
            json_payload = self.cipher.encrypt(json_payload)
            preMd5String = b'data=' + json_payload + b'||lpv=' + PROTOCOL_VERSION_BYTES + b'||' + self.local_key
            m = md5()
            m.update(preMd5String)
            hexdigest = m.hexdigest()

            json_payload = PROTOCOL_VERSION_BYTES + hexdigest[8:][:16].encode('latin1') + json_payload

            self.cipher = None  # expect to connect and then disconnect to set new

        postfix_payload = hex2bin(bin2hex(json_payload) + payload_dict[self.dev_type]['suffix'])

        assert len(postfix_payload) <= 0xff
        postfix_payload_hex_len = '%x' % len(postfix_payload)  # TODO this assumes a single byte 0-255 (0x00-0xff)
        buffer = hex2bin( payload_dict[self.dev_type]['prefix'] +
                          payload_dict[self.dev_type][command]['hexByte'] +
                          '000000' +
                          postfix_payload_hex_len ) + postfix_payload
        return buffer



class GenericDevice(TuyaDevice):
    def __init__(self, dev_id, address, local_key=None, dev_type=None):
        super(GenericDevice, self).__init__(dev_id, address, local_key, dev_type)

    def status(self):
        log.debug('status() entry')
        # open device, send request, then close connection
        payload = self.generate_payload('status')

        data = self._send_receive(payload)
        log.debug('status received data=%r', data)

        result = data[20:-8]  # hard coded offsets
        log.debug('result=%r', result)

        if result.startswith(b'{'):
            # this is the regular expected code path
            if not isinstance(result, str):
                result = result.decode()
            result = json.loads(result)
        elif result.startswith(PROTOCOL_VERSION_BYTES):
            # got an encrypted payload, happens occasionally
            # expect resulting json to look similar to:: {"devId":"ID","dps":{"1":true,"2":0},"t":EPOCH_SECS,"s":3_DIGIT_NUM}
            # NOTE dps.2 may or may not be present
            result = result[len(PROTOCOL_VERSION_BYTES):]  # remove version header
            result = result[16:]  # remove (what I'm guessing, but not confirmed is) 16-bytes of MD5 hexdigest of payload
            cipher = AESCipher(self.local_key)
            result = cipher.decrypt(result)
            log.debug('decrypted result=%r', result)
            if not isinstance(result, str):
                result = result.decode()
            result = json.loads(result)
        else:
            log.error('Unexpected status() payload=%r', result)

        return result

    def set_status(self, on, switch=1):
        """
        Set status of the device to 'on' or 'off'.

        Args:
            on(bool):  True for 'on', False for 'off'.
            switch(int): The switch to set
        """
        # open device, send request, then close connection
        if isinstance(switch, int):
            switch = str(switch)  # index and payload is a string
        payload = self.generate_payload(SET, {switch:on})

        data = self._send_receive(payload)
        log.debug('set_status received data=%r', data)

        return data

    def turn_on(self, switch=1):
        """Turn the device on"""
        self.set_status(True, switch)

    def turn_off(self, switch=1):
        """Turn the device off"""
        self.set_status(False, switch)

    def set_timer(self, num_secs):
        """
        Set a timer.

        Args:
            num_secs(int): Number of seconds
        """
        # FIXME / TODO support schemas? Accept timer id number as parameter?
        # Dumb heuristic; Query status, pick last device id as that is probably the timer
        status = self.status()
        devices = status['dps']
        devices_numbers = list(devices.keys())
        devices_numbers.sort()
        dps_id = devices_numbers[-1]

        payload = self.generate_payload(SET, {dps_id:num_secs})

        data = self._send_receive(payload)
        log.debug('set_timer received data=%r', data)
        return data


class OutletDevice(GenericDevice):
    def __init__(self, dev_id, address, local_key=None):
        dev_type = 'device'
        super(OutletDevice, self).__init__(dev_id, address, local_key, dev_type)
