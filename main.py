from smartoutlet import OutletDevice

# wi-fi settings
ssid_ = ""
wp2_pass = ""

# smart power outlet settings
DEVICE_ID_HERE = ""
IP_ADDRESS = ""
LOCAL_KEY = ""

# connecting to wi-fi
def do_connect():
    import network
    sta_if = network.WLAN(network.STA_IF)
    if not sta_if.isconnected():
        print('connecting to network...')
        sta_if.active(True)
        sta_if.connect(ssid_, wp2_pass)
        while not sta_if.isconnected():
            pass
    print('network config:', sta_if.ifconfig())
do_connect()

# connecting to the power outlet
outlet = OutletDevice(DEVICE_ID_HERE, IP_ADDRESS, LOCAL_KEY)
