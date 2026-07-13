from mke.adapters.video.process import ActiveProcessController


class FakeProcess:
    def __init__(self) -> None:
        self.killed = False
        self.waited = False

    def poll(self) -> int | None:
        return -9 if self.killed else None

    def kill(self) -> None:
        self.killed = True

    def wait(self, timeout: float | None = None) -> int:
        self.waited = True
        return -9


def test_cancel_operation_kills_only_its_children() -> None:
    controller = ActiveProcessController()
    first = controller.begin_operation()
    second = controller.begin_operation()
    first_process = FakeProcess()
    second_process = FakeProcess()
    controller.register(first_process, operation_id=first)  # type: ignore[arg-type]
    controller.register(second_process, operation_id=second)  # type: ignore[arg-type]
    controller.cancel_operation(first)
    assert first_process.killed is True
    assert first_process.waited is True
    assert second_process.killed is False


def test_late_registration_after_targeted_cancel_is_killed() -> None:
    controller = ActiveProcessController()
    operation_id = controller.begin_operation()
    controller.cancel_operation(operation_id)
    process = FakeProcess()
    controller.register(process, operation_id=operation_id)  # type: ignore[arg-type]
    assert process.killed is True
    assert process.waited is True


def test_shutdown_kills_scoped_and_unscoped_children() -> None:
    controller = ActiveProcessController()
    operation_id = controller.begin_operation()
    scoped = FakeProcess()
    unscoped = FakeProcess()
    controller.register(scoped, operation_id=operation_id)  # type: ignore[arg-type]
    controller.register(unscoped)  # type: ignore[arg-type]
    controller.shutdown()
    assert scoped.killed is True
    assert unscoped.killed is True
    assert scoped.waited is True
    assert unscoped.waited is True
