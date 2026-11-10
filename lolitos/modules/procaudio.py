"""Captura de áudio do Windows (WASAPI) para os Clipes, em ctypes puro.

- Só o jogo: 'process loopback' (Windows 10 build 20348+ / Windows 11) — pega o som do processo do jogo e dos
  filhos dele, e nada do Discord, música ou navegador.
- Todo o PC: loopback do dispositivo de saída padrão (qualquer Windows 10/11), usado quando o Windows não tem o
  modo por processo.

O áudio sai em PCM contínuo: quando o jogo fica em silêncio o Windows não entrega pacotes, então completamos com
silêncio para o som não sair adiantado em relação ao vídeo."""
from __future__ import annotations

import ctypes
import sys
import threading
import time
from ctypes import POINTER, byref, c_int, c_longlong, c_uint32, c_uint64, c_ushort, c_void_p

from lolitos.core.system import IS_WIN

if IS_WIN:
    from ctypes import WINFUNCTYPE, wintypes
    HRESULT = ctypes.HRESULT
else:   # permite importar (e testar a lógica pura) fora do Windows
    WINFUNCTYPE = ctypes.CFUNCTYPE
    wintypes = None
    HRESULT = ctypes.c_long

S_OK, E_NOINTERFACE = 0, -2147467262
CLSCTX_ALL = 23
AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
AUDCLNT_STREAMFLAGS_EVENTCALLBACK = 0x00040000
AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM = 0x80000000
AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY = 0x08000000
AUDCLNT_BUFFERFLAGS_SILENT = 0x2
ACTIVATION_TYPE_PROCESS_LOOPBACK = 1
LOOPBACK_INCLUDE_TREE, LOOPBACK_EXCLUDE_TREE = 0, 1
VT_BLOB = 65
WAVE_FORMAT_PCM, WAVE_FORMAT_IEEE_FLOAT, WAVE_FORMAT_EXTENSIBLE = 1, 3, 0xFFFE
PROCESS_LOOPBACK_BUILD = 20348


class GUID(ctypes.Structure):
    _fields_ = [("Data1", ctypes.c_uint32), ("Data2", ctypes.c_uint16), ("Data3", ctypes.c_uint16),
                ("Data4", ctypes.c_ubyte * 8)]

    @classmethod
    def of(cls, s: str) -> "GUID":
        h = s.strip("{}").replace("-", "")
        g = cls(int(h[0:8], 16), int(h[8:12], 16), int(h[12:16], 16))
        for i in range(8):
            g.Data4[i] = int(h[16 + 2 * i:18 + 2 * i], 16)
        return g

    def __eq__(self, o):
        return bytes(self) == bytes(o)


IID_IUnknown = GUID.of("00000000-0000-0000-C000-000000000046")
IID_IAgileObject = GUID.of("94EA2B94-E9CC-49E0-C0FF-EE64CA8F5B90")
IID_IActivateCompletion = GUID.of("41D949AB-9862-444A-80F6-C261334DA5EB")
IID_IAudioClient = GUID.of("1CB9AD4C-DBFA-4c32-B178-C2F568A703B2")
IID_IAudioCaptureClient = GUID.of("C8ADBD64-E71E-48a0-A4DE-185C395CD317")
CLSID_MMDeviceEnumerator = GUID.of("BCDE0395-E52F-467C-8E3D-C4579291692E")
IID_IMMDeviceEnumerator = GUID.of("A95664D2-9614-4F35-A746-DE8DB63617E6")


class WAVEFORMATEX(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("wFormatTag", c_ushort), ("nChannels", c_ushort), ("nSamplesPerSec", ctypes.c_uint32),
                ("nAvgBytesPerSec", ctypes.c_uint32), ("nBlockAlign", c_ushort), ("wBitsPerSample", c_ushort),
                ("cbSize", c_ushort)]


