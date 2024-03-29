from pathlib import Path
from typing import Union
import numpy as np
import torch
from torch import nn

from smol.modules import ConvLayer


def darknet_numel(model: nn.Module) -> int:
    """Number of elements in the model as expected by Darknet."""
    num_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    for m in model.modules():
        if isinstance(m, nn.BatchNorm2d):
            num_params += len(m.running_mean)
            num_params += len(m.running_var)
    return num_params


def _load_conv_norm(weights: np.ndarray, module: ConvLayer) -> np.ndarray:
    norm_bias_numel = module.norm.bias.numel()
    norm_bias, weights = weights[:norm_bias_numel], weights[norm_bias_numel:]
    norm_bias = torch.from_numpy(norm_bias).view_as(module.norm.bias)

    norm_weight_numel = module.norm.weight.numel()
    norm_weight, weights = weights[:norm_weight_numel], weights[norm_weight_numel:]
    norm_weight = torch.from_numpy(norm_weight).view_as(module.norm.weight)

    norm_mean_numel = module.norm.running_mean.numel()
    norm_mean, weights = weights[:norm_mean_numel], weights[norm_mean_numel:]
    norm_mean = torch.from_numpy(norm_mean).view_as(module.norm.running_mean)

    norm_var_numel = module.norm.running_var.numel()
    norm_var, weights = weights[:norm_var_numel], weights[norm_var_numel:]
    norm_var = torch.from_numpy(norm_var).view_as(module.norm.running_var)

    conv_weight_numel = module.conv.weight.numel()
    conv_weight, weights = weights[:conv_weight_numel], weights[conv_weight_numel:]
    conv_weight = torch.from_numpy(conv_weight).view_as(module.conv.weight)

    module.norm.bias.data.copy_(norm_bias)
    module.norm.weight.data.copy_(norm_weight)
    module.norm.running_mean.data.copy_(norm_mean)
    module.norm.running_var.data.copy_(norm_var)
    module.conv.weight.data.copy_(conv_weight)

    return weights


def _load_conv(weights: np.ndarray, module: ConvLayer) -> np.ndarray:
    conv_bias_numel = module.conv.bias.numel()
    conv_bias, weights = weights[:conv_bias_numel], weights[conv_bias_numel:]
    conv_bias = torch.from_numpy(conv_bias).view_as(module.conv.bias)

    conv_weight_numel = module.conv.weight.numel()
    conv_weight, weights = weights[:conv_weight_numel], weights[conv_weight_numel:]
    conv_weight = torch.from_numpy(conv_weight).view_as(module.conv.weight)

    module.conv.bias.data.copy_(conv_bias)
    module.conv.weight.data.copy_(conv_weight)

    return weights


def load_darknet_weights(model: nn.Module, weights_path: Union[str, Path]) -> bool:
    """Load Darknet weights into PyTorch YOLO models."""
    with open(weights_path, "rb") as f:
        header = np.fromfile(f, count=5, dtype=np.int32)
        weights = np.fromfile(f, dtype=np.float32)

    model_name = Path(weights_path).stem
    major, minor, revision, seen, _ = header
    version = f"v{major}.{minor}.{revision}-{seen}"
    print(f"Loading {model_name} {version}...")

    if darknet_numel(model) != len(weights):
        raise ValueError("Unmatching number of weights")

    for name, module in model.named_children():
        if isinstance(module, ConvLayer):
            if module.batch_norm:
                weights = _load_conv_norm(weights, module)
            else:
                weights = _load_conv(weights, module)

    success = len(weights) == 0
    return success
