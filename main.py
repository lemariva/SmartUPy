from smartoutlet import OutletDevice
from MicroWebSrv.microWebSrv import MicroWebSrv
from MicroWebSrv.microWebTemplate import MicroWebTemplate
import gc
# wi-fi settings
ssid_ = ""
wp2_pass = ""

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

# smart power outlet settings
devices = [
    {
     "name": "smarttom",
     "devIp": "192.168.178.139",
     "devId": "80023....",
     "lokalKey": "559...",
    },
    {
     "name": "smarttom",
     "devIp": "192.168.178.139",
     "devId": "80023....",
     "lokalKey": "559....",
    }
]

# connecting to the power outlets
outlet = []
for j in range(0, len(devices)):
    outlet.append(OutletDevice(devices[j]['devId'], devices[j]['devIp'], devices[j]['lokalKey']))

# ----------------------------------------------------------------------------

@MicroWebSrv.route('/status', 'POST')
def _httpHandlerTestPost(httpClient, httpResponse) :
    formData  = httpClient.ReadRequestPostedFormData()
    try:
        if(formData['action'] == 'turnon'):
            outlet[int(formData['device'])].turn_on()
        elif(formData['action'] == 'turnoff'):
            outlet[int(formData['device'])].turn_off()

        content = str(outlet[int(formData['device'])].status())
        gc.collect()
    except Exception as e:
        content = "Error" + e;
        print(e)
    httpResponse.WriteResponseOk( headers		 = None,
								  contentType	 = "text/html",
								  contentCharset = "UTF-8",
								  content 		 = content )

@MicroWebSrv.route('/sockets')
def _httpHandlerTestGet(httpClient, httpResponse) :
    try:
        file = open("www/index_test.pyhtml", "r")
        content = file.read()
        content = content.replace("#devices#", str(len(devices)))
        webpage = MicroWebTemplate(content)
        content = webpage.Execute()
        gc.collect()
    except Exception as e:
        print(e)
    httpResponse.WriteResponseOk( headers		 = None,
								  contentType	 = "text/html",
								  contentCharset = "UTF-8",
								  content 		 = content )



# ----------------------------------------------------------------------------

def _acceptWebSocketCallback(webSocket, httpClient) :
	print("WS ACCEPT")
	webSocket.RecvTextCallback   = _recvTextCallback
	webSocket.RecvBinaryCallback = _recvBinaryCallback
	webSocket.ClosedCallback 	 = _closedCallback

def _recvTextCallback(webSocket, msg) :
	print("WS RECV TEXT : %s" % msg)
	webSocket.SendText("Reply for %s" % msg)

def _recvBinaryCallback(webSocket, data) :
	print("WS RECV DATA : %s" % data)

def _closedCallback(webSocket) :
	print("WS CLOSED")


# ----------------------------------------------------------------------------
srv = MicroWebSrv(webPath='www/')
srv.MaxWebSocketRecvLen     = 256
srv.WebSocketThreaded		= False
srv.AcceptWebSocketCallback = _acceptWebSocketCallback
srv.Start(threaded=False)
gc.collect()
