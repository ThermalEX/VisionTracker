"""Target tracking and aim control module."""

import time
import math
from utils.config import Config


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


class ADRCController:
    """
    Discrete ADRC for frame-by-frame tracking.

    Uses a per-frame disturbance estimator instead of continuous-time ESO,
    which avoids the divergence caused by misattributing control effects as
    disturbances when applied frame-by-frame.

    System model (per frame):
      error_new = error_old - b0 * u_applied + target_motion

    Disturbance estimation:
      raw_dist = (error_new - error_old) + b0 * u_applied
      z2 = alpha * raw_dist + (1 - alpha) * z2   [low-pass filter]

    Control law:
      u = kp * error + z2 / b0
        - kp * error : proportional feedback
        - z2 / b0    : feedforward to pre-compensate target motion
    """

    def __init__(self, kp=None, b0=None, alpha=None, max_output=100):
        self.kp = kp if kp is not None else Config.ADRC_KP
        self.b0 = b0 if b0 is not None else Config.ADRC_B0
        self.alpha = alpha if alpha is not None else Config.ADRC_ALPHA
        self.max_output = max_output

        self.z2_x = 0.0
        self.z2_y = 0.0
        self.prev_error_x = 0.0
        self.prev_error_y = 0.0
        self.prev_u_x = 0.0
        self.prev_u_y = 0.0
        self.first_run = True

    def reset(self):
        self.z2_x = 0.0
        self.z2_y = 0.0
        self.prev_error_x = 0.0
        self.prev_error_y = 0.0
        self.prev_u_x = 0.0
        self.prev_u_y = 0.0
        self.first_run = True

    def compute(self, error_x, error_y, u_applied_x=None, u_applied_y=None):
        """
        Update disturbance estimate and compute control output.

        Args:
            error_x, error_y:         Current pixel error (target - center).
            u_applied_x, u_applied_y: Actual mouse movement applied last frame.
                                       If None, uses internally stored prev_u.
        Returns:
            (output_x, output_y): Desired mouse movement.
        """
        if u_applied_x is not None:
            self.prev_u_x = float(u_applied_x)
            self.prev_u_y = float(u_applied_y)

        if self.first_run:
            self.prev_error_x = float(error_x)
            self.prev_error_y = float(error_y)
            self.z2_x = 0.0
            self.z2_y = 0.0
            self.first_run = False
            return 0.0, 0.0

        # Isolate target motion from control effect
        raw_dist_x = (error_x - self.prev_error_x) + self.b0 * self.prev_u_x
        raw_dist_y = (error_y - self.prev_error_y) + self.b0 * self.prev_u_y

        # Low-pass filter disturbance estimate
        self.z2_x = self.alpha * raw_dist_x + (1.0 - self.alpha) * self.z2_x
        self.z2_y = self.alpha * raw_dist_y + (1.0 - self.alpha) * self.z2_y

        self.prev_error_x = float(error_x)
        self.prev_error_y = float(error_y)

        # Control: proportional feedback + disturbance feedforward
        u_x = self.kp * error_x + self.z2_x / self.b0
        u_y = self.kp * error_y + self.z2_y / self.b0

        u_x = max(-self.max_output, min(self.max_output, u_x))
        u_y = max(-self.max_output, min(self.max_output, u_y))

        return u_x, u_y


class AimController:
    """
    Aim controller combining snap and PID modes.
    - Snap mode: Fast teleport for large errors
    - PID mode: Smooth adjustment for small errors
    """

    # Frames of forced PID after each snap to prevent oscillation
    POST_SNAP_SETTLE = 4

    def __init__(self, mouse_driver):
        self.mouse = mouse_driver
        self.pid = PIDController()
        self.adrc = ADRCController()

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

        # Anti-oscillation: post-snap settle counter and velocity tracking
        self._post_snap_frames = 0
        self._prev_error_x = 0.0
        self._prev_error_y = 0.0
        self._has_prev = False

        # Last applied move for ADRC feedback
        self._adrc_applied_x = 0.0
        self._adrc_applied_y = 0.0

    def reset(self):
        """Reset controller state."""
        self.pid.reset()
        self.adrc.reset()
        self.move_acc_x = 0.0
        self.move_acc_y = 0.0
        self.waiting_for_update = False
        self.last_target_id = None
        self._post_snap_frames = 0
        self._prev_error_x = 0.0
        self._prev_error_y = 0.0
        self._has_prev = False
        self._adrc_applied_x = 0.0
        self._adrc_applied_y = 0.0

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
                self.adrc.reset()
                self._post_snap_frames = 0
                self._has_prev = False
                self._adrc_applied_x = 0.0
                self._adrc_applied_y = 0.0
        self.last_target_id = target_id

        error_dist = math.sqrt(error_x ** 2 + error_y ** 2)

        # Deadzone check
        if error_dist <= Config.DEADZONE:
            self.current_mode = 'PID'
            self.waiting_for_update = False
            self._post_snap_frames = 0
            return 'IDLE'

        # Decrement post-snap settle counter each frame
        if self._post_snap_frames > 0:
            self._post_snap_frames -= 1

        if error_dist > Config.SNAP_THRESHOLD and (Config.SNAP_THRESHOLD == 0 or self._post_snap_frames == 0):
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
                # Reset PID accumulator so stale sub-pixel values don't carry over
                self.move_acc_x = 0.0
                self.move_acc_y = 0.0
                self._record_move(error_x, error_y)
                # Block snap for N frames to prevent oscillation from overshoot
                self._post_snap_frames = self.POST_SNAP_SETTLE

        else:
            # === PID / ADRC mode: fine adjustment or post-snap settle ===
            use_adrc = Config.CONTROLLER_TYPE == 'adrc'
            self.current_mode = 'ADRC' if use_adrc else 'PID'
            can_move = self._check_can_move(
                error_x, error_y,
                Config.PID_COOLDOWN,
                Config.PID_ERROR_THRESHOLD
            )

            if can_move:
                if use_adrc:
                    out_x, out_y = self.adrc.compute(
                        error_x, error_y,
                        u_applied_x=self._adrc_applied_x,
                        u_applied_y=self._adrc_applied_y,
                    )
                else:
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

                # Record actual applied move for ADRC feedback next frame
                self._adrc_applied_x = float(int_move_x)
                self._adrc_applied_y = float(int_move_y)

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
        Calibration is handled by TrackerWorker._run_calibration().
        """
        pass
