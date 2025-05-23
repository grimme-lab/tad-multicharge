# This file is part of tad-multicharge.
#
# SPDX-Identifier: Apache-2.0
# Copyright (C) 2024 Grimme Group
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
Testing the charges module
==========================

This module tests the EEQ charge model including:
 - single molecule
 - batched
 - ghost atoms
 - autograd via `gradcheck`

Note that `torch.linalg.solve` gives slightly different results (around 1e-5
to 1e-6) across different PyTorch versions (1.11.0 vs 1.13.0) for single
precision. For double precision, however the results are identical.
"""
from __future__ import annotations

import pytest
import torch
from tad_mctc.convert import str_to_device
from tad_mctc.typing import MockTensor

from tad_multicharge.model import ChargeModel, eeq


@pytest.mark.parametrize("dtype", [torch.float16, torch.float32, torch.float64])
def test_change_type(dtype: torch.dtype) -> None:
    model = eeq.EEQModel.param2019().type(dtype)
    assert model.dtype == dtype


def test_change_type_fail() -> None:
    model = eeq.EEQModel.param2019()

    # trying to use setter
    with pytest.raises(AttributeError):
        model.dtype = torch.float64

    # passing disallowed dtype
    with pytest.raises(ValueError):
        model.type(torch.bool)


@pytest.mark.cuda
@pytest.mark.parametrize("device_str", ["cpu", "cuda"])
def test_change_device(device_str: str) -> None:
    device = str_to_device(device_str)
    model = eeq.EEQModel.param2019().to(device)
    assert model.device == device


def test_change_device_fail() -> None:
    model = eeq.EEQModel.param2019()

    # trying to use setter
    with pytest.raises(AttributeError):
        model.device = torch.device("cpu")


def test_init_dtype_fail() -> None:
    t = torch.rand(5)

    # all tensor must have the same type
    with pytest.raises(RuntimeError):
        eeq.EEQModel(t.type(torch.double), t, t, t)


@pytest.mark.cuda
def test_init_device_fail() -> None:
    t = torch.rand(5)
    if "cuda" in str(t.device):
        t = t.cpu()
    elif "cpu" in str(t.device):
        t = t.cuda()

    # all tensor must be on the same device
    with pytest.raises(RuntimeError):
        eeq.EEQModel(t, t, t, t)


def test_solve_dtype_fail() -> None:
    t = torch.rand(5, dtype=torch.float64)
    model = eeq.EEQModel.param2019()

    # all tensor must have the same type
    with pytest.raises(RuntimeError):
        model.solve(t, t.type(torch.float16), t, t)


@pytest.mark.cuda
def test_solve_device_fail() -> None:
    t = torch.rand(5)
    t2 = t.clone()
    model = eeq.EEQModel.param2019()

    if "cuda" in str(t.device):
        t2 = t2.cpu()
    elif "cpu" in str(t.device):
        t2 = t2.cuda()

    # all tensor must be on the same device
    with pytest.raises(RuntimeError):
        model.solve(t, t2, t, t)


def test_model_device_different() -> None:
    cuda_tensor = MockTensor([4, 5, 6])
    cuda_tensor.device = torch.device("cuda")

    cpu_tensor = MockTensor([1, 2, 3])
    cpu_tensor.device = torch.device("cpu")
    with pytest.raises(RuntimeError) as exc:
        ChargeModel(cpu_tensor, cpu_tensor, cpu_tensor, cuda_tensor)

    assert "All tensors must be on the same device!" in str(exc.value)


def test_solve_device_different() -> None:
    model = eeq.EEQModel.param2019()

    cuda_tensor = MockTensor([4, 5, 6])
    cuda_tensor.device = torch.device("cuda")

    cpu_tensor = MockTensor([1, 2, 3])
    cpu_tensor.device = torch.device("cpu")

    # all tensor must be on the same device
    with pytest.raises(RuntimeError) as exc:
        model.solve(cpu_tensor, cuda_tensor, cpu_tensor, cpu_tensor)

    assert "must be on the same device!" in str(exc.value)


def test_solve_shape_fail() -> None:
    numbers = torch.ones((1, 5), dtype=torch.long)
    positions = torch.ones((1, 5, 3), dtype=torch.float64)

    charge = torch.tensor([1.0], dtype=torch.float64)
    model = eeq.EEQModel.param2019(dtype=torch.float64)

    # Shape of charge must be (1, 5) too
    with pytest.raises(ValueError):
        model.solve(numbers, positions, charge, numbers)