class LOOPBACK_PARAMS(ctypes.Structure):
    _fields_ = [("TargetProcessId", ctypes.c_uint32), ("ProcessLoopbackMode", c_int)]


class ACTIVATION_PARAMS(ctypes.Structure):
    _fields_ = [("ActivationType", c_int), ("ProcessLoopbackParams", LOOPBACK_PARAMS)]


class BLOB(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint32), ("pBlobData", c_void_p)]


class PROPVARIANT(ctypes.Structure):
    _fields_ = [("vt", c_ushort), ("r1", c_ushort), ("r2", c_ushort), ("r3", c_ushort), ("blob", BLOB)]


def _method(ptr, index: int, *argtypes):
    """Método `index` da vtable de uma interface COM (o HRESULT de erro vira OSError)."""
    vtbl = ctypes.cast(ptr, POINTER(POINTER(c_void_p)))[0]
    fn = WINFUNCTYPE(HRESULT, c_void_p, *argtypes)(vtbl[index])
    return lambda *a: fn(ptr, *a)


def _release(ptr):
    if ptr:
        vtbl = ctypes.cast(ptr, POINTER(POINTER(c_void_p)))[0]
        WINFUNCTYPE(ctypes.c_ulong, c_void_p)(vtbl[2])(ptr)


# ---------------------------------------------------------------- objeto de retorno da ativação assíncrona
_QI = WINFUNCTYPE(ctypes.c_long, c_void_p, POINTER(GUID), POINTER(c_void_p))
_REF = WINFUNCTYPE(ctypes.c_ulong, c_void_p)
_DONE = WINFUNCTYPE(ctypes.c_long, c_void_p, c_void_p)


class _Vtbl(ctypes.Structure):
    _fields_ = [("QueryInterface", _QI), ("AddRef", _REF), ("Release", _REF), ("ActivateCompleted", _DONE)]


class _Handler(ctypes.Structure):
    _fields_ = [("lpVtbl", POINTER(_Vtbl))]


class _Completion:
    """IActivateAudioInterfaceCompletionHandler + IAgileObject feitos à mão (o Windows chama de outra thread)."""

    def __init__(self):
        self.done = threading.Event()

        def qi(this, riid, ppv):
            if riid and (riid[0] == IID_IUnknown or riid[0] == IID_IActivateCompletion
                         or riid[0] == IID_IAgileObject):
                ppv[0] = this
                return S_OK
            ppv[0] = None
            return E_NOINTERFACE

        def completed(this, op):
            self.done.set()
            return S_OK
        self._fns = (_QI(qi), _REF(lambda this: 1), _REF(lambda this: 1), _DONE(completed))
        self.vtbl = _Vtbl(*self._fns)
        self.obj = _Handler(ctypes.pointer(self.vtbl))

    @property
    def ptr(self):
        return ctypes.addressof(self.obj)


# ---------------------------------------------------------------- utilidades
def windows_build() -> int:
    if not IS_WIN:
        return 0
    return sys.getwindowsversion().build


def process_loopback_supported() -> bool:
    return windows_build() >= PROCESS_LOOPBACK_BUILD


def silence_needed(started: float, now: float, frames_written: int, rate: int, slack: float = 0.06) -> int:
    """Quantos quadros de silêncio faltam para o áudio acompanhar o relógio (com folga para a latência)."""
    expected = int((now - started - slack) * rate)
    return max(0, expected - frames_written)


