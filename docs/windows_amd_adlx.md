# Windows AMD GPU telemetry via ADLX

This fork adds a native Windows telemetry path for AMD GPUs. It is designed for ComfyUI portable builds that use an AMD ROCm/HIP PyTorch build on Windows.

## What changed

- Windows now prefers AMD ADLX, the telemetry interface provided by the installed Radeon driver.
- Linux keeps the existing \`rocm_smi\` path.
- PyTorch allocator statistics remain available on all supported AMD builds.
- AMD ROCm/HIP builds that do not expose \`torch.version.roc\` are detected from their \`+rocm\` or \`+hip\` version marker, preventing an accidental NVIDIA provider selection.

No extra Python package or copied DLL is required. The backend loads the AMD driver-installed \`amdadlx64.dll\` with Python \`ctypes\`.

## Windows requirements

1. A current AMD Radeon driver that includes ADLX.
2. A Windows x64 ComfyUI/Python process.
3. An AMD-compatible PyTorch build. The normal ComfyUI AMD portable package is sufficient.

If ADLX is unavailable, the plugin logs the reason and falls back to its existing ROCm SMI / PyTorch paths.

## Metrics provided by ADLX

| Metric | Source |
| --- | --- |
| GPU load | Current GPU usage |
| GPU frequency | Current core clock |
| Temperature | Current GPU temperature |
| Power | Current GPU power when the driver exposes it |
| VRAM used/free/total | Driver-reported memory budget |
| Allocated/reserved | PyTorch allocator statistics |

The TGP/board-power limit may be unavailable on APUs or laptops. The plugin reports an unavailable limit as \`0\`; it does not substitute instantaneous power.

## APU / UMA note

On an AMD APU, the reported GPU memory budget can be shared system memory rather than dedicated VRAM. For example, a Radeon 8060S can expose a 64 GB GPU memory budget on a 64 GB system. Treat that number as the current driver/UMA budget, not as 64 GB of physically dedicated VRAM.

## Verified environment

This implementation was validated on:

- AMD Radeon(TM) 8060S Graphics (PCI \`0x1586\`)
- Windows AMD portable ComfyUI
- Python 3.12.10 and PyTorch 2.9.1+rocm7.2.1
- AMD ADLX 1.5.0.124

Live readings included GPU load, core clock, 49 C temperature, instantaneous power, and 24 GB used of a 64 GB UMA memory budget. It works without Administrator privileges.

## Known limitations

- The provider currently monitors GPU index 0.
- ADLX availability depends on the installed AMD driver.
- AMD SMI / ROCm SMI does not currently provide the same full native Windows monitoring route, which is why this backend is used.

---

# Windows AMD GPU 监控（ADLX）

这个 fork 为 Windows AMD GPU 增加了原生 ADLX 监控后端，适用于使用 AMD ROCm/HIP PyTorch 的 ComfyUI 便携版。

## 改动内容

- Windows 优先使用 AMD 显卡驱动提供的 ADLX。
- Linux 继续使用原有的 \`rocm_smi\` 路径。
- 保留 PyTorch 的 allocated / reserved 显存统计。
- 当 Windows ROCm/HIP PyTorch 没有 \`torch.version.roc\` 时，使用版本号中的 \`+rocm\` 或 \`+hip\` 标识识别 AMD，避免误选 NVIDIA Provider。

不需要额外安装 Python 包，也不需要复制 DLL。后端通过 Python \`ctypes\` 调用 Radeon 驱动已安装的 \`amdadlx64.dll\`。

## 可读取的数据

GPU 占用、核心频率、温度、实时功耗、驱动报告的显存已用/可用/总量，以及 PyTorch 分配器统计。

APU 或笔记本可能不支持读取 TGP / 整卡功耗上限；此时显示为 \`0\`，不会把瞬时功耗冒充上限。

## APU / UMA 说明

AMD APU 的 GPU 内存预算通常来自共享系统内存，不等于独立显存。例如 64 GB 内存的 Radeon 8060S 可能显示 64 GB GPU 内存预算；应把它理解为驱动当前可用的 UMA 预算。

当前仍只监控 GPU 索引 0；ADLX 是否可用取决于已安装的 AMD 显卡驱动。
