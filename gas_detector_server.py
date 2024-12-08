import RPi.GPIO as GPIO
from http.server import BaseHTTPRequestHandler, HTTPServer
import time
import threading
from gpiozero import Button, LED, Buzzer, MCP3008

# Set the IP address and port
host_name = '192.168.1.165'  # Update with your Raspberry Pi IP address
host_port = 5000             # Update the port to 5000

# GPIO Setup
def setupGPIO():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(17, GPIO.OUT)  # Use GPIO pin 17 for the LED
    GPIO.setup(2, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Button connected to GPIO pin 2 (with pull-up resistor)
    GPIO.setup(27, GPIO.OUT)  # Buzzer connected to GPIO pin 27

# Define components for the gas sensor
button = Button(2)
led = LED(17)
buzzer = Buzzer(27)
gas_sensor = MCP3008(1)

# Variables
gas_sensor_status = False
threshold = 0.03

def arm_gas_sensor():
    """Toggle the gas sensor status on button press."""
    global gas_sensor_status
    if gas_sensor_status:
        gas_sensor_status = False
        led.off()
        print("GAS SENSOR DISARMED.")
    else:
        gas_sensor_status = True
        led.on()
        print("GAS SENSOR ARMED.")

def check_button_press():
    """Function to check the button press and trigger the buzzer."""
    if GPIO.input(2) == GPIO.LOW:  # Button is pressed when the GPIO pin is LOW
        print("Button Pressed! Activating Buzzer.")
        GPIO.output(27, GPIO.HIGH)  # Turn the buzzer on
        time.sleep(1)  # Buzzer stays on for 1 second
        GPIO.output(27, GPIO.LOW)   # Turn the buzzer off

def check_gas_sensor():
    """Check the gas sensor status and trigger alarm if needed."""
    global gas_sensor_status
    gas_value = gas_sensor.value
    print(f"Gas Sensor Value: {gas_value:.2f}")

    if gas_sensor_status and gas_value > threshold:
        led.on()
        print("ALARM! GAS LEVEL EXCEED THRESHOLD!")
        buzzer.beep(on_time=0.5, off_time=0.5, n=3, background=False)  # 3 short beeps
    else:
        led.off()
        buzzer.off()
        print("System is normal.")

class MyServer(BaseHTTPRequestHandler):

    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def _redirect(self, path):
        self.send_response(303)
        self.send_header('Content-type', 'text/html')
        self.send_header('Location', path)
        self.end_headers()

    def do_GET(self):
        if self.path == "/styles.css":
        # Serve the CSS file
            self.send_response(200)
            self.send_header('Content-type', 'text/css')
            self.end_headers()
            with open("styles.css", "r") as file:
                self.wfile.write(file.read().encode())
            return
        
        elif self.path == "/script.js":
        # Serve the JavaScript file
            self.send_response(200)
            self.send_header('Content-type', 'application/javascript')
            self.end_headers()
            with open("script.js", "r") as file:
                self.wfile.write(file.read().encode())
            return
    
        # Get the current gas sensor value
        gas_value = gas_sensor.value
        gas_status = "ARMED" if gas_sensor_status else "DISARMED"
        alarm_status = "ALARM! GAS LEVEL EXCEEDS THRESHOLD!" if gas_value > threshold else "System is normal."

        # HTML response for GET requests
        html = '''
        <html>
            <head>
                <link rel="stylesheet" type="text/css" href="/styles.css">
                <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
                <script src="/script.js"></script>  <!-- Link to external JS file -->
            </head>
            <body>
            <div class="container">
                <h1>Smoke and Fire Alarm with Raspberry Pi 4</h1>
                <div>
                    <i class="fas fa-fire-alt" style="color: red; font-size: 48px;" title="Fire Alarm Icon"></i>
                    <i class="fas fa-bell" style="color: orange; font-size: 48px;" title="Buzzer Icon"></i>
                </div>
                <p>Gas Sensor Status: {}</p>
                <p>Gas Sensor Value: {:.2f}</p>
                <p>Status: {}</p>
                <form action="/" method="POST">
                    <input class="on" type="submit" name="submit" value="On">
                    <input class="off" type="submit" name="submit" value="Off">
                </form>
                <button class="refresh" type="submit" name="submit" onclick="refreshPage()">Refresh</button>  <!-- Refresh button -->
            </div>
            </body>
            </html>
        '''
        self.do_HEAD()
        self.wfile.write(html.format(gas_status, gas_value, alarm_status).encode("utf-8"))

    def do_POST(self):
        # Handle POST requests to control the LED and arm/disarm the gas sensor
        global gas_sensor_status
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode("utf-8")
        post_data = post_data.split("=")[1]

        setupGPIO()

        if post_data == 'On':
            GPIO.output(17, GPIO.HIGH)  # Turn the LED on
            if not gas_sensor_status:  # Ensure the gas sensor is armed
                arm_gas_sensor()  # Arm the gas sensor
        else:
            GPIO.output(17, GPIO.LOW)   # Turn the LED off
            if gas_sensor_status:  # Ensure the gas sensor is disarmed
                arm_gas_sensor()  # Disarm the gas sensor

        print("LED is {} and Gas Sensor is {}".format(post_data, "ARMED" if gas_sensor_status else "DISARMED"))
        self._redirect('/')  # Redirect back to the root URL

# # # # # Main # # # # #

def run_server():
    """Start the HTTP server"""
    http_server = HTTPServer((host_name, host_port), MyServer)
    print("Server Starts - %s:%s" % (host_name, host_port))

    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        http_server.server_close()
        GPIO.cleanup()  # Clean up GPIO when the server stops

if __name__ == '__main__':
    setupGPIO()
    
    # Assign the button action
    button.when_pressed = arm_gas_sensor

    # Start the HTTP server in a separate thread so it doesn't block the button checking
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()

    # Continuously check the button press and gas sensor in the main thread
    while True:
        check_button_press()  # Check for button presses and activate the buzzer
        check_gas_sensor()  # Check for gas sensor status and trigger alarm if needed
        time.sleep(2)  # Loop delay
