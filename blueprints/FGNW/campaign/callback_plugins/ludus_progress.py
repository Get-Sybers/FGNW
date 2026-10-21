from __future__ import annotations
import json
import re
from ansible.plugins.callback import CallbackBase
DOCUMENTATION = r"""
    name: ludus_progress
    type: aggregate
    short_description: Per-stage deploy progress markers for the FGNW campaign
    description:
        - Emits one-line C(LUDUS_PROGRESS | {json}) markers reporting, per stage,
          how many tasks have run and how many have completed.
        - Rides alongside the normal stdout callback; does not replace it.
    requirements:
        - Enable with C(callbacks_enabled = ludus_progress) in the campaign ansible.cfg.
    options:
        stage_regex:
            description: Regex a task NAME must match to open a new stage.
            type: str
            default: '^(Phase\s|Cleanup\b)'
            env:
                - name: LUDUS_PROGRESS_STAGE_RE
            ini:
                - section: callback_ludus_progress
                  key: stage_regex
        per_task:
            description: Emit a snapshot marker before every task (near-live). If
                false, emit only at stage boundaries and at the final stats.
            type: bool
            default: true
            env:
                - name: LUDUS_PROGRESS_PER_TASK
            ini:
                - section: callback_ludus_progress
                  key: per_task
"""
MARKER = "LUDUS_PROGRESS | "
SCHEMA = "ludus-progress/1"
PREFLIGHT = "Preflight"
class Stage(object):
    """Counters for one stage. `started` counts tasks entered; the rest count
    task results. finished == the sum of results; at a stage's end it equals
    `started` (minus the boundary wrapper, which yields no host result)."""
    __slots__ = ("name", "started", "ok", "changed", "failed", "skipped", "unreachable")
    def __init__(self, name):
        self.name = name
        self.started = 0
        self.ok = 0
        self.changed = 0
        self.failed = 0
        self.skipped = 0
        self.unreachable = 0
    @property
    def finished(self):
        return self.ok + self.changed + self.failed + self.skipped + self.unreachable
    def to_dict(self, state):
        return {
            "name": self.name,
            "state": state,
            "tasks": self.started,
            "finished": self.finished,
            "ok": self.ok,
            "changed": self.changed,
            "failed": self.failed,
            "skipped": self.skipped,
            "unreachable": self.unreachable,
        }
class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "aggregate"
    CALLBACK_NAME = "ludus_progress"
    CALLBACK_NEEDS_ENABLED = True
    def __init__(self):
        super(CallbackModule, self).__init__()
        self._stages = []
        self._by_name = {}
        self._current = None
        self._current_is_boundary = False
        self._stage_re = None
        self._per_task = True
        self._open_stage(PREFLIGHT)
    def set_options(self, task_keys=None, var_options=None, direct=None):
        super(CallbackModule, self).set_options(
            task_keys=task_keys, var_options=var_options, direct=direct
        )
        pattern = self.get_option("stage_regex")
        try:
            self._stage_re = re.compile(pattern)
        except re.error:
            self._stage_re = re.compile(r"^(Phase\s|Cleanup\b)")
        self._per_task = bool(self.get_option("per_task"))
    def _open_stage(self, name):
        stage = self._by_name.get(name)
        if stage is None:
            stage = Stage(name)
            self._by_name[name] = stage
            self._stages.append(stage)
        self._current = stage
        return stage
    def _is_boundary(self, name):
        return bool(name) and self._stage_re is not None and self._stage_re.search(name)
    def _snapshot(self, event, final=False):
        stages = []
        for st in self._stages:
            if final:
                state = "done"
            elif st is self._current:
                state = "running"
            else:
                state = "done"
            stages.append(st.to_dict(state))
        totals = {
            "stages": len(self._stages),
            "tasks": sum(s.started for s in self._stages),
            "finished": sum(s.finished for s in self._stages),
            "ok": sum(s.ok for s in self._stages),
            "changed": sum(s.changed for s in self._stages),
            "failed": sum(s.failed for s in self._stages),
            "skipped": sum(s.skipped for s in self._stages),
            "unreachable": sum(s.unreachable for s in self._stages),
        }
        payload = {
            "schema": SCHEMA,
            "event": event,
            "current_stage": self._current.name if self._current else None,
            "totals": totals,
            "stages": stages,
        }
        self._display.display(MARKER + json.dumps(payload, sort_keys=True))
    def v2_playbook_on_task_start(self, task, is_conditional):
        name = task.get_name()
        self._current_is_boundary = self._is_boundary(name)
        if self._current_is_boundary:
            self._open_stage(name)
            self._snapshot("stage_start")
        else:
            self._current.started += 1
            if self._per_task:
                self._snapshot("task")
    def v2_playbook_on_handler_task_start(self, task):
        self.v2_playbook_on_task_start(task, False)
    def v2_runner_on_ok(self, result):
        if self._current_is_boundary:
            return
        if result._result.get("changed", False):
            self._current.changed += 1
        else:
            self._current.ok += 1
    def v2_runner_on_failed(self, result, ignore_errors=False):
        if self._current_is_boundary:
            return
        self._current.failed += 1
    def v2_runner_on_skipped(self, result):
        if self._current_is_boundary:
            return
        self._current.skipped += 1
    def v2_runner_on_unreachable(self, result):
        if self._current_is_boundary:
            return
        self._current.unreachable += 1
    def v2_runner_item_on_ok(self, result):
        if self._current_is_boundary:
            return
        self.v2_runner_on_ok(result)
        self._current.started += 1
    def v2_runner_item_on_failed(self, result):
        if self._current_is_boundary:
            return
        self._current.failed += 1
        self._current.started += 1
    def v2_runner_item_on_skipped(self, result):
        if self._current_is_boundary:
            return
        self._current.skipped += 1
        self._current.started += 1
    def v2_playbook_on_stats(self, stats):
        self._snapshot("final", final=True)
