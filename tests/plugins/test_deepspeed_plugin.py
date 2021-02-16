import json
import os
import platform

import pytest
import torch

from pytorch_lightning import Trainer
from pytorch_lightning.callbacks import Callback
from pytorch_lightning.plugins import DeepSpeedPlugin, DeepSpeedPrecisionPlugin
from pytorch_lightning.utilities import _APEX_AVAILABLE, _DEEPSPEED_AVAILABLE, _NATIVE_AMP_AVAILABLE
from pytorch_lightning.utilities.exceptions import MisconfigurationException
from tests.helpers.boring_model import BoringModel

PRETEND_N_OF_GPUS = 1


@pytest.fixture
def deepspeed_config():
    return {
        "optimizer": {
            "type": "Adam",
            "torch_adam": True,
            "params": {
                "lr": 3e-5,
                "betas": [0.998, 0.999],
                "eps": 1e-5,
                "weight_decay": 1e-9,
            },
        },
        'scheduler': {
            "type": "WarmupLR",
            "params": {
                "last_batch_iteration": -1,
                "warmup_min_lr": 0,
                "warmup_max_lr": 3e-5,
                "warmup_num_steps": 100,
            }
        }
    }


@pytest.mark.skipif(not _DEEPSPEED_AVAILABLE, reason="DeepSpeed not available.")
def test_deepspeed_plugin_string(tmpdir):
    """
        Test to ensure that the plugin can be passed via string, and parallel devices is correctly set.
    """

    class CB(Callback):

        def on_fit_start(self, trainer, pl_module):
            assert isinstance(trainer.accelerator_backend.training_type_plugin, DeepSpeedPlugin)
            assert trainer.accelerator_backend.training_type_plugin.parallel_devices == [torch.device('cpu')]
            raise SystemExit()

    model = BoringModel()
    trainer = Trainer(
        fast_dev_run=True,
        plugins='deepspeed',
        callbacks=[CB()],
    )

    with pytest.raises(SystemExit):
        trainer.fit(model)


@pytest.mark.skipif(not _DEEPSPEED_AVAILABLE, reason="DeepSpeed not available.")
def test_deepspeed_plugin(tmpdir):
    """
        Test to ensure that the plugin can be passed directly, and parallel devices is correctly set.
    """

    class CB(Callback):

        def on_fit_start(self, trainer, pl_module):
            assert isinstance(trainer.accelerator_backend.training_type_plugin, DeepSpeedPlugin)
            assert trainer.accelerator_backend.training_type_plugin.parallel_devices == [torch.device('cpu')]
            raise SystemExit()

    model = BoringModel()
    trainer = Trainer(
        fast_dev_run=True,
        plugins=[DeepSpeedPlugin()],
        callbacks=[CB()],
    )

    with pytest.raises(SystemExit):
        trainer.fit(model)


@pytest.mark.skipif(not _DEEPSPEED_AVAILABLE, reason="DeepSpeed not available.")
def test_deepspeed_plugin_env(tmpdir, monkeypatch, deepspeed_config):
    """
        Test to ensure that the plugin can be passed via a string with an environment variable.
    """
    config_path = os.path.join(tmpdir, 'temp.json')
    with open(config_path, 'w') as f:
        f.write(json.dumps(deepspeed_config))
    monkeypatch.setenv("DEEPSPEED_CONFIG_PATH", config_path)

    class CB(Callback):

        def on_fit_start(self, trainer, pl_module):
            plugin = trainer.accelerator_backend.training_type_plugin
            assert isinstance(plugin, DeepSpeedPlugin)
            assert plugin.parallel_devices == [torch.device('cpu')]
            assert plugin.config == deepspeed_config
            raise SystemExit()

    model = BoringModel()
    trainer = Trainer(
        fast_dev_run=True,
        plugins='deepspeed',
        callbacks=[CB()],
    )

    with pytest.raises(SystemExit):
        trainer.fit(model)


@pytest.mark.skipif(not _DEEPSPEED_AVAILABLE, reason="DeepSpeed not available.")
@pytest.mark.skipif(not _NATIVE_AMP_AVAILABLE, reason="Requires native AMP")
def test_deepspeed_amp_choice(tmpdir):
    """
        Test to ensure precision plugin is also correctly chosen. DeepSpeed handles precision via
        Custom DeepSpeedPrecisionPlugin
    """

    class CB(Callback):

        def on_fit_start(self, trainer, pl_module):
            assert isinstance(trainer.accelerator_backend.training_type_plugin, DeepSpeedPlugin)
            assert isinstance(trainer.accelerator_backend.precision_plugin, DeepSpeedPrecisionPlugin)
            assert trainer.accelerator_backend.precision_plugin.precision == 16
            raise SystemExit()

    model = BoringModel()
    trainer = Trainer(fast_dev_run=True, plugins='deepspeed', callbacks=[CB()], amp_backend='native', precision=16)

    with pytest.raises(SystemExit):
        trainer.fit(model)