# ---------------------------------------------------------------- captura
class AudioCapture(threading.Thread):
    """Lê o áudio e entrega blocos de bytes em `sink(bytes)`. `pid`: só esse processo (e filhos); 0: o PC todo."""

    RATE, CH = 48000, 2

    def __init__(self, sink, pid: int = 0):
        super().__init__(daemon=True)
        self.sink, self.pid = sink, pid
        self.mode = ""                  # "processo" ou "sistema"
        self.fmt = ("s16le", self.RATE, self.CH)
        self.error = ""
        self.ready = threading.Event()
        self._stop = threading.Event()

    # o formato que o ffmpeg recebe (definido antes de começar a entregar dados)
    @property
    def ffmpeg_args(self) -> list[str]:
        f, r, c = self.fmt
        return ["-f", f, "-ar", str(r), "-ac", str(c)]

    def stop(self):
        self._stop.set()

    def reset_clock(self):
        """Chamado quando o ffmpeg começa a ler: o relógio do silêncio passa a contar daqui."""
        self._t0, self._written = time.perf_counter(), 0

    def run(self):
        ole32 = ctypes.windll.ole32
        ole32.CoInitializeEx(None, 0)            # COINIT_MULTITHREADED
        client = capture = None
        try:
            client = None
            if self.pid and process_loopback_supported():
                try:
                    client = self._activate_process(self.pid)
                    self.mode = "processo"
                except OSError as e:
                    self.error = f"modo por processo indisponível ({e}); usando o som do PC"
            if client is None:
                client = self._activate_system()
                self.mode = "sistema"
            capture = self._loop(client)
        except Exception as e:  # noqa: BLE001
            self.error = str(e)
        finally:
            self.ready.set()
            _release(capture)
            _release(client)
            ole32.CoUninitialize()

    # -- ativação
    def _activate_process(self, pid: int):
        params = ACTIVATION_PARAMS(ACTIVATION_TYPE_PROCESS_LOOPBACK, LOOPBACK_PARAMS(pid, LOOPBACK_INCLUDE_TREE))
        pv = PROPVARIANT()
        pv.vt = VT_BLOB
        pv.blob.cbSize = ctypes.sizeof(params)
        pv.blob.pBlobData = ctypes.cast(byref(params), c_void_p)
        handler = _Completion()
        self._keep = (params, pv, handler)      # o Windows usa esses objetos depois que a função retorna
        op = c_void_p()
        fn = ctypes.windll.Mmdevapi.ActivateAudioInterfaceAsync
        fn.restype = HRESULT
        fn.argtypes = [wintypes.LPCWSTR, POINTER(GUID), POINTER(PROPVARIANT), c_void_p, POINTER(c_void_p)]
        fn("VAD\\Process_Loopback", byref(IID_IAudioClient), byref(pv), c_void_p(handler.ptr), byref(op))
        if not handler.done.wait(5):
            _release(op.value)
            raise OSError("o Windows não respondeu à ativação do áudio")
        hr, unk = ctypes.c_long(0), c_void_p()
        _method(op.value, 3, POINTER(ctypes.c_long), POINTER(c_void_p))(byref(hr), byref(unk))
        _release(op.value)
        if hr.value != 0 or not unk.value:
            raise OSError(f"ativação recusada (0x{hr.value & 0xFFFFFFFF:08X})")
        client = unk.value
        wf = WAVEFORMATEX(WAVE_FORMAT_PCM, self.CH, self.RATE, self.RATE * self.CH * 2, self.CH * 2, 16, 0)
        flags = (AUDCLNT_STREAMFLAGS_LOOPBACK | AUDCLNT_STREAMFLAGS_EVENTCALLBACK
                 | AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM | AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY)
        init = _method(client, 3, c_int, ctypes.c_uint32, c_longlong, c_longlong, POINTER(WAVEFORMATEX), c_void_p)
        try:
            init(AUDCLNT_SHAREMODE_SHARED, flags, 2_000_000, 0, byref(wf), None)
        except OSError:
            _release(client)
            raise
        self.fmt = ("s16le", self.RATE, self.CH)
        self._event = True
        return client

    def _activate_system(self):
        ole32 = ctypes.windll.ole32
        enum = c_void_p()
        ole32.CoCreateInstance.restype = HRESULT
        ole32.CoCreateInstance(byref(CLSID_MMDeviceEnumerator), None, CLSCTX_ALL, byref(IID_IMMDeviceEnumerator),
                               byref(enum))
        dev = c_void_p()
        _method(enum.value, 4, c_int, c_int, POINTER(c_void_p))(0, 0, byref(dev))   # eRender, eConsole
        _release(enum.value)
        client = c_void_p()
        _method(dev.value, 3, POINTER(GUID), ctypes.c_uint32, c_void_p, POINTER(c_void_p))(
            byref(IID_IAudioClient), CLSCTX_ALL, None, byref(client))
        _release(dev.value)
        pwf = POINTER(WAVEFORMATEX)()
        _method(client.value, 8, POINTER(POINTER(WAVEFORMATEX)))(byref(pwf))     # GetMixFormat
        wf = pwf.contents
        rate, ch, bits, tag = wf.nSamplesPerSec, wf.nChannels, wf.wBitsPerSample, wf.wFormatTag
        if tag == WAVE_FORMAT_EXTENSIBLE and wf.cbSize >= 22:
            sub = ctypes.cast(ctypes.addressof(wf) + 18 + 6, POINTER(GUID)).contents   # SubFormat
            tag = sub.Data1
        init = _method(client.value, 3, c_int, ctypes.c_uint32, c_longlong, c_longlong, POINTER(WAVEFORMATEX),
                       c_void_p)
        init(AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK, 2_000_000, 0, pwf, None)
        ole32.CoTaskMemFree(pwf)
        if tag == WAVE_FORMAT_IEEE_FLOAT and bits == 32:
            self.fmt = ("f32le", rate, ch)
        elif bits == 16:
            self.fmt = ("s16le", rate, ch)
        elif bits == 24:
            self.fmt = ("s24le", rate, ch)
        else:
            self.fmt = ("s32le", rate, ch)
        self._event = False
        return client.value

    # -- leitura
    def _loop(self, client):
        k32 = ctypes.windll.kernel32
        ev = None
        if getattr(self, "_event", False):
            ev = k32.CreateEventW(None, False, False, None)
            _method(client, 13, c_void_p)(ev)                                  # SetEventHandle
        cap = c_void_p()
        _method(client, 14, POINTER(GUID), POINTER(c_void_p))(byref(IID_IAudioCaptureClient), byref(cap))
        get_buf = _method(cap.value, 3, POINTER(c_void_p), POINTER(c_uint32), POINTER(ctypes.c_ulong),
                          POINTER(c_uint64), POINTER(c_uint64))
        rel_buf = _method(cap.value, 4, c_uint32)
        next_size = _method(cap.value, 5, POINTER(c_uint32))
        _f, rate, ch = self.fmt
        width = {"s16le": 2, "s24le": 3, "s32le": 4, "f32le": 4}[_f] * ch
        _method(client, 10)()                                                   # Start
        self.ready.set()
        self.reset_clock()
        try:
            while not self._stop.is_set():
                if ev:
                    k32.WaitForSingleObject(ev, 20)
                else:
                    time.sleep(0.01)
                n = c_uint32(0)
                next_size(byref(n))
                while n.value and not self._stop.is_set():
                    data, frames, flags = c_void_p(), c_uint32(0), ctypes.c_ulong(0)
                    get_buf(byref(data), byref(frames), byref(flags), None, None)
                    size = frames.value * width
                    if flags.value & AUDCLNT_BUFFERFLAGS_SILENT or not data.value:
                        chunk = bytes(size)
                    else:
                        chunk = ctypes.string_at(data.value, size)
                    rel_buf(frames)
                    self.sink(chunk)
                    self._written += frames.value
                    next_size(byref(n))
                gap = silence_needed(self._t0, time.perf_counter(), self._written, rate)
                if gap:
                    self.sink(bytes(gap * width))
                    self._written += gap
        finally:
            try:
                _method(client, 11)()                                           # Stop
            except OSError:
                pass
            if ev:
                k32.CloseHandle(ev)
        return cap.value
