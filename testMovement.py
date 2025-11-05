from ServoController import ServoController

sc = ServoController()

# Test absolute servo positioning
# sc.set_elevation(1)      # Move to middle elevation
# sc.set_translation(70)    # Move forward
# sc.set_translation(1)    # Move backward
# sc.set_elevation(80)      # Move up
# sc.set_elevation(10)      # Move down

# Test relative stepper rotation
sc.move_right(10)
# sc.move_left(10)