@pytest.mark.skipif(not _DEEPSPEED_AVAILABLE, reason="DeepSpeed not available.")
@pytest.mark.skipif(not _APEX_AVAILABLE, reason="Requires Apex")
def test_deepspeed_apex_choice(tmpdir):
    """
        Test to ensure precision plugin is also correctly chosen. DeepSpeed handles precision via
        Custom DeepSpeedPrecisionPlugin
    """

    class CB(Callback):

        def on_fit_start(self, trainer, pl_module):
            assert isinstance(trainer.accelerator_backend.training_type_plugin, DeepSpeedPlugin)
            assert isinstance(trainer.accelerator_backend.precision_plugin, DeepSpeedPrecisionPlugin)
            assert trainer.accelerator_backend.precision_plugin.precision == 16
            raise SystemExit()

    model = BoringModel()
    trainer = Trainer(fast_dev_run=True, plugins='deepspeed', callbacks=[CB()], amp_backend='apex', precision=16)

    with pytest.raises(SystemExit):
        trainer.fit(model)


@pytest.mark.skipif(not _DEEPSPEED_AVAILABLE, reason="DeepSpeed not available.")
def test_deepspeed_with_invalid_config_path(tmpdir):
    """
        Test to ensure if we pass an invalid config path we throw an exception.
    """

    with pytest.raises(
        MisconfigurationException, match="You passed in a path to a DeepSpeed config but the path does not exist"
    ):
        DeepSpeedPlugin(config='invalid_path.json')


@pytest.mark.skipif(not _DEEPSPEED_AVAILABLE, reason="DeepSpeed not available.")
def test_deepspeed_with_env_path(tmpdir, monkeypatch, deepspeed_config):
    """
        Test to ensure if we pass an env variable, we load the config from the path.
    """
    config_path = os.path.join(tmpdir, 'temp.json')
    with open(config_path, 'w') as f:
        f.write(json.dumps(deepspeed_config))
    monkeypatch.setenv("DEEPSPEED_CONFIG_PATH", config_path)
    plugin = DeepSpeedPlugin()
    assert plugin.config == deepspeed_config


@pytest.mark.skipif(not _DEEPSPEED_AVAILABLE, reason="DeepSpeed not available.")
def test_deepspeed_defaults(tmpdir):
    """
    Ensure that defaults are correctly set as a config for DeepSpeed if no arguments are passed.
    """
    plugin = DeepSpeedPlugin()
    assert plugin.config is not None
    assert isinstance(plugin.config["zero_optimization"], dict)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="requires GPU machine")
@pytest.mark.skipif(platform.system() == "Windows", reason="Distributed training is not supported on Windows")
@pytest.mark.skipif(not _DEEPSPEED_AVAILABLE, reason="DeepSpeed not available.")
def test_invalid_deepspeed_defaults_no_precision(tmpdir):
    """
        Test to ensure that using defaults, if precision is not set to 16, we throw an exception.
    """
    model = BoringModel()
    trainer = Trainer(
        fast_dev_run=True,
        plugins='deepspeed',
        gpus=1,
    )
    with pytest.raises(
        MisconfigurationException, match='To use DeepSpeed ZeRO Optimization, you must set precision=16.'
    ):
        trainer.fit(model)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="requires GPU machine")
