"""
MLflow tracking for a training run.

Tracking is opt-in: with no --mlflow-uri (and no MLFLOW_TRACKING_URI in the
environment) every call here is a no-op, so the script still runs unchanged
outside the cluster.

Under Katib each trial is its own pod, so each trial becomes its own MLflow
run. The Katib trial name arrives via the downward API as POD_NAME and is used
as the run name, which is what ties an MLflow run back to its trial.
"""

from __future__ import annotations

import functools
import os
from pathlib import Path

# Per-epoch metrics come from an ultralytics callback. Ultralytics also ships
# its own mlflow integration, which would open a second, competing run; the
# env var below disables it.
os.environ.setdefault("MLFLOW", "False")


def _safe(method):
    """
    Tracking must never take the training run down with it.

    A trial that trained successfully but failed to log is still a valid trial:
    Katib reads the objective from stdout, so a tracking error here would throw
    away a finished GPU-hour. Failures are reported once and then ignored.
    """

    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if self._broken:
            return None
        try:
            return method(self, *args, **kwargs)
        except Exception as exc:
            self._broken = True
            print(f"mlflow      {method.__name__} failed, tracking off "
                  f"({type(exc).__name__}: {exc})")
            return None

    return wrapper


class NullTracker:
    """Used when tracking is disabled; every method does nothing."""

    enabled = False

    def start(self, *args, **kwargs):
        return self

    def log_params(self, params):
        pass

    def log_metrics(self, metrics, step=None):
        pass

    def log_artifacts(self, path):
        pass

    def set_tags(self, tags):
        pass

    def attach(self, model):
        pass

    def finish(self):
        pass


class MlflowTracker:
    """Thin wrapper so train.py does not carry mlflow specifics."""

    enabled = True

    def __init__(self, uri: str, experiment: str):
        import mlflow

        self._mlflow = mlflow
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment(experiment)

        # The default 10s sample logged one point at a time is noisy over a
        # long train, so average 6 samples into one point per minute.
        mlflow.system_metrics.set_system_metrics_sampling_interval(10)
        mlflow.system_metrics.set_system_metrics_samples_before_logging(6)
        mlflow.system_metrics.set_system_metrics_node_id(
            os.environ.get("POD_NAME", os.environ.get("HOSTNAME", "trial"))
        )
        self._run = None
        self._broken = False

    @_safe
    def start(self, run_name: str):
        # log_system_metrics starts a background sampler for cpu/mem/disk/net,
        # plus gpu when pynvml sees a device.
        self._run = self._mlflow.start_run(
            run_name=run_name, log_system_metrics=True
        )
        print("mlflow run  ", run_name, self._run.info.run_id)
        return self

    @_safe
    def log_params(self, params):
        self._mlflow.log_params(params)

    @_safe
    def log_metrics(self, metrics, step=None):
        # mlflow only accepts numeric values
        clean = {
            k: float(v) for k, v in metrics.items()
            if isinstance(v, (int, float))
        }
        if clean:
            self._mlflow.log_metrics(clean, step=step)

    @_safe
    def log_artifacts(self, path: Path):
        self._mlflow.log_artifacts(str(path))

    @_safe
    def set_tags(self, tags):
        self._mlflow.set_tags(tags)

    @_safe
    def attach(self, model):
        """Log ultralytics' per-epoch metrics as an MLflow curve."""

        def on_fit_epoch_end(trainer):
            metrics = {
                # "metrics/mAP50(B)" -> "mAP50"; mlflow rejects "(" and ")"
                key.split("/")[-1].removesuffix("(B)"): value
                for key, value in trainer.metrics.items()
            }
            metrics.update(
                {f"loss/{k}": v for k, v in (trainer.label_loss_items(
                    trainer.tloss, prefix="train") or {}).items()}
            )
            self.log_metrics(metrics, step=trainer.epoch)

        model.add_callback("on_fit_epoch_end", on_fit_epoch_end)

    def finish(self):
        # Not @_safe: this must run even after an earlier call marked tracking
        # broken, or the run stays open and the metrics sampler keeps going.
        if self._run is None:
            return
        try:
            self._mlflow.end_run()
        except Exception as exc:
            print(f"mlflow      end_run failed ({type(exc).__name__}: {exc})")
        finally:
            self._run = None


def build_tracker(uri: str | None, experiment: str) -> NullTracker | MlflowTracker:
    """Return a live tracker when a tracking uri is configured, else a no-op."""
    uri = uri or os.environ.get("MLFLOW_TRACKING_URI")
    if not uri:
        print("mlflow      disabled (no tracking uri)")
        return NullTracker()
    try:
        return MlflowTracker(uri, experiment)
    except Exception as exc:
        # Tracking must never take the training run down with it.
        print(f"mlflow      disabled ({type(exc).__name__}: {exc})")
        return NullTracker()
