"""Own and cancel only our background acquisition process tree on Windows."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import time

from .common import read_json, write_json

HIDDEN = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


class IO(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in ('read', 'write', 'other', 'read_bytes', 'write_bytes', 'other_bytes')]


class Basic(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
        ('flags', wintypes.DWORD), ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t),
        ('active_limit', wintypes.DWORD), ('affinity', ctypes.c_size_t),
        ('priority', wintypes.DWORD), ('scheduling', wintypes.DWORD)]


class Limits(ctypes.Structure):
    _fields_ = [('basic', Basic), ('io', IO), ('process_memory', ctypes.c_size_t),
        ('job_memory', ctypes.c_size_t), ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]


class Accounting(ctypes.Structure):
    _fields_ = [(n, ctypes.c_longlong) for n in ('user', 'kernel', 'period_user', 'period_kernel')] + [
        (n, wintypes.DWORD) for n in ('faults', 'total', 'active', 'terminated')]


class Job:
    def __init__(self):
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        for name, args, result in (
            ('CreateJobObjectW', [ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE),
            ('SetInformationJobObject', [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD], wintypes.BOOL),
            ('AssignProcessToJobObject', [wintypes.HANDLE, wintypes.HANDLE], wintypes.BOOL),
            ('QueryInformationJobObject', [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p], wintypes.BOOL),
            ('TerminateJobObject', [wintypes.HANDLE, wintypes.UINT], wintypes.BOOL),
            ('CloseHandle', [wintypes.HANDLE], wintypes.BOOL)):
            method = getattr(self.api, name)
            method.argtypes, method.restype = args, result
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Limits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close()
            raise ctypes.WinError(ctypes.get_last_error())

    def assign(self, process):
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())

    def accounting(self):
        value = Accounting()
        if not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(value), ctypes.sizeof(value), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return {'total_processes': value.total, 'active_processes': value.active, 'terminated_processes': value.terminated}

    def stop(self):
        if not self.api.TerminateJobObject(self.handle, 124):
            raise ctypes.WinError(ctypes.get_last_error())
        until = time.monotonic() + 5
        while self.accounting()['active_processes'] and time.monotonic() < until:
            time.sleep(0.02)
        result = self.accounting()
        if result['active_processes']:
            raise RuntimeError('本次获取子进程未结束，停止调度后续素材')
        return result

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


class Worker:
    """Reusable child; stdin handshake prevents spawning before Job assignment."""
    def __init__(self, log: Path, command: list[str] | None = None):
        self.log, self.command = log, command or [sys.executable, '-B', '-X', 'utf8', '-m', 'douyin_text.acquisition_worker']
        self.process = self.job = self.stream = None
        self.receipts = []

    def start(self):
        self.log.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.log.open('ab')
        self.job = Job()
        env = {k: v for k, v in os.environ.items() if not k.startswith('DOUBAO_ASR_')}
        env['PYTHONPATH'] = str(Path(__file__).resolve().parent.parent)
        env['CY_UPDATE_CHECK'] = '0'
        self.process = subprocess.Popen(self.command, stdin=subprocess.PIPE, stdout=self.stream,
            stderr=subprocess.STDOUT, env=env, creationflags=HIDDEN, cwd=Path(__file__).resolve().parent.parent)
        try:
            self.job.assign(self.process)
        except Exception:
            self.process.kill()
            self.process.wait(timeout=5)
            self.close()
            raise

    def run(self, data: dict, folder: Path, timeout: float = 90) -> dict:
        started = time.monotonic()
        if self.process is None:
            self.start()
        request_file, response_file = folder / 'request.json', folder / 'response.json'
        if response_file.exists():
            raise ValueError('获取尝试目录必须唯一')
        write_json(request_file, {**data, 'response_file': str(response_file)})
        self.process.stdin.write((str(request_file) + '\n').encode('utf-8'))
        self.process.stdin.flush()
        while not response_file.is_file():
            if time.monotonic() - started >= timeout:
                self.close()
                raise TimeoutError('素材获取超过总时限，已停止本次获取进程；未提交豆包')
            if self.process.poll() is not None:
                self.close()
                raise RuntimeError('后台获取进程提前退出，详情保存在本地 worker 日志')
            time.sleep(0.025)
        return {**read_json(response_file), 'elapsed_seconds': round(time.monotonic() - started, 3)}

    def close(self):
        try:
            if self.job:
                self.receipts.append(self.job.stop())
                self.job.close()
            if self.process:
                self.process.wait(timeout=5)
                self.process.stdin.close()
        finally:
            if self.stream:
                self.stream.close()
            self.process = self.job = self.stream = None
