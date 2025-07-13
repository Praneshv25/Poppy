import ServoController as sc
import time

# servo = sc.ServoController()
# # while True:
# servo.move_servo(0, 0)
# print('ok')
# servo.hold_position(100)
    # time.sleep(0.1)

# time.sleep(100)
# servo.close()


controller = sc.ServoController()
# controller.move_up(20)

# controller.move_down(20)

# controller.move_forward(20)
# controller.move_servo(8, 0)
# controller.move_servo(0, 0)
# controller.move_stepper('left', 90)
controller.move_stepper('right', 45)
# sc = ServoController()
#
# sc.move_servo(0, 75)          # Move servo channel 0 to 75%
# sc.move_stepper("left")       # Move stepper motor left with default steps
# sc.move_stepper("right", 120) # Move stepper motor right for 120 steps
#
# sc.close()


