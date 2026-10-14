"""Illustrative definition text only; this file does not generate history.csv."""


class TutorialBalance:
    """Synthetic two-temperature balance, not a validated physical model."""

    def front_rate(self, input_W, conductance_W_K, front_K, rear_K, capacity_J_K):
        """C_f dT_f/dt = Q_in - G (T_f - T_r); rate has units K/s."""
        return (input_W - conductance_W_K * (front_K - rear_K)) / capacity_J_K

    def contrast(self, front_K, rear_K):
        """Same-record front-minus-rear temperature contrast in K."""
        return front_K - rear_K


raise RuntimeError("Static illustrative source: do not execute or import model.py")
