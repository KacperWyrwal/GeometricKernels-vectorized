"""
GPyTorch kernel wrapper.

A tutorial on how to use this wrapper to run Gaussian process regression on
a geometric space is available in the `frontends/GPyTorch.ipynb <https://github.com/GPflow/GeometricKernels/blob/main/notebooks/frontends/GPyTorch.ipynb>`_
notebook.
"""
from typing import Union

import gpytorch
import numpy as np
import torch

from geometric_kernels.kernels import BaseGeometricKernel
from geometric_kernels.spaces.base import Space


class GPyTorchGeometricKernel(gpytorch.kernels.Kernel):
    """
    GPyTorch wrapper for :class:`BaseGeometricKernel`.

    A tutorial on how to use this wrapper to run Gaussian process regression on
    a geometric space is available in the `frontends/GPyTorch.ipynb <https://github.com/GPflow/GeometricKernels/blob/main/notebooks/frontends/GPyTorch.ipynb>`_
    notebook.

    **Note**: the `base_kernel` itself does not store any of its hyperparameters
    (like `lengthscale` and `nu`), therefore you either need to pass them down to
    this wrapper explicitly or use the default values, as provided by the
    `init_params` method of the `base_kernel`. As customary in GPyTorch, this
    wrapper does not maintain a variance (outputscale) parameter. To add it,
    use :code:`gpytorch.kernels.ScaleKernel(GPyTorchGeometricKernel(...))`.

    :param base_kernel:
        The kernel to wrap.
    :param lengthscale:
        Initial value of the length scale.

        If not given or set to None, uses the default value of the
        `base_kernel`, as provided by its `init_params` method.
    :param nu:
        Initial value of the smoothness parameter nu.

        If not given or set to None, uses the default value of the
        `base_kernel`, as provided by its `init_params` method.

    :param trainable_nu:
        Whether or not the parameter nu is to be optimized over.

        Cannot be True if nu is equal to infinity. You cannot change
        this parameter after constructing the object. Defaults to False.

    :raises ValueError: if trying to set nu = infinity together with
        trainable_nu = True.
    """

    has_lengthscale = True

    def __init__(
        self,
        base_kernel: BaseGeometricKernel,
        lengthscale: Union[float, torch.Tensor, np.ndarray] = None,
        nu: Union[float, torch.Tensor, np.ndarray] = None,
        trainable_nu: bool = False,
        **kwargs,
    ):
        """
        Initialize a GPyTorchGeometricKernel object.
        """
        super().__init__(**kwargs)

        self.base_kernel = base_kernel

        default_params = base_kernel.init_params()

        if nu is None:
            nu = default_params["nu"]

        if lengthscale is None:
            lengthscale = default_params["lengthscale"]

        lengthscale = torch.as_tensor(lengthscale)
        nu = torch.as_tensor(nu)

        self._trainable_nu = trainable_nu
        if self._trainable_nu and torch.isinf(nu):
            raise ValueError("Cannot have trainable `nu` parameter with infinite value")

        self.lengthscale = lengthscale

        if self._trainable_nu:
            self.register_parameter(
                name="raw_nu", parameter=torch.nn.Parameter(torch.tensor(1.0))
            )
            self.register_constraint("raw_nu", gpytorch.constraints.Positive())
            self.nu = nu
        else:
            self.register_buffer("raw_nu", nu)

    @property
    def space(self) -> Space:
        """Alias to kernel space"""
        return self.base_kernel.space

    @property
    def nu(self) -> torch.Tensor:
        """The smoothness parameter"""
        if self._trainable_nu:
            return self.raw_nu_constraint.transform(self.raw_nu)
        else:
            return self.raw_nu

    @nu.setter
    def nu(self, value):
        if self._trainable_nu:
            if torch.isinf(value):
                raise ValueError(
                    "Cannot have infinite `nu` value when trainable_nu = True"
                )
            value = torch.as_tensor(value).to(self.raw_nu)
            self.initialize(raw_nu=self.raw_nu_constraint.inverse_transform(value))
        else:
            self.raw_nu = torch.as_tensor(value)

    def forward(self, x1, x2, diag=False, last_dim_is_batch=False, **kwargs):
        """Evaluate kernel"""
        params = dict(lengthscale=self.lengthscale, nu=self.nu)
        if diag:
            return self.base_kernel.K_diag(params, x1)
        return self.base_kernel.K(params, x1, x2)
