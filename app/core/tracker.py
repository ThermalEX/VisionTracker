"""Target tracking and aim control module."""

import time
import math
from ..utils.config import Config


class PIDController:
    """PID controller for smooth mouse movement."""

    def __init__(self, kp=None, ki=None, kd=None, max_output=100):
        self.kp = kp if kp is not None else Config.PID_KP
        self.ki = ki if ki is not None else Config.PID_KI
        self.kd = kd if kd is not None else Config.PID_KD
        self.max_output = max_output

        self.prev_error_x = 0
        self.prev_error_y = 0
        self.integral_x = 0
        self.integral_y = 0
        self.last_time = time.time()
        self.first_run = True

    def reset(self):
        """Reset controller state."""
        self.prev_error_x = 0
        self.prev_error_y = 0
        self.integral_x = 0
        self.integral_y = 0
        self.last_time = time.time()
        self.first_run = True

    def compute(self, error_x, error_y):
        """
        Compute PID output.

        Args:
            error_x: X axis error (target - current)
            error_y: Y axis error

        Returns:
            (output_x, output_y): Movement values
        """
        current_time = time.time()
        dt = max(0.001, min(current_time - self.last_time, 0.1))

        # Proportional
        p_x = self.kp * error_x
        p_y = self.kp * error_y

        # Integral (with anti-windup)
        self.integral_x = max(-100, min(100, self.integral_x + error_x * dt))
        self.integral_y = max(-100, min(100, self.integral_y + error_y * dt))
        i_x = self.ki * self.integral_x
        i_y = self.ki * self.integral_y

        # Derivative
        if self.first_run:
            d_x, d_y = 0, 0
            self.first_run = False
        else:
            d_x = max(-50, min(50, self.kd * (error_x - self.prev_error_x) / dt))
            d_y = max(-50, min(50, self.kd * (error_y - self.prev_error_y) / dt))

        self.prev_error_x = error_x
        self.prev_error_y = error_y
        self.last_time = current_time

        # Combined output with limits
        output_x = max(-self.max_output, min(self.max_output, p_x + i_x + d_x))
        output_y = max(-self.max_output, min(self.max_output, p_y + i_y + d_y))

        return output_x, output_y


class AimController:
    """
    Aim controller combining snap and PID modes.
    - Snap mode: Fast teleport for large errors
    - PID mode: Smooth adjustment for small errors
    """

    def __init__(self, mouse_driver):
        self.mouse = mouse_driver
        self.pid = PIDController()

        # State
        self.last_move_time = 0
        self.pre_move_error_x = 0
        self.pre_move_error_y = 0
        self.waiting_for_update = False
        self.current_mode = 'PID'

        # Accumulator for sub-pixel movements
        self.move_acc_x = 0.0
        self.move_acc_y = 0.0

        # Last target tracking
        self.last_target_id = None

        # Sensitivity (can be calibrated)
        self.snap_sensitivity = Config.SNAP_SENSITIVITY

    def reset(self):
        """Reset controller state."""
        self.pid.reset()
        self.move_acc_x = 0.0
        self.move_acc_y = 0.0
        self.waiting_for_update = False
        self.last_target_id = None

    def update(self, error_x, error_y, target_id=None):
        """
        Update aim based on error.

        Args:
            error_x: X axis error (target_x - center_x)
            error_y: Y axis error
            target_id: Target identifier for tracking

        Returns:
            str: Current mode ('SNAP', 'PID', or 'IDLE')
        """
        if not self.mouse.is_loaded():
            return 'IDLE'

        # Target switch detection
        if target_id is not None and self.last_target_id is not None:
            if target_id != self.last_target_id:
                self.pid.reset()
        self.last_target_id = target_id

        error_dist = math.sqrt(error_x ** 2 + error_y ** 2)

        # Deadzone check
        if error_dist <= Config.DEADZONE:
            self.current_mode = 'PID'
            self.waiting_for_update = False
            return 'IDLE'

        now = time.time()
        time_since_move = now - self.last_move_time

        if error_dist > Config.SNAP_THRESHOLD:
            # === SNAP mode for large errors ===
            self.current_mode = 'SNAP'
            can_move = self._check_can_move(
                error_x, error_y,
                Config.SNAP_COOLDOWN,
                Config.SNAP_UPDATE_THRESHOLD
            )

            if can_move:
                move_x = int(error_x * self.snap_sensitivity)
                move_y = int(error_y * self.snap_sensitivity)
                self.mouse.move(move_x, move_y)
                self._record_move(error_x, error_y)

        else:
            # === PID mode for fine adjustment ===
            self.current_mode = 'PID'
            can_move = self._check_can_move(
                error_x, error_y,
                Config.PID_COOLDOWN,
                Config.PID_ERROR_THRESHOLD
            )

            if can_move:
                out_x, out_y = self.pid.compute(error_x, error_y)

                # Accumulator for sub-pixel precision
                self.move_acc_x += out_x
                self.move_acc_y += out_y

                int_move_x = int(self.move_acc_x)
                int_move_y = int(self.move_acc_y)

                if int_move_x != 0 or int_move_y != 0:
                    self.mouse.move(int_move_x, int_move_y)
                    self.move_acc_x -= int_move_x
                    self.move_acc_y -= int_move_y

                self._record_move(error_x, error_y)

        return self.current_mode

    def _check_can_move(self, error_x, error_y, cooldown, threshold):
        """Check if movement is allowed based on cooldown and error change."""
        if not self.waiting_for_update:
            return True

        now = time.time()
        time_since_move = now - self.last_move_time

        error_change = math.sqrt(
            (error_x - self.pre_move_error_x) ** 2 +
            (error_y - self.pre_move_error_y) ** 2
        )

        # Can move if: screen updated OR cooldown elapsed
        if error_change > threshold or time_since_move >= cooldown:
            self.waiting_for_update = False
            return True

        return False

    def _record_move(self, error_x, error_y):
        """Record movement for next update check."""
        self.last_move_time = time.time()
        self.pre_move_error_x = error_x
        self.pre_move_error_y = error_y
        self.waiting_for_update = True

    def calibrate(self, model, frame_queue, overlay_queue=None):
        """
        Calibrate snap sensitivity.
        (Implementation would go here - simplified for module structure)
        """
        # TODO: Implement calibration logic
        pass
