import serial
import time

MIN_STEPPER_DEG = -180
MAX_STEPPER_DEG = 180


class ServoController:
    def __init__(self, port='/dev/tty.usbmodem1101', baud=9600, delay=2):
        self.port = port
        self.baud = baud
        self.delay = delay
        self.arduino = None
        self.elevation_motor_port = 8
        self.translation_motor_port = 0
        self.elevation_servo_pos = 0
        self.rotation_stepper_deg = 0
        self.translation_servo_pos = 0
        self._connect()

    def _connect(self):
        try:
            self.arduino = serial.Serial(self.port, self.baud, timeout=1)
            time.sleep(self.delay)
            print(f"[?] Connected to Arduino on {self.port}")
        except serial.SerialException as e:
            print(f"[?] Failed to connect: {e}")

    def move_servo(self, channel, value):
        if self.arduino is None:
            print("No Arduino connected.")
            return False

        if not (0 <= channel <= 15 and 0 <= value <= 100):
            print("Invalid input. Channel 0?15, value 0?100")
            return False

        command = f"s:{channel}:{value}\n"
        self.arduino.write(command.encode())
        print(f"[?] Sent servo: {command.strip()}")
        return True

    def move_up(self, value):
        new_pos = self.elevation_servo_pos + value
        shifted = self.move_servo(self.elevation_motor_port, new_pos)
        if shifted:
            self.elevation_servo_pos = new_pos

        # make sure that change is not too drastic

    def move_down(self, value):
        new_pos = self.elevation_servo_pos - value
        shifted = self.move_servo(self.elevation_motor_port, new_pos)
        if shifted:
            self.elevation_servo_pos = new_pos

    def move_forward(self, value):
        new_pos = self.translation_servo_pos + value
        shifted = self.move_servo(self.translation_motor_port, new_pos)
        if shifted:
            self.translation_servo_pos = new_pos

    def move_backward(self, value):
        new_pos = self.translation_servo_pos - value
        shifted = self.move_servo(self.translation_motor_port, new_pos)
        if shifted:
            self.translation_servo_pos = new_pos

    def move_left(self, degrees):
        self.move_stepper('left', degrees)
        # Add validation

    def move_right(self, degrees):
        self.move_stepper('right', degrees)

    def move_stepper(self, direction, degrees=None):
        if self.arduino is None:
            print("No Arduino connected.")
            return

        if direction not in ["left", "right"]:
            print("Invalid direction. Use 'left' or 'right'.")
            return

        if degrees is not None:
            steps = degrees * 1000 // 360
            new_step_deg = self.rotation_stepper_deg - degrees if direction == 'left' else self.rotation_stepper_deg + degrees
            if new_step_deg < MIN_STEPPER_DEG or new_step_deg > MAX_STEPPER_DEG:
                return False
            self.rotation_stepper_deg = new_step_deg
            command = f"step:{direction}:{steps}\n"
        else:
            return False

        self.arduino.write(command.encode())
        print(f"[?] Sent stepper: {command.strip()}")
        return True

    def hold_position(self, seconds):
        time.sleep(seconds)

    def close(self):
        if self.arduino:
            self.arduino.close()
            print("[?] Serial connection closed.")
