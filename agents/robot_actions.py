"""
Robot action translation and execution
Separated to avoid circular imports
"""
import time
from typing import List, Dict, Any
from agents.ServoController import ServoController

def translate_actions(act_list: List[list], servo_controller: ServoController = None) -> List[Dict[str, Any]]:
    """
    Translate numeric action lists to structured action dictionaries
    
    Command map:
    0: set_translation (absolute)
    1: set_elevation (absolute)
    2: move_left (relative degrees)
    3: move_right (relative degrees)
    4: move_servo (direct control)
    5: wait (hold position)
    """
    if not act_list:
        return []

    command_map = {
        0: 'set_translation',
        1: 'set_elevation',
        2: 'move_left',
        3: 'move_right',
        4: 'move_servo',
        5: 'wait',
    }

    translated_list = []
    for action in act_list:
        if not isinstance(action, list) or len(action) < 1:
            print(f"Invalid action format: {action}")
            continue

        cmd_id = action[0]
        if cmd_id in command_map and cmd_id != 5:
            translated_list.append({
                'type': 'motor',
                'command': command_map[cmd_id],
                'args': action[1:]
            })
        elif cmd_id == 5:
            translated_list.append({
                'type': 'wait',
                'duration': action[1] if len(action) > 1 and isinstance(action[1], (int, float)) else 1.0
            })
        else:
            print(f"Unknown command ID: {cmd_id}")
    return translated_list


def execute_motion_sequence(actions: List[Dict[str, Any]], servo_controller: ServoController) -> bool:
    """Execute a sequence of robot actions"""
    print(f"Executing {len(actions)} actions...")

    for i, action in enumerate(actions):
        print(f"Action {i + 1}: {action.get('type', 'unknown')}")

        if action.get('type') == 'motor':
            command = action.get('command')
            args = action.get('args', [])

            # Map commands to servo controller methods
            if command == 'set_elevation' and args:
                servo_controller.set_elevation(args[0])
            elif command == 'set_translation' and args:
                servo_controller.set_translation(args[0])
            elif command == 'move_left' and args:
                servo_controller.move_left(args[0])
            elif command == 'move_right' and args:
                servo_controller.move_right(args[0])
            elif command == 'move_servo' and len(args) >= 2:
                servo_controller.move_servo(args[0], args[1])
            elif command == 'hold_position' and args:
                servo_controller.hold_position(args[0])
            else:
                print(f"Unknown motor command: {command}")

        elif action.get('type') == 'wait':
            duration = action.get('duration', 1.0)
            time.sleep(duration)

        # Brief pause between actions for safety
        time.sleep(0.1)

    return True

