import time
from ADCS_final2 import ADCSController

def test_pd_symmetry():
    controller = ADCSController()
    print("\n[TEST] Starting PD symmetry test...")

    # Start the PD controller
    controller.start_auto_control("PWM PD")
    time.sleep(2)

    # Test sequence: small and large positive/negative targets
    test_targets = [10, 0, -10, 0, 20, 0, -20, 0, 5, 0, -5, 0]
    for target in test_targets:
        print(f"\n[TEST] Setting target yaw to {target}°")
        controller.set_target_yaw(target)
        # Wait for system to settle (adjust as needed for your system)
        time.sleep(4)
        # Print current yaw and error
        data, _ = controller.get_current_data()
        print(f"[TEST] Current yaw: {data['mpu']['yaw']:.2f}°, Target: {target}°, Error: {data['controller']['error']:.2f}°")

    # Stop the controller
    controller.stop_auto_control()
    controller.shutdown()
    print("[TEST] PD symmetry test complete.")

if __name__ == "__main__":
    test_pd_symmetry()