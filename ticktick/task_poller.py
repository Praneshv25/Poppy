"""
TickTick Task Poller — Background thread that periodically checks TickTick
for due or overdue tasks and has the robot proactively remind the user.

Usage:
    from ticktick.task_poller import TickTickPoller

    poller = TickTickPoller(
        ticktick_agent=ticktick_agent,
        voice_fn=voice.stream_audio,
        servo_controller=servo_controller,   # optional
        check_interval_minutes=30,
    )
    poller.start()
    ...
    poller.stop()
"""

import threading
import time
from datetime import datetime
from typing import Optional, Callable


class TickTickPoller:
    """
    Periodically polls TickTick for tasks that are due today or overdue,
    then has the robot speak a reminder (and optionally move).

    The poller avoids nagging by tracking which tasks it has already
    reminded about in the current session.
    """

    def __init__(
        self,
        ticktick_agent,
        voice_fn: Callable[[str], None],
        servo_controller=None,
        check_interval_minutes: int = 30,
    ):
        """
        Args:
            ticktick_agent: A started TickTickAgent instance.
            voice_fn: Callable that speaks text (e.g. voice.stream_audio).
            servo_controller: Optional ServoController for attention gesture.
            check_interval_minutes: How often to poll (default 30 min).
        """
        self.agent = ticktick_agent
        self.voice_fn = voice_fn
        self.servo = servo_controller
        self.interval = check_interval_minutes * 60
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._reminded_cache: set = set()  # task summaries already spoken

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        """Start polling in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="ticktick-poller"
        )
        self._thread.start()
        print(
            f"📋 TickTick poller started (checking every "
            f"{self.interval // 60} min)"
        )

    def stop(self):
        """Stop the poller."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("📋 TickTick poller stopped")

    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _poll_loop(self):
        """Entry point for the background thread."""
        # Small initial delay so the system finishes booting first
        time.sleep(30)

        while self._running:
            try:
                self._check_and_remind()
            except Exception as e:
                print(f"[TickTickPoller] Error during check: {e}")

            # Sleep in small increments so stop() is responsive
            for _ in range(self.interval):
                if not self._running:
                    return
                time.sleep(1)

    def _check_and_remind(self):
        """Ask the TickTick sub-agent for due tasks and remind the user."""
        if not self.agent.is_running():
            return

        now = datetime.now()
        result = self.agent.ask(
            f"List all tasks that are due today ({now.strftime('%A, %B %d, %Y')}) "
            f"or overdue (past their due date). "
            f"For each task include its title and due date/time. "
            f"If there are no due or overdue tasks, respond with exactly: "
            f"'No tasks due.'"
        )

        # Nothing to remind about
        if not result:
            return
        result_lower = result.lower()
        if any(phrase in result_lower for phrase in [
            "no tasks due", "no tasks", "no overdue", "nothing due",
            "none", "all clear",
        ]):
            print(f"[TickTickPoller] {now.strftime('%H:%M')} — No tasks due.")
            return

        # Avoid repeating the exact same reminder
        result_key = result.strip()[:200]
        if result_key in self._reminded_cache:
            print(f"[TickTickPoller] {now.strftime('%H:%M')} — Already reminded, skipping.")
            return
        self._reminded_cache.add(result_key)

        print(f"[TickTickPoller] {now.strftime('%H:%M')} — Reminding about tasks")

        # Optional: attention-getting gesture
        if self.servo:
            self._attention_gesture()

        # Speak the reminder
        reminder = f"Hey, quick reminder — {result}"
        try:
            self.voice_fn(reminder)
        except Exception as e:
            print(f"[TickTickPoller] Voice error: {e}")

    def _attention_gesture(self):
        """Small physical movement to get the user's attention before speaking."""
        try:
            from agents.robot_actions import translate_actions, execute_motion_sequence

            # Gentle "look up and forward" gesture
            gesture = translate_actions([
                [1, 65],    # raise elevation
                [5, 0.4],   # pause
                [1, 50],    # settle back
                [5, 0.3],
            ])
            if gesture:
                execute_motion_sequence(gesture, self.servo)
        except Exception:
            pass  # No servo or import issue — voice-only is fine

    def clear_reminder_cache(self):
        """
        Reset the 'already reminded' cache.
        Useful at the start of a new day or on demand.
        """
        self._reminded_cache.clear()
        print("[TickTickPoller] Reminder cache cleared.")
