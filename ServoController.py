import serial
import time
from typing import Dict

MIN_STEPPER_DEG = -180
MAX_STEPPER_DEG = 180

MICROSTEP = 8  # set this to 1,2,4,8,16 depending on MS1/MS2/MS3 on A4988
FULL_STEPS_PER_REV = 200  # typical NEMA17
STEPS_PER_REV = FULL_STEPS_PER_REV * MICROSTEP
STEPS_PER_DEG = STEPS_PER_REV / 360.0

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
        self.max_servo_change = 20  # Hardware safety limit
        self._connect()

    def _connect(self):
        try:
            self.arduino = serial.Serial(self.port, self.baud, timeout=1)
            time.sleep(self.delay)
            print(f"[?] Connected to Arduino on {self.port}")
        except serial.SerialException as e:
            print(f"[?] Failed to connect: {e}")

    def _clamp_servo(self, value: int) -> int:
        """Ensure servo value stays within 0-100 range"""
        return max(0, min(100, value))

    def _clamp_rotation(self, value: int) -> int:
        """Ensure rotation stays within -180 to +180 range"""
        return max(MIN_STEPPER_DEG, min(MAX_STEPPER_DEG, value))

    def _safe_servo_move(self, current_pos: int, target_change: int) -> int:
        """Ensure servo movement doesn't exceed safety limits"""
        if abs(target_change) > self.max_servo_change:
            target_change = self.max_servo_change if target_change > 0 else -self.max_servo_change
        return target_change

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

    def set_elevation(self, value):
        """Set absolute elevation position (0-100) with safety limits"""
        target_pos = self._clamp_servo(value)
        
        # Check if movement exceeds safety limits
        delta = abs(target_pos - self.elevation_servo_pos)
        if delta > self.max_servo_change:
            print(f"Warning: Movement of {delta} exceeds safety limit of {self.max_servo_change}")
            return False
        
        if target_pos != self.elevation_servo_pos:
            shifted = self.move_servo(self.elevation_motor_port, target_pos)
            if shifted:
                self.elevation_servo_pos = target_pos
                print(f"Set elevation to: {self.elevation_servo_pos}")
                return True
        return False

    def set_translation(self, value):
        """Set absolute translation position (0-100) with safety limits"""
        target_pos = self._clamp_servo(value)
        
        # Check if movement exceeds safety limits
        delta = abs(target_pos - self.translation_servo_pos)
        if delta > self.max_servo_change:
            print(f"Warning: Movement of {delta} exceeds safety limit of {self.max_servo_change}")
            return False
        
        if target_pos != self.translation_servo_pos:
            shifted = self.move_servo(self.translation_motor_port, target_pos)
            if shifted:
                self.translation_servo_pos = target_pos
                print(f"Set translation to: {self.translation_servo_pos}")
                return True
        return False

    def move_left(self, degrees):
        """Rotate stepper left by degrees with validation"""
        new_rotation = self._clamp_rotation(self.rotation_stepper_deg - abs(degrees))

        if new_rotation != self.rotation_stepper_deg:
            success = self.move_stepper('left', abs(degrees))
            if success:
                self.rotation_stepper_deg = new_rotation
                print(f"Rotated left to: {self.rotation_stepper_deg}?")
                return True
        return False

    def move_right(self, degrees):
        """Rotate stepper right by degrees with validation"""
        new_rotation = self._clamp_rotation(self.rotation_stepper_deg + abs(degrees))

        if new_rotation != self.rotation_stepper_deg:
            success = self.move_stepper('right', abs(degrees))
            if success:
                self.rotation_stepper_deg = new_rotation
                print(f"Rotated right to: {self.rotation_stepper_deg}?")
                return True
        return False

    def move_stepper(self, direction, degrees=None):
        if self.arduino is None:
            print("No Arduino connected.")
            return False

        if direction not in ["left", "right"]:
            print("Invalid direction. Use 'left' or 'right'.")
            return False

        if degrees is not None:
            steps = int(round(abs(degrees) * STEPS_PER_DEG))
            # sanity clamp to avoid sending 0 when degrees small
            if steps == 0 and abs(degrees) > 0.01:
                steps = 1
            new_step_deg = self.rotation_stepper_deg - degrees if direction == 'left' else self.rotation_stepper_deg + degrees
            if new_step_deg < MIN_STEPPER_DEG or new_step_deg > MAX_STEPPER_DEG:
                return False
            command = f"step:{direction}:{steps}\n"
        else:
            return False

        self.arduino.write(command.encode())
        print(f"[?] Sent stepper: {command.strip()}")
        return True

    def hold_position(self, seconds):
        """Maintain current position for specified duration"""
        print(f"Holding position for {seconds} seconds...")
        time.sleep(seconds)

    def get_current_state(self) -> Dict[str, int]:
        """Return current robot state for AI system"""
        return {
            "elevation_servo_pos": self.elevation_servo_pos,
            "translation_servo_pos": self.translation_servo_pos,
            "rotation_stepper_deg": self.rotation_stepper_deg
        }

    def close(self):
        if self.arduino:
            self.arduino.close()
            print("[?] Serial connection closed.")
