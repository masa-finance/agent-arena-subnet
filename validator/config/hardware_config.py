from dataclasses import dataclass
from typing import Optional
import torch
import psutil

@dataclass
class HardwareConfig:
    """Hardware configuration for performance tuning"""
    batch_size: int
    max_samples: int
    shap_background_samples: int
    shap_nsamples: int
    device_type: str  # 'cpu', 'mps', 'cuda'
    gpu_memory: Optional[int] = None  # GPU memory in GB, if applicable

class PerformanceConfig:
    """Performance configuration profiles for different hardware specs"""
    
    # Default CPU settings
    DEFAULT_CPU = HardwareConfig(
        batch_size=512,
        max_samples=1000,
        shap_background_samples=100,
        shap_nsamples=100,
        device_type='cpu'
    )
    
    # Apple Silicon Configurations
    M_SERIES = {
        32: HardwareConfig(
            batch_size=1024,
            max_samples=2000,
            shap_background_samples=100,
            shap_nsamples=50,
            device_type='mps'
        ),
        64: HardwareConfig(
            batch_size=2048,
            max_samples=4000,
            shap_background_samples=200,
            shap_nsamples=100,
            device_type='mps'
        ),
        96: HardwareConfig(
            batch_size=4096,
            max_samples=8000,
            shap_background_samples=400,
            shap_nsamples=200,
            device_type='mps'
        )
    }
    
    # NVIDIA GPU Configurations
    NVIDIA_GPU = {
        8: HardwareConfig(
            batch_size=2048,
            max_samples=4000,
            shap_background_samples=200,
            shap_nsamples=100,
            device_type='cuda',
            gpu_memory=8
        ),
        12: HardwareConfig(
            batch_size=4096,
            max_samples=8000,
            shap_background_samples=400,
            shap_nsamples=200,
            device_type='cuda',
            gpu_memory=12
        ),
        24: HardwareConfig(
            batch_size=8192,
            max_samples=16000,
            shap_background_samples=800,
            shap_nsamples=400,
            device_type='cuda',
            gpu_memory=24
        ),
        48: HardwareConfig(
            batch_size=16384,
            max_samples=32000,
            shap_background_samples=1600,
            shap_nsamples=800,
            device_type='cuda',
            gpu_memory=48
        )
    }

    @staticmethod
    def get_gpu_memory_gb() -> Optional[int]:
        """Get GPU memory in GB if CUDA is available"""
        if torch.cuda.is_available():
            try:
                gpu_memory = torch.cuda.get_device_properties(0).total_memory
                return int(gpu_memory / (1024**3))  # Convert bytes to GB
            except:
                return None
        return None

    @staticmethod
    def get_config(ram_override: Optional[int] = None, 
                  gpu_memory_override: Optional[int] = None) -> HardwareConfig:
        """Get the appropriate configuration based on system hardware"""
        if gpu_memory_override is not None:
            gpu_memory = gpu_memory_override
        else:
            gpu_memory = PerformanceConfig.get_gpu_memory_gb()

        total_ram = ram_override or (psutil.virtual_memory().total / (1024 ** 3))

        if torch.cuda.is_available() and gpu_memory:
            gpu_configs = sorted(PerformanceConfig.NVIDIA_GPU.keys())
            for gpu_size in gpu_configs:
                if gpu_memory <= gpu_size:
                    return PerformanceConfig.NVIDIA_GPU[gpu_size]
            return PerformanceConfig.NVIDIA_GPU[gpu_configs[-1]]

        elif torch.backends.mps.is_available():
            ram_configs = sorted(PerformanceConfig.M_SERIES.keys())
            for ram_size in ram_configs:
                if total_ram <= ram_size:
                    return PerformanceConfig.M_SERIES[ram_size]
            return PerformanceConfig.M_SERIES[ram_configs[-1]]

        else:
            return PerformanceConfig.DEFAULT_CPU 