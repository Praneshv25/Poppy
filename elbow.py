import serial
import time

# Replace with your correct port!
PORT = '/dev/tty.usbmodem1101'
BAUD = 9600

arduino = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(2)  # Let Arduino boot/reset

def move_servo(channel, degrees):
    if 0 <= channel <= 15 and 0 <= degrees <= 500:
        command = f"{channel}:{degrees}\n"
        arduino.write(command.encode())
        print(f"Sent: {command.strip()}")
        time.sleep(0.1)
    else:
        print("Invalid input. Channel 0?15, percent 0?100")

# Example usage:
move_servo(0, 300)
# move_servo(1, 40)

# Optional: close when done
arduino.close()
print("orange")
