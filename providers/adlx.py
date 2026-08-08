"""Minimal Windows AMD ADLX telemetry backend."""

import ctypes
import os


_RESULT = ctypes.c_int32
_PVOID = ctypes.c_void_p
_CALL = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)


def _method(obj, index, restype, *argtypes):
    vtable = ctypes.cast(obj, ctypes.POINTER(_PVOID))[0]
    address = ctypes.cast(vtable, ctypes.POINTER(_PVOID))[index]
    return _CALL(restype, _PVOID, *argtypes)(address)


def _release(obj):
    if obj:
        _method(obj, 1, ctypes.c_long)(obj)


class ADLXTelemetry:
    """Read one AMD GPU through the ADLX DLL installed with Radeon drivers."""

    def __init__(self, device_index=0):
        if os.name != "nt":
            raise RuntimeError("ADLX is only available on Windows")

        self._dll = ctypes.CDLL("amdadlx64.dll")
        self._dll.ADLXQueryFullVersion.argtypes = [ctypes.POINTER(ctypes.c_uint64)]
        self._dll.ADLXQueryFullVersion.restype = _RESULT
        self._dll.ADLXInitialize.argtypes = [ctypes.c_uint64, ctypes.POINTER(_PVOID)]
        self._dll.ADLXInitialize.restype = _RESULT

        version = ctypes.c_uint64()
        if self._dll.ADLXQueryFullVersion(ctypes.byref(version)) != 0:
            raise RuntimeError("ADLXQueryFullVersion failed")

        self._system = _PVOID()
        result = self._dll.ADLXInitialize(version.value, ctypes.byref(self._system))
        if result not in (0, 1, 2) or not self._system:
            raise RuntimeError(f"ADLXInitialize failed: {result}")

        self._gpu_list = _PVOID()
        result = _method(self._system, 1, _RESULT, ctypes.POINTER(_PVOID))(
            self._system, ctypes.byref(self._gpu_list)
        )
        if result != 0:
            raise RuntimeError(f"ADLX GetGPUs failed: {result}")

        count = _method(self._gpu_list, 3, ctypes.c_uint32)(self._gpu_list)
        if device_index >= count:
            raise RuntimeError(f"ADLX GPU index {device_index} is unavailable")

        self._gpu = _PVOID()
        begin = _method(self._gpu_list, 5, ctypes.c_uint32)(self._gpu_list)
        result = _method(
            self._gpu_list, 11, _RESULT, ctypes.c_uint32, ctypes.POINTER(_PVOID)
        )(self._gpu_list, begin + device_index, ctypes.byref(self._gpu))
        if result != 0:
            raise RuntimeError(f"ADLX GPU lookup failed: {result}")

        self.device_name = self._read_string(7) or "AMD GPU"
        self.device_id = self._read_string(14) or ""
        self.vram_total_gb = self._read_uint(11) / 1024.0

        self._performance = _PVOID()
        result = _method(self._system, 9, _RESULT, ctypes.POINTER(_PVOID))(
            self._system, ctypes.byref(self._performance)
        )
        if result != 0:
            raise RuntimeError(f"ADLX performance service failed: {result}")

        self._support = _PVOID()
        result = _method(
            self._performance, 21, _RESULT, _PVOID, ctypes.POINTER(_PVOID)
        )(self._performance, self._gpu, ctypes.byref(self._support))
        if result != 0:
            raise RuntimeError(f"ADLX metric support query failed: {result}")

        self.tgp_w = self._read_power_limit()

    def _read_string(self, index):
        value = ctypes.c_char_p()
        result = _method(self._gpu, index, _RESULT, ctypes.POINTER(ctypes.c_char_p))(
            self._gpu, ctypes.byref(value)
        )
        return value.value.decode(errors="replace") if result == 0 and value.value else ""

    def _read_uint(self, index):
        value = ctypes.c_uint32()
        result = _method(self._gpu, index, _RESULT, ctypes.POINTER(ctypes.c_uint32))(
            self._gpu, ctypes.byref(value)
        )
        return value.value if result == 0 else 0

    def _read_power_limit(self):
        minimum = ctypes.c_int32()
        maximum = ctypes.c_int32()
        result = _method(
            self._support,
            18,
            _RESULT,
            ctypes.POINTER(ctypes.c_int32),
            ctypes.POINTER(ctypes.c_int32),
        )(self._support, ctypes.byref(minimum), ctypes.byref(maximum))
        return float(maximum.value) if result == 0 else 0.0

    def _metric(self, metrics, support_index, metric_index, value_type):
        supported = ctypes.c_uint8()
        result = _method(
            self._support, support_index, _RESULT, ctypes.POINTER(ctypes.c_uint8)
        )(self._support, ctypes.byref(supported))
        if result != 0 or not supported.value:
            return None

        value = value_type()
        result = _method(
            metrics, metric_index, _RESULT, ctypes.POINTER(value_type)
        )(metrics, ctypes.byref(value))
        return value.value if result == 0 else None

    def read(self):
        metrics = _PVOID()
        result = _method(
            self._performance, 18, _RESULT, _PVOID, ctypes.POINTER(_PVOID)
        )(self._performance, self._gpu, ctypes.byref(metrics))
        if result != 0:
            raise RuntimeError(f"ADLX metric read failed: {result}")

        try:
            vram_mb = self._metric(metrics, 11, 12, ctypes.c_int32)
            return {
                "device_name": self.device_name,
                "device_id": self.device_id,
                "vram_total_gb": self.vram_total_gb,
                "vram_used_gb": vram_mb / 1024.0 if vram_mb is not None else None,
                "gpu_load_pct": self._metric(metrics, 3, 4, ctypes.c_double),
                "gpu_freq_mhz": self._metric(metrics, 4, 5, ctypes.c_int32),
                "gpu_temp_c": self._metric(metrics, 6, 7, ctypes.c_double),
                "power_w": self._metric(metrics, 8, 9, ctypes.c_double),
                "tgp_w": self.tgp_w,
            }
        finally:
            _release(metrics)


__all__ = ["ADLXTelemetry"]