@pytest.mark.skipif(platform.system() == "Windows", reason="Distributed training is not supported on Windows")
@pytest.mark.skipif(not _DEEPSPEED_AVAILABLE, reason="DeepSpeed not available.")
def test_deepspeed_run_configure_optimizers(tmpdir):
    """
        Test to end to end that deepspeed works with defaults,
        whilst using configure_optimizers for optimizers and schedulers.
    """

    class TestModel(BoringModel):

        def on_train_start(self) -> None:
            from deepspeed.runtime.zero.stage2 import FP16_DeepSpeedZeroOptimizer
            assert isinstance(self.trainer.optimizers[0], FP16_DeepSpeedZeroOptimizer)
            assert isinstance(self.trainer.optimizers[0].optimizer, torch.optim.SGD)
            assert self.trainer.lr_schedulers == []  # DeepSpeed manages LR scheduler internally
            # Ensure DeepSpeed engine has initialized with our optimizer/lr_scheduler
            assert isinstance(self.trainer.model.optimizer, FP16_DeepSpeedZeroOptimizer)
            assert isinstance(self.trainer.model.lr_scheduler, torch.optim.lr_scheduler.StepLR)

    model = TestModel()
    trainer = Trainer(
        plugins='deepspeed',
        gpus=1,
        precision=16,
        fast_dev_run=True,
    )

    trainer.fit(model)

    checkpoint_path = os.path.join(tmpdir, 'model.pt')
    trainer.save_checkpoint(checkpoint_path)
    saved_model = BoringModel.load_from_checkpoint(checkpoint_path)
    model = model.cpu().float()

    # Assert model parameters are identical after loading
    for orig_param, trained_model_param in zip(model.parameters(), saved_model.parameters()):
        assert torch.equal(orig_param, trained_model_param)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="requires GPU machine")
@pytest.mark.skipif(platform.system() == "Windows", reason="Distributed training is not supported on Windows")
@pytest.mark.skipif(not _DEEPSPEED_AVAILABLE, reason="DeepSpeed not available.")
def test_deepspeed_config(tmpdir, deepspeed_config):
    """
        Test to ensure deepspeed works correctly when passed a DeepSpeed config object including optimizers/schedulers
        and saves the model weights to load correctly.
    """

    class TestModel(BoringModel):

        def on_train_start(self) -> None:
            import deepspeed
            assert isinstance(self.trainer.optimizers[0], deepspeed.ops.adam.FusedAdam)
            assert self.trainer.lr_schedulers == []  # DeepSpeed manages LR scheduler internally
            assert isinstance(self.trainer.model.optimizer, deepspeed.ops.adam.FusedAdam)
            assert isinstance(self.trainer.model.lr_scheduler, deepspeed.runtime.lr_schedules.WarmupLR)

    model = TestModel()
    trainer = Trainer(
        plugins=[DeepSpeedPlugin(config=deepspeed_config)],
        gpus=1,
        fast_dev_run=True,
    )

    trainer.fit(model)
    trainer.test(model)

    checkpoint_path = os.path.join(tmpdir, 'model.pt')
    trainer.save_checkpoint(checkpoint_path)
    saved_model = BoringModel.load_from_checkpoint(checkpoint_path)
    model = model.cpu()
    # Assert model parameters are identical after loading
    for orig_param, trained_model_param in zip(model.parameters(), saved_model.parameters()):
        assert torch.equal(orig_param, trained_model_param)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="requires GPU machine")
@pytest.mark.skipif(platform.system() == "Windows", reason="Distributed training is not supported on Windows")
@pytest.mark.skipif(not _DEEPSPEED_AVAILABLE, reason="DeepSpeed not available.")
@pytest.mark.skipif(torch.cuda.device_count() < 2, reason="test requires multi-GPU machine")
@pytest.mark.skipif(
    not os.getenv("PL_RUNNING_SPECIAL_TESTS", '0') == '1', reason="test should be run outside of pytest"
)
def test_deepspeed_offload_zero_multigpu_config(tmpdir, deepspeed_config):
    """
        Test to ensure that zero offload with multiple GPUs works correctly if a user passes a ZeRO enabled config.
    """
    deepspeed_config = {
        **deepspeed_config, "zero_allow_untested_optimizer": True,
        "zero_optimization": {
            "stage": 2,
            "cpu_offload": True,
            "contiguous_gradients": True,
            "overlap_comm": True
        }
    }
    model = BoringModel()
    trainer = Trainer(
        plugins=[DeepSpeedPlugin(config=deepspeed_config)],
        gpus=2,
        fast_dev_run=True,
        precision=16,
    )
    trainer.fit(model)
    trainer.test(model)

    checkpoint_path = os.path.join(tmpdir, 'model.pt')
    trainer.save_checkpoint(checkpoint_path)
    # carry out the check only on rank 0
    if trainer.global_rank == 0:
        saved_model = BoringModel.load_from_checkpoint(checkpoint_path)
        saved_model = saved_model.float()
        model = model.float().cpu()
        # Assert model parameters are identical after loading
        for orig_param, trained_model_param in zip(model.parameters(), saved_model.parameters()):
            assert torch.equal(orig_param, trained_model_param)
