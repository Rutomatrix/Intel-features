#servo.py
import time
import pigpio
from http import server
from socketserver import ThreadingMixIn

# GPIO pins that support hardware PWM
VERTICAL_SERVO_PIN = 18   # Hardware PWM channel 0
HORIZONTAL_SERVO_PIN = 12 # Hardware PWM channel 0

# Start pigpio daemon (make sure it's running: sudo pigpiod)
pi = pigpio.pi()
if not pi.connected:
    exit("Pigpio daemon not running. Start with: sudo pigpiod")
def angle_to_pulsewidth(angle):
    return 500 + (angle / 180.0) * 2000

# Smooth Servo Function
def set_servo_angle(pi_obj, gpio_pin, current_angle, target_angle, step=1, delay=0.02):
    if current_angle < target_angle:
        angle = current_angle
        while angle <= target_angle:
            pi_obj.set_servo_pulsewidth(gpio_pin, angle_to_pulsewidth(angle))
            time.sleep(delay)
            angle += step
    else:
        angle = current_angle
        while angle >= target_angle:
            pi_obj.set_servo_pulsewidth(gpio_pin, angle_to_pulsewidth(angle))
            time.sleep(delay)
            angle -= step
    return target_angle

# Initialize servos at 90 degrees
pi.set_servo_pulsewidth(VERTICAL_SERVO_PIN, angle_to_pulsewidth(90))
pi.set_servo_pulsewidth(HORIZONTAL_SERVO_PIN, angle_to_pulsewidth(90))
time.sleep(0.5)
current_vertical_angle = set_servo_angle(pi, VERTICAL_SERVO_PIN, 90, 180)
current_vertical_angle = set_servo_angle(pi, VERTICAL_SERVO_PIN, 180, 90)
current_horizontal_angle = set_servo_angle(pi, HORIZONTAL_SERVO_PIN, 90, 0)
current_horizontal_angle = set_servo_angle(pi, HORIZONTAL_SERVO_PIN, 0, 90)

# HTTP Handler
class ServoHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        global current_vertical_angle, current_horizontal_angle

        if self.path == '/' or self.path == '/index.html':
            try:
                with open("index.html", "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.send_header('Content-Length', len(content))
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_error(404, "index.html not found")

        elif self.path.startswith('/servo'):
            try:
                query = self.path.split('?')[1]
                params = dict(q.split('=') for q in query.split('&'))
                axis = params.get('axis')
                angle = int(params.get('angle', -1))

                if 0 <= angle <= 180:
                    if axis == 'vertical':
                        current_vertical_angle = set_servo_angle(pi, VERTICAL_SERVO_PIN, current_vertical_angle, angle)
                    elif axis == 'horizontal':
                        current_horizontal_angle = set_servo_angle(pi, HORIZONTAL_SERVO_PIN, current_horizontal_angle, angle)
                    else:
                        self.send_error(400, "Invalid axis")
                        return

                    self.send_response(200)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(f"{axis.capitalize()} servo moved to {angle}".encode())
                else:
                    self.send_error(400, "Invalid angle (must be 0-180)")
            except:
                self.send_error(400, "Invalid request")
        else:
            self.send_error(404)
            self.end_headers()

# Threaded HTTP Server
class ServoServer(ThreadingMixIn, server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

# Run the server
try:
    address = ('100.124.235.42', 8003)
    httpd = ServoServer(address, ServoHandler)
    print(f"Starting dual servo hardware PWM server on http://{address[0]}:{address[1]}")
    httpd.serve_forever()
finally:
    # Stop servo pulses
    pi.set_servo_pulsewidth(VERTICAL_SERVO_PIN, 0)
    pi.set_servo_pulsewidth(HORIZONTAL_SERVO_PIN, 0)
    pi.stop()