import time

from control.input import InputController


class DummyDriver:
    def __init__(self) -> None:
        self.actions = []

    def key_down(self, key: str) -> None:
        self.actions.append(("down", key))

    def key_up(self, key: str) -> None:
        self.actions.append(("up", key))

    def move_rel(self, x: int, y: int) -> None:
        self.actions.append(("move", x, y))


def test_panic_stop_releases_all_keys():
    driver = DummyDriver()
    controller = InputController(max_hold_sec=1.2, max_click_hz=5, driver=driver)

    controller.press("w")
    assert controller.is_holding("w")

    controller.panic_stop()

    assert controller.is_holding("w") is False
    assert ("up", "w") in driver.actions


def test_update_releases_long_hold():
    driver = DummyDriver()
    controller = InputController(max_hold_sec=0.01, max_click_hz=5, driver=driver)

    controller.press("w")
    assert controller.is_holding("w")
    time.sleep(0.02)
    controller.update()
    assert controller.is_holding("w") is False
