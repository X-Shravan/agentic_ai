class HardwareAlert:

    def __init__(self, enabled=False):
        self.enabled = enabled
        print("[INFO] Hardware alert system initialized")

    # ✅ ADD THIS METHOD
    def trigger(self, message: str):

        if not self.enabled:
            print(f"🔔 ALERT (SIMULATED): {message}")
            return

        # If real hardware (buzzer/LED) is connected
        try:
            print(f"🚨 HARDWARE ALERT: {message}")

            # Example:
            # buzzer.on()
            # time.sleep(1)
            # buzzer.off()

        except Exception as e:
            print(f"[ERROR] Hardware alert failed: {e}")